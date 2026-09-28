// Alfred brain UI: conversation + voice, live brain graph, tasks / memory / modules / log / settings.
const $ = (s) => document.querySelector(s);
const api = async (path, opts = {}) => {
  const res = await fetch(path, { headers: { "Content-Type": "application/json" }, ...opts });
  if (!res.ok) throw new Error(`${res.status} ${await res.text()}`);
  return res.json();
};
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const css = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();

let status = { keys: {} };
let ws;

// ---------------------------------------------------------------- messages
function addMsg(kind, text, meta = "") {
  const el = document.createElement("div");
  el.className = `msg ${kind}`;
  el.innerHTML = esc(text) + (meta ? `<span class="meta">${esc(meta)}</span>` : "");
  $("#messages").appendChild(el);
  $("#messages").scrollTop = 1e9;
}

// ------------------------------------------------------------------- audio
const audioQueue = [];
let playing = null;
function speak(text, b64, lang) {
  audioQueue.push({ text, b64, lang });
  if (!playing) playNext();
}
function playNext() {
  const item = audioQueue.shift();
  if (!item) { playing = null; return; }
  if (item.b64) {
    playing = new Audio(`data:audio/mpeg;base64,${item.b64}`);
    playing.onended = playNext;
    playing.onerror = playNext;
    playing.play().catch(playNext);
  } else if ("speechSynthesis" in window) {
    const u = new SpeechSynthesisUtterance(item.text);
    u.lang = item.lang === "en" ? "en-GB" : "pl-PL";
    u.onend = playNext;
    playing = u;
    speechSynthesis.speak(u);
  } else playNext();
}
function stopSpeaking() {                 // barge-in: you start talking, Alfred stops
  audioQueue.length = 0;
  if (playing instanceof Audio) playing.pause();
  if ("speechSynthesis" in window) speechSynthesis.cancel();
  playing = null;
}

