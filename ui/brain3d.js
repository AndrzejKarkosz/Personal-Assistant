// 3D brain view: the architecture as a 3D graph, and every event as a data "packet" travelling
// between the parts of the brain, labelled with what it carries. The flow panel explains each
// step in plain words. "Demo" plays a scripted request so the flow can be seen without API keys.
(() => {
  const css = (n) => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
  const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const short = (s, n = 42) => { s = String(s ?? "").replace(/\s+/g, " ").trim(); return s.length > n ? s.slice(0, n - 1) + "…" : s; };

  // What each part of the brain does - shown when a node is clicked.
  const INFO = {
    user: ["Ty", "Mówisz lub piszesz. Alfred odpowiada głosem.", "wejście: głos / tekst"],
    ears: ["Uszy — mowa na tekst", "ElevenLabs Scribe zamienia nagranie na tekst i rozpoznaje język (PL/EN).", "audio → tekst + język"],
    router: ["Router — Jev", "Jedno szybkie zapytanie do Jev: moduł, możliwości (grupy narzędzi), umiejętność, temat z bazy wiedzy, pilność, czy akcja zmienia coś w świecie, czy potrzebna jest pamięć. Wszystkie kategorie pochodzą z mapy mózgu (brain_map/, OKF).", "tekst → trasa z prawdopodobieństwami"],
    executor: ["Wykonawca — Claude", "Claude dostaje tylko narzędzia wybranego modułu, jego prompt, procedurę umiejętności i briefing z pamięci. Wywołuje narzędzia w pętli aż do wyniku.", "trasa + tekst + briefing → wynik"],
    guard: ["Strażnik", "Akcje, które rezerwują, wysyłają lub kasują, czekają na Twoje „tak”. Pytanie jest czytane na głos.", "akcja → pytanie → tak / nie"],
    voice: ["Głos — Alfred", "Najpierw natychmiastowe „Już się tym zajmuję”, potem krótka odpowiedź do ucha (ElevenLabs TTS).", "wynik → mowa"],
    memory: ["Pamięć sesji — OKF", "Zadania ze statusami, podsumowania sesji, fakty i dziennik zmian w plikach markdown. Na starcie sesji powstaje z nich briefing: co otwarte, co się zmieniło.", "tury i akcje → pliki OKF → briefing"],
    proactive: ["Tryb proaktywny", "Zadania z terminem i cron uruchamiają się same. Najpierw Jev ocenia, czy warto Ci przerwać — dopiero potem budzi się Claude.", "zegar → bramka Jev → router"],
  };

  const KIND_INFO = {
    module: "Moduł — płat mózgu. Pierwsze pytanie routera Jev wybiera moduł.",
    capability: "Możliwość — grupa narzędzi i kategoria routera Jev. Claude dostaje tylko narzędzia wybranych możliwości.",
    skill: "Umiejętność — procedura krok po kroku. Jev może ją wybrać bezpośrednio; korzysta z podanych możliwości.",
    tool: "Narzędzie, które Claude może wywołać.",
    mcp: "Serwer — miejsce, gdzie żyją narzędzia (serwer MCP, wbudowane narzędzia Alfreda albo narzędzia serwerowe Claude).",
    topic: "Temat z Twojej bazy wiedzy. Jev może rozpoznać temat i skierować pytanie prosto do biblioteki.",
  };

  // The brain as shells around the pipeline axis: modules, then their skills and capabilities,
  // then tools, then the servers the tools live on, then the knowledge topics. A module's
  // capabilities, tools and servers all sit in the same direction, so relations read as rays.
  function layout(g) {
    const pos = {
      user: [-460, 0, 0], ears: [-310, 0, 0], router: [-170, 0, 0], executor: [40, 0, 0],
      voice: [230, 0, 0], guard: [160, -110, 70], memory: [40, -150, -40], proactive: [-170, -150, 40],
    };
    const byKind = (k) => g.nodes.filter((n) => n.kind === k);
    const out = {}, inn = {};
    g.edges.forEach((e) => { (out[e.source] ||= []).push(e.target); (inn[e.target] ||= []).push(e.source); });
    const ang = {};
    const place = (id, a, r, x) => { ang[id] = a; pos[id] = [x, r * Math.cos(a) + 30, r * Math.sin(a)]; };
    const mean = (angles) => Math.atan2(angles.reduce((s, a) => s + Math.sin(a), 0), angles.reduce((s, a) => s + Math.cos(a), 0));
    const spread = (i, n, step) => (i - (n - 1) / 2) * step;

    const mods = byKind("module");
    mods.forEach((m, i) => place(m.id, (2 * Math.PI * i) / mods.length, 175, -60));
    mods.forEach((m) => {
      const own = (out[m.id] || []).filter((c) => c.startsWith(`cap:${m.id.slice(7)}.`));
      own.forEach((c, i) => place(c, ang[m.id] + spread(i, own.length, 0.2), 275, 10));
      const skills = (out[m.id] || []).filter((t) => t.startsWith("skill:"));
      skills.forEach((s, i) => place(s, ang[m.id] + spread(i, skills.length, 0.18) + 0.25, 225, -20));
    });
    const tools = byKind("tool");
    const toolsOfCap = {};
    tools.forEach((t) => { const c = (inn[t.id] || []).find((x) => x.startsWith("cap:") && x in ang); (toolsOfCap[c || "none"] ||= []).push(t.id); });
    Object.entries(toolsOfCap).forEach(([c, ts]) => {
      const base = c in ang ? ang[c] : Math.PI;
      ts.forEach((t, i) => place(t, base + spread(i, ts.length, 0.075), 370, 90));
    });
    const servers = byKind("mcp");
    const orphans = [];
    servers.forEach((s) => {
      const ts = (inn[s.id] || []).filter((t) => t in ang);
      if (ts.length) place(s.id, mean(ts.map((t) => ang[t])), 470, 170); else orphans.push(s.id);
    });
    orphans.forEach((s, i) => place(s, Math.PI * 0.75 + i * 0.35, 470, 170));
    const topics = byKind("topic");
    topics.forEach((t, i) => {
      const srv = (out[t.id] || [])[0];
      place(t.id, (srv in ang ? ang[srv] : 0) + spread(i, topics.length, 0.09), 560, 230);
    });
    return pos;
  }

  let Graph, nodesById = {}, adjacency = {}, packets = [], el, root;
  const COLORS = { core: "--core", module: "--module", skill: "--skill", mcp: "--mcp", user: "--ink",
                   capability: "--cap", tool: "--tool", topic: "--topic" };
  const colorOf = (kind) => css(COLORS[kind] || "--core");
  const radiusOf = (kind) => ({ core: 14, user: 15, module: 10, skill: 6.5, mcp: 9, capability: 7.5, tool: 4.5, topic: 4.5 }[kind] || 6);
  const labelSize = (kind) => ({ core: 12, user: 12, module: 10, mcp: 9, capability: 8, skill: 7, tool: 6, topic: 6 }[kind] || 7);

  function nodeObject(n) {
    const group = new THREE.Group();
    const dim = n.enabled === false || ["error", "disabled", "missing", "offline"].includes(n.status) ||
      (n.kind === "capability" && n.available === 0 && n.label !== "Talk without tools");
    const mat = new THREE.MeshLambertMaterial({ color: n.confirm && n.kind === "tool" ? css("--err") : colorOf(n.kind), transparent: true, opacity: dim ? 0.3 : 0.95 });
    const sphere = new THREE.Mesh(new THREE.SphereGeometry(radiusOf(n.kind), 24, 16), mat);
    group.add(sphere);
    const label = new SpriteText(String(n.label).replace(/\n/g, " "), n.kind === "core" || n.kind === "user" ? 12 : 9, css("--ink"));
    label.fontFace = "Inter, sans-serif";
    label.fontWeight = n.kind === "core" ? "600" : "400";
    label.position.set(0, -(radiusOf(n.kind) + 10), 0);
    group.add(label);
    n.__sphere = sphere;
    n.__baseColor = mat.color.getHex();
    return group;
  }

  function init(g) {
    el = document.getElementById("graph");
    root = el.parentElement;
    const data = {
      nodes: [{ id: "user", label: "Ty", kind: "user" }, ...g.nodes],
      links: [...g.edges.map((e) => ({ ...e })), { source: "user", target: "ears" }, { source: "voice", target: "user", back: true }],
    };
    const pos = layout({ nodes: data.nodes, edges: g.edges });
    data.nodes.forEach((n) => { const p = pos[n.id] || [0, 0, 0]; n.fx = n.x = p[0]; n.fy = n.y = p[1]; n.fz = n.z = p[2]; });
    nodesById = Object.fromEntries(data.nodes.map((n) => [n.id, n]));
    adjacency = {};
    data.links.forEach((l) => {
      (adjacency[l.source] ||= []).push(l.target);
      (adjacency[l.target] ||= []).push(l.source);
    });

    if (!Graph) {
      Graph = ForceGraph3D({ controlType: "orbit" })(el)
        .showNavInfo(false)
        .nodeThreeObject(nodeObject)
        .nodeLabel((n) => `<b>${esc((INFO[n.id] || [n.label])[0])}</b>${n.description ? `<br>${esc(short(n.description, 90))}` : ""}`)
        .linkColor((l) => css(l.rel === "uses" ? "--cap" : "--line"))
        .linkOpacity(0.5)
        .linkWidth((l) => (l.back ? 0.8 : l.rel === "flow" ? 0.6 : 0.25))
        .linkLabel((l) => l.rel || "")
        .linkCurvature((l) => (l.back ? 0.55 : 0))
        .linkCurveRotation((l) => (l.back ? Math.PI / 2 : 0))
        .linkDirectionalArrowLength(3)
        .linkDirectionalArrowRelPos(0.85)
        .cooldownTicks(0)
        .onNodeClick(showInfo);
      Graph.scene().add(new THREE.AmbientLight(0xffffff, 1.1));
      const sun = new THREE.DirectionalLight(0xffffff, 1.4);
      sun.position.set(200, 300, 400);
      Graph.scene().add(sun);
      const controls = Graph.controls();
      controls.autoRotate = true;
      controls.autoRotateSpeed = 0.25;
      el.addEventListener("pointerdown", () => (controls.autoRotate = false));
      new ResizeObserver(() => Graph.width(el.clientWidth).height(el.clientHeight)).observe(el);
      requestAnimationFrame(tick);
    }
    Graph.backgroundColor(css("--panel")).graphData(data);
    Graph.width(el.clientWidth).height(el.clientHeight);
    frame();
  }

  // Camera distance so the whole brain fits the stage, whatever its aspect ratio.
  function frame() {
    // Look at the brain from an oblique angle so the rings around the pipeline axis open up,
    // and back off until the whole bounding sphere fits the narrower field of view.
    const ns = Object.values(nodesById);
    const cx = ns.reduce((s, n) => s + n.fx, 0) / ns.length, cy = ns.reduce((s, n) => s + n.fy, 0) / ns.length;
    const r = Math.max(...ns.map((n) => Math.hypot(n.fx - cx, n.fy - cy, n.fz)));
    const cam = Graph.camera();
    const aspect = el.clientWidth / Math.max(1, el.clientHeight);
    const half = Math.min((cam.fov * Math.PI) / 360, Math.atan(Math.tan((cam.fov * Math.PI) / 360) * aspect));
    const dist = (r / Math.sin(half)) * 0.78;
    const dir = [0.62, 0.3, 0.72], len = Math.hypot(...dir);
    const ty = cy - r * 0.18;                       // shift up: the flow panel covers the bottom
    Graph.cameraPosition({ x: cx + (dist * dir[0]) / len, y: ty + (dist * dir[1]) / len, z: (dist * dir[2]) / len },
                         { x: cx, y: ty, z: 0 });
    Graph.controls().target.set(cx, ty, 0);
  }

  // ------------------------------------------------------------- packets
  function path(from, to) {                 // shortest path through the brain (BFS, undirected)
    if (from === to || !nodesById[from] || !nodesById[to]) return nodesById[to] ? [to] : [];
    const prev = { [from]: null }, queue = [from];
    while (queue.length) {
      const cur = queue.shift();
      if (cur === to) break;
      for (const nb of adjacency[cur] || []) if (!(nb in prev)) { prev[nb] = cur; queue.push(nb); }
    }
    if (!(to in prev)) return [to];
    const out = [];
    for (let c = to; c !== null; c = prev[c]) out.unshift(c);
    return out;
  }

  function send(from, to, label, color = css("--accent")) {
    const hops = path(from, to);
    if (!Graph || hops.length < 2) { if (hops.length) flash(hops[0]); return; }
    const group = new THREE.Group();
    const orb = new THREE.Mesh(new THREE.SphereGeometry(6.5, 16, 12), new THREE.MeshBasicMaterial({ color }));
    const glow = new THREE.Mesh(new THREE.SphereGeometry(13, 16, 12), new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.25 }));
    group.add(orb, glow);
    if (label) {
      const tag = new SpriteText(short(label), 10, css("--ink"));
      tag.backgroundColor = css("--panel");
      tag.padding = 1.6;
      tag.borderRadius = 2;
      tag.fontFace = "Inter, sans-serif";
      tag.position.set(0, 22, 0);
      group.add(tag);
    }
    Graph.scene().add(group);
    packets.push({ group, hops, seg: 0, t: 0, speed: 0.018 });
  }

  function tick() {
    for (const p of packets) {
      const a = nodesById[p.hops[p.seg]], b = nodesById[p.hops[p.seg + 1]];
      p.t += p.speed;
      if (p.t >= 1) { flash(b.id); p.seg += 1; p.t = 0; }
      if (p.seg >= p.hops.length - 1) { p.done = true; continue; }
      const k = p.t < 0.5 ? 2 * p.t * p.t : 1 - (-2 * p.t + 2) ** 2 / 2;     // ease in-out per hop
      p.group.position.set(a.fx + (b.fx - a.fx) * k, a.fy + (b.fy - a.fy) * k, a.fz + (b.fz - a.fz) * k);
    }
    packets.filter((p) => p.done).forEach((p) => Graph.scene().remove(p.group));
    packets = packets.filter((p) => !p.done);
    requestAnimationFrame(tick);
  }

  function flash(id) {
    const n = nodesById[id];
    if (!n || !n.__sphere) return;
    n.__sphere.material.color.set(css("--accent"));
    n.__sphere.scale.setScalar(1.6);
    clearTimeout(n.__timer);
    n.__timer = setTimeout(() => { n.__sphere.material.color.set(n.__baseColor); n.__sphere.scale.setScalar(1); }, 900);
  }

  // ---------------------------------------------------------- flow panel
  const flow = () => document.getElementById("flow-steps");
  function step(title, detail, node) {
    const li = document.createElement("li");
    li.innerHTML = `<b>${esc(title)}</b>${detail ? `<span>${esc(detail)}</span>` : ""}`;
    li.onclick = () => node && showInfo(nodesById[node]);
    flow().appendChild(li);
    flow().querySelectorAll("li").forEach((x) => x.classList.remove("now"));
    li.classList.add("now");
    flow().scrollTop = 1e9;
  }

  function showInfo(n) {
    if (!n) return;
    const facts = [];
    if (n.kind === "tool") facts.push(`serwer: ${n.server}`, `efekt: ${n.side_effect}`, n.confirm ? "wymaga Twojej zgody" : "bez zgody", n.status);
    if (n.kind === "capability") facts.push(`${n.available} narzędzi online`, n.confirm ? "wymaga zgody" : "");
    if (n.kind === "mcp") facts.push(`status: ${n.status}`);
    const rel = (adjacency[n.id] || []).filter((x) => nodesById[x] && !["router", "executor"].includes(x))
      .map((x) => nodesById[x].label).slice(0, 12);
    const [title, text, io] = INFO[n.id] || [n.label, [KIND_INFO[n.kind], n.description].filter(Boolean).join(" "), facts.filter(Boolean).join(" · ")];
    const card = document.getElementById("node-info");
    card.innerHTML = `<button class="x" aria-label="Zamknij">×</button><b>${esc(title)}</b><p>${esc(text)}</p>` +
      (io ? `<code>${esc(io)}</code>` : "") +
      (rel.length ? `<p class="rel">Połączony z: ${rel.map(esc).join(", ")}</p>` : "") +
      (n.path ? `<button class="link" data-path="${esc(n.path)}">Otwórz stronę w mapie →</button>` : "");
    const open = card.querySelector(".link");
    if (open) open.onclick = () => window.openMapPage && window.openMapPage(open.dataset.path);
    card.classList.remove("hidden");
    card.querySelector(".x").onclick = () => card.classList.add("hidden");
    flash(n.id);
  }

  // ------------------------------------------------------ event mapping
  const routeOf = {};       // request_id -> first routed module node
  let flowFor = null;       // request the flow panel currently describes
  const newFlow = (rid) => { if (rid !== flowFor) { flow().innerHTML = ""; flowFor = rid; } };
  const toolNode = (tool) => (nodesById[`tool:${tool}`] ? `tool:${tool}` : "memory");
  const serverOf = (tool) => nodesById[`tool:${tool}`]?.server;
  const C = () => ({ text: css("--module"), route: css("--accent"), tool: css("--mcp"), voice: css("--core"), warn: css("--err") });

  function event(ev) {
    const d = ev.data || {}, c = C(), rid = ev.request_id;
    const mod = routeOf[rid] || "executor";
    switch (ev.kind) {
      case "listening":
        newFlow(rid);
        send("user", "ears", "nagranie audio", c.text);
        step("Uszy odbierają nagranie", `${Math.round((d.bytes || 0) / 1024)} KB audio → ElevenLabs Scribe`, "ears");
        break;
      case "transcript":
        if (d.confirmation) { send("user", "guard", `„${d.text}”`, c.text); step("Twoja odpowiedź trafia do strażnika", `„${d.text}”`, "guard"); break; }
        if (d.source === "proactive") { newFlow(rid); send("proactive", "router", "zadanie z harmonogramu", c.route); step("Alfred zaczyna sam", short(d.text, 90), "proactive"); break; }
        newFlow(rid);
        send("user", "ears", `„${d.text}”`, c.text);
        setTimeout(() => send("ears", "router", `tekst · ${d.language || ""}`, c.text), 450);
        step("1 · Uszy: mowa → tekst", `„${short(d.text, 90)}” (${d.language || "?"})`, "ears");
        break;
      case "classified": {
        const target = `module:${d.module}`;
        routeOf[rid] = target;
        send("router", target, `${d.module} ${Math.round(d.confidence * 100)}%`, c.route);
        (d.also || []).forEach((m) => send("router", `module:${m}`, `${m} (też)`, c.route));
        (d.capabilities || []).forEach((cap, i) => setTimeout(() => send(target, `cap:${cap}`,
          `${cap.split(".")[1]} ${Math.round((d.capability_probabilities?.[cap] || 0) * 100) || ""}%`.replace(/ %$/, ""), c.route), 500 + i * 150));
        if (d.skill) setTimeout(() => send(target, `skill:${d.skill}`, "procedura", c.route), 500);
        if (d.topic) setTimeout(() => send("router", d.topic, "temat", c.text), 400);
        const top = Object.entries(d.probabilities || {}).sort((a, b) => b[1] - a[1]).slice(0, 3)
          .map(([k, v]) => `${k} ${Math.round(v * 100)}%`).join(" · ");
        step(`2 · Router (${d.source}, ${d.latency_ms} ms) → ${d.module}`,
          `${top}${d.capabilities?.length ? ` · możliwości: ${d.capabilities.join(", ")}` : " · wszystkie możliwości modułu"}${d.skill ? ` · umiejętność: ${d.skill}` : ""}${d.topic ? ` · temat: ${d.topic.replace("topic:", "")}` : ""} · pilność ${(+d.urgency || 0).toFixed(1)} · akcja w świecie ${Math.round((d.acts_on_world || 0) * 100)}%`, "router");
        break;
      }
      case "ack":
        send("router", "voice", "potwierdzenie", c.voice);
        setTimeout(() => send("voice", "user", `„${d.text}”`, c.voice), 700);
        step("3 · Natychmiastowe potwierdzenie", `„${d.text}”`, "voice");
        break;
      case "executor_start":
        send(mod, "executor", `${(d.tools || []).length} narzędzi`, c.route);
        (d.capabilities || []).slice(0, 4).forEach((cap) => flash(`cap:${cap}`));
        send("memory", "executor", "briefing", c.text);
        step(`4 · Claude (${d.model}, ${d.backend === "subscription" ? "subskrypcja" : "API"}, wysiłek ${d.effort}) zaczyna`, `moduły: ${(d.modules || []).join(", ")} · narzędzia: ${(d.tools || []).slice(0, 6).join(", ")}${(d.tools || []).length > 6 ? "…" : ""}`, "executor");
        break;
      case "llm_call":
        flash("executor");
        step(`Claude myśli (runda ${d.round + 1}, ${d.ms} ms)`, `${d.stop_reason === "tool_use" ? "chce użyć narzędzia" : d.stop_reason === "end_turn" ? "ma odpowiedź" : d.stop_reason} · tokeny in ${d.usage?.input ?? 0} / out ${d.usage?.output ?? 0}`, "executor");
        break;
      case "tool_call":
        send("executor", toolNode(d.tool), d.tool.split("__").pop(), c.tool);
        if (serverOf(d.tool)) setTimeout(() => send(toolNode(d.tool), `mcp:${serverOf(d.tool)}`, "wywołanie", c.tool), 900);
        step(`Narzędzie: ${d.tool}`, short(JSON.stringify(d.input || {}), 110), toolNode(d.tool));
        break;
      case "tool_result":
        send(serverOf(d.tool) ? `mcp:${serverOf(d.tool)}` : toolNode(d.tool), "executor", d.is_error ? "błąd" : `wynik · ${d.ms} ms`, d.is_error ? c.warn : c.tool);
        step(`Wynik ${d.tool.split("__").pop()}${d.is_error ? " (błąd)" : ""}`, short(d.preview, 110), toolNode(d.tool));
        break;
      case "confirm_request":
        send("executor", "guard", "wymaga zgody", c.warn);
        setTimeout(() => send("guard", "user", "„potwierdzasz?”", c.warn), 600);
        step("Strażnik pyta o zgodę", d.text, "guard");
        break;
      case "confirm_result":
        send("guard", "executor", d.approved ? "zgoda" : "odmowa", d.approved ? c.tool : c.warn);
        step(d.approved ? "Zgoda — Claude kontynuuje" : "Odmowa — akcja wstrzymana", d.tool, "guard");
        break;
      case "answer":
        send("executor", "voice", "odpowiedź", c.voice);
        setTimeout(() => send("voice", "user", `„${d.text}”`, c.voice), 650);
        send("executor", "memory", "zapis tury", c.text);
        step("5 · Odpowiedź głosem", `„${short(d.text, 110)}” · in ${d.usage?.input ?? 0} / out ${d.usage?.output ?? 0} / cache ${d.usage?.cache_read ?? 0}`, "voice");
        step("6 · Pamięć sesji", (d.actions || []).length ? `zapisane akcje: ${d.actions.join("; ")}` : "tura dopisana do sesji", "memory");
        break;
      case "session_started": flash("memory"); break;
      case "session_closed":
        flash("memory");
        step("Sesja zapisana do pamięci (OKF)", d.title || "", "memory");
        break;
      case "proactive_gate":
        send("proactive", "router", `bramka ${Math.round(d.probability * 100)}%`, d.fired ? c.route : c.warn);
        step(d.fired ? "Bramka Jev: warto przerwać" : "Bramka Jev: nie teraz", `${d.task} (${d.trigger})`, "proactive");
        break;
      case "error":
        flash(ev.node);
        step("Błąd", d.message, ev.node);
        break;
    }
  }

  // ---------------------------------------------------------------- demo
  function demo() {
    const rid = "demo-" + Date.now();
    const E = (kind, node, data) => ({ kind, node, request_id: rid, data });
    const script = [
      [0, E("listening", "ears", { bytes: 48000 })],
      [900, E("transcript", "ears", { text: "Zarezerwuj stolik dla dwóch w Nolicie na piątek na dziewiętnastą", language: "pl" })],
      [1900, E("classified", "router", { module: "bookings", skill: "bookings.restaurant-table", capabilities: ["bookings.browse", "memory.recall", "research.web", "bookings.confirm", "calendar.write", "memory.remember", "tasks.manage"], capability_probabilities: { "bookings.browse": 0.71, "research.web": 0.12 }, confidence: 0.86, source: "jev", latency_ms: 180, urgency: 1.1, acts_on_world: 0.94, probabilities: { bookings: 0.86, calendar: 0.09, research: 0.05 }, also: [] })],
      [2800, E("ack", "voice", { text: "Oczywiście, szefie. Już się tym zajmuję." })],
      [3600, E("executor_start", "executor", { model: "claude-opus-5", backend: "subscription", capabilities: ["bookings.browse", "memory.recall", "research.web", "bookings.confirm"], effort: "medium", modules: ["bookings"], tools: ["browser__browser_navigate", "browser__browser_click", "memory_search", "confirm_action", "task_create"] })],
      [4400, E("llm_call", "executor", { round: 0, ms: 1400, stop_reason: "tool_use", usage: { input: 2100, output: 90 } })],
      [4700, E("tool_call", "memory", { tool: "memory_search", input: { query: "restauracja Nolita" } })],
      [5600, E("tool_result", "memory", { tool: "memory_search", ms: 12, preview: "facts/places/nolita.md — ulubiona włoska, stolik przy oknie" })],
      [6400, E("tool_call", "tool:web_search", { tool: "web_search", input: { query: "Nolita rezerwacja stolika" } })],
      [7500, E("tool_result", "tool:web_search", { tool: "web_search", ms: 820, preview: "nolita.pl/rezerwacja — wolne: 18:30, 19:00, 20:15" })],
      [8400, E("confirm_request", "guard", { tool: "confirm_action", text: "Zanim to zrobię: stolik dla dwóch w Nolicie, piątek 19:00. Potwierdzasz?" })],
      [10200, E("transcript", "ears", { text: "tak", confirmation: true })],
      [10700, E("confirm_result", "guard", { tool: "confirm_action", approved: true })],
      [11500, E("tool_call", "memory", { tool: "task_create", input: { title: "Sprawdź SMS z potwierdzeniem", due: "piątek 12:00" } })],
      [12300, E("tool_result", "memory", { tool: "task_create", ms: 4, preview: "Created task 20260925-sprawdz-sms" })],
      [13100, E("answer", "voice", { text: "Zarezerwowane, szefie: Nolita, piątek o dziewiętnastej, stolik dla dwóch. Przypomnę o potwierdzeniu.", usage: { input: 3900, output: 140, cache_read: 1800 }, actions: ["confirm_action: stolik Nolita", "task_create: Sprawdź SMS"] })],
    ];
    script.forEach(([t, ev]) => setTimeout(() => event(ev), t));
  }

  window.Brain3D = { init, event, demo, flash, showInfo: (id) => showInfo(nodesById[id]) };
})();
