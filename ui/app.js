// Alfred UI. Brain view: the 3D brain, Alfred's universe (bottom left), the path to the answer (right).
// Tasks view: to-do by category, routines, Google calendar and tabs for summary / conversation / memory / map /
// persona / modules / log / settings. Both: subtitles with what Alfred says and a low bar (composer, Jev, session cost).
const $ = (s) => document.querySelector(s);
const api = async (path, opts = {}) => {
  const res = await fetch(path, { headers: { "Content-Type": "application/json" }, ...opts });
  if (!res.ok) throw new Error(`${res.status} ${await res.text()}`);
  return res.json();
};
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const Brain3D = window.Brain3D;          // missing when three.js could not load - the day view still works

let status = { keys: {}, mcp: [] };
let ws;

// ---------------------------------------------------------------- messages
function addMsg(kind, text, meta = "") {
  const el = document.createElement("div");
  el.className = `msg ${kind}`;
  el.innerHTML = esc(text) + (meta ? `<span class="meta">${esc(meta)}</span>` : "");
  $("#messages").appendChild(el);
  $("#tab-chat").scrollTop = 1e9;
}

// ---------------------------------------------------------------- subtitles
let subTimer, lastSaid = "";
function hideSubtitle(ms) {               // never while Alfred is still talking or waiting for a yes/no
  clearTimeout(subTimer);
  subTimer = setTimeout(() => talking || !$("#confirm").classList.contains("hidden") || $("#subtitle").classList.add("hidden"), ms);
}
function subtitle(text, kind = "say", you = "") {
  $("#subtitle").className = `subtitle ${kind}`;
  $("#sub-text").textContent = text;
  $("#sub-you").textContent = you ? `„${you}”` : "";
  hideSubtitle(Math.max(6000, text.length * 70));
}
$("#subtitle-x").onclick = () => $("#subtitle").classList.add("hidden");

// ------------------------------------------------------------------- audio
const audioQueue = [];
let playing = null;
let thinking = false, talking = false;
function mood() {                         // Alfred's universe: idle / listening / thinking / speaking
  const s = isRecording() ? "listening" : talking ? "speaking" : thinking ? "thinking" : "idle";
  $("#alfred").dataset.state = s;
  $("#alfred-state").textContent = { idle: "czeka", listening: "słucha", thinking: "myśli…", speaking: "mówi" }[s];
}
function setSpeaking(on) {                // the speaker icon (and the brain's voice) light up while Alfred talks
  $("#speaking").classList.toggle("on", on);
  Brain3D?.speaking(on);
  talking = on; mood();
  if (!on) hideSubtitle(4000);
}

// Alfred's universe: a tilted spiral galaxy with three worlds on orbits. It turns slowly while he waits, whirls
// while he thinks and breathes light while he speaks.
(() => {
  const cv = $("#universe"), g = cv.getContext("2d"), S = cv.width, R = S / 2, TAU = Math.PI * 2;
  const rnd = (a, b) => a + Math.random() * (b - a);
  const stars = Array.from({ length: 320 }, (_, i) => {
    const r = Math.pow(Math.random(), 0.75) * R * 0.8;
    return { r, a: (i % 3) * TAU / 3 + r / 24 + rnd(-0.4, 0.4), size: rnd(1.4, 3.6), hue: rnd(185, 290), tw: rnd(0, TAU) };
  });
  const worlds = [{ r: 0.5, size: 4, v: 1, c: "#22d3ee", a: 0 }, { r: 0.7, size: 3, v: -0.6, c: "#a78bfa", a: 2 }, { r: 0.9, size: 5, v: 0.4, c: "#4ade80", a: 4 }];
  const SPIN = { idle: 0.1, listening: 0.3, thinking: 1.2, speaking: 0.45 };
  const GLOW = { idle: 0.3, listening: 0.75, thinking: 0.65, speaking: 0.7 };
  const calm = matchMedia("(prefers-reduced-motion: reduce)").matches ? 0.2 : 1;
  let rot = 0, spin = 0.1, glow = 0.3, last = performance.now();
  function frame(now) {
    requestAnimationFrame(frame);
    const dt = Math.min(0.1, (now - last) / 1000), t = now / 1000;
    last = now;
    if (!cv.offsetParent) return;                        // brain view not shown
    const state = $("#alfred").dataset.state;
    // the real loudness of Alfred's voice; the browser's own voice cannot be measured, so there it is made up from sines
    const voice = state === "speaking" ? voiceLevel() ?? 0.5 + 0.5 * Math.abs(Math.sin(t * 9) * Math.sin(t * 3.7 + 1)) : 0;
    spin += ((SPIN[state] ?? 0.1) - spin) * Math.min(1, dt * 3);
    glow += ((GLOW[state] ?? 0.3) + voice * 0.3 - glow) * Math.min(1, dt * 8);
    rot += spin * dt * calm;
    g.globalCompositeOperation = "source-over";
    g.clearRect(0, 0, S, S);
    const halo = g.createRadialGradient(R, R, 0, R, R, R);
    halo.addColorStop(0, `rgba(167,139,250,${0.4 * glow})`);
    halo.addColorStop(0.45, `rgba(34,211,238,${0.14 * glow})`);
    halo.addColorStop(1, "rgba(0,0,0,0)");
    g.fillStyle = halo;
    g.fillRect(0, 0, S, S);
    g.globalCompositeOperation = "lighter";
    for (const st of stars) {                            // inner stars turn faster, like a real galaxy
      const a = st.a + rot * (1.8 - st.r / R), r = st.r * (1 + voice * 0.14 * Math.sin(t * 7 + st.tw));
      g.fillStyle = `hsla(${state === "listening" ? st.hue - 50 : st.hue},90%,72%,${(0.3 + 0.7 * glow) * (0.55 + 0.45 * Math.sin(t * 2 + st.tw))})`;
      g.fillRect(R + Math.cos(a) * r, R + Math.sin(a) * r * 0.6, st.size, st.size);
    }
    for (const w of worlds) {
      g.strokeStyle = `rgba(148,163,255,${0.06 + 0.16 * glow})`;
      g.beginPath(); g.ellipse(R, R, w.r * R * 0.95, w.r * R * 0.57, 0, 0, TAU); g.stroke();
      w.a += w.v * (0.3 + spin) * dt * calm;
      g.shadowColor = w.c; g.shadowBlur = 6 + 14 * glow; g.fillStyle = w.c;
      g.beginPath(); g.arc(R + Math.cos(w.a) * w.r * R * 0.95, R + Math.sin(w.a) * w.r * R * 0.57, w.size * (1 + voice * 0.4), 0, TAU); g.fill();
    }
    const cr = R * (0.13 + 0.09 * voice + 0.04 * glow), core = g.createRadialGradient(R, R, 0, R, R, cr);
    core.addColorStop(0, "#fff"); core.addColorStop(0.35, "rgba(34,211,238,.9)"); core.addColorStop(1, "rgba(167,139,250,0)");
    g.shadowBlur = 0; g.fillStyle = core;
    g.beginPath(); g.arc(R, R, cr, 0, TAU); g.fill();
  }
  requestAnimationFrame(frame);
})();
// Alfred's voice goes through an analyser, so the galaxy follows how loud he really speaks. Browsers start the
// audio context only after a click or a key; until then the voice plays directly.
let audioCtx = null, analyser = null, levels = null;
["pointerdown", "keydown"].forEach((e) => addEventListener(e, () => {
  try { (audioCtx ??= new AudioContext()).resume(); } catch { /* no Web Audio */ }
}, { once: true }));
function analyse(el) {
  if (audioCtx?.state !== "running") return;
  if (!analyser) {
    analyser = audioCtx.createAnalyser();
    analyser.fftSize = 256;
    analyser.connect(audioCtx.destination);
    levels = new Uint8Array(analyser.frequencyBinCount);
  }
  audioCtx.createMediaElementSource(el).connect(analyser);
  el.analysed = true;
}
function voiceLevel() {                   // 0..1, or null when it cannot be measured
  if (!playing?.analysed) return null;
  analyser.getByteFrequencyData(levels);
  return Math.min(1, levels.reduce((s, v) => s + v, 0) / levels.length / 80);
}
function speak(text, b64, lang) {
  audioQueue.push({ text, b64, lang });
  if (!playing) playNext();
}
function playNext() {
  const item = audioQueue.shift();
  setSpeaking(Boolean(item));
  if (!item) { playing = null; return; }
  if (item.b64) {
    playing = new Audio(`data:audio/mpeg;base64,${item.b64}`);
    analyse(playing);
    playing.onended = playNext;
    playing.onerror = playNext;
    playing.play().catch(playNext);
  } else if ("speechSynthesis" in window) {
    const u = new SpeechSynthesisUtterance(item.text);
    u.lang = item.lang === "en" ? "en-GB" : "pl-PL";
    u.rate = 1.2;                         // same pace as the ElevenLabs voice (voice.settings.speed)
    u.onend = u.onerror = playNext;
    playing = u;
    speechSynthesis.speak(u);
  } else playNext();
}
function stopSpeaking() {                 // barge-in: you start talking, Alfred stops
  audioQueue.length = 0;
  if (playing instanceof Audio) playing.pause();
  if ("speechSynthesis" in window) speechSynthesis.cancel();
  playing = null;
  setSpeaking(false);
}
$("#speaking").onclick = stopSpeaking;