// ------------------------------------------------------------- microphone
let recorder = null, chunks = [], recognition = null;
async function startRec() {
  stopSpeaking();
  $("#mic").classList.add("rec");
  if (!status.keys.elevenlabs && ("webkitSpeechRecognition" in window || "SpeechRecognition" in window)) {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    recognition = new SR();
    recognition.lang = status.language === "en" ? "en-GB" : "pl-PL";
    recognition.onresult = (e) => sendText(e.results[0][0].transcript);
    recognition.onend = () => $("#mic").classList.remove("rec");
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
  $("#mic").classList.remove("rec");
  if (recognition) { recognition.stop(); recognition = null; }
  if (recorder && recorder.state === "recording") recorder.stop();
}
const isRecording = () => $("#mic").classList.contains("rec");
$("#mic").onclick = () => (isRecording() ? stopRec() : startRec());
document.addEventListener("keydown", (e) => {
  if (e.code === "Space" && !e.repeat && document.activeElement.tagName !== "INPUT") { e.preventDefault(); startRec(); }
});
document.addEventListener("keyup", (e) => {
  if (e.code === "Space" && document.activeElement.tagName !== "INPUT" && isRecording()) { e.preventDefault(); stopRec(); }
});

function sendText(text) {
  if (!text.trim()) return;
  ws.send(JSON.stringify({ type: "text", text }));
}
$("#text-form").onsubmit = (e) => { e.preventDefault(); sendText($("#text").value); $("#text").value = ""; };
$("#yes").onclick = () => ws.send(JSON.stringify({ type: "confirm", approved: true }));
$("#no").onclick = () => ws.send(JSON.stringify({ type: "confirm", approved: false }));

// ------------------------------------------------------------------ graph
async function loadGraph() { Brain3D.init(await api("/api/graph")); }
const flash = (id) => Brain3D.flash(id);
$("#demo").onclick = () => Brain3D.demo();

// ---------------------------------------------------------------- events
function onEvent(ev) {
  const d = ev.data || {};
  Brain3D.event(ev);
  switch (ev.kind) {
    case "transcript":
      if (d.source === "proactive") addMsg("system", "⏰ Alfred zaczyna sam (zadanie zaplanowane)");
      else addMsg("user", d.text);
      break;
    case "classified": {
      $("#route-info").textContent = `→ ${d.module}${d.also?.length ? " + " + d.also.join(", ") : ""}` +
        `${d.skill ? " · " + d.skill : ""} · ${Math.round(d.confidence * 100)}% · ${d.source} · ${d.latency_ms} ms`;
      break;
    }
    case "ack": addMsg("ack", d.text); speak(d.text, d.audio_b64, d.language); break;
    case "confirm_request":
      $("#confirm-text").textContent = d.text;
      $("#confirm").classList.remove("hidden");
      speak(d.text, d.audio_b64, status.language);
      break;
    case "confirm_result": $("#confirm").classList.add("hidden"); break;
    case "answer": {
      const u = d.usage || {};
      addMsg("alfred", d.text, `${d.model || ""} · in ${u.input || 0} / out ${u.output || 0} / cache ${u.cache_read || 0}` +
        (d.tools?.length ? ` · ${d.tools.join(", ")}` : ""));
      speak(d.text, d.audio_b64, d.language);
      refreshTasks();
      break;
    }
    case "error": addMsg("system", `⚠ ${d.message}`); break;
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
    status.mcp.map((s) => s.status === "disabled" ? "" : pill(s.name, s.status === "ready", s.error || "")).join("") +
    (status.session ? `<span class="pill">sesja · ${status.session.turns} tur · ${status.session.usage.input + status.session.usage.output} tok.</span>` : "");
}

// -------------------------------------------------------------------- tabs
document.querySelectorAll(".tabs button").forEach((b) => (b.onclick = () => {
  document.querySelectorAll(".tabs button").forEach((x) => x.classList.toggle("active", x === b));
  document.querySelectorAll(".tab").forEach((t) => t.classList.toggle("hidden", t.id !== `tab-${b.dataset.tab}`));
  ({ tasks: refreshTasks, memory: loadBriefing, map: loadMap, persona: loadPersona, modules: loadModules, log: loadLog, settings: loadSettings })[b.dataset.tab]();
}));

// Tasks
async function refreshTasks() {
  const tasks = await api(`/api/tasks?status=${$("#task-filter").value}`);
  const now = new Date();
  $("#tasks").innerHTML = tasks.map((t) => {
    const overdue = t.due && new Date(t.due) < now && !["done", "cancelled"].includes(t.status);
    return `<div class="card"><div class="row"><span class="title">${esc(t.title)}</span>
      <span class="badge ${t.status}">${t.status}</span>${overdue ? '<span class="badge overdue">po terminie</span>' : ""}</div>
      <div class="sub">${t.due ? "termin " + esc(t.due.replace("T", " ").slice(0, 16)) : ""}${t.schedule ? " · co " + esc(t.schedule) : ""}${t.module ? " · " + esc(t.module) : ""}</div>
      ${t.description ? `<div class="sub">${esc(t.description)}</div>` : ""}
      <div class="actions">${["in_progress", "waiting", "done", "cancelled"].filter((s) => s !== t.status)
        .map((s) => `<button data-id="${t.id}" data-status="${s}">${s}</button>`).join("")}</div></div>`;
  }).join("") || '<div class="sub">Brak zadań.</div>';
  $("#tasks").querySelectorAll("button").forEach((b) => (b.onclick = async () => {
    await api(`/api/tasks/${b.dataset.id}`, { method: "PATCH", body: JSON.stringify({ status: b.dataset.status }) });
    refreshTasks();
  }));
}
$("#task-filter").onchange = refreshTasks;
$("#task-form").onsubmit = async (e) => {
  e.preventDefault();
  const f = new FormData(e.target);
  const due = f.get("due") ? new Date(f.get("due")).toISOString() : null;
  await api("/api/tasks", { method: "POST", body: JSON.stringify({ title: f.get("title"), due, schedule: f.get("schedule") || null }) });
  e.target.reset();
  refreshTasks();
};

// Memory
async function loadBriefing() { $("#briefing").textContent = (await api("/api/memory/briefing")).briefing; }
$("#close-session").onclick = async () => { await api("/api/session/close", { method: "POST" }); loadBriefing(); };
$("#mem-search").onsubmit = async (e) => {
  e.preventDefault();
  const hits = await api(`/api/memory/search?q=${encodeURIComponent($("#mem-q").value)}`);
  $("#mem-results").innerHTML = hits.map((h) => `<div class="card" data-path="${esc(h.path)}" style="cursor:pointer">
    <span class="title">${esc(h.title)}</span><span class="sub">${esc(h.type)} · ${esc(h.path)}</span>
    <span class="sub">${esc(h.description || "")}</span></div>`).join("") || '<div class="sub">Nic nie znaleziono.</div>';
  $("#mem-results").querySelectorAll(".card").forEach((c) => (c.onclick = async () => {
    const page = await api(`/api/memory/page?path=${encodeURIComponent(c.dataset.path)}`);
    $("#mem-page").textContent = page.content;
    $("#mem-page").classList.remove("hidden");
  }));
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
  flash(`module:${r.module}`);
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
  let list = false, table = false;
  const close = () => { if (list) html.push("</ul>"); if (table) html.push("</table>"); list = table = false; };
  for (const l of lines) {
    if (/^\|/.test(l)) {
      if (/^\|[-| ]+\|$/.test(l)) continue;
      if (!table) { close(); html.push("<table>"); table = true; }
      html.push("<tr>" + l.split("|").slice(1, -1).map((c) => `<td>${inline(c.trim())}</td>`).join("") + "</tr>");
    } else if (/^[-*] /.test(l)) {
      if (!list) { close(); html.push("<ul>"); list = true; }
      html.push(`<li>${inline(l.slice(2))}</li>`);
    } else {
      close();
      if (/^## /.test(l)) html.push(`<h2>${inline(l.slice(3))}</h2>`);
      else if (/^# /.test(l)) html.push(`<h1>${inline(l.slice(2))}</h1>`);
      else if (l.trim()) html.push(`<p>${inline(l)}</p>`);
    }
  }
  close();
  return (fm ? `<div class="fm">${esc(fm)}</div>` : "") + html.join("");
}
const mapHistory = [];
async function openMapPage(path, push = true) {
  const page = await api(`/api/map/page?path=${encodeURIComponent(path)}`);
  if (push) mapHistory.push(path);
  $("#map-crumbs").innerHTML = [`<a data-page="index.md">brain_map</a>`, ...path.split("/").map((x) => esc(x))].join(" / ");
  $("#map-page").innerHTML = renderMd(page.content, path);
  document.querySelectorAll("#map-page a[data-page], #map-crumbs a[data-page]").forEach((a) => (a.onclick = () => openMapPage(a.dataset.page)));
  document.querySelector('.tabs button[data-tab="map"]').classList.contains("active") ||
    document.querySelector('.tabs button[data-tab="map"]').click();
  const id = page.content.match(/\nid: (.+)/)?.[1]?.trim();
  if (id) ["module:", "cap:", "skill:", "tool:", "mcp:", ""].forEach((p) => Brain3D.flash(p + id));
}
async function loadMap() {
  const m = await api("/api/map");
  $("#map-backend").textContent = `Claude: ${status.backend === "subscription" ? "subskrypcja (Claude Code)" : "API (tokeny)"}`;
  $("#map-counts").innerHTML = Object.entries({ modules: "moduły", capabilities: "możliwości", skills: "umiejętności", tools: "narzędzia", servers: "serwery", topics: "tematy" })
    .map(([k, l]) => `<div><b>${m.counts[k]}</b>${l}</div>`).join("");
  const q = m.jev;
  $("#jev-cats").innerHTML = Object.entries(q).map(([k, v]) => {
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
  ["llm.backend", "Konto Claude: subscription (Twoja subskrypcja) / api (tokeny)"], ["assistant.default_language", "Domyślny język (pl/en)"],
  ["models.executor", "Model wykonawczy"], ["models.executor_effort", "Wysiłek (low/medium/high)"],
  ["models.light", "Model lekki"], ["router.confident_at", "Próg pewności routera"],
  ["router.ask_below", "Dopytaj poniżej"], ["voice.voice_id", "ElevenLabs voice ID"],
  ["voice.tts_model", "Model TTS"], ["memory.session_idle_minutes", "Zamknij sesję po (min)"],
  ["proactive.heartbeat_minutes", "Heartbeat (min)"],
];
async function loadSettings() {
  const s = await api("/api/settings");
  const get = (path) => path === "voice.voice_id" ? s.voice_id : path.split(".").reduce((o, k) => o?.[k], s);
  $("#settings-form").innerHTML = FIELDS.map(([p, l]) => `<label class="field">${l}<input name="${p}" value="${esc(get(p) ?? "")}"></label>`).join("") +
    `<label class="switch"><input type="checkbox" name="proactive.enabled" ${s.proactive?.enabled ? "checked" : ""}> Tryb proaktywny</label>
     <button class="primary">Zapisz</button>`;
}
$("#settings-form").onsubmit = async (e) => {
  e.preventDefault();
  const patch = {};
  e.target.querySelectorAll("input").forEach((i) => {
    const [a, b] = i.name.split(".");
    let v = i.type === "checkbox" ? i.checked : i.value;
    if (i.type !== "checkbox" && v !== "" && !isNaN(v)) v = Number(v);
    (patch[a] ||= {})[b] = v;
  });
  await api("/api/settings", { method: "PUT", body: JSON.stringify(patch) });
  addMsg("system", "Ustawienia zapisane.");
};

// ---------------------------------------------------------------- boot
(async () => {
  await loadStatus();
  await loadGraph();
  connect();
  refreshTasks();
  setInterval(loadStatus, 15000);
})();
