// Alfred UI. A left nav of pages: Chat; Przegląd; Planowanie (tasks, calendar, goals); Zdrowie (training, diet);
// Moje rzeczy (products, memory); Alfred's own pages (voice conversation, persona, modules, map, log, settings).
// Every page: subtitles with what Alfred says and a low bar (Alfred's universe - a click opens his 3D network -,
// composer, Jev, session cost).
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
const metaHtml = (meta, detail) => (meta ? `<span class="meta" title="${esc(detail)}">${esc(meta)}</span>` : "");
function addMsg(kind, text, meta = "", detail = "") {
  const el = document.createElement("div");
  el.className = `msg ${kind}`;
  el.innerHTML = esc(text) + metaHtml(meta, detail);
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
  const stars = Array.from({ length: 140 }, (_, i) => {
    const r = Math.pow(Math.random(), 0.75) * R * 0.8;
    return { r, a: (i % 3) * TAU / 3 + r / 8 + rnd(-0.4, 0.4), size: rnd(1, 2.4), hue: rnd(225, 290), tw: rnd(0, TAU) };
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
if ("speechSynthesis" in window) speechSynthesis.getVoices();   // Edge/Chrome load their voices lazily - start now
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
    // the natural (online) voices of Edge / Chrome sound far less robotic than the system default
    const voices = speechSynthesis.getVoices().filter((v) => v.lang.replace("_", "-").startsWith(u.lang.slice(0, 2)));
    const natural = voices.filter((v) => /natural|online|google/i.test(v.name));
    u.voice = natural.find((v) => /marek|ryan|thomas/i.test(v.name)) || natural[0] || voices[0] || null;  // Alfred is a man
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
// Two mic buttons: the low bar (spoken answer) and the chat (written answer in the chat).
let recorder = null, chunks = [], recognition = null;
const micOf = (mode) => $(mode === "chat" ? "#chat-mic" : "#mic");
async function startRec(mode = view === "chat" ? "chat" : "voice") {
  stopSpeaking();
  micOf(mode).classList.add("rec"); mood();
  if (!status.keys.elevenlabs && ("webkitSpeechRecognition" in window || "SpeechRecognition" in window)) {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    recognition = new SR();
    recognition.lang = status.language === "en" ? "en-GB" : "pl-PL";
    recognition.onresult = (e) => (mode === "chat" ? sendChat : sendText)(e.results[0][0].transcript);
    recognition.onend = () => { micOf(mode).classList.remove("rec"); mood(); };
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
    reader.onload = () => ws.send(JSON.stringify({ type: "audio", b64: reader.result.split(",")[1], mime: recorder.mimeType, mode }));
    reader.readAsDataURL(blob);
  };
  recorder.start();
}
function stopRec() {
  document.querySelectorAll(".mic.rec").forEach((b) => b.classList.remove("rec")); mood();
  if (recognition) { recognition.stop(); recognition = null; }
  if (recorder && recorder.state === "recording") recorder.stop();
}
function isRecording() { return Boolean(document.querySelector(".mic.rec")); }
// A letter or the space bar would type into a text field, so there it stays a letter; F-keys, Ctrl, Alt... work everywhere.
const typing = (e) => e.target.closest?.("input, textarea, select") && e.key.length === 1;
$("#mic").onclick = () => (isRecording() ? stopRec() : startRec("voice"));
$("#chat-mic").onclick = () => (isRecording() ? stopRec() : startRec("chat"));

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
function chatMsg(kind, html, meta = "", detail = "") {
  $(".chat-empty")?.remove();
  const el = document.createElement("div");
  el.className = `bubble ${kind}`;
  el.innerHTML = html + metaHtml(meta, detail);
  $("#chat-log").appendChild(el);
  $("#chat-log").scrollTop = 1e9;
  return el;
}
function chatTyping(on) {
  $("#chat-typing")?.remove();
  if (on) chatMsg("alfred typing", "<span class=\"dots\"><i></i><i></i><i></i></span>").id = "chat-typing";
}
const chatAnswer = (text, meta, detail) => chatMsg("alfred", `<div class="md">${renderMd(text, "")}</div>`, meta, detail);
function sendChat(text) {
  if (text.trim()) ws.send(JSON.stringify({ type: "text", text, mode: "chat" }));
}
$("#chat-form").onsubmit = (e) => {
  e.preventDefault();
  sendChat($("#chat-text").value);
  $("#chat-text").value = "";
};
$("#chat-text").onkeydown = (e) => {
  if (e.key === "Enter" && !e.shiftKey && !e.isComposing) { e.preventDefault(); $("#chat-form").requestSubmit(); }
};
let hello = "Cześć";                               // "Cześć, <his name>" once the persona is read
$("#chat-new").onclick = async () => {
  go("chat");
  await api("/api/session/close", { method: "POST" });
  $("#chat-log").innerHTML = `<div class="chat-empty"><h2 class="hello">${esc(hello)}</h2><p>Nowa rozmowa — poprzednia jest zapisana w pamięci.</p></div>`;
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
  Brain3D?.init(await api("/api/graph"), { openPage: openMapPage, openMemory: openMemoryPage });
}
$("#demo").onclick = () => Brain3D?.demo();
$("#alfred").onclick = () => go("brain");             // Alfred on every page leads back to his network

// ---------------------------------------------------------------- events
function onEvent(ev) {
  const d = ev.data || {};
  Brain3D?.event(ev);
  switch (ev.kind) {
    case "transcript":
      said[ev.request_id] = d.text;
      if (!d.confirmation) { thinking = true; mood(); }
      if (d.source === "proactive") { /* only the answer shows, marked "sam" */ }
      else if (d.source === "routine") loadRoutines();
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
      // Shown: the time (+ "rutyna" / "sam" when Alfred spoke first). Model, tokens and cost: a tooltip.
      const meta = ev.ts.slice(11, 16) + ({ routine: " · rutyna", proactive: " · sam" }[d.source] || "");
      const detail = `${d.model || ""} · ${tokens(u)} tok. (in ${u.input || 0} · cache ${u.cache_read || 0}` +
        ` odczyt / ${u.cache_write || 0} zapis · out ${u.output || 0}${u.router ? ` · router ${u.router}` : ""})` +
        (d.cost_usd != null ? ` · ${usd(d.cost_usd)}` : "") + (d.tools?.length ? ` · ${d.tools.join(", ")}` : "");
      addMsg("alfred", d.text, meta, detail);
      loadStatus();                         // session total in the low bar
      if (d.mode === "chat" || chatReq.has(ev.request_id)) { chatTyping(false); chatAnswer(d.text, meta, detail); }
      else { subtitle(d.text, "say", d.source === "user" ? lastSaid : ""); speak(d.text, d.audio_b64, d.language); }
      if (d.source === "routine") showBrief(d.text, ev.ts.slice(11, 16), "rutyna");
      refreshLeft();                        // Alfred may have changed the tasks or the calendar
      if (view === "tasks") refreshDay();
      if (view === "tasks" && $("main").dataset.sub === "diet" && d.tools?.some((t) => t.startsWith("nutrition__"))) loadDiet().catch(warn);
      if (training && d.tools?.some((t) => /^(strava|google-calendar)__/.test(t))) loadTraining().catch(warn);   // a session moved, a workout synced
      break;
    }
    case "error": thinking = false; mood(); addMsg("system", `⚠ ${d.message}`);
      if (chatReq.has(ev.request_id)) { chatTyping(false); chatMsg("system", `⚠ ${esc(d.message)}`); } subtitle(`⚠ ${d.message}`, "system"); loadRoutines(); break;
    case "session_closed": loadBriefing(); break;
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
    pill("Claude · subskrypcja", status.keys.anthropic, status.claude?.detail || "") +
    pill("Jev", status.keys.jev, "bez klucza tarcza nie przepuści żadnej prośby - Alfred nic nie zrobi") +
    pill("ElevenLabs", status.keys.elevenlabs, "bez klucza: głos przeglądarki") +
    status.mcp.map((s) => s.status === "disabled" ? "" : pill(s.name, s.status === "ready", s.error || "")).join("");
  const u = status.session?.usage || {};
  // Split per service: Claude (subscription = API-equivalent, not a bill), Jev and ElevenLabs (real money).
  const claudeTok = ["input", "output", "cache_read", "cache_write"].reduce((s, k) => s + (u[k] || 0), 0);
  const paid = (u.jev_usd || 0) + (u.elevenlabs_usd || 0);
  $("#session-cost").textContent = cash(paid);
  $("#session-cost").title = [
    `Sesja: ${status.session?.turns || 0} tur`,
    `Claude: ${num(claudeTok)} tok. · ${usd(u.cost_usd || 0)} — subskrypcja: równowartość API, nie rachunek (zużywa limit planu)`,
    `Jev: ${num(u.jev || 0)} tok. · ${cash(u.jev_usd)} (płatne tylko wejście)`,
    `ElevenLabs: ${num(u.tts_chars || 0)} znaków głosu + ${num(Math.round(u.stt_s || 0))} s rozpoznawania mowy · ${cash(u.elevenlabs_usd)}`,
    `Płacisz: Jev + ElevenLabs = ${cash(paid)} (ceny: config/brain.yaml → prices)`,
  ].join("\n");
}
const cash = (v) => `$${(v || 0).toFixed(4)}`;
const tokens = (u) => ["input", "output", "cache_read", "cache_write", "router", "jev"].reduce((s, k) => s + (u[k] || 0), 0);
const num = (n) => Math.round(+n || 0).toLocaleString("pl-PL");
// Subscription: no per-token bill, the figure is what the same call would cost on the API.
const usd = (v) => `≈$${v.toFixed(4)}`;

// --------------------------------------------------------------------- views
// One nav (on the left). data-go = "brain" | "chat" | "tasks:<page>" (they share main[data-sub]) | "panel:<page>" (one tab of #drawer).
let view = "brain";
function setView(v) {
  view = v;
  $("main").dataset.view = v;
  document.body.dataset.view = v;
  if (v === "chat") $("#chat-text").focus();
  if (v === "tasks") refreshDay();
}
const navButtons = [...document.querySelectorAll("#nav [data-go]")];
function go(target) {
  const [v, page] = target.split(":");
  setView(v);
  if (v === "tasks") setSub(page);
  if (v === "panel") openTab(page);
  const button = navButtons.find((b) => b.dataset.go === target);
  navButtons.forEach((b) => b.classList.toggle("active", b === button));
  $("#page-title").textContent = button?.querySelector(".lbl-t").textContent || "";
  document.body.classList.remove("nav-open");
  try { localStorage.setItem("page", target); } catch { /* private mode */ }
}
navButtons.forEach((b) => (b.onclick = () => go(b.dataset.go)));
// the menu button: icons only on a wide screen, the nav slides in on a narrow one
$("#menu").onclick = () => document.body.classList.toggle(innerWidth < 900 ? "nav-open" : "nav-mini");

// Tasks tabs: Przegląd (board + small calendar + panels) or Kanban / Kalendarz over the whole page.
function setSub(s) {
  $("main").dataset.sub = s;
  delete $("#calendar").dataset.scrolled;             // taller hours on the full page: scroll to "now" again
  renderCalendar();
  if (s === "goals") loadGoals().catch(warn);
  if (s === "training") loadTraining().catch(warn);
  if (s === "diet") loadDiet().catch(warn);
  if (s === "products") loadProducts().catch(warn);
}

// Produkty tab: an editable list - every change saves the whole list (a memory page Alfred finds with memory_search)
let products = [];
const isLink = (u) => /^https?:\/\/\S+$/.test(u || "");
async function loadProducts() {
  try { products = await api("/api/products"); } catch (e) { return productsError("nie udało się wczytać listy", e); }
  renderProducts();
}
// A failed save must show here, not only in the Rozmowa tab - the rows exist only on this page until it works
function productsError(what, e) {
  $("#products-saved").className = "bad";
  $("#products-saved").textContent = `⚠ ${what} (${e.message.slice(0, 80)}) — zrestartuj Alfreda i odśwież stronę, ` +
    "inaczej wpisane produkty znikną";
}
function setLink(row, url) {
  const a = row.querySelector(".open");
  a.classList.toggle("hidden", !isLink(url));
  a.href = isLink(url) ? url : "#";
}
function renderProducts() {
  $("#products").innerHTML = products.map((p, i) => `<div class="product" data-i="${i}">
    <input name="name" value="${esc(p.name)}" placeholder="Nazwa, np. Odżywka białkowa" aria-label="Nazwa">
    <input name="url" type="url" value="${esc(p.url)}" placeholder="https://…" aria-label="Link">
    <input name="grams" type="number" min="1" max="5000" step="any" value="${p.grams ?? ""}" placeholder="porcja g" aria-label="Zwykła porcja w gramach" title="Zwykła porcja w gramach — gdy powiesz inną gramaturę, liczy się ta powiedziana">
    <input name="note" value="${esc(p.note)}" placeholder="Notatka: smak, rozmiar, co ile kupuję" aria-label="Notatka">
    <span class="label muted" title="Etykieta na 100 g (z linku) — z niej Alfred liczy ten produkt">${p.kcal != null
      ? `${p.kcal} kcal · B ${p.protein_g} · W ${p.carbs_g} · T ${p.fat_g} /100 g` : "brak etykiety"}</span>
    <a class="open" target="_blank" rel="noopener" title="Otwórz link">↗</a>
    <button class="del" type="button" title="Usuń">✕</button></div>`).join("")
    || '<div class="sub">Brak produktów — dodaj pierwszy przyciskiem „+ Dodaj produkt”.</div>';
  $("#products").querySelectorAll(".product").forEach((row) => {
    const p = products[row.dataset.i];
    setLink(row, p.url);
    row.querySelectorAll("input").forEach((inp) => (inp.onchange = () => {
      p[inp.name] = inp.name === "grams" ? (+inp.value > 0 ? +inp.value : null) : inp.value.trim();
      if (inp.name === "url") setLink(row, p.url);
      saveProducts();
    }));
    row.querySelector(".del").onclick = () => { products.splice(+row.dataset.i, 1); renderProducts(); saveProducts(); };
  });
}
async function saveProducts() {
  const ready = products.filter((p) => p.name && isLink(p.url));     // half-typed rows stay on screen until complete
  try {
    await api("/api/products", { method: "PUT", body: JSON.stringify(ready) });
    $("#products-saved").className = "muted";
    $("#products-saved").textContent = `zapisane ${hhmm(new Date())}` +
      (ready.length < products.length ? " · uzupełnij nazwę i link (https://…), żeby zapisać resztę" : "");
  } catch (e) { productsError("NIE zapisano", e); }
}
$("#product-add").onclick = () => {
  products.push({ name: "", url: "", note: "" });
  renderProducts();
  $("#products .product:last-child input").focus();
};

// Dieta tab: today's macros against the goals (raised by today's training), what you said -> how it was saved, 7 days
const MEAL_PL = { breakfast: "śniadanie", lunch: "obiad", dinner: "kolacja", snack: "przekąska" };
const LOG_PL = { log_meal: "posiłek", log_weight: "waga", log_body_measurement: "pomiar", log_water: "woda" };
const MACRO_COLOR = { calories: "var(--blue)", protein_g: "var(--green)", carbs_g: "var(--cyan)", fat_g: "var(--purple)", fiber_g: "var(--violet)", water_ml: "var(--cyan)" };
const left = (r) => (r.goal ? (r.goal >= r.eaten ? `zostało ${num(r.goal - r.eaten)} ${r.unit}` : `${num(r.eaten - r.goal)} ${r.unit} ponad cel`) : "brak celu — ustal go z Alfredem");
async function loadDiet() {
  $("#dt-status").textContent = "ładuję…";
  renderDiet(await api("/api/diet"));
}
function renderDiet(d) {
  $("#dt-status").textContent = `odświeżone ${hhmm(new Date())}`;
  const note = d.status === "ready" ? (d.strava?.error ? `Strava: ${d.strava.error} — kalorie z treningów niedostępne` : "")
    : `Nutrition MCP: ${d.error || d.status}. Zaloguj się: w terminalu „uv run alfred mcp-login nutrition”, potem zrestartuj Alfreda.`;
  $("#dt-note").textContent = note;
  $("#dt-note").classList.toggle("hidden", !note);
  const b = d.balance;
  $(".diet-top").classList.toggle("hidden", !b);
  if (b) {
    const kc = b.rows.find((r) => r.key === "calories"), p = kc.goal ? kc.eaten / kc.goal : 0;
    $("#dt-ring").style.setProperty("--p", Math.min(100, p * 100));
    $("#dt-ring").classList.toggle("over", p > 1);
    $("#dt-ring").innerHTML = `<div><b>${num(kc.eaten)}</b><span>${kc.goal ? `z ${num(kc.goal)} kcal` : "kcal dziś"}</span><small>${esc(left(kc))}</small></div>`;
    $("#dt-sub").textContent = b.extra_kcal ? `cel ${num(kc.base_goal)} + ${num(b.extra_kcal)} kcal za dzisiejszy trening${d.goals_synced ? " · zapisane w Nutrition MCP" : ""}`
      : b.training_kcal ? `trening dziś ~${num(b.training_kcal)} kcal` : "";
    $("#dt-macros").innerHTML = b.rows.filter((r) => r.key !== "calories").map((r) => {
      const q = r.goal ? r.eaten / r.goal : 0;
      return `<div class="macro" style="--c:${MACRO_COLOR[r.key]}"><div class="row between"><span>${esc(r.label)}</span>
        <span><b>${num(r.eaten)}</b><span class="muted">${r.goal ? ` / ${num(r.goal)}` : ""} ${r.unit}</span></span></div>
        <div class="bar-lg${q > 1 ? " over" : ""}${r.goal ? "" : " nogoal"}" role="progressbar" aria-label="${esc(r.label)}" aria-valuenow="${r.eaten}" aria-valuemax="${r.goal || 0}"><i style="width:${Math.min(100, q * 100)}%"></i></div>
        <small class="muted">${esc(left(r))}</small></div>`;
    }).join("");
    const wt = b.weight;
    $("#dt-stats").innerHTML = [
      tile("purple", wt?.current != null ? `${wt.current} ${wt.unit}` : "—", "waga", wt?.target != null ? `cel ${wt.target} ${wt.unit}` : "cel wagowy: powiedz Alfredowi"),
      tile("blue", b.meal_count, "posiłków dziś"),
      tile("green", b.training_kcal ? `~${num(b.training_kcal)}` : "0", "kcal spalone na treningu", (d.workouts || []).map((a) => a.name).join(", ") || "dziś bez treningu w Stravie"),
    ].join("");
  }
  const meals = d.meals || [];
  $("#dt-meals-sum").textContent = meals.length ? `· ${meals.length} · ${num(meals.reduce((s, m) => s + (m.calories || 0), 0))} kcal — kliknij posiłek, żeby zobaczyć produkty` : "";
  renderDiscipline(d.discipline);
  $("#dt-meals").innerHTML = meals.map(mealCard).join("")
    || `<div class="sub">${d.status === "ready" ? "Dziś jeszcze nic nie zapisano." : "Posiłki pojawią się po połączeniu z Nutrition MCP."}</div>`;
  $("#dt-meals").querySelectorAll("[data-split]").forEach((b) => (b.onclick = () => {
    splitMeal(d.meals.find((m) => m.id === b.dataset.split));
    b.disabled = true;
    b.textContent = "Alfred liczy — potwierdź „tak”, potem ↻";
  }));
  $("#dt-log").innerHTML = d.log.map(feedCard).join("") || '<div class="sub">Powiedz Alfredowi, co zjadłeś albo ile ważysz — tu zobaczysz, jak to zrozumiał i zapisał.</div>';
  const days = d.week?.days || [], goal = d.week?.goals?.calories || Math.max(1, ...days.map((x) => x.calories));
  $("#dt-week").innerHTML = days.map((x) => `<div class="tr-row"><span>${esc(dm(x.date))}</span>${meter(x.calories, goal)}
    <span class="sub">${num(x.calories)} kcal · B ${num(x.protein_g)} · W ${num(x.carbs_g)} · T ${num(x.fat_g)} g</span></div>`).join("");
}
// Per product: what each one gave (Claude writes it into the meal's notes; the backend reads the lines)
const mealItems = (items) => `<div class="items"><div class="sub">Produkty (${items.length}) — kcal i makro każdego</div>${itemsTable(items)}</div>`;
function itemsTable(items) {
  const g = (v) => (v == null ? "—" : num(Math.round(v * 10) / 10));
  const sum = (k) => items.reduce((s, i) => s + (i[k] || 0), 0);
  const row = (i) => `<tr><td>${esc(i.name)}</td><td>${i.approx ? "~" : ""}${g(i.grams)} g</td><td><b>${g(i.kcal)}</b></td>
    <td>${g(i.protein_g)}</td><td>${g(i.carbs_g)}</td><td>${g(i.fat_g)}</td></tr>`;
  return `<table class="items-table"><thead><tr><th>Produkt</th><th>Ilość</th><th>kcal</th><th>B g</th><th>W g</th><th>T g</th></tr></thead>
    <tbody>${items.map(row).join("")}</tbody>
    <tfoot><tr><td>Razem</td><td>${g(sum("grams"))} g</td><td><b>${g(sum("kcal"))}</b></td><td>${g(sum("protein_g"))}</td>
    <td>${g(sum("carbs_g"))}</td><td>${g(sum("fat_g"))}</td></tr></tfoot></table>`;
}
// One of today's meals from Nutrition MCP: totals, then each product - or a button that asks Alfred to split it
function mealCard(m) {
  const n = (v) => (v == null ? "—" : num(v));
  return `<div class="meal"><div class="meal-head"><span><b>${esc((m.time || "").slice(11, 16))}</b> · ${esc(MEAL_PL[m.type] || m.type || "")}</span>
    <span class="nowrap"><b>${n(m.calories)} kcal</b> <span class="muted">· B ${n(m.protein_g)} · W ${n(m.carbs_g)} · T ${n(m.fat_g)} g</span></span></div>
    <div class="what">${esc(m.description)}</div>
    ${m.items.length ? itemsTable(m.items) : `<div class="row"><span class="sub">bez rozbicia na produkty</span>
      <button class="mini" data-split="${esc(m.id)}" title="Alfred policzy kcal i makro każdego produktu i dopisze to do notatki posiłku">Rozbij na produkty</button></div>`}</div>`;
}
// Discipline over 30 days: tiles, one bar per day (kcal against the goal, coloured by how the day went), weekly scores
const DISC_PL = { hit: "na celu", partial: "połowicznie", miss: "poza celem", empty: "nic nie zapisano", today: "dziś — w toku" };
function renderDiscipline(x) {
  if (!x) { $("#dt-disc").innerHTML = '<div class="sub">Analiza pojawi się po połączeniu z Nutrition MCP.</div>'; return; }
  const pct = (v) => (v == null ? "—" : `${Math.round(v * 100)}%`), kg = x.goals.calories;
  const top = Math.max(kg ? kg * 1.3 : 0, ...x.days.map((r) => r.calories), 1);
  $("#dt-disc").innerHTML = `<div class="stats wide">${[
      tile(x.score >= 0.7 ? "green" : x.score >= 0.4 ? "purple" : "err", pct(x.score), "dyscyplina", `${x.total_days} zakończonych dni`),
      tile("blue", `${x.logged_days}/${x.total_days}`, "dni zapisane", "dzień bez posiłków = 0"),
      tile("green", pct(x.kcal_on_target), "kcal na celu", kg ? `±10% od ${num(kg)} kcal` : "brak celu kcal"),
      tile("purple", pct(x.protein_on_target), "białko na celu", x.goals.protein_g ? `≥ 90% z ${num(x.goals.protein_g)} g` : "brak celu białka"),
      tile(x.streak ? "green" : "blue", `${x.streak} 🔥`, "dni z rzędu na celu", `rekord: ${x.best_streak}`),
      tile("blue", x.avg_kcal == null ? "—" : num(x.avg_kcal), "średnio kcal / dzień", kg ? `cel ${num(kg)}` : ""),
    ].join("")}</div>
    ${columns(x.days.map((r) => ({ h: (r.calories / top) * 100, value: r.calories ? `${Math.round(r.calories / 100) / 10}k` : "",
      label: r.date.slice(8), cls: r.status, title: `${r.date}: ${DISC_PL[r.status]} · ${num(r.calories)} kcal · białko ${num(r.protein_g)} g` })),
      kg ? (kg / top) * 100 : 0, kg ? `cel ${num(kg)}` : "")}
    <div class="disc-legend">${["hit", "partial", "miss", "empty", "today"].map((s) => `<span class="${s}"><i></i>${DISC_PL[s]}</span>`).join("")}</div>
    <h4>Tydzień po tygodniu</h4><div class="tr-list">${x.weeks.map((w) => `<div class="tr-row"><span>od ${esc(dm(w.start))}</span>
      ${meter(w.score || 0, 1)}<span class="sub">${pct(w.score)} · zapisane ${w.logged}/${w.days} dni</span></div>`).join("")}</div>`;
}
// The split goes through Alfred (chat mode): he computes each product and writes the lines into the meal's notes
function splitMeal(m) {
  sendChat(`Rozbij posiłek ${m.id} na produkty (${(m.time || "").slice(11, 16)}, „${m.description}”, razem ${m.calories} kcal, ` +
    `B ${m.protein_g} g, W ${m.carbs_g} g, T ${m.fat_g} g): każdy produkt z kcal i makro w formacie z zasad, dopisz do notatki ` +
    "tego posiłku przez update_meal, sum nie zmieniaj.");
}
function feedCard(e) {
  const a = e.input || {};
  const what = e.tool === "log_meal" ? [a.description, a.calories != null && `${num(a.calories)} kcal`, a.protein_g != null && `B ${num(a.protein_g)} g`,
    a.carbs_g != null && `W ${num(a.carbs_g)} g`, a.fat_g != null && `T ${num(a.fat_g)} g`]
    : e.tool === "log_weight" ? [`${a.weight} ${a.unit || "kg"}`, a.notes]
    : e.tool === "log_body_measurement" ? [`${a.kind} ${a.value} ${a.unit || "cm"}`, a.notes]
    : Object.entries(a).map(([k, v]) => `${k}: ${v}`);
  const jev = a.meal_type ? `<span class="chip ${e.source === "jev" ? "jev" : ""}" title="${e.source === "jev" ? "Typ posiłku wybrał Jev" : "Jev nie odpowiedział — wybrał Claude"}">${e.source === "jev" ? "Jev" : "Claude"}: ${esc(MEAL_PL[a.meal_type] || a.meal_type)}</span>` : "";
  const short = { calories: "kcal", protein_g: "B", carbs_g: "W", fat_g: "T" };
  const bal = e.balance ? `<div class="sub">po posiłku: ${Object.keys(short).filter((k) => e.balance[k]).map((k) => {
    const [x, g] = e.balance[k]; return `${short[k]} ${num(x)}${g ? `/${num(g)}` : ""}`; }).join(" · ")}</div>` : "";
  return `<div class="feed"><div class="row between"><span class="said">${e.said ? `„${esc(e.said)}”` : '<span class="muted">(rutyna)</span>'}</span>
    <span class="muted">${esc(dm(e.ts))} ${esc(e.ts.slice(11, 16))}</span></div>
    <div class="flow-line"><span class="muted">→</span>${jev}<span class="chip">${esc(LOG_PL[e.tool] || e.tool)}</span>
    <span class="${e.ok === false ? "bad" : "ok"}">${e.ok === false ? "✗ błąd zapisu" : e.ok ? "✓ zapisane w Nutrition MCP" : "…"}</span></div>
    <div class="what">${what.filter(Boolean).map(esc).join(" · ")}</div>${bal}${e.items?.length ? mealItems(e.items) : ""}</div>`;
}
$("#dt-refresh").onclick = () => loadDiet().catch(warn);

// Treningi tab: the triathlon plan and how it goes (Strava), the work week, diet and weight (Nutrition MCP)
const SPORT_PL = { swim: ["🏊", "Pływanie"], bike: ["🚴", "Rower"], run: ["🏃", "Bieg"], strength: ["🏋️", "Siła"], other: ["⏱️", "Inne"] };
const DIST_PL = { sprint: "sprint", olympic: "olimpijski", half: "1/2 Ironman", full: "Ironman" };
const hrs = (x) => `${(+x || 0).toFixed(1).replace(".", ",")} h`;
const dm = (iso) => new Date(`${iso.slice(0, 10)}T12:00`).toLocaleDateString("pl-PL", { weekday: "short", day: "numeric", month: "short" });
const dur = (s) => `${Math.floor(s / 3600)}:${String(Math.floor((s % 3600) / 60)).padStart(2, "0")}`;
const sportName = (s) => `${(SPORT_PL[s] || SPORT_PL.other)[0]} ${esc((SPORT_PL[s] || [, s])[1])}`;
const meter = (done, target) => `<div class="meter${target && done > target ? " over" : ""}"><i style="width:${target ? Math.min(100, (done / target) * 100) : 0}%"></i></div>`;
const tile = (cls, big, label, small = "") => `<div class="tile ${cls}"><b>${esc(big)}</b><span>${esc(label)}</span><small title="${esc(small)}">${esc(small)}</small></div>`;
let training = null;
async function loadTraining() {
  $("#tr-status").textContent = "ładuję…";
  renderTraining((training = await api("/api/training")));
}
const SPORT_COLOR = { swim: "var(--cyan)", bike: "var(--blue)", run: "var(--green)", strength: "var(--purple)", other: "var(--violet)" };
// vertical bars: items {h: 0-100, value, label, cls, title}; line = where the goal sits (0-100)
const columns = (items, line, lineLabel) => `<div class="cols" style="--line:${Math.min(100, line)}">${items.map((c) => `<div class="bar-col ${c.cls || ""}" title="${esc(c.title || "")}">
  <span class="v">${esc(c.value)}</span><div class="plot"><i style="height:${Math.max(3, Math.min(100, c.h))}%"></i></div><span class="l">${esc(c.label)}</span></div>`).join("")}
  ${line ? `<div class="goal-line" data-label="${esc(lineLabel)}"></div>` : ""}</div>`;
// ---- Treningi: the week as 7 days (calendar sessions + Strava), the chosen day in full, the week's progress ----
let trDay = null;                                          // the day open under the week (ISO), today by default
const sportOf = (s) => SPORT_PL[s] || SPORT_PL.other;
const colorOf = (s) => SPORT_COLOR[s] || SPORT_COLOR.other;
const plusDays = (iso, n) => { const d = new Date(`${iso}T00:00Z`); d.setUTCDate(d.getUTCDate() + n); return d.toISOString().slice(0, 10); };
const mmss = (s) => `${Math.floor(Math.round(s) / 60)}:${String(Math.round(s) % 60).padStart(2, "0")}`;
const actKey = (a) => a.id ?? a.start_date_local;
const TR_STATUS = { done: "✓ zrobione", missed: "✗ brak w Stravie", planned: "zaplanowane" };
// how to do a session of this kind - modules/training/prompt.md in one line
const howTo = (kind, hr) => ({
  spokojnie: `Z1–2, średnie tętno do ${hr} — możesz swobodnie rozmawiać.`,
  technika: `Ćwiczenia techniczne i czysty ruch, tętno do ${hr}.`,
  jakość: "Odcinki w progu (RPE 7–8) między spokojną rozgrzewką a schłodzeniem.",
  brick: "Rower, a od razu po nim bieg — pierwsze minuty biegu luźno.",
  siła: "Najpierw technika, potem ciężar (RPE 7–8); nie dzień przed długim biegiem.",
  mobilność: "Spokojnie i bez bólu.",
}[kind] || "");
// a Strava workout: time, distance, pace (run /km, swim /100 m, bike km/h), heart rate, kcal
function actChips(a) {
  const km = (a.distance || 0) / 1000, s = a.moving_time || 0;
  const pace = !km || !s ? "" : a.sport === "run" ? `${mmss(s / km)} /km` : a.sport === "swim" ? `${mmss(s / (km * 10))} /100 m`
    : a.sport === "bike" ? `${(km / (s / 3600)).toFixed(1).replace(".", ",")} km/h` : "";
  return `<div class="chips start"><span class="chip">⏱ ${dur(s)}</span>${km ? `<span class="chip">📏 ${km.toFixed(1).replace(".", ",")} km</span>` : ""}${pace ? `<span class="chip">${pace}</span>` : ""}${a.average_heartrate ? `<span class="chip" title="średnie tętno">♥ ${Math.round(a.average_heartrate)}</span>` : ""}${a.kcal ? `<span class="chip" title="szacunek: ${esc(a.kcal_source)}">🔥 ~${num(a.kcal)} kcal</span>` : ""}</div>`;
}
// one session in full: when, how, Alfred's description from the calendar, what Strava recorded, what to do with it
function sessionCard(x, hr) {
  const at = `${dm(x.date || "")}${x.time ? ` ${x.time}` : ""}`;
  const ask = x.status === "planned" ? ["Przełóż z Alfredem", `Przełóż trening „${x.name}” z ${at} — zaproponuj inny termin w kalendarzu.`]
    : x.status === "missed" ? ["Nadrobić?", `Nie zrobiłem treningu „${x.name}” z ${at} — czy i kiedy go nadrobić w tym tygodniu?`] : null;
  return `<article class="wo ${x.status || ""}" style="--c:${colorOf(x.sport)}">
    <header><span class="icon">${sportOf(x.sport)[0]}</span>
      <div><div class="title">${esc(x.name)}</div><div class="sub">${x.time ? `${esc(x.time)}${x.end ? `–${esc(x.end)}` : ""} · ` : ""}${x.minutes} min · <span class="kind ${esc(x.kind)}">${esc(x.kind)}</span></div></div>
      ${x.status ? `<span class="st ${x.status}">${TR_STATUS[x.status]}</span>` : ""}</header>
    <div class="how">${esc(howTo(x.kind, hr))}</div>
    ${x.note ? `<div class="note">${esc(x.note)}</div>` : ""}
    ${x.activity ? `<div class="did"><span class="muted">Strava: ${esc(x.activity.name)}</span>${actChips(x.activity)}</div>` : ""}
    ${x.link || ask ? `<div class="actions">${x.link ? `<a href="${esc(x.link)}" target="_blank" rel="noopener">Otwórz w kalendarzu ↗</a>` : ""}
      ${ask ? `<button class="mini" data-ask="${esc(ask[1])}">${ask[0]}</button>` : ""}</div>` : ""}
  </article>`;
}
function renderWeek(t) {
  const days = [...Array(7)].map((_, i) => plusDays(t.weeks[0].start, i)), hr = t.plan.easy_hr_max;
  if (!days.includes(trDay)) trDay = days.includes(t.today) ? t.today : days[0];
  const used = new Set(t.planned.filter((x) => x.activity).map((x) => actKey(x.activity)));
  const extra = t.activities.filter((a) => days.includes(a.start_date_local.slice(0, 10)) && !used.has(actKey(a)));
  const on = (day) => [t.planned.filter((x) => x.date === day), extra.filter((a) => a.start_date_local.startsWith(day))];
  $("#tr-week").innerHTML = days.map((day) => {
    const [ss, ex] = on(day);
    return `<button class="tr-day${day === t.today ? " today" : ""}${day === trDay ? " sel" : ""}${day < t.today ? " past" : ""}" data-day="${day}">
      <span class="d">${esc(dm(day).split(",")[0])} <b>${+day.slice(8)}</b></span>
      ${ss.map((x) => `<span class="wchip ${x.status}" style="--c:${colorOf(x.sport)}" title="${esc(x.name)} · ${TR_STATUS[x.status]}">${sportOf(x.sport)[0]} ${x.minutes}′</span>`).join("")}
      ${ex.map((a) => `<span class="wchip extra" style="--c:${colorOf(a.sport)}" title="poza planem: ${esc(a.name)}">${sportOf(a.sport)[0]} ${Math.round((a.moving_time || 0) / 60)}′</span>`).join("")}
      ${ss.length + ex.length ? "" : '<span class="free">wolne</span>'}</button>`;
  }).join("");
  const [ss, ex] = on(trDay), mins = ss.reduce((s, x) => s + x.minutes, 0);
  const label = trDay === t.today ? "Dziś · " : trDay === plusDays(t.today, 1) ? "Jutro · " : "";
  const extras = ex.map((a) => `<article class="wo extra" style="--c:${colorOf(a.sport)}"><header><span class="icon">${sportOf(a.sport)[0]}</span>
    <div><div class="title">${esc(a.name)}</div><div class="sub">${esc(a.start_date_local.slice(11, 16))} · poza planem</div></div></header>${actChips(a)}</article>`).join("");
  let body;
  if (!t.planned.length) {                                 // the week is not in the calendar yet: the phase's template
    const tw = t.roadmap[0]?.this_week;
    body = tw?.sessions.length ? `<div class="tr-empty"><span>Ten tydzień nie jest jeszcze rozpisany w kalendarzu — szablon fazy <b>${esc(tw.phase_pl)}</b>:</span>
      <button class="primary" data-ask="Rozpisz mi treningi na ten tydzień w kalendarzu według planu (training_status) — uwzględnij pracę i moją porę treningu.">Rozpisz tydzień w kalendarzu</button></div>
      ${tw.sessions.map((x) => sessionCard(x, hr)).join("")}`
      : '<div class="tr-empty">Ustaw datę zawodów w „Zmień plan” na dole, żeby zobaczyć plan na ten tydzień.</div>';
  } else if (ss.length) body = ss.map((x) => sessionCard(x, hr)).join("");
  else {
    const next = t.planned.find((x) => x.date > trDay && x.status === "planned");
    body = `<div class="tr-empty">${ex.length ? "Bez planu na ten dzień." : "Dzień wolny — regeneracja, spacer, sen."}${next ? `<span>Następny trening: <b>${esc(next.name)}</b> · ${esc(dm(next.date))}${next.time ? ` ${esc(next.time)}` : ""}</span>` : ""}</div>`;
  }
  $("#tr-detail").innerHTML = `<header><h3>${label}${esc(new Date(`${trDay}T12:00`).toLocaleDateString("pl-PL", { weekday: "long", day: "numeric", month: "long" }))}</h3>
    <span class="muted">${ss.length ? `${ss.length} ${ss.length === 1 ? "trening" : ss.length < 5 ? "treningi" : "treningów"} · ${mins} min` : ""}</span></header>${body}${extras}`;
}
function renderTraining(t) {
  const w = t.weeks[0], r = t.race;
  $("#tr-status").textContent = `odświeżone ${hhmm(new Date())}`;
  $("#tr-note").textContent = t.strava.error ? `Strava: ${t.strava.error}` : "";
  $("#tr-note").classList.toggle("hidden", !t.strava.error);
  const when = r.date ? new Date(`${r.date}T12:00`).toLocaleDateString("pl-PL", { day: "numeric", month: "long", year: "numeric" }) : "";
  $("#tr-top").innerHTML = `<div><div class="race">🏁 ${esc(r.name || DIST_PL[r.distance] || "Zawody")}</div>
    <div class="muted">${r.date ? `${esc(when)} · faza <b>${esc(w.phase_pl)}</b> · objętość ${Math.round(w.volume * 100)}% planu` : "Ustaw datę zawodów w „Zmień plan” na dole"}</div></div>
    ${r.date ? `<div class="count"><b>${r.days_to}</b> dni do startu</div>` : ""}`;
  const total = t.timeline.reduce((s, x) => s + x.days, 0);
  $("#tr-timeline").innerHTML = t.timeline.map((x, i) => `<span class="${x.phase}${i === 0 ? " now" : ""}" style="flex:${x.days}"
    title="${esc(x.phase_pl)} od ${esc(x.start)} · ${Math.round(x.days / 7)} tyg.">${x.days / total > 0.08 ? `${esc(x.phase_pl)} · ${Math.round(x.days / 7)} tyg` : ""}</span>`).join("");
  renderWeek(t);
  const work = t.work, steps = t.steps.days, today = steps[steps.length - 1].steps, goal = t.steps.goal;
  $("#tr-prog").innerHTML = `<div class="row between"><span><span class="big">${w.pct ?? 0}%</span> tygodnia · ${hrs(w.done_h)} z ${hrs(w.target_h)}</span>
    <span class="muted">${w.source === "calendar" ? "cel z kalendarza" : "cel z planu"}${w.target_h > w.done_h ? ` · zostało ${hrs(w.target_h - w.done_h)}` : " · zrobione 🎉"}</span></div>
    ${Object.entries(w.sports).map(([s, v]) => `<div class="tr-sport" style="--c:${colorOf(s)}"><span>${sportName(s)}</span>
      <div class="tr-bar"><i style="width:${v.target_h ? Math.min(100, (v.done_h / v.target_h) * 100) : 0}%"></i></div>
      <span class="muted">${v.done_sessions}/${v.target_sessions} · ${hrs(v.done_h)} z ${hrs(v.target_h)}</span></div>`).join("")}
    <div class="tr-facts"><span title="wg średniego tętna treningów">80/20: <b>${w.easy_share == null ? "—" : `${Math.round(w.easy_share * 100)}%`}</b> spokojnie (cel ${Math.round(t.easy_target * 100)}%)</span>
      <span title="${t.weight_kg ? `szacunek dla ${t.weight_kg} kg` : "podaj wagę, żeby liczyć kcal"}">🔥 <b>~${num(w.kcal)}</b> kcal</span>
      ${w.other_h ? `<span>poza planem <b>${hrs(w.other_h)}</b></span>` : ""}
      <span title="${today == null ? "powiedz Alfredowi, ile kroków zrobiłeś" : ""}">👣 <b>${today == null ? "—" : num(today)}</b> / ${num(goal)} kroków dziś</span>
      <span>💼 <b>${hrs(work.meeting_h)}</b> spotkań · ${work.work_tasks_due} zadań z terminem</span></div>
    ${work.busy ? `<div class="tr-warn">🧠 ${esc(work.advice)}</div>` : ""}`;
  const maxSteps = Math.max(goal * 1.2, ...steps.map((d) => d.steps || 0));
  $("#tr-steps").innerHTML = columns(steps.map((d) => ({ h: ((d.steps || 0) / maxSteps) * 100, value: d.steps == null ? "—" : `${Math.round(d.steps / 100) / 10}k`,
    label: dm(d.date).split(",")[0], cls: d.steps == null ? "empty" : d.steps >= goal ? "hit" : "", title: `${d.date}: ${d.steps ?? "brak"} kroków` })),
    (goal / maxSteps) * 100, `cel ${num(goal)}`);
  $("#tr-weeks").innerHTML = columns([...t.weeks].reverse().map((x) => ({ h: ((x.pct || 0) / 130) * 100, value: `${x.pct ?? 0}%`,
    label: dm(x.start).split(",")[1] || x.start.slice(5), cls: (x.pct || 0) >= 100 ? "hit" : x.done_h ? "" : "empty",
    title: `tydzień od ${x.start} · ${x.phase_pl} · ${x.done_h} z ${x.target_h} h` })), (100 / 130) * 100, "plan");
  $("#tr-acts").innerHTML = t.activities.map((a) => `<div class="act" style="--c:${SPORT_COLOR[a.sport] || SPORT_COLOR.other}">
    <span class="icon">${(SPORT_PL[a.sport] || SPORT_PL.other)[0]}</span>
    <div><div class="name">${esc(a.name)}</div><div class="sub">${esc(dm(a.start_date_local))} · ${esc(a.start_date_local.slice(11, 16))}</div></div>
    <div class="chips"><span class="chip">⏱ ${dur(a.moving_time || 0)}</span>${a.distance ? `<span class="chip">📏 ${(a.distance / 1000).toFixed(1).replace(".", ",")} km</span>` : ""}
    ${a.average_heartrate ? `<span class="chip" title="średnie tętno">♥ ${Math.round(a.average_heartrate)}</span>` : ""}${a.kcal ? `<span class="chip" title="szacunek: ${esc(a.kcal_source)}">🔥 ~${num(a.kcal)} kcal</span>` : ""}</div></div>`).join("")
    || '<div class="sub">Brak treningów z ostatnich 14 dni — czas ruszyć! 🏃</div>';
  const f = $("#tr-plan");
  if (f.contains(document.activeElement)) return;            // do not overwrite what is being typed
  f.elements.race_name.value = r.name || "";
  f.elements.race_date.value = r.date || "";
  f.elements.distance.value = r.distance || "half";
  f.elements.easy_hr_max.value = t.plan.easy_hr_max;
  f.elements.steps_goal.value = t.plan.steps_goal;
  $("#tr-weekly").innerHTML = Object.entries(t.plan.weekly).map(([s, v]) => `<label class="field">${sportName(s)} — jednostki i godziny w tygodniu
    <span class="row"><input name="${esc(s)}.sessions" type="number" min="0" max="14" value="${+v.sessions}" aria-label="jednostki">
    <input name="${esc(s)}.hours" type="number" min="0" max="40" step="0.1" value="${+v.hours}" aria-label="godziny"> h</span></label>`).join("");
}
$("#tr-refresh").onclick = () => loadTraining().catch(warn);
$("#tr-week").onclick = (e) => { const b = e.target.closest("[data-day]"); if (b && training) { trDay = b.dataset.day; renderWeek(training); } };
// a session's button asks Alfred in the Chat (move it, make it up, plan the week)
$("#tr-detail").onclick = (e) => { const b = e.target.closest("[data-ask]"); if (b) { go("chat"); sendChat(b.dataset.ask); } };
// "I want to change something": a fixed opening so Jev reads it as a plan change; the proposals come in the Chat
$("#tr-change").onsubmit = (e) => {
  e.preventDefault();
  const text = e.target.elements.text.value.trim();
  if (!text) return;
  go("chat");
  sendChat(`Chcę zmienić plan treningowy: ${text}`);
  e.target.reset();
};
$("#tr-plan").onsubmit = async (e) => {
  e.preventDefault();
  const f = e.target, weekly = {};
  Object.keys(training.plan.weekly).forEach((s) => (weekly[s] = { sessions: +f.elements[`${s}.sessions`].value, hours: +f.elements[`${s}.hours`].value }));
  const race = { name: f.elements.race_name.value.trim(), date: f.elements.race_date.value, distance: f.elements.distance.value };
  try {
    document.activeElement.blur();
    renderTraining((training = await api("/api/training/plan", { method: "PUT", body: JSON.stringify({ race, weekly, easy_hr_max: +f.elements.easy_hr_max.value, steps_goal: +f.elements.steps_goal.value }) })));
    $("#tr-saved").textContent = `zapisane ${hhmm(new Date())} — Alfred planuje już według tego`;
  } catch (err) { warn(err); }
};
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
  $("#sum-open").querySelectorAll("button").forEach((b) => (b.onclick = () => { setFilter(b.dataset.c); go("tasks:kanban"); }));
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
let catFilter = "", who = "me", range = "all";          // "" = every category; whose board: "me" | "alfred"; "all" | "today"
try {
  catFilter = localStorage.getItem("catfilter") || ""; who = localStorage.getItem("board") || "me";
  range = localStorage.getItem("boardrange") || "all";
} catch { /* private mode */ }
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
document.querySelectorAll("#board-range button").forEach((b) => (b.onclick = () => {
  range = b.dataset.range;
  try { localStorage.setItem("boardrange", range); } catch { /* private mode */ }
  refreshTasks().catch(warn);
}));
// "Dzisiaj": open tasks due today or already late, and what was finished today.
// ponytail: a recurring task (cron) without a due date does not count as today's; add a cron check if it should.
const forToday = (t, now) => (isOpen(t) ? !!t.due && new Date(t.due) < addDays(startOfDay(now), 1)
  : new Date(t.updated) >= startOfDay(now));
async function refreshTasks() {
  day.tasks = await api("/api/tasks?status=all");
  document.querySelectorAll("#board-who button").forEach((b) => b.classList.toggle("on", b.dataset.who === who));
  document.querySelectorAll("#board-range button").forEach((b) => b.classList.toggle("on", b.dataset.range === range));
  const now = new Date();
  const board = day.tasks.filter((t) => !!t.alfred === (who === "alfred") && (range !== "today" || forToday(t, now)));
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
    const dueText = due ? due.toLocaleString("pl-PL", { weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }) : "+ termin";
    return `<div class="kcard${late ? " overdue" : ""}" data-id="${esc(t.id)}"><button class="title" data-edit="${esc(t.id)}" title="Otwórz zadanie">${esc(t.title)}</button>
      ${t.description ? `<div class="sub desc">${esc(t.description.split("\n")[0])}</div>` : ""}
      <div class="sub"><button class="due" data-due="${esc(t.id)}" title="Zmień termin">${esc(dueText)}</button>${t.schedule ? ` · co ${esc(t.schedule)}` : ""}</div>${t.goal ? `<div class="sub goal" title="Jak przybliża do celu">🎯 ${esc(t.goal)}</div>` : ""}
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
  $("#board").querySelectorAll("[data-due]").forEach((b) => (b.onclick = () => editDue(b, day.tasks.find((x) => x.id === b.dataset.due))));
  $("#board").querySelectorAll("[data-edit]").forEach((b) => (b.onclick = () => editTask(day.tasks.find((x) => x.id === b.dataset.edit))));
  const Sortable = await sortable;
  $("#board").querySelectorAll(".cards").forEach((list) => Sortable?.create(list, {
    group: "tasks", sort: false, animation: 150, ghostClass: "ghost", filter: "input", preventOnFilter: false,
    onAdd: (e) => setTaskStatus(e.item.dataset.id, e.to.dataset.status),
  }));
  renderStats();
  renderCalendar();
}
// The browser's own date-time picker in place of the date. Saved on Enter or leaving the field; emptied = no due date; Esc = cancel.
function editDue(el, t) {
  const old = t.due ? localIso(new Date(t.due)).slice(0, 16) : "";
  const input = Object.assign(document.createElement("input"), { type: "datetime-local", value: old, className: "due-in" });
  const done = async (save) => {
    input.onblur = null;
    if (save && input.value !== old) {
      await api(`/api/tasks/${t.id}`, { method: "PATCH", body: JSON.stringify({ due: input.value ? new Date(input.value).toISOString() : "" }) }).catch(warn);
    }
    refreshTasks().catch(warn);
  };
  input.onblur = () => done(true);
  input.onkeydown = (e) => { if (e.key === "Enter") done(true); if (e.key === "Escape") { e.stopPropagation(); done(false); } };
  el.replaceWith(input);
  input.focus();
}
// A task, all of it, in a dialog. Only what changed is saved (the history shows the change).
function editTask(t) {
  const f = $("#task-edit").elements, cats = [...new Set([...(status.task_categories || []), t.category].filter(Boolean))];
  f.status.innerHTML = Object.entries(STATUS_PL).map(([s, l]) => `<option value="${s}">${l}</option>`).join("");
  f.category.innerHTML = `<option value="">bez kategorii</option>` + cats.map((c) => `<option>${esc(c)}</option>`).join("");
  const due = t.due ? localIso(new Date(t.due)).slice(0, 16) : "";
  f.title.value = t.title; f.description.value = t.description || "";
  f.status.value = t.status; f.category.value = t.category || ""; f.due.value = due; f.schedule.value = t.schedule || "";
  $("#task-edit").dataset.id = t.id; $("#task-edit").dataset.due = due;
  $("#task-dlg").returnValue = "";                    // Esc keeps the last value - it must not mean "save"
  $("#task-dlg").showModal();
}
$("#task-dlg").onclose = async () => {
  if ($("#task-dlg").returnValue !== "save") return;
  const form = $("#task-edit"), f = form.elements;
  const patch = { title: f.title.value.trim(), description: f.description.value, status: f.status.value,
    category: f.category.value, schedule: f.schedule.value.trim() };
  if (f.due.value !== form.dataset.due) patch.due = f.due.value ? new Date(f.due.value).toISOString() : "";
  await api(`/api/tasks/${form.dataset.id}`, { method: "PATCH", body: JSON.stringify(patch) }).catch(warn);
  refreshTasks().catch(warn);
};
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
    ${t ? `<p>${esc(STATUS_PL[t.status])}${t.description ? ` · ${esc(t.description)}` : ""}</p><button class="link" data-done>✓ Oznacz jako zrobione</button><button class="link" data-edit>Edytuj</button>` : ""}
    ${/^https:\/\//.test(e.htmlLink || "") ? `<a class="link" href="${esc(e.htmlLink)}" target="_blank" rel="noopener">Otwórz w Google Calendar →</a>` : ""}`;
  card.classList.remove("hidden");
  card.querySelector(".x").onclick = () => card.classList.add("hidden");
  const done = card.querySelector("[data-done]");
  if (done) done.onclick = () => { card.classList.add("hidden"); setTaskStatus(t.id, "done"); };
  const edit = card.querySelector("[data-edit]");
  if (edit) edit.onclick = () => { card.classList.add("hidden"); editTask(t); };
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
  const t = s.tasks, c = s.cost;
  const paid = c.jev_usd + c.elevenlabs_usd;
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
    tile(usd(c.cost_usd), "Claude", `${num(claudeTok)} tok. · subskrypcja: równowartość API, nie rachunek`, "blue") +
    tile(cash(c.elevenlabs_usd), "ElevenLabs", `${num(c.tts_chars)} znaków głosu · ${num(Math.round(c.stt_s))} s mowy`, "green") +
    tile(cash(paid), "płacisz razem", "Jev + ElevenLabs · ceny: config/brain.yaml → prices", paid ? "err" : "green");
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
function openTab(name) {                          // only through go("panel:<name>")
  document.querySelectorAll("#drawer .tab").forEach((t) => t.classList.toggle("hidden", t.id !== `tab-${name}`));
  $("#drawer").dataset.tab = name;
  TAB_LOAD[name]();
}

// Memory
async function loadBriefing() { $("#briefing").textContent = (await api("/api/memory/briefing")).briefing; }
$("#close-session").onclick = async () => { await api("/api/session/close", { method: "POST" }); loadBriefing(); };
async function openMemoryPage(path) {
  const page = await api(`/api/memory/page?path=${encodeURIComponent(path)}`);
  go("panel:memory");
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
  if (view !== "panel" || $("#drawer").dataset.tab !== "map") go("panel:map");
  const id = page.content.match(/\nid: (.+)/)?.[1]?.trim();
  if (id) ["module:", "cap:", "skill:", "tool:", "mcp:", ""].forEach((p) => Brain3D?.flash(p + id));
}
async function loadMap() {
  const m = await api("/api/map");
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
  ["voice.tts_model", "Model TTS"], ["voice.max_chars", "Mówione znaki na odpowiedź (reszta na ekranie)"], ["memory.session_idle_minutes", "Zamknij sesję po (min)"],
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
  // Only what you changed: an untouched field must not override config/brain.yaml (data/settings.json wins over it).
  const patch = {};
  e.target.querySelectorAll("input").forEach((i) => {
    if (i.type === "checkbox" ? i.checked === i.defaultChecked : i.value === i.defaultValue) return;
    const keys = i.name.split("."), last = keys.pop();
    let v = i.type === "checkbox" ? i.checked : i.value;
    if (i.type !== "checkbox" && v !== "" && !isNaN(v)) v = Number(v);
    keys.reduce((o, k) => (o[k] ||= {}), patch)[last] = v;
  });
  if (Object.keys(patch).length) await api("/api/settings", { method: "PUT", body: JSON.stringify(patch) });
  addMsg("system", Object.keys(patch).length ? "Ustawienia zapisane." : "Nic się nie zmieniło.");
  loadSettings();                                   // what is saved now becomes the new "unchanged"
};

// ---------------------------------------------------------------- first run
// The keys Alfred needs before he can talk (Claude Code login, Jev); then the chat, where he runs the setup himself.
function renderSetup() {
  const f = $("#setup-form");
  $("#setup-claude-ok").className = `dot ${status.keys.anthropic ? "on" : "bad"}`;
  $("#setup-claude").innerHTML = status.keys.anthropic ? "Gotowe."
    : `${esc(status.claude?.detail || "Nie widzę Claude Code.")} Zainstaluj Claude Code, w terminalu uruchom
       <code>claude</code> i zaloguj się, potem kliknij „Sprawdź ponownie”.`;
  $("#setup-jev-ok").className = `dot ${status.keys.jev ? "on" : "bad"}`;
  f.elements.jev.placeholder = status.keys.jev ? "zapisany — wpisz, żeby zmienić" : "JEV_API_KEY";
  f.elements.elevenlabs.placeholder = status.keys.elevenlabs ? "zapisany — wpisz, żeby zmienić" : "ELEVENLABS_API_KEY";
  $("#setup-go").disabled = !status.keys.anthropic || !(status.keys.jev || f.elements.jev.value.trim());
}
$("#setup").oncancel = (e) => e.preventDefault();       // Esc does not skip it
$("#setup-form").elements.jev.oninput = renderSetup;
$("#setup-recheck").onclick = async () => {
  $("#setup-claude").textContent = "Sprawdzam…";
  status = { ...status, ...(await api("/api/setup/check", { method: "POST" })) };
  renderSetup();
};
$("#setup-form").onsubmit = async (e) => {
  e.preventDefault();
  const f = e.target;
  status = { ...status, ...(await api("/api/setup/keys", { method: "POST",
    body: JSON.stringify({ jev: f.elements.jev.value, elevenlabs: f.elements.elevenlabs.value }) })) };
  f.reset();
  if (!status.keys.jev) return renderSetup();
  $("#setup").close();
  loadStatus();
  go("chat");
  const greet = () => (ws.readyState === 1 ? sendChat("Cześć Alfred, skonfigurujmy cię.") : setTimeout(greet, 300));
  greet();
};

// ---------------------------------------------------------------- boot
(async () => {
  await loadStatus();
  connect();
  if (status.setup?.done === false) { renderSetup(); $("#setup").showModal(); }
  let saved = null;
  try { saved = localStorage.getItem("page"); } catch { /* private mode */ }
  go("brain");                                      // always start on Alfred's network
  api("/api/persona").then((p) => {
    if (p.meta?.user_name) hello = `Cześć, ${p.meta.user_name}`;
    const h = $(".chat-empty .hello");
    if (h) h.textContent = hello;
  }).catch(() => {});
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
