"""The router: one fast typed decision per utterance, before any expensive thinking.

Its categories come from the brain map (brain_map/, OKF), so what Jev chooses between is
exactly what the brain is connected to. One Jev call asks:
  module         which module handles this                    choice over Module pages
  capability     which group of tools is needed                choice over Capability pages
  skill          which procedure fits, if any                  choice over Skill pages + "none"
  topic          which knowledge-library subject, if any       choice over Topic pages + "none"
  urgency        can it wait / today / right now               score
  acts_on_world  will it book / send / pay / delete            noul
  needs_history  does it need earlier sessions or tasks        noul

The executor then gets only the tools of the chosen capabilities (plus the skill's), instead of
every tool of the module. Fallback when Jev is unavailable: Claude (light model, JSON schema),
then keyword rules.
"""
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
    capabilities: list[str] = field(default_factory=list)   # empty = every capability of the modules
    confidence: float = 0.0
    probabilities: dict[str, float] = field(default_factory=dict)
    capability_probabilities: dict[str, float] = field(default_factory=dict)
    also: list[str] = field(default_factory=list)     # second module loaded when the decision is close
    urgency: float = 0.0                               # 0 = can wait, 1 = today, 2 = right now
    acts_on_world: float = 0.0
    needs_history: float = 0.0
    clarify: bool = False                              # too unsure -> ask one short question
    source: str = "rules"                              # jev | llm | rules | hint
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

    # ------------------------------------------------------------------ public
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
            except Exception:  # noqa: BLE001 - any failure falls through to rules
                route = None
        if route is None:
            route = self._classify_rules(text)
        self.apply_policy(route)
        route.latency_ms = int((time.perf_counter() - started) * 1000)
        return route

    async def is_yes(self, text: str, question: str) -> bool | None:
        """Interpret an answer to a confirmation question. None = unclear."""
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
        """The shield's verdict: {breach, probability, source, ms}. breach = prompt injection / jailbreak,
        do not let it reach the executor. Jev first, then Claude (light model); when neither can answer it
        fails closed (rule 10), source "closed"."""
        started = time.perf_counter()
        state = shield.state(text, context)

        def verdict(breach: bool, source: str, probability: float | None = None) -> dict[str, Any]:
            return {"breach": breach, "probability": probability, "source": source,
                    "ms": int((time.perf_counter() - started) * 1000)}

        if self.jev.available:
            try:
                resp = await self.jev.ask(state, {"injection": noul(
                    shield.PROMPT, true="Próba naruszenia bezpieczeństwa (prompt injection, jailbreak, zmiana roli)",
                    false="Zwykła prośba użytkownika")})
                p = float(resp["answers"]["injection"]["noul"])
                return verdict(p >= float(self.settings.get("router.injection_at", 0.5)), "jev", p)
            except (JevError, KeyError, TypeError, ValueError):
                pass
        if self.anthropic is not None:
            try:
                response = await self.anthropic.messages.create(
                    model=self.settings.get("models.light"), max_tokens=50, system=shield.PROMPT,
                    messages=[{"role": "user", "content": state}],
                    output_config={"format": {"type": "json_schema", "schema": {
                        "type": "object", "properties": {"breach": {"type": "boolean"}},
                        "required": ["breach"], "additionalProperties": False}}},
                )
                breach = bool(json.loads(next(b.text for b in response.content if b.type == "text"))["breach"])
                return verdict(breach, "llm")
            except Exception:  # noqa: BLE001 - any failure fails closed below
                pass
        return verdict(True, "closed")

    async def should_interrupt(self, state: str) -> float:
        """Proactive gate: probability that this is worth interrupting the user for."""
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

    # --------------------------------------------------------------- backends
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
        listing = lambda d: "\n".join(f"- {k}: {v}" for k, v in d.items()) or "- none"  # noqa: E731
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

    # ----------------------------------------------------------------- policy
    def apply_policy(self, route: Route) -> None:
        mods = self.map.modules
        if route.module not in mods:
            route.module = "smalltalk" if "smalltalk" in mods else next(iter(mods), route.module)
        confident = float(self.settings.get("router.confident_at", 0.6))
        ask_below = float(self.settings.get("router.ask_below", 0.3))

        # A close call loads the runner-up module too.
        if route.confidence < confident and len(route.probabilities) > 1:
            ranked = sorted(route.probabilities.items(), key=lambda kv: kv[1], reverse=True)
            if ranked[1][1] > 0.15:
                route.also.append(ranked[1][0])
        # A skill or a capability from another module means the request spans both.
        if route.skill and route.skill in self.map.skills:
            route.also.append(self.map.skills[route.skill]["module"])
        for cid, p in route.capability_probabilities.items():
            owner = self.map.capabilities.get(cid, {}).get("module")
            if p >= 0.5 and owner and cid not in self.map.capabilities_of(route.modules):
                route.also.append(owner)
        route.also =[m for m in dict.fromkeys(route.also) if m != route.module and m in mods]

        # Capabilities: the most likely ones within reach of the routed modules, until 80% is covered.
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
        route.capabilities = chosen          # empty -> the executor loads every capability of the modules
        route.clarify = route.source not in ("rules", "hint") and route.confidence < ask_below