// ------------------------------------------------------------- microphone
let recorder = null, chunks = [], recognition = null;
async function startRec() {
  stopSpeaking();
  $("#mic").classList.add("rec"); mood();
  if (!status.keys.elevenlabs && ("webkitSpeechRecognition" in window || "SpeechRecognition" in window)) {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    recognition = new SR();
    recognition.lang = status.language === "en" ? "en-GB" : "pl-PL";
    recognition.onresult = (e) => sendText(e.results[0][0].transcript);
    recognition.onend = () => { $("#mic").classList.remove("rec"); mood(); };
    recognition.start();
    return;
  }
  const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  recorder = new MediaRecorder(stream, { mimeType: MediaRecorder.isTypeSupported("audio/webm") ? "audio/webm" : "" });
  chunks = [];
  recorder.ondataavailable = (e) => chunks.push(e.data);
  recorder.onstop = async () => {
    stream.getTracks().forEach((t) => t.stop());
    const blob = new Blob(chunks, { type: recorder.mimeType });
    if (blob.size < 2000) return;
    const reader = new FileReader();
    reader.onload = () => ws.send(JSON.stringify({ type: "audio", b64: reader.result.split(",")[1], mime: recorder.mimeType }));
    reader.readAsDataURL(blob);
  };
  recorder.start();
}
function stopRec() {
  $("#mic").classList.remove("rec"); mood();
  if (recognition) { recognition.stop(); recognition = null; }
  if (recorder && recorder.state === "recording") recorder.stop();
}
function isRecording() { return $("#mic").classList.contains("rec"); }
// A letter or the space bar would type into a text field, so there it stays a letter; F-keys, Ctrl, Alt... work everywhere.
const typing = (e) => e.target.closest?.("input, textarea, select") && e.key.length === 1;
$("#mic").onclick = () => (isRecording() ? stopRec() : startRec());

// Push-to-talk key: remembered in this browser, changed in Ustawienia.
let ptt = "Space", capturing = false;
try { ptt = localStorage.getItem("ptt") || ptt; } catch { /* private mode */ }
const keyName = (code) => code === "Space" ? "Spację" : code.replace(/^(Key|Digit)/, "");
function showPtt() {
  $("#text").placeholder = `Napisz do Alfreda albo przytrzymaj ${keyName(ptt)} i mów…`;
  $("#ptt-btn").textContent = capturing ? "naciśnij klawisz… (Esc anuluje)" : keyName(ptt);
}
$("#ptt-btn").onclick = () => { capturing = true; showPtt(); };
document.addEventListener("keydown", (e) => {
  if (capturing) {
    e.preventDefault();
    capturing = false;
    if (e.code !== "Escape") { ptt = e.code; try { localStorage.setItem("ptt", ptt); } catch { /* private mode */ } }
    return showPtt();
  }
  if (e.code === ptt && !e.repeat && !typing(e)) { e.preventDefault(); startRec(); }
  if (e.key === "Escape") { $("#jev-dock").classList.add("hidden"); $("#jev-sum").setAttribute("aria-expanded", false); }
});
document.addEventListener("keyup", (e) => {
  if (e.code === ptt && !typing(e) && isRecording()) { e.preventDefault(); stopRec(); }
});
showPtt();

function sendText(text) {
  if (!text.trim()) return;
  ws.send(JSON.stringify({ type: "text", text }));
}
$("#text-form").onsubmit = (e) => { e.preventDefault(); sendText($("#text").value); $("#text").value = ""; };

// ------------------------------------------------------------------- chat
// Written conversation: the server answers in full Markdown and skips the voice for these requests.
const chatReq = new Set();                        // request_ids that came from the chat
function chatMsg(kind, html, meta = "") {
  $(".chat-empty")?.remove();
  const el = document.createElement("div");
  el.className = `bubble ${kind}`;
  el.innerHTML = html + (meta ? `<span class="meta">${esc(meta)}</span>` : "");
  $("#chat-log").appendChild(el);
  $("#chat-log").scrollTop = 1e9;
  return el;
}
function chatTyping(on) {
  $("#chat-typing")?.remove();
  if (on) chatMsg("alfred typing", "<span class=\"dots\"><i></i><i></i><i></i></span>").id = "chat-typing";
}
const chatAnswer = (text, meta) => chatMsg("alfred", `<div class="md">${renderMd(text, "")}</div>`, meta);
$("#chat-form").onsubmit = (e) => {
  e.preventDefault();
  const text = $("#chat-text").value.trim();
  if (!text) return;
  ws.send(JSON.stringify({ type: "text", text, mode: "chat" }));
  $("#chat-text").value = "";
};
$("#chat-text").onkeydown = (e) => {
  if (e.key === "Enter" && !e.shiftKey && !e.isComposing) { e.preventDefault(); $("#chat-form").requestSubmit(); }
};
$("#chat-new").onclick = async () => {
  await api("/api/session/close", { method: "POST" });
  $("#chat-log").innerHTML = '<div class="chat-empty">Nowa rozmowa. Poprzednia jest zapisana w pamięci Alfreda.</div>';
};
async function loadChat() {                        // after a reload: this session's chat
  const sid = status.session?.id;
  if (!sid) return;
  const [heard, answers] = await Promise.all([api("/api/logs?kind=transcript&limit=300"), api("/api/logs?kind=answer&limit=300")]);
  [...heard, ...answers].filter((e) => e.data.mode === "chat" && e.session_id === sid).sort((a, b) => a.ts.localeCompare(b.ts))
    .forEach((e) => (e.kind === "transcript" ? chatMsg("user", esc(e.data.text)) : chatAnswer(e.data.text)));
}
$("#yes").onclick = () => ws.send(JSON.stringify({ type: "confirm", approved: true }));
$("#no").onclick = () => ws.send(JSON.stringify({ type: "confirm", approved: false }));

// ------------------------------------------------------------------ graph
async function loadGraph() {
  Brain3D?.init(await api("/api/graph"), { openPage: (p) => { setView("tasks"); openMapPage(p); }, openMemory: openMemoryPage });
}
$("#demo").onclick = () => Brain3D?.demo();

// ---------------------------------------------------------------- events
function onEvent(ev) {
  const d = ev.data || {};
  Brain3D?.event(ev);
  switch (ev.kind) {
    case "transcript":
      said[ev.request_id] = d.text;
      if (!d.confirmation) { thinking = true; mood(); }
      if (d.source === "proactive") addMsg("system", "⏰ Alfred zaczyna sam (zadanie zaplanowane)");
      else if (d.source === "routine") { addMsg("system", `🔁 Rutyna: ${d.text}`); loadRoutines(); }
      else if (d.mode === "chat") { addMsg("user", d.text); chatReq.add(ev.request_id); chatMsg("user", esc(d.text)); chatTyping(true); }
      else { addMsg("user", d.text); lastSaid = d.text; if (!d.confirmation) subtitle("…", "ack", d.text); }
      break;
    case "shield":
      shields[ev.request_id] = d;
      $("#jev-dock").innerHTML = `<div class="jev-head"><b>Jev → osłona</b><span class="said">${said[ev.request_id] ? `„${esc(said[ev.request_id])}”` : ""}</span>${shieldPill(d)}</div>
        <p class="sub">${d.breach ? "Zapytanie zatrzymane — Claude go nie zobaczy." : "Czyste. Alfred potwierdza, a Jev w tym czasie kieruje zapytanie do właściwej części mózgu…"}</p>`;
      $("#jev-sum").innerHTML = `Jev → osłona: <b>${d.breach ? "zablokowano" : "bezpieczne"}</b> · ${d.ms} ms`;
      if (d.breach) addMsg("system", `🛡 Osłona zablokowała zapytanie (${SHIELD_SRC[d.source] || d.source})`);
      break;
    case "classified": {
      $("#route-info").textContent = `→ ${d.module}${d.also?.length ? " + " + d.also.join(", ") : ""}` +
        `${d.skill ? " · " + d.skill : ""} · ${Math.round(d.confidence * 100)}% · ${d.source} · ${d.latency_ms} ms`;
      showRoute(d, said[ev.request_id], shields[ev.request_id]);
      break;
    }
    case "ack": addMsg("ack", d.text); subtitle(d.text, "ack", lastSaid); speak(d.text, d.audio_b64, d.language); break;
    case "confirm_request":
      addMsg("alfred", d.text);
      subtitle(d.text);
      $("#confirm").classList.remove("hidden");
      if (chatReq.has(ev.request_id)) chatMsg("alfred", esc(d.text));
      else speak(d.text, d.audio_b64, status.language);
      break;
    case "confirm_result": $("#confirm").classList.add("hidden"); hideSubtitle(1500); break;
    case "answer": {
      if (!d.interim) { thinking = false; mood(); }  // interim = welcome-back line, the real answer is coming
      const u = d.usage || {};
      // Alfred speaking first (maybe while the UI was closed): show when it happened.
      const at = d.source && d.source !== "user" ? `${ev.ts.slice(11, 16)} · ` : "";
      const meta = `${at}${d.model || ""} · ${tokens(u)} tok. (in ${u.input || 0} · cache ${u.cache_read || 0}` +
        ` odczyt / ${u.cache_write || 0} zapis · out ${u.output || 0}${u.router ? ` · router ${u.router}` : ""})` +
        (d.cost_usd != null ? ` · ${usd(d.cost_usd)}` : "") + (d.tools?.length ? ` · ${d.tools.join(", ")}` : "");
      addMsg("alfred", d.text, meta);
      loadStatus();                         // session total in the low bar
      if (d.mode === "chat" || chatReq.has(ev.request_id)) { chatTyping(false); chatAnswer(d.text, meta); }
      else { subtitle(d.text, "say", d.source === "user" ? lastSaid : ""); speak(d.text, d.audio_b64, d.language); }
      if (d.source === "routine") showBrief(d.text, ev.ts.slice(11, 16), "rutyna");
      refreshLeft();                        // Alfred may have changed the tasks or the calendar
      if (view === "tasks") refreshDay();
      break;
    }
    case "error": thinking = false; mood(); addMsg("system", `⚠ ${d.message}`);
      if (chatReq.has(ev.request_id)) { chatTyping(false); chatMsg("system", `⚠ ${esc(d.message)}`); } subtitle(`⚠ ${d.message}`, "system"); loadRoutines(); break;
    case "session_closed": addMsg("system", `Sesja zapisana: ${d.title || ""}`); loadBriefing(); break;
    case "proactive_gate": if (!d.fired) addMsg("system", `Pominięto przypomnienie „${d.task}” (bramka ${Math.round(d.probability * 100)}%)`); break;
  }
  if (!$("#tab-log").classList.contains("hidden")) appendLog(ev);
}

