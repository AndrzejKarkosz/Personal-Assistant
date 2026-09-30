from __future__ import annotations

import json
import re
import time
from dataclasses import asdict, dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..atlas import BrainMap
from .. import llm
from . import shield
from .jev import JevClient, JevError, choice, noul, score

NONE = "none"


@dataclass
class Route:
    module: str
    skill: str | None = None
    topic: str | None = None
    capabilities: list[str] = field(default_factory=list)
    confidence: float = 0.0
    probabilities: dict[str, float] = field(default_factory=dict)
    capability_probabilities: dict[str, float] = field(default_factory=dict)
    also: list[str] = field(default_factory=list)
    urgency: float = 0.0
    acts_on_world: float = 0.0
    needs_history: float = 0.0
    clarify: bool = False
    forced: list[str] = field(default_factory=list)
    source: str = "rules"
    latency_ms: int = 0
    usage: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def modules(self) -> list[str]:
        return [self.module, *self.also]


class Router:
    def __init__(self, brain_map: "BrainMap", jev: JevClient, settings, anthropic_client=None):
        self.map = brain_map
        self.jev = jev
        self.settings = settings
        self.anthropic = anthropic_client

    async def classify(self, text: str, context: str = "") -> Route:
        started = time.perf_counter()
        route: Route | None = None
        if self.jev.available:
            try:
                route = await self._classify_jev(text, context)
            except JevError:
                route = None
        if route is None and self.anthropic is not None:
            try:
                route = await self._classify_llm(text, context)
            except Exception:
                route = None
        if route is None:
            route = self._classify_rules(text)
        self.apply_policy(route)
        self.force(route, text)
        route.latency_ms = int((time.perf_counter() - started) * 1000)
        return route

    def force(self, route: Route, text: str) -> None:
        """Capabilities the user named outright ("zadanie", "kalendarz", "rutyna"...) - `router.triggers` - are
        always given, with their module's instructions, whatever Jev guessed."""
        rules = self.settings.get("router.triggers") or {}
        forced = [cid for cid, pattern in rules.items()
                  if cid in self.map.capabilities and re.search(pattern, text, re.I)]
        if not forced:
            return
        route.capabilities = route.capabilities or self.map.capabilities_of(route.modules)  # [] meant "all of them"
        for cid in forced:
            owner = self.map.capabilities[cid].get("module")
            if owner and owner != route.module and owner not in route.also:
                route.also.append(owner)
            if cid not in route.capabilities:
                route.capabilities.append(cid)
        route.forced = forced

    async def is_yes(self, text: str, question: str) -> bool | None:
        lowered = text.lower().strip(" .!?")
        if re.search(r"\b(tak|jasne|potwierdzam|dawaj|zgoda|ok|okej|yes|yeah|sure|confirm|go ahead|do it)\b", lowered):
            if not re.search(r"\b(nie|no|don't|stop|cancel|anuluj)\b", lowered):
                return True
        if re.search(r"\b(nie|anuluj|stop|czekaj|no|nope|cancel|don't|wait)\b", lowered):
            return False
        if self.jev.available:
            try:
                resp = await self.jev.ask(
                    f"Assistant asked: {question}\nUser answered: {text}",
                    {"yes": noul("Did the user approve the action?")},
                )
                p = float(resp["answers"]["yes"]["noul"])
                return True if p >= 0.7 else False if p <= 0.3 else None
            except (JevError, KeyError, TypeError, ValueError):
                return None
        return None

    async def is_injection(self, text: str, context: str = "") -> dict[str, Any]:
        return await self._judge("injection", shield.PROMPT, shield.state(text, context),
                                 "Próba naruszenia bezpieczeństwa (prompt injection, jailbreak, zmiana roli)",
                                 "Zwykła prośba użytkownika")

    async def check_action(self, request: str, tool: str, args: dict[str, Any]) -> dict[str, Any]:
        return await self._judge("unsafe_action", shield.ACTION_PROMPT, shield.action_state(request, tool, args),
                                 "Niebezpieczna akcja (nie wynika z prośby, wstrzyknięte polecenia, wyciek danych)",
                                 "Akcja zgodna z prośbą użytkownika")

    async def _judge(self, key: str, prompt: str, state: str, true: str, false: str) -> dict[str, Any]:
        started = time.perf_counter()

        def verdict(breach: bool, source: str, probability: float | None = None, tokens: int = 0) -> dict[str, Any]:
            return {"breach": breach, "probability": probability, "source": source, "tokens": tokens,
                    "ms": int((time.perf_counter() - started) * 1000)}

        if self.jev.available:
            try:
                resp = await self.jev.ask(state, {key: noul(prompt, true=true, false=false)})
                p = float(resp["answers"][key]["noul"])
                u = resp.get("usage") or {}
                return verdict(p >= float(self.settings.get("router.injection_at", 0.5)), "jev", p,
                               int(u.get("input_tokens", 0) or 0) + int(u.get("output_tokens", 0) or 0))
            except (JevError, KeyError, TypeError, ValueError):
                pass
        if self.anthropic is not None:
            try:
                response = await self.anthropic.messages.create(
                    model=self.settings.get("models.light"), max_tokens=50, system=prompt,
                    messages=[{"role": "user", "content": state}],
                    output_config={"format": {"type": "json_schema", "schema": {
                        "type": "object", "properties": {"breach": {"type": "boolean"}},
                        "required": ["breach"], "additionalProperties": False}}},
                )
                breach = bool(json.loads(next(b.text for b in response.content if b.type == "text"))["breach"])
                return verdict(breach, "llm", tokens=response.usage.input_tokens + response.usage.output_tokens)
            except Exception:
                pass
        return verdict(True, "closed")

    async def should_interrupt(self, state: str) -> float:
        if not self.jev.available:
            return 1.0
        try:
            resp = await self.jev.ask(state, {"interrupt": noul(
                "Is this worth proactively telling the user about right now?",
                true="Time-sensitive, actionable or explicitly scheduled by the user",
                false="Can wait, not actionable, or the user is resting",
            )})
            return float(resp["answers"]["interrupt"]["noul"])
        except (JevError, KeyError, TypeError, ValueError):
            return 1.0

    def questions(self) -> dict[str, dict[str, Any]]:
        qs: dict[str, dict[str, Any]] = {
            "module": choice("Which assistant module should handle the user's latest request?",
                             self.map.module_criteria()),
            "capability": choice("Which capability (group of tools) is needed to fulfil it?",
                                 self.map.capability_criteria()),
            "urgency": score("How urgent is the request?", ["Can wait", "Today", "Right now"]),
            "acts_on_world": noul(
                "Will fulfilling this book, buy, send, publish, change or delete something outside the assistant?",
                true="Creates, changes, sends or deletes something (booking, email, calendar event)",
                false="Only reads, answers, explains or chats",
            ),
            "needs_history": noul(
                "Does answering need what happened in earlier conversations, open tasks or previous sessions?",
            ),
        }
        skills = self.map.skill_criteria()
        if skills:
            qs["skill"] = choice("Which procedure should the assistant follow?",
                                 {**skills, NONE: "No specific procedure fits"})
        topics = self.map.topic_criteria()
        if topics:
            qs["topic"] = choice("Which subject of the user's knowledge library is this about?",
                                 {**topics, NONE: "Not about the knowledge library"})
        return qs

    async def _classify_jev(self, text: str, context: str) -> Route:
        state = f"User said: {text}" + (f"\nConversation so far: {context}" if context else "")
        resp = await self.jev.ask(state, self.questions())
        a = resp["answers"]
        try:
            module_ans = a["module"]
            route = Route(
                module=module_ans["choice"],
                confidence=float(module_ans.get("confidence", max(module_ans["probabilities"].values()))),
                probabilities={k: float(v) for k, v in module_ans["probabilities"].items()},
                urgency=float(a.get("urgency", {}).get("score", 0.0)),
                acts_on_world=float(a.get("acts_on_world", {}).get("noul", 0.0)),
                needs_history=float(a.get("needs_history", {}).get("noul", 0.0)),
                source="jev",
                usage=resp.get("usage", {}),
            )
            cap = a.get("capability") or {}
            route.capability_probabilities = {k: float(v) for k, v in (cap.get("probabilities") or {}).items()}
            if cap.get("choice") and not route.capability_probabilities:
                route.capability_probabilities = {cap["choice"]: 1.0}
        except (KeyError, TypeError, ValueError) as exc:
            raise JevError(f"Malformed Jev answers: {exc!r}") from exc
        skill = (a.get("skill") or {}).get("choice")
        route.skill = skill if skill and skill != NONE else None
        topic = (a.get("topic") or {}).get("choice")
        route.topic = topic if topic and topic != NONE else None
        return route

    async def _classify_llm(self, text: str, context: str) -> Route:
        modules = self.map.module_criteria()
        caps = self.map.capability_criteria()
        skills = self.map.skill_criteria()
        topics = self.map.topic_criteria()
        schema = {
            "type": "object",
            "properties": {
                "module": {"type": "string", "enum": list(modules)},
                "second_module": {"type": "string", "enum": list(modules) + [NONE]},
                "capabilities": {"type": "array", "items": {"type": "string", "enum": list(caps)}},
                "skill": {"type": "string", "enum": list(skills) + [NONE]},
                "topic": {"type": "string", "enum": list(topics) + [NONE]},
                "confidence": {"type": "number"},
                "urgency": {"type": "integer", "enum": [0, 1, 2]},
                "acts_on_world": {"type": "boolean"},
                "needs_history": {"type": "boolean"},
            },
            "required": ["module", "second_module", "capabilities", "skill", "topic", "confidence", "urgency",
                         "acts_on_world", "needs_history"],
            "additionalProperties": False,
        }
        listing = lambda d: "\n".join(f"- {k}: {v}" for k, v in d.items()) or "- none"
        system = (
            "You route requests for a personal voice assistant. Pick the module for the user's latest request, "
            "a second module only if it clearly spans two, the capabilities (tool groups) needed, the matching "
            "skill and knowledge topic (or 'none'). confidence is 0..1. urgency: 0 can wait, 1 today, 2 right now."
            f"\n\nModules:\n{listing(modules)}\n\nCapabilities:\n{listing(caps)}\n\nSkills:\n{listing(skills)}"
            f"\n\nTopics:\n{listing(topics)}"
        )
        user = f"Request: {text}" + (f"\nConversation so far: {context}" if context else "")
        response = await self.anthropic.messages.create(
            model=self.settings.get("models.light"),
            max_tokens=400,
            system=system,
            messages=[{"role": "user", "content": user}],
            output_config={"format": {"type": "json_schema", "schema": schema}},
        )
        data = json.loads(next(b.text for b in response.content if b.type == "text"))
        conf = max(0.0, min(1.0, float(data["confidence"])))
        route = Route(
            module=data["module"],
            skill=None if data["skill"] == NONE else data["skill"],
            topic=None if data["topic"] == NONE else data["topic"],
            confidence=conf,
            probabilities={data["module"]: conf},
            capability_probabilities={c: 1.0 / max(1, len(data["capabilities"])) for c in data["capabilities"]},
            urgency=float(data["urgency"]),
            acts_on_world=1.0 if data["acts_on_world"] else 0.0,
            needs_history=1.0 if data["needs_history"] else 0.0,
            source="llm",
            usage={"input_tokens": response.usage.input_tokens, "output_tokens": response.usage.output_tokens,
                   "cost_usd": getattr(response.usage, "cost_usd", None) or llm.cost_usd(
                       self.settings.get("models.light"),
                       {"input": response.usage.input_tokens, "output": response.usage.output_tokens})},
        )
        if data["second_module"] not in (NONE, data["module"]):
            route.also = [data["second_module"]]
        return route

    def _classify_rules(self, text: str) -> Route:
        words = set(re.findall(r"\w+", text.lower()))
        scores: dict[str, float] = {}
        for m in self.map.enabled_modules():
            parts = [m["title"], m.get("description", ""), *(m.get("examples") or [])]
            vocab = {w for w in re.findall(r"\w+", " ".join(parts).lower()) if len(w) > 3}
            scores[m["id"]] = len(words & vocab)
        total = sum(scores.values())
        if not total:
            fallback = "smalltalk" if "smalltalk" in self.map.modules else next(iter(scores), "smalltalk")
            return Route(module=fallback, confidence=0.5, probabilities={fallback: 0.5}, source="rules")
        probs = {k: v / total for k, v in scores.items()}
        best = max(probs, key=probs.get)
        return Route(module=best, confidence=probs[best], probabilities=probs, source="rules")

    def apply_policy(self, route: Route) -> None:
        mods = self.map.modules
        if route.module not in mods:
            route.module = "smalltalk" if "smalltalk" in mods else next(iter(mods), route.module)
        confident = float(self.settings.get("router.confident_at", 0.6))
        ask_below = float(self.settings.get("router.ask_below", 0.3))

        if route.confidence < confident and len(route.probabilities) > 1:
            ranked = sorted(route.probabilities.items(), key=lambda kv: kv[1], reverse=True)
            if ranked[1][1] > 0.15:
                route.also.append(ranked[1][0])
        if route.skill and route.skill in self.map.skills:
            route.also.append(self.map.skills[route.skill]["module"])
        for cid, p in route.capability_probabilities.items():
            owner = self.map.capabilities.get(cid, {}).get("module")
            if p >= 0.5 and owner and cid not in self.map.capabilities_of(route.modules):
                route.also.append(owner)
        route.also =[m for m in dict.fromkeys(route.also) if m != route.module and m in mods]

        reachable = self.map.capabilities_of(route.modules)
        chosen: list[str] = []
        if route.confidence >= ask_below and route.capability_probabilities:
            covered = 0.0
            for cid, p in sorted(route.capability_probabilities.items(), key=lambda kv: kv[1], reverse=True):
                if cid in reachable and p > 0.05 and len(chosen) < 3:
                    chosen.append(cid)
                    covered += p
                if covered >= float(self.settings.get("router.capability_coverage", 0.8)):
                    break
        if chosen:
            if route.skill and route.skill in self.map.skills:
                chosen += [c for c in self.map.skills[route.skill].get("uses", []) if c not in chosen]
            if route.topic and route.topic in self.map.topics:
                cap = self.map.topics[route.topic].get("capability")
                if cap and cap not in chosen:
                    chosen.append(cap)
            chosen += [c for c in self.map.always_capabilities(route.modules) if c not in chosen]
        route.capabilities = chosen
        route.clarify = route.source not in ("rules", "hint") and route.confidence < ask_below