function connect() {
  ws = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws`);
  ws.onopen = () => $("#live-dot").classList.add("on");
  ws.onclose = () => { $("#live-dot").classList.remove("on"); setTimeout(connect, 1500); };
  ws.onmessage = (m) => onEvent(JSON.parse(m.data));
}

// ------------------------------------------------------------------- status
async function loadStatus() {
  status = await api("/api/status");
  status.language = status.session?.language || "pl";
  const pill = (label, ok, title = "") => `<span class="pill ${ok ? "ok" : "bad"}" title="${esc(title)}">${label}</span>`;
  $("#pills").innerHTML =
    pill(status.backend === "subscription" ? "Claude · subskrypcja" : "Claude · API", status.keys.anthropic,
      status.claude?.detail || "") + pill("Jev", status.keys.jev, "bez klucza: fallback na Claude Haiku") +
    pill("ElevenLabs", status.keys.elevenlabs, "bez klucza: głos przeglądarki") +
    status.mcp.map((s) => s.status === "disabled" ? "" : pill(s.name, s.status === "ready", s.error || "")).join("");
  const u = status.session?.usage || {};
  // Split per service: Claude (subscription = API-equivalent, not a bill), Jev and ElevenLabs (real money).
  const sub = status.backend === "subscription";
  const claudeTok = ["input", "output", "cache_read", "cache_write"].reduce((s, k) => s + (u[k] || 0), 0);
  const paid = (u.jev_usd || 0) + (u.elevenlabs_usd || 0) + (sub ? 0 : u.cost_usd || 0);
  $("#session-cost").innerHTML = `<b>Płacisz ${cash(paid)}</b> · Jev ${cash(u.jev_usd)} · ` +
    `ElevenLabs ${cash(u.elevenlabs_usd)} · Claude ${usd(u.cost_usd || 0)}`;
  $("#session-cost").title = [
    `Sesja: ${status.session?.turns || 0} tur`,
    `Claude: ${num(claudeTok)} tok. · ${usd(u.cost_usd || 0)}` + (sub ? " — subskrypcja: równowartość API, nie rachunek (zużywa limit planu)" : ""),
    `Jev: ${num(u.jev || 0)} tok. · ${cash(u.jev_usd)} (płatne tylko wejście)`,
    `ElevenLabs: ${num(u.tts_chars || 0)} znaków głosu + ${num(Math.round(u.stt_s || 0))} s rozpoznawania mowy · ${cash(u.elevenlabs_usd)}`,
    `Płacisz: Jev + ElevenLabs${sub ? "" : " + Claude"} = ${cash(paid)} (ceny: config/brain.yaml → prices)`,
  ].join("\n");
}
const cash = (v) => `$${(v || 0).toFixed(4)}`;
const tokens = (u) => ["input", "output", "cache_read", "cache_write", "router", "jev"].reduce((s, k) => s + (u[k] || 0), 0);
const num = (n) => n.toLocaleString("pl-PL");
// Subscription: no per-token bill, the figure is what the same call would cost on the API.
const usd = (v) => `${status.backend === "subscription" ? "≈" : ""}$${v.toFixed(4)}`;

// --------------------------------------------------------------------- views
let view = "brain";
function setView(v) {
  view = v;
  $("main").dataset.view = v;
  document.body.dataset.view = v;
  if (v === "chat") $("#chat-text").focus();
  document.querySelectorAll(".views button").forEach((b) => b.classList.toggle("active", b.dataset.view === v));
  try { localStorage.setItem("view", v); } catch { /* private mode */ }
  if (v === "tasks") refreshDay();
}
document.querySelectorAll(".views button").forEach((b) => (b.onclick = () => setView(b.dataset.view)));

// Tasks tabs: Przegląd (board + small calendar + panels) or Kanban / Kalendarz over the whole page.
function setSub(s) {
  $("main").dataset.sub = s;
  document.querySelectorAll(".subviews button").forEach((b) => b.classList.toggle("active", b.dataset.sub === s));
  try { localStorage.setItem("tasksub", s); } catch { /* private mode */ }
  delete $("#calendar").dataset.scrolled;             // taller hours on the full page: scroll to "now" again
  renderCalendar();
  if (s === "goals") loadGoals().catch(warn);
}
async function loadGoals() {
  const [g, prod] = await Promise.all([api("/api/goals"), api("/api/productivity")]);
  $("#goals-text").value = g.goals;
  $("#resolutions-text").value = g.resolutions;
  $("#goals-saved").textContent = "";
  renderProductivity(prod);
}
function renderProductivity(prod) {
  $("#prod-on").checked = prod.enabled;
  const f = $("#prod-plan");
  Object.entries(prod.plan).forEach(([k, v]) => f.elements[k] && (f.elements[k].value = v));
  $("#prod-routines").innerHTML = prod.routines.map((r) => `<div class="routine ${prod.enabled ? "done" : "wait"}" title="${esc(r.prompt)}">
    <div class="row between"><span class="title">${esc(r.id)}</span><span class="state">${esc(cronPl(r.schedule))}</span></div>
    <div class="sub answer">${esc(r.prompt)}</div></div>`).join("") || '<div class="sub">Brak rutyn w config/brain.yaml → productivity.</div>';
}
const putProductivity = async (enabled) => {
  const plan = Object.fromEntries(new FormData($("#prod-plan")));
  plan.hours_limit = +plan.hours_limit;
  renderProductivity(await api("/api/productivity", { method: "PUT", body: JSON.stringify({ enabled, plan }) }));
  loadRoutines();
};
$("#prod-on").onchange = (e) => putProductivity(e.target.checked).catch((err) => { e.target.checked = !e.target.checked; warn(err); });
$("#prod-plan").onsubmit = async (e) => {
  e.preventDefault();
  try {
    await putProductivity($("#prod-on").checked);
    $("#plan-saved").textContent = `zapisane ${hhmm(new Date())}` + ($("#prod-on").checked ? " — rutyny już mają nowe godziny" : " — włącz rutynę, żeby ruszyła");
  } catch (err) { warn(err); }
};
// "30 7 * * 1-5" -> "pn–pt 07:30"; anything fancier is shown as is
function cronPl(cron) {
  if (cron === "@start") return "przy starcie";
  const [m, h, dom, mon, dow] = cron.split(" ");
  if (!/^\d+$/.test(m) || !/^\d+$/.test(h) || dom !== "*" || mon !== "*") return `cron ${cron}`;
  const days = { "*": "codziennie", "1-5": "pn–pt", "0": "niedziela", "7": "niedziela", "6": "sobota", "0,6": "weekend", "6,0": "weekend" };
  return `${days[dow] || `dni ${dow}`} ${h.padStart(2, "0")}:${m.padStart(2, "0")}`;
}
$("#goals-save").onclick = async () => {
  await api("/api/goals", { method: "PUT", body: JSON.stringify({ goals: $("#goals-text").value, resolutions: $("#resolutions-text").value }) });
  $("#goals-saved").textContent = `zapisane ${hhmm(new Date())} — Alfred już je zna`;
};
document.querySelectorAll(".subviews button").forEach((b) => (b.onclick = () => setSub(b.dataset.sub)));
const warn = (e) => addMsg("system", `⚠ ${e.message}`);
const refreshLeft = () => Promise.all([refreshTasks(), loadRoutines()]).catch(warn);
const refreshDay = () => Promise.all([loadCalendar(), loadSessions(), loadSummary()]).catch(warn);

// ---------------------------------------------------------------- Jev panel
const said = {};                                  // request_id -> what was said
const SOURCE = { jev: "Jev", llm: "Claude Haiku — Jev niedostępny", rules: "reguły słów — Jev i Claude niedostępne", hint: "moduł wskazany przez rutynę" };
const shields = {};                               // request_id -> the shield's verdict
const SHIELD_SRC = { jev: "Jev", llm: "Claude Haiku — Jev niedostępny", closed: "nikt nie odpowiedział — zablokowano z ostrożności" };
function shieldPill(s) {
  if (!s) return "";
  const risk = s.probability != null ? ` · ryzyko ${Math.round(s.probability * 100)}%` : "";
  return `<span class="pill ${s.breach ? "bad" : "ok"}" title="Sprawdzenie prompt injection · ${esc(SHIELD_SRC[s.source] || s.source)}">🛡 ${s.breach ? "zablokowano" : "bezpieczne"}${risk} · ${esc(s.source)} · ${s.ms} ms</span>`;
}
function showRoute(d, text, shield) {
  const pct = (v) => `${Math.round((v || 0) * 100)}%`;
  const top = (probs) => Object.entries(probs || {}).sort((a, b) => b[1] - a[1]).slice(0, 5);
  const bars = (rows, chosen = []) => rows.map(([k, v]) => `<div class="meter-row${chosen.includes(k) ? " on" : ""}">
    <span title="${esc(k)}">${esc(k)}</span><b>${pct(v)}</b><div class="meter"><i style="width:${Math.max(1, (v || 0) * 100)}%"></i></div></div>`).join("");
  const urgency = ["niska", "dziś", "teraz"][Math.max(0, Math.min(2, Math.round(d.urgency || 0)))];
  $("#jev-sum").innerHTML = `Jev → <b>${esc(d.module)}</b> ${pct(d.confidence)}` + (d.capabilities?.length ? ` · ${esc(d.capabilities.slice(0, 3).join(", "))}` : "") +
    (shield ? ` · 🛡 ${shield.breach ? "zablokowano" : "ok"}` : "") + ` · pilność ${urgency} · ${d.latency_ms} ms`;
  $("#jev-dock").innerHTML = `<div class="jev-head"><b>Jev → ${esc(d.module)}</b><span class="said">${text ? `„${esc(text)}”` : ""}</span>
      ${shieldPill(shield)}<span class="pill ${d.source === "jev" ? "ok" : "bad"}">${esc(SOURCE[d.source] || d.source)} · ${d.latency_ms} ms</span></div>
    <div class="jev-cols">
      <div class="c-blue"><h5>Moduł · pewność ${pct(d.confidence)}</h5>${bars(top(d.probabilities), [d.module, ...(d.also || [])])}</div>
      <div class="c-purple"><h5>Możliwości</h5>${bars(top(d.capability_probabilities), d.capabilities) || '<p class="sub">wszystkie możliwości modułu</p>'}</div>
      <div class="c-green"><h5>Sygnały</h5>${bars([[`pilność · ${urgency}`, (d.urgency || 0) / 2], ["akcja w świecie", d.acts_on_world], ["potrzebna pamięć", d.needs_history]])}
        <p class="sub">umiejętność: <b>${esc(d.skill || "—")}</b> · temat: <b>${esc(d.topic ? d.topic.replace("topic:", "") : "—")}</b>${d.clarify ? " · <b>za mało pewne — Alfred dopyta</b>" : ""}</p></div>
    </div>`;
}
$("#jev-sum").onclick = () => {
  const open = $("#jev-dock").classList.toggle("hidden") === false;
  $("#jev-sum").setAttribute("aria-expanded", open);
};
async function loadLastRoute() {                  // after a reload: the last classification of today
  const [last] = await api("/api/logs?kind=classified&limit=1");
  if (!last) return;
  const heard = (await api("/api/logs?kind=transcript&limit=50")).find((r) => r.request_id === last.request_id);
  const shield = (await api("/api/logs?kind=shield&limit=50")).find((r) => r.request_id === last.request_id);
  showRoute(last.data, heard?.data.text, shield?.data);
}

// -------------------------------------------------------------- routines
async function loadRoutines() {
  const routines = await api("/api/routines");
  const at = (iso) => hhmm(new Date(iso));
  const state = (r) => r.result === "answer" ? ["done", `✓ wykonana ${at(r.ran_at)}`]
    : r.result === "error" ? ["err", `✗ błąd ${at(r.ran_at)}`]
    : r.ran_at ? ["run", "⏳ w trakcie"]
    : r.due_today ? ["err", "✗ nie wykonana"]
    : r.schedule === "@start" ? ["wait", "○ przy starcie aplikacji"]
    : ["wait", `○ ${new Date(r.next_run).toLocaleString("pl-PL", { weekday: "short", hour: "2-digit", minute: "2-digit" })}`];
  $("#routines").innerHTML = routines.map((r) => {
    const [cls, label] = state(r);
    return `<div class="routine ${cls}" data-id="${esc(r.id)}" title="${esc(r.prompt)}"><div class="row between"><span class="title">${esc(r.id)}</span>
      <span class="row"><span class="state">${esc(label)}</span><button class="del" data-del="1" title="Usuń rutynę" aria-label="Usuń rutynę ${esc(r.id)}">×</button></span></div>
      <div class="sub">${esc(r.schedule === "@start" ? "przy każdym starcie" : cronPl(r.schedule))}${r.module ? ` · ${esc(r.module)}` : ""}</div>
      <div class="sub answer">${esc(r.answer || r.prompt)}</div></div>`;
  }).join("") || '<div class="sub">Brak rutyn — dodaj pierwszą powyżej albo włącz rutynę produktywności w Celach.</div>';
  $("#routines").querySelectorAll(".routine").forEach((el) => (el.onclick = (e) => {
    const r = routines.find((x) => x.id === el.dataset.id);
    if (e.target.dataset.del) {
      if (confirm(`Usunąć rutynę „${r.id}”?`)) api(`/api/routines/${encodeURIComponent(r.id)}`, { method: "DELETE" }).then(loadRoutines, warn);
      return;
    }
    const f = $("#routine-form");
    ["id", "schedule", "prompt"].forEach((k) => (f.elements[k].value = r[k]));
    f.elements.module.value = r.module || "";
    f.elements.prompt.focus();
  }));
  if (!$("#routine-form").elements.module.options.length) {
    const mods = await api("/api/modules");
    $("#routine-form").elements.module.innerHTML = '<option value="">moduł: wybierze Jev</option>' +
      mods.filter((m) => m.enabled).map((m) => `<option value="${esc(m.id)}">${esc(m.label || m.id)}</option>`).join("");
  }
}
$("#routine-form").onsubmit = async (e) => {
  e.preventDefault();
  const f = new FormData(e.target);
  try {
    await api("/api/routines", { method: "POST", body: JSON.stringify({ id: f.get("id"), schedule: f.get("schedule").trim(),
      prompt: f.get("prompt"), module: f.get("module") || null }) });
    e.target.reset();
    loadRoutines();
  } catch (err) { warn(err); }
};

// ================================================================ day view
const DAY_MS = 864e5, OPEN = ["todo", "in_progress"];
const STATUS_PL = { todo: "do zrobienia", in_progress: "w toku", done: "zrobione", cancelled: "anulowane" };
const isOpen = (t) => OPEN.includes(t.status);
const addDays = (d, n) => { const x = new Date(d); x.setDate(x.getDate() + n); return x; };
const startOfDay = (d) => { const x = new Date(d); x.setHours(0, 0, 0, 0); return x; };
const localIso = (d) => new Date(d - d.getTimezoneOffset() * 6e4).toISOString().slice(0, 19);
const hhmm = (d) => d.toLocaleTimeString("pl-PL", { hour: "2-digit", minute: "2-digit" });
const when = (x) => (x?.dateTime ? new Date(x.dateTime) : x?.date ? new Date(`${x.date}T00:00:00`) : null);
const day = { tasks: [], cal: null, today: null, items: [] };

// Summary
function renderStats() {
  const now = new Date(), open = day.tasks.filter((t) => isOpen(t) && !t.alfred);
  const overdue = open.filter((t) => t.due && new Date(t.due) < now);
  const done = day.tasks.filter((t) => t.status === "done" && now - new Date(t.updated) < 7 * DAY_MS);
  const next = day.today?.find((e) => (when(e.end) || when(e.start)) > now);
  const tile = (n, label, sub, cls) => `<div class="tile ${cls}"><b>${n}</b><span>${label}</span><small>${esc(sub)}</small></div>`;
  $("#stats").innerHTML =
    tile(day.today ? day.today.length : "—", "dziś w kalendarzu", next ? `następne: ${next.start?.dateTime ? hhmm(when(next.start)) : "cały dzień"} ${next.summary || ""}`
      : day.today ? "nic więcej dziś" : "Google niepołączony", "blue") +
    tile(open.length, "otwarte zadania", open.find((t) => t.status === "in_progress")?.title || "", "purple") +
    tile(overdue.length, "po terminie", overdue[0]?.title || "wszystko na czas", overdue.length ? "err" : "green") +
    tile(done.length, "zrobione · 7 dni", "", "green");
  const byCat = {};
  open.forEach((t) => (byCat[t.category || "bez kategorii"] = (byCat[t.category || "bez kategorii"] || 0) + 1));
  $("#sum-open").innerHTML = `<span class="sub">Otwarte teraz:</span>` +
    Object.entries(byCat).map(([c, n]) => `<button class="chip on" data-c="${esc(c === "bez kategorii" ? NO_CAT : c)}" title="Pokaż na Kanbanie">${esc(c)} <span class="muted">${n}</span></button>`).join("") +
    (overdue.length ? `<span class="chip late">po terminie <span class="muted">${overdue.length}</span></span>` : "");
  $("#sum-open").querySelectorAll("button").forEach((b) => (b.onclick = () => { setFilter(b.dataset.c); setSub("kanban"); }));
  $("#greeting").textContent = `${now.getHours() < 18 && now.getHours() >= 5 ? "Dzień dobry" : "Dobry wieczór"} · ` +
    now.toLocaleDateString("pl-PL", { weekday: "long", day: "numeric", month: "long" });
}

const BRIEFS = {
  day: "Podsumuj mój dzień: co mam dziś w kalendarzu, które zadania są na dziś albo po terminie i jaki otwarty wątek warto domknąć.",
  week: "Podsumuj mój tydzień: najważniejsze spotkania, zadania na ten tydzień i co udało się zamknąć.",
  prio: "Zaproponuj priorytety moich otwartych zadań według rutyny produktywności: co przybliża mnie do celów, " +
    "co głębokie zrobić rano w szczycie energii, co płytkie zebrać na popołudnie, co odłożyć. " +
    "Dla pierwszego podaj najszybszą drogę. Niczego nie zmieniaj bez mojej zgody.",
};
function showBrief(text, at, source) {
  $("#brief").innerHTML = `<p>${esc(text)}</p><span class="meta">${esc(source)} · ${esc(at)}</span>`;
  try { localStorage.setItem("brief", JSON.stringify({ text, at, source, day: new Date().toDateString() })); } catch { /* private mode */ }
}
document.querySelectorAll("[data-brief]").forEach((b) => (b.onclick = async () => {
  $("#brief").innerHTML = '<p class="sub pulse">Alfred przygotowuje podsumowanie…</p>';
  try {
    const { answer } = await api("/api/ask", { method: "POST", body: JSON.stringify({ text: BRIEFS[b.dataset.brief] }) });
    showBrief(answer, hhmm(new Date()), b.textContent.toLowerCase());
  } catch (e) { $("#brief").innerHTML = `<p class="sub">⚠ ${esc(e.message)}</p>`; }
}));
async function loadBrief() {
  let saved = null;
  try { saved = JSON.parse(localStorage.getItem("brief")); } catch { /* private mode */ }
  if (saved?.day === new Date().toDateString()) return showBrief(saved.text, saved.at, saved.source);
  const routine = (await api("/api/logs?kind=answer&limit=50")).reverse().find((r) => r.data.source === "routine");
  if (routine) showBrief(routine.data.text, routine.ts.slice(11, 16), "rutyna");
  else $("#brief").innerHTML = '<p class="sub">Poproś Alfreda o brief dnia albo tygodnia — odpowie głosem, a podsumowanie zostanie tutaj.</p>';
}

// To-do: a kanban board - one column per status; drag a card to another column to change its status (SortableJS)
const sortable = import("sortablejs").then((m) => m.default).catch(() => null);   // CDN down: the board still shows
const NO_CAT = "__none__";                              // the "no category" chip
let catFilter = "", who = "me";                         // "" = every category; whose board: "me" | "alfred"
try { catFilter = localStorage.getItem("catfilter") || ""; who = localStorage.getItem("board") || "me"; } catch { /* private mode */ }
function setFilter(c) {
  catFilter = c;
  try { localStorage.setItem("catfilter", c); } catch { /* private mode */ }
  refreshTasks().catch(warn);
}
document.querySelectorAll("#board-who button").forEach((b) => (b.onclick = () => {
  who = b.dataset.who;
  try { localStorage.setItem("board", who); } catch { /* private mode */ }
  refreshTasks().catch(warn);
}));
async function refreshTasks() {
  day.tasks = await api("/api/tasks?status=all");
  document.querySelectorAll("#board-who button").forEach((b) => b.classList.toggle("on", b.dataset.who === who));
  const board = day.tasks.filter((t) => !!t.alfred === (who === "alfred"));
  const now = new Date();
  const fixed = status.task_categories || [];      // config/brain.yaml tasks.categories - the only ones, in that order
  const others = board.map((t) => t.category).filter((c) => c && !fixed.includes(c)).sort((a, b) => a.localeCompare(b, "pl"));
  const cats = [...new Set([...fixed, ...others])];   // `others` only for old tasks from before the fixed list
  const picked = $("#task-cats").value;
  $("#task-cats").innerHTML = `<option value="">bez kategorii</option>` +
    fixed.map((c) => `<option${c === picked ? " selected" : ""}>${esc(c)}</option>`).join("");

  const open = board.filter(isOpen);
  const count = (c) => open.filter((t) => (c === NO_CAT ? !t.category : !c || t.category === c)).length;
  const chips = ["", ...cats, ...(open.some((t) => !t.category) ? [NO_CAT] : [])];
  if (!chips.includes(catFilter)) catFilter = "";      // a remembered category this board does not have
  $("#cat-filter").innerHTML = chips.map((c) => `<button class="chip${c === catFilter ? " on" : ""}" data-c="${esc(c)}">` +
    `${esc(c === NO_CAT ? "bez kategorii" : c || "wszystkie")} <span class="muted">${count(c)}</span></button>`).join("");
  $("#cat-filter").querySelectorAll("button").forEach((b) => (b.onclick = () => setFilter(b.dataset.c)));

  const inFilter = (t) => !catFilter || (catFilter === NO_CAT ? !t.category : t.category === catFilter);
  const recent = (t) => isOpen(t) || now - new Date(t.updated) < 14 * DAY_MS;   // finished cards leave after 2 weeks
  const card = (t) => {
    const due = t.due && new Date(t.due), late = due && due < now && isOpen(t);
    const sub = [due && due.toLocaleString("pl-PL", { weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }),
      t.schedule && `co ${t.schedule}`].filter(Boolean).map(esc).join(" · ");
    return `<div class="kcard${late ? " overdue" : ""}" data-id="${esc(t.id)}"><div class="title">${esc(t.title)}</div>
      ${sub ? `<div class="sub">${sub}</div>` : ""}${t.goal ? `<div class="sub goal" title="Jak przybliża do celu">🎯 ${esc(t.goal)}</div>` : ""}
      <button class="tag c${fixed.indexOf(t.category)}" data-cat="${esc(t.id)}" title="Zmień kategorię">🏷 ${esc(t.category || "kategoria")}</button></div>`;
  };
  $("#board").innerHTML = Object.entries(STATUS_PL).map(([s, label]) => {
    const ts = board.filter((t) => t.status === s && inFilter(t) && recent(t));
    return `<div class="lane ${s}"><div class="lane-title">${label} <span class="muted">${ts.length}${OPEN.includes(s) ? "" : " · 14 dni"}</span></div>
      <div class="cards" data-status="${s}">${ts.map(card).join("")}</div></div>`;
  }).join("");
  $("#board").querySelectorAll("[data-cat]").forEach((b) => (b.onclick = async () => {
    const t = day.tasks.find((x) => x.id === b.dataset.cat);
    const c = prompt(`Kategoria zadania: ${fixed.join(", ")} (puste = bez kategorii; nowe dodasz w Ustawieniach):`, t.category || "");
    if (c === null) return;
    await api(`/api/tasks/${t.id}`, { method: "PATCH", body: JSON.stringify({ category: c.trim() }) }).catch(warn);
    refreshTasks();
  }));
  const Sortable = await sortable;
  $("#board").querySelectorAll(".cards").forEach((list) => Sortable?.create(list, {
    group: "tasks", sort: false, animation: 150, ghostClass: "ghost",
    onAdd: (e) => setTaskStatus(e.item.dataset.id, e.to.dataset.status),
  }));
  renderStats();
  renderCalendar();
}
async function setTaskStatus(id, value) {
  await api(`/api/tasks/${id}`, { method: "PATCH", body: JSON.stringify({ status: value }) });
  refreshTasks();
}
$("#task-form").onsubmit = async (e) => {
  e.preventDefault();
  const f = new FormData(e.target);
  const due = f.get("due") ? new Date(f.get("due")).toISOString() : null;
  await api("/api/tasks", { method: "POST", body: JSON.stringify({ title: f.get("title"), due, schedule: f.get("schedule") || null,
    category: f.get("category") || null, alfred: who === "alfred" }) });
  e.target.reset();
  refreshTasks();
};

// Calendar: Google events + tasks with a due time, a week (a day on narrow screens) at a time.
// Dzień / Tydzień: an hour grid. Miesiąc: what is on each day (click a day -> Dzień).
const CAL_MODES = { day: "Dzień", week: "Tydzień", month: "Miesiąc" };
let calMode = "week";
try { calMode = CAL_MODES[localStorage.getItem("calmode")] ? localStorage.getItem("calmode") : "week"; } catch { /* private mode */ }
const calDays = () => (calMode === "day" || innerWidth < 760 ? 1 : 7);                 // the hour grid's width
const addMonths = (d, n) => new Date(d.getFullYear(), d.getMonth() + n, 1);
const firstDay = (d) => calMode === "month" ? addMonths(d, 0)
  : calDays() === 1 ? startOfDay(d) : addDays(startOfDay(d), -((d.getDay() + 6) % 7));
const calStep = (from, dir) => (calMode === "month" ? addMonths(from, dir) : addDays(from, dir * calDays()));
let calFrom = firstDay(new Date());
function setCalMode(mode, at = calFrom <= new Date() && new Date() < calStep(calFrom, 1) ? new Date() : calFrom) {
  calMode = mode;
  try { localStorage.setItem("calmode", mode); } catch { /* private mode */ }
  calFrom = firstDay(at);
  delete $("#calendar").dataset.scrolled;
  renderCalModes();
  loadCalendar().catch(warn);
}
function renderCalModes() {
  $("#cal-modes").innerHTML = Object.entries(CAL_MODES).map(([m, l]) => `<button data-m="${m}" class="${m === calMode ? "on" : ""}">${l}</button>`).join("");
  $("#cal-modes").querySelectorAll("button").forEach((b) => (b.onclick = () => setCalMode(b.dataset.m)));
}
async function loadCalendar() {
  const from = calFrom, to = calStep(from, 1), now = new Date();
  const cal = await api(`/api/calendar?start=${localIso(from)}&end=${localIso(to)}`);
  if (from !== calFrom) return;                        // the user moved on while this was loading
  day.cal = cal;
  if (from <= now && now < to) {
    day.today = cal.status === "ready" ? cal.events.filter((e) => when(e.start) < addDays(startOfDay(now), 1) && (when(e.end) || when(e.start)) > startOfDay(now))
      .sort((a, b) => when(a.start) - when(b.start)) : null;
  }
  const s = status.mcp.find((x) => x.name === "google-calendar")?.status || cal.status;
  $("#cal-status").className = `pill ${cal.status === "ready" ? "ok" : "bad"}`;
  $("#cal-status").textContent = cal.status === "ready" ? `Google · ${hhmm(now)}` : s === "disabled" || s === "missing" ? "Google · niepołączony" : "Google · błąd";
  $("#cal-status").title = cal.error || (cal.status === "ready" ? "zsynchronizowano" : "");
  renderCalendar();
  renderStats();
}
$("#cal-prev").onclick = () => { calFrom = calStep(calFrom, -1); loadCalendar(); };
$("#cal-next").onclick = () => { calFrom = calStep(calFrom, 1); loadCalendar(); };
$("#cal-today").onclick = () => { calFrom = firstDay(new Date()); loadCalendar(); };

function renderCalendar() {
  if (!day.cal) return;
  const n = calDays(), days = [...Array(n)].map((_, i) => addDays(calFrom, i)), end = calStep(calFrom, 1);
  const now = new Date(), H = $("main").dataset.sub === "calendar" ? 52 : 30;  // px per hour: full page vs next to the board
  const items = [
    ...day.cal.events.map((e) => {
      const start = when(e.start), allDay = !e.start?.dateTime;
      return { kind: "event", title: e.summary || "(bez tytułu)", start, end: when(e.end) || addDays(start, allDay ? 1 : 0), allDay, e };
    }),
    ...day.tasks.filter((t) => t.due && isOpen(t)).map((t) => ({ kind: "task", title: t.title, start: new Date(t.due), end: new Date(+new Date(t.due) + 30 * 6e4), t })),
  ].filter((i) => i.start && i.start < end && i.end > calFrom);
  day.items = items;
  $("#cal-note").classList.toggle("hidden", day.cal.status === "ready");
  $("#cal-note").textContent = `Kalendarz Google nie jest połączony${day.cal.error ? ` (${day.cal.error})` : ""} — widać tylko zadania z terminem. Jak połączyć: README → „MCP servers”.`;
  const cal = $("#calendar");
  cal.className = "calendar";
  if (calMode === "month") return renderMonth(cal, items, now);
  const timed = items.filter((i) => !i.allDay);
  const endHour = (i) => (startOfDay(i.end) - startOfDay(i.start) ? 24 : i.end.getHours() + (i.end.getMinutes() ? 1 : 0));
  const from = Math.min(7, ...timed.map((i) => i.start.getHours()));
  const to = Math.max(21, ...timed.map(endHour));
  const chip = (i) => `<div class="ev ${i.kind} allday" data-i="${items.indexOf(i)}">${esc(i.title)}</div>`;
  const cols = days.map((d) => {
    const evs = timed.filter((i) => startOfDay(i.start) - d === 0).sort((a, b) => a.start - b.start);
    // side by side only where events overlap: each group of overlapping events shares its own lanes
    let lanes = [], group = [];
    const close = () => { group.forEach((i) => (i.lanes = lanes.length)); lanes = []; group = []; };
    evs.forEach((i) => {
      if (lanes.length && lanes.every((e) => e <= i.start)) close();
      let k = lanes.findIndex((e) => e <= i.start);
      if (k < 0) k = lanes.push(0) - 1;
      lanes[k] = i.end; i.lane = k; group.push(i);
    });
    close();
    const boxes = evs.map((i) => {
      const top = (i.start.getHours() + i.start.getMinutes() / 60 - from) * H, w = 100 / i.lanes;
      const h = Math.max(20, (Math.min(i.end, addDays(d, 1)) - i.start) / 36e5 * H - 2);
      const late = i.kind === "task" && i.start < now ? " overdue" : "";
      return `<div class="ev ${i.kind}${late}" data-i="${items.indexOf(i)}" style="top:${top}px;height:${h}px;left:calc(${i.lane * w}% + 2px);width:calc(${w}% - 4px)"><b>${hhmm(i.start)}</b> ${esc(i.title)}</div>`;
    }).join("");
    const nowLine = startOfDay(now) - d === 0 ? `<div class="now-line" style="top:${(now.getHours() + now.getMinutes() / 60 - from) * H}px"></div>` : "";
    return `<div class="cal-day" data-day="${+d}" style="height:${(to - from) * H}px">${boxes}${nowLine}</div>`;
  }).join("");
  cal.style.setProperty("--days", n);
  cal.style.setProperty("--h", `${H}px`);
  cal.innerHTML = `<div class="cal-head"></div>` +
    days.map((d) => `<div class="cal-head${startOfDay(now) - d === 0 ? " today" : ""}">${d.toLocaleDateString("pl-PL", { weekday: "short", day: "numeric" })}</div>`).join("") +
    `<div class="cal-allday cal-label">cały dzień</div>` +
    days.map((d) => `<div class="cal-allday">${items.filter((i) => i.allDay && i.start < addDays(d, 1) && i.end > d).map(chip).join("")}</div>`).join("") +
    `<div class="cal-hours">${Array.from({ length: to - from }, (_, k) => `<div>${from + k}:00</div>`).join("")}</div>` + cols;
  $("#cal-range").textContent = n === 1 ? calFrom.toLocaleDateString("pl-PL", { weekday: "long", day: "numeric", month: "long" })
    : `${calFrom.toLocaleDateString("pl-PL", { day: "numeric", month: "short" })} – ${addDays(end, -1).toLocaleDateString("pl-PL", { day: "numeric", month: "short", year: "numeric" })}`;
  cal.querySelectorAll(".ev").forEach((x) => (x.onclick = (e) => { e.stopPropagation(); showEvent(day.items[x.dataset.i]); }));
  cal.querySelectorAll(".cal-day").forEach((c) => (c.onclick = (e) => {    // empty slot: ask Alfred to add an event there
    const d = new Date(+c.dataset.day), h = Math.floor(from + (e.clientY - c.getBoundingClientRect().top) / H);
    $("#text").value = `Dodaj do kalendarza: ${d.toLocaleDateString("pl-PL", { weekday: "long", day: "numeric", month: "long" })} o ${h}:00 — `;
    $("#text").focus();
  }));
  if (!cal.dataset.scrolled) { cal.scrollTop = Math.max(0, (Math.min(now.getHours(), to - 3) - from - 1) * H); cal.dataset.scrolled = 1; }
}

// Miesiąc: a grid of days, each listing what is on it.
function renderMonth(cal, items, now) {
  const m = calFrom, first = addDays(m, -((m.getDay() + 6) % 7)), next = addMonths(m, 1);
  const chip = (i) => `<div class="ev ${i.kind}${i.kind === "task" && i.start < now ? " overdue" : ""}" data-i="${items.indexOf(i)}">` +
    `${i.allDay ? "" : `<b>${hhmm(i.start)}</b> `}${esc(i.title)}</div>`;
  const cells = [];
  for (let d = first; d < next || (d.getDay() + 6) % 7 !== 0; d = addDays(d, 1)) {   // Monday before .. Sunday after
    const its = items.filter((i) => i.start < addDays(d, 1) && i.end > d).sort((a, b) => a.start - b.start);
    const out = d.getMonth() !== m.getMonth(), today = startOfDay(now) - d === 0;
    cells.push(`<div class="mday${out ? " out" : ""}${today ? " today" : ""}" data-day="${+d}"><span class="n">${d.getDate()}</span>` +
      (out ? "" : its.slice(0, 3).map(chip).join("") + (its.length > 3 ? `<span class="more">+${its.length - 3} więcej</span>` : "")) + `</div>`);
  }
  cal.className = "calendar month";
  cal.innerHTML = `<div class="mgrid">${["Pn", "Wt", "Śr", "Cz", "Pt", "So", "Nd"].map((w) => `<div class="wd">${w}</div>`).join("")}${cells.join("")}</div>`;
  $("#cal-range").textContent = m.toLocaleDateString("pl-PL", { month: "long", year: "numeric" });
  cal.querySelectorAll(".ev").forEach((x) => (x.onclick = (e) => { e.stopPropagation(); showEvent(day.items[x.dataset.i]); }));
  cal.querySelectorAll(".mday").forEach((c) => (c.onclick = () => setCalMode("day", new Date(+c.dataset.day))));
}

function showEvent(i) {
  const card = $("#event-card"), e = i.e || {}, t = i.t;
  const time = i.allDay ? "cały dzień" : `${i.start.toLocaleDateString("pl-PL", { weekday: "long", day: "numeric", month: "long" })}, ${hhmm(i.start)}` + (t ? "" : ` – ${hhmm(i.end)}`);
  card.innerHTML = `<button class="x" aria-label="Zamknij">×</button><span class="crumb">${t ? "zadanie" : "Google Calendar"}</span><b>${esc(i.title)}</b>
    <p>${esc(time)}${e.location ? ` · ${esc(e.location)}` : ""}</p>
    ${e.description ? `<p>${esc(e.description.slice(0, 400))}</p>` : ""}
    ${t ? `<p>${esc(STATUS_PL[t.status])}${t.description ? ` · ${esc(t.description)}` : ""}</p><button class="link" data-done>✓ Oznacz jako zrobione</button>` : ""}
    ${/^https:\/\//.test(e.htmlLink || "") ? `<a class="link" href="${esc(e.htmlLink)}" target="_blank" rel="noopener">Otwórz w Google Calendar →</a>` : ""}`;
  card.classList.remove("hidden");
  card.querySelector(".x").onclick = () => card.classList.add("hidden");
  const done = card.querySelector("[data-done]");
  if (done) done.onclick = () => { card.classList.add("hidden"); setTaskStatus(t.id, "done"); };
}

// Session summaries
// Podsumowanie okresu: tasks, calendar, sessions and cost summed over a day / month / quarter / year (‹ › = earlier/later)
const SUM_PERIODS = { day: "Dzień", month: "Miesiąc", quarter: "Kwartał", year: "Rok" };
let sumPeriod = "day", sumOffset = 0;
try { sumPeriod = SUM_PERIODS[localStorage.getItem("sumperiod")] ? localStorage.getItem("sumperiod") : "day"; } catch { /* private mode */ }
async function loadSummary() {
  $("#sum-modes").innerHTML = Object.entries(SUM_PERIODS).map(([p, l]) => `<button data-p="${p}" class="${p === sumPeriod ? "on" : ""}">${l}</button>`).join("");
  $("#sum-modes").querySelectorAll("button").forEach((b) => (b.onclick = () => {
    sumPeriod = b.dataset.p; sumOffset = 0;
    try { localStorage.setItem("sumperiod", sumPeriod); } catch { /* private mode */ }
    loadSummary().catch(warn);
  }));
  const s = await api(`/api/summary?period=${sumPeriod}&offset=${sumOffset}`);
  if (s.period !== sumPeriod || s.offset !== sumOffset) return;     // clicked on while this was loading
  const from = new Date(s.start);
  $("#sum-range").textContent = { day: from.toLocaleDateString("pl-PL", { weekday: "long", day: "numeric", month: "long", year: "numeric" }),
    month: from.toLocaleDateString("pl-PL", { month: "long", year: "numeric" }), quarter: `Q${Math.floor(from.getMonth() / 3) + 1} ${from.getFullYear()}`,
    year: `${from.getFullYear()}` }[s.period] + (s.offset === 0 ? " · bieżący" : "");
  const t = s.tasks, c = s.cost, sub = status.backend === "subscription";
  const paid = c.jev_usd + c.elevenlabs_usd + (sub ? 0 : c.cost_usd);
  const tile = (n, label, small, cls) => `<div class="tile ${cls}"><b>${n}</b><span>${label}</span><small title="${esc(small)}">${esc(small)}</small></div>`;
  const cats = Object.entries(t.done_by_category).map(([k, v]) => `${k} ${v}`).join(" · ");
  $("#sum-stats").innerHTML =
    tile(t.done, "zrobione", cats || "—", "green") + tile(t.planned, "zaplanowane", `${t.created} dodanych`, "purple") +
    tile(t.rolled, "przeniesione", `${t.cancelled} anulowanych`, t.rolled ? "err" : "green") +
    tile(s.events ?? "—", "w kalendarzu", s.events == null ? "Google niepołączony" : "wydarzeń", "blue") +
    tile(s.sessions.count, "sesje", `${s.sessions.turns} tur`, "blue");
  const claudeTok = c.input + c.output + c.cache_read + c.cache_write;
  $("#sum-costs").innerHTML =
    tile(cash(c.jev_usd), "Jev", `${num(c.jev)} tok. · płatne tylko wejście`, "purple") +
    tile(usd(c.cost_usd), "Claude", `${num(claudeTok)} tok.` + (sub ? " · subskrypcja: równowartość API, nie rachunek" : ""), "blue") +
    tile(cash(c.elevenlabs_usd), "ElevenLabs", `${num(c.tts_chars)} znaków głosu · ${num(Math.round(c.stt_s))} s mowy`, "green") +
    tile(cash(paid), "płacisz razem", `Jev + ElevenLabs${sub ? "" : " + Claude"} · ceny: config/brain.yaml → prices`, paid ? "err" : "green");
  $("#sum-detail").textContent = t.done_titles.length ? `Zrobione: ${t.done_titles.join(" · ")}` : "";
}
$("#sum-prev").onclick = () => { sumOffset -= 1; loadSummary().catch(warn); };
$("#sum-next").onclick = () => { sumOffset += 1; loadSummary().catch(warn); };

async function loadSessions() {
  const sessions = await api("/api/memory/sessions?limit=6");
  $("#sessions").innerHTML = sessions.map((s) => `<div class="card"><div class="row between"><span class="title">${esc(s.title)}</span>
    <span class="sub">${esc(String(s.ended || "").slice(0, 16).replace("T", " "))}</span></div>
    <div class="sub">${esc(s.description || "")}</div>
    ${(s.open_threads || []).length ? `<div class="threads">${s.open_threads.map((x) => `<span class="badge">${esc(x)}</span>`).join("")}</div>` : ""}</div>`).join("")
    || '<div class="sub">Jeszcze nie ma zapisanych sesji. Alfred podsumowuje sesję po 15 minutach ciszy.</div>';
}

// ============================================================== tasks view: the panel that slides out of the rail
const TAB_LOAD = { chat: () => ($("#tab-chat").scrollTop = 1e9), memory: loadBriefing, map: loadMap,
  persona: loadPersona, modules: loadModules, log: loadLog, settings: loadSettings };
function openTab(name) {
  const button = document.querySelector(`.rail button[data-tab="${name}"]`);
  document.querySelectorAll(".rail button").forEach((b) => b.classList.toggle("active", b === button));
  document.querySelectorAll("#drawer .tab").forEach((t) => t.classList.toggle("hidden", t.id !== `tab-${name}`));
  $("#drawer-title").textContent = button.title;
  $("#drawer").classList.add("open");
  TAB_LOAD[name]();
}
function closeDrawer() {
  $("#drawer").classList.remove("open");
  document.querySelectorAll(".rail button").forEach((b) => b.classList.remove("active"));
}
document.querySelectorAll(".rail button").forEach((b) => (b.onclick = () => (b.classList.contains("active") ? closeDrawer() : openTab(b.dataset.tab))));
$("#drawer-x").onclick = closeDrawer;
document.addEventListener("keydown", (e) => e.key === "Escape" && closeDrawer());

// Memory
async function loadBriefing() { $("#briefing").textContent = (await api("/api/memory/briefing")).briefing; }
$("#close-session").onclick = async () => { await api("/api/session/close", { method: "POST" }); loadBriefing(); };
async function openMemoryPage(path) {
  const page = await api(`/api/memory/page?path=${encodeURIComponent(path)}`);
  if (view !== "tasks") setView("tasks");
  openTab("memory");
  $("#mem-page").textContent = page.content;
  $("#mem-page").classList.remove("hidden");
}
$("#mem-search").onsubmit = async (e) => {
  e.preventDefault();
  const hits = await api(`/api/memory/search?q=${encodeURIComponent($("#mem-q").value)}`);
  $("#mem-results").innerHTML = hits.map((h) => `<div class="card" data-path="${esc(h.path)}" style="cursor:pointer">
    <span class="title">${esc(h.title)}</span><span class="sub">${esc(h.type)} · ${esc(h.path)}</span>
    <span class="sub">${esc(h.description || "")}</span></div>`).join("") || '<div class="sub">Nic nie znaleziono.</div>';
  $("#mem-results").querySelectorAll(".card").forEach((c) => (c.onclick = () => openMemoryPage(c.dataset.path)));
};

// Modules + router tester
async function loadModules() {
  const mods = await api("/api/modules");
  $("#modules").innerHTML = mods.map((m) => `<div class="card"><div class="row"><span class="title">${esc(m.id)}</span>
    <label class="switch"><input type="checkbox" data-id="${m.id}" ${m.enabled ? "checked" : ""}> aktywny</label></div>
    <div class="sub">${esc(m.label)}</div>
    ${m.capabilities.map((c) => `<div class="sub">▸ ${esc(c.label)} <code>${esc(c.id)}</code>${c.confirm ? " · wymaga zgody" : ""} — ${c.tools.length ? c.tools.map((t) => esc(t.split("__").pop())).join(", ") : "brak podłączonych narzędzi"}</div>`).join("")}
    ${m.uses.length ? `<div class="sub">korzysta z: ${m.uses.map(esc).join(", ")}</div>` : ""}
    ${m.servers.length ? `<div class="sub">serwery: ${m.servers.map(esc).join(", ")}</div>` : ""}
    ${m.skills.length ? `<div class="sub">umiejętności: ${m.skills.map((s) => esc(s.name)).join(", ")}</div>` : ""}</div>`).join("");
  $("#modules").querySelectorAll("input[type=checkbox]").forEach((c) => (c.onchange = async () => {
    await api(`/api/modules/${c.dataset.id}/enabled`, { method: "POST", body: JSON.stringify({ enabled: c.checked }) });
    await loadGraph();
    loadModules();
  }));
  $("#mcp").innerHTML = status.mcp.map((s) => `<div class="card"><div class="row"><span class="title">${esc(s.name)}</span>
    <span class="badge ${s.status === "ready" ? "done" : s.status === "error" ? "error" : ""}">${s.status}</span></div>
    <div class="sub">${esc(s.description)}</div>${s.error ? `<div class="sub">${esc(s.error)}</div>` : ""}
    <div class="sub">${s.tools.length} narzędzi</div></div>`).join("");
}
$("#classify-form").onsubmit = async (e) => {
  e.preventDefault();
  const r = await api("/api/classify", { method: "POST", body: JSON.stringify({ text: $("#classify-text").value }) });
  const probs = Object.entries(r.probabilities).sort((a, b) => b[1] - a[1]);
  $("#classify-out").innerHTML = `<div class="card"><div class="sub">${esc(r.source)} · ${r.latency_ms} ms · skill: ${esc(r.skill || "—")}
    · pilność ${r.urgency.toFixed(1)} · działanie ${Math.round(r.acts_on_world * 100)}% · historia ${Math.round(r.needs_history * 100)}%</div>
    <div class="probs">${probs.map(([k, v]) => `<span>${esc(k)}</span><div class="bar" style="width:${Math.max(2, v * 100)}%"></div><span>${Math.round(v * 100)}%</span>`).join("")}</div></div>`;
  Brain3D?.flash(`module:${r.module}`);
};

// Brain map (OKF)
function renderMd(text, base) {
  let fm = "";
  if (text.startsWith("---")) { const i = text.indexOf("\n---", 3); fm = text.slice(4, i); text = text.slice(i + 4); }
  const dir = base.includes("/") ? base.slice(0, base.lastIndexOf("/") + 1) : "";
  const resolve = (href) => {
    const parts = (dir + href).split("/"), out = [];
    parts.forEach((x) => (x === ".." ? out.pop() : x !== "." && out.push(x)));
    return out.join("/");
  };
  const inline = (s) => esc(s)
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\*\*([^*]+)\*\*/g, "<b>$1</b>")
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, (m, t, h) => /^https?:/.test(h) ? `<a href="${h}" target="_blank" rel="noopener">${t}</a>` : `<a data-page="${esc(resolve(h))}">${t}</a>`);
  const lines = text.split("\n"), html = [];
  let list = "", table = false, code = false;
  const close = () => { if (list) html.push(`</${list}>`); if (table) html.push("</table>"); list = ""; table = false; };
  for (const l of lines) {
    if (/^```/.test(l)) {
      if (code) html.push("</code></pre>"); else { close(); html.push("<pre><code>"); }
      code = !code;
    } else if (code) html.push(esc(l) + "\n");
    else if (/^\|/.test(l)) {
      if (/^\|[-| ]+\|$/.test(l)) continue;
      if (!table) { close(); html.push("<table>"); table = true; }
      html.push("<tr>" + l.split("|").slice(1, -1).map((c) => `<td>${inline(c.trim())}</td>`).join("") + "</tr>");
    } else if (/^\s*([-*]|\d+\.) /.test(l)) {
      const tag = /^\s*\d/.test(l) ? "ol" : "ul";
      if (list !== tag) { close(); html.push(`<${tag}>`); list = tag; }
      html.push(`<li>${inline(l.replace(/^\s*([-*]|\d+\.) /, ""))}</li>`);
    } else {
      close();
      if (/^### /.test(l)) html.push(`<h3>${inline(l.slice(4))}</h3>`);
      else if (/^## /.test(l)) html.push(`<h2>${inline(l.slice(3))}</h2>`);
      else if (/^# /.test(l)) html.push(`<h1>${inline(l.slice(2))}</h1>`);
      else if (l.trim()) html.push(`<p>${inline(l)}</p>`);
    }
  }
  close();
  if (code) html.push("</code></pre>");
  return (fm ? `<div class="fm">${esc(fm)}</div>` : "") + html.join("");
}
async function openMapPage(path) {
  const page = await api(`/api/map/page?path=${encodeURIComponent(path)}`);
  $("#map-crumbs").innerHTML = [`<a data-page="index.md">brain_map</a>`, ...path.split("/").map((x) => esc(x))].join(" / ");
  $("#map-page").innerHTML = renderMd(page.content, path);
  document.querySelectorAll("#map-page a[data-page], #map-crumbs a[data-page]").forEach((a) => (a.onclick = () => openMapPage(a.dataset.page)));
  if (!document.querySelector('.rail button[data-tab="map"]').classList.contains("active")) openTab("map");
  const id = page.content.match(/\nid: (.+)/)?.[1]?.trim();
  if (id) ["module:", "cap:", "skill:", "tool:", "mcp:", ""].forEach((p) => Brain3D?.flash(p + id));
}
async function loadMap() {
  const m = await api("/api/map");
  $("#map-backend").textContent = `Claude: ${status.backend === "subscription" ? "subskrypcja (Claude Code)" : "API (tokeny)"}`;
  $("#map-counts").innerHTML = Object.entries({ modules: "moduły", capabilities: "możliwości", skills: "umiejętności", tools: "narzędzia", servers: "serwery", topics: "tematy" })
    .map(([k, l]) => `<div><b>${m.counts[k]}</b>${l}</div>`).join("");
  $("#jev-cats").innerHTML = Object.entries(m.jev).map(([k, v]) => {
    const crit = Array.isArray(v.criteria) ? v.criteria : Object.keys(v.criteria || {});
    return `<li><b>${esc(k)}</b> <span class="muted">(${esc(v.type)})</span> — ${esc(v.instructions)}${crit.length ? `<br><span class="muted">${crit.map(esc).join(" · ")}</span>` : ""}</li>`;
  }).join("");
  if (!$("#map-page").innerHTML) openMapPage("index.md");
}
$("#map-rebuild").onclick = async () => {
  const r = await api("/api/map/rebuild", { method: "POST" });
  addMsg("system", `Mapa przebudowana: ${r.tools} narzędzi, ${r.capabilities} możliwości, ${r.changes.length} zmian.`);
  await loadGraph(); loadMap(); openMapPage("log.md");
};

// Persona
async function loadPersona() {
  const p = await api("/api/persona");
  const f = $("#persona-form"), m = p.meta;
  f.name.value = m.name || ""; f.user_name.value = m.user_name || "";
  f["address.pl"].value = m.address?.pl || ""; f["address.en"].value = m.address?.en || "";
  f.body.value = p.body;
  f["acks.pl"].value = (m.acks?.pl || []).join("\n"); f["acks.en"].value = (m.acks?.en || []).join("\n");
  f["confirm.pl"].value = m.confirm?.pl || ""; f["confirm.en"].value = m.confirm?.en || "";
  $("#persona-preview").textContent = p.preview;
  status.personaMeta = m;
}
$("#persona-form").onsubmit = async (e) => {
  e.preventDefault();
  const f = e.target, lines = (v) => v.split("\n").map((x) => x.trim()).filter(Boolean);
  const meta = { ...(status.personaMeta || {}), title: f.name.value, name: f.name.value, user_name: f.user_name.value,
    address: { pl: f["address.pl"].value, en: f["address.en"].value },
    acks: { pl: lines(f["acks.pl"].value), en: lines(f["acks.en"].value) },
    confirm: { pl: f["confirm.pl"].value, en: f["confirm.en"].value } };
  const p = await api("/api/persona", { method: "PUT", body: JSON.stringify({ meta, body: f.body.value }) });
  $("#persona-preview").textContent = p.preview;
  addMsg("system", "Osobowość zapisana — obowiązuje od następnego polecenia.");
};

// Log
async function loadLog() {
  const days = await api("/api/logs/days");
  const sel = $("#log-day");
  if (!sel.options.length) sel.innerHTML = days.map((d) => `<option>${d}</option>`).join("");
  const rows = await api(`/api/logs?day=${sel.value || ""}&kind=${$("#log-kind").value}&limit=400`);
  $("#log").innerHTML = "";
  rows.reverse().forEach((r) => appendLog(r, true));
}
function appendLog(ev, bottom = false) {
  if ($("#log-kind").value && ev.kind !== $("#log-kind").value) return;
  const d = { ...ev.data }; delete d.audio_b64;
  const el = document.createElement("div");
  el.innerHTML = `<span class="t">${esc(ev.ts.slice(11, 19))}</span> <b>${esc(ev.kind)}</b> ${esc(ev.node)} ${esc(JSON.stringify(d)).slice(0, 400)}`;
  bottom ? $("#log").appendChild(el) : $("#log").prepend(el);
}
$("#log-day").onchange = loadLog;
$("#log-kind").onchange = loadLog;

// Settings
const FIELDS = [
  ["assistant.default_language", "Domyślny język (pl/en)"],
  ["models.executor", "Model wykonawczy"], ["models.executor_effort", "Wysiłek (low/medium/high)"],
  ["models.light", "Model lekki"], ["router.confident_at", "Próg pewności routera"],
  ["router.ask_below", "Dopytaj poniżej"], ["voice.voice_id", "ElevenLabs voice ID"],
  ["voice.tts_model", "Model TTS"], ["memory.session_idle_minutes", "Zamknij sesję po (min)"],
  ["proactive.heartbeat_minutes", "Heartbeat (min)"],
  ["proactive.reminders.lead_minutes", "Przypomnienie przed terminem (min, 0 = o czasie)"],
];
const renderCats = () => ($("#cat-list").innerHTML = (status.task_categories || []).map((c) => `<span class="chip on">${esc(c)}</span>`).join(""));
$("#cat-form").onsubmit = async (e) => {
  e.preventDefault();
  const f = new FormData(e.target);
  status.task_categories = await api("/api/task-categories", { method: "POST",
    body: JSON.stringify({ name: f.get("name"), description: f.get("description") }) });
  e.target.reset();
  renderCats();
  refreshTasks();
};
async function loadSettings() {
  renderCats();
  const s = await api("/api/settings");
  const get = (path) => path === "voice.voice_id" ? s.voice_id : path.split(".").reduce((o, k) => o?.[k], s);
  $("#settings-form").innerHTML = FIELDS.map(([p, l]) => `<label class="field">${l}<input name="${p}" value="${esc(get(p) ?? "")}"></label>`).join("") +
    `<label class="switch"><input type="checkbox" name="proactive.enabled" ${s.proactive?.enabled ? "checked" : ""}> Tryb proaktywny</label>
     <label class="switch"><input type="checkbox" name="proactive.reminders.fastest_path" ${s.proactive?.reminders?.fastest_path ? "checked" : ""}> Przy przypomnieniu proponuj najszybszą drogę do zrobienia zadania</label>
     <label class="switch"><input type="checkbox" name="voice.tts_enabled" ${s.voice?.tts_enabled !== false ? "checked" : ""}> Odpowiedzi głosem ElevenLabs (wyłączone = głos przeglądarki, bez kosztów)</label>
     <button class="primary">Zapisz</button>`;
}
$("#settings-form").onsubmit = async (e) => {
  e.preventDefault();
  const patch = {};
  e.target.querySelectorAll("input").forEach((i) => {
    const keys = i.name.split("."), last = keys.pop();
    let v = i.type === "checkbox" ? i.checked : i.value;
    if (i.type !== "checkbox" && v !== "" && !isNaN(v)) v = Number(v);
    keys.reduce((o, k) => (o[k] ||= {}), patch)[last] = v;
  });
  await api("/api/settings", { method: "PUT", body: JSON.stringify(patch) });
  addMsg("system", "Ustawienia zapisane.");
};

// ---------------------------------------------------------------- boot
(async () => {
  await loadStatus();
  connect();
  let saved = null;
  try { saved = localStorage.getItem("view"); } catch { /* private mode */ }
  setView(["tasks", "chat"].includes(saved) ? saved : "brain");
  try { saved = localStorage.getItem("tasksub"); } catch { saved = null; }
  setSub(["kanban", "calendar", "goals"].includes(saved) ? saved : "overview");
  renderCalModes();
  loadChat().catch(() => {});
  refreshLeft();
  loadBrief().catch(() => {});
  loadLastRoute().catch(() => {});
  loadGraph().catch((e) => addMsg("system", `⚠ Mózg 3D: ${e.message}`));
  setInterval(loadStatus, 15000);
  setInterval(loadRoutines, 60e3);                   // "due" changes with the clock
  setInterval(() => view === "tasks" && loadCalendar(), 5 * 60e3);
})();
