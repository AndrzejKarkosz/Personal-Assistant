import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { EffectComposer } from "three/addons/postprocessing/EffectComposer.js";
import { RenderPass } from "three/addons/postprocessing/RenderPass.js";
import { UnrealBloomPass } from "three/addons/postprocessing/UnrealBloomPass.js";
import { OutputPass } from "three/addons/postprocessing/OutputPass.js";
import { CSS2DRenderer, CSS2DObject } from "three/addons/renderers/CSS2DRenderer.js";

const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const short = (s, n = 42) => { s = String(s ?? "").replace(/\s+/g, " ").trim(); return s.length > n ? s.slice(0, n - 1) + "…" : s; };

const REGIONS = [
  { id: "core", label: "Rdzeń", color: "#22d3ee",
    info: "Pień mózgu. Każdy sygnał przechodzi tędy: uszy (mowa → tekst), router Jev, wykonawca Claude, strażnik zgód, głos i tryb proaktywny." },
  { id: "memory", label: "Pamięć", color: "#4ade80", nerve: "memory", folders: ["Zadania", "Sesje", "Fakty"],
    info: "Dziennik Alfreda (OKF): otwarte zadania, podsumowania sesji i fakty o Tobie." },
  { id: "knowledge", label: "Wiedza", color: "#2dd4bf", nerve: "router",
    info: "Tematy z Twojej biblioteki wiedzy. Router może skierować pytanie prosto do tematu." },
  { id: "mcp", label: "Serwery MCP", color: "#38bdf8", nerve: "executor",
    info: "Serwery z narzędziami: MCP, wbudowane narzędzia Alfreda i narzędzia serwerowe Claude. Każdy serwer to folder z narzędziami." },
  { id: "tech", label: "Mózg techniczny", color: "#a78bfa", nerve: "proactive", folders: ["Umiejętności", "Rutyny", "Repozytorium", "Testy"],
    info: "Umiejętności (procedury), rutyny z harmonogramu, kod w repozytorium i testy pytest." },
  { id: "modules", label: "Moduły", color: "#60a5fa", nerve: "router",
    info: "Płaty mózgu. Router wybiera moduł, a moduł daje Claude swoje możliwości (grupy narzędzi)." },
  { id: "persona", label: "Osobowość Alfreda", color: "#e879f9", nerve: "voice", folders: ["Tożsamość", "Charakter", "Zwroty"],
    info: "Kim jest Alfred: imię, jak się do Ciebie zwraca, charakter i sposób mówienia (config/persona.md)." },
];
REGIONS.forEach((r) => (r.rgb = new THREE.Color(r.color)));
const REGION = Object.fromEntries(REGIONS.map((r) => [r.id, r]));
const REGION_OF = { core: "core", user: "core", memory: "memory", topic: "knowledge", mcp: "mcp", tool: "mcp", skill: "tech",
                    routine: "tech", repo: "tech", test: "tech", module: "modules", capability: "modules", persona: "persona" };
const FOLDER_OF = { skill: "Umiejętności", routine: "Rutyny", repo: "Repozytorium", test: "Testy" };
const folderOf = (n) => n.kind === "tool" ? `mcp:${n.server}` : n.kind === "capability" ? `module:${n.id.slice(4).split(".")[0]}`
  : n.kind === "topic" ? n.path?.split("/")[1] : FOLDER_OF[n.kind] || n.group || "Inne";
const LABELLED = ["hub", "folder", "core", "user", "module", "mcp"];

const INFO = {
  user: ["Ty", "Mówisz lub piszesz. Alfred odpowiada głosem.", "wejście: głos / tekst"],
  ears: ["Uszy — mowa na tekst", "ElevenLabs Scribe zamienia nagranie na tekst i rozpoznaje język (PL/EN).", "audio → tekst + język"],
  router: ["Router — Jev", "Jedno szybkie zapytanie do Jev: moduł, możliwości (grupy narzędzi), umiejętność, temat z bazy wiedzy, pilność, czy akcja zmienia coś w świecie, czy potrzebna jest pamięć. Wszystkie kategorie pochodzą z mapy mózgu (brain_map/, OKF).", "tekst → trasa z prawdopodobieństwami"],
  executor: ["Wykonawca — Claude", "Claude dostaje tylko narzędzia wybranego modułu, jego prompt, procedurę umiejętności i briefing z pamięci. Wywołuje narzędzia w pętli aż do wyniku.", "trasa + tekst + briefing → wynik"],
  guard: ["Strażnik", "Akcje, które rezerwują, wysyłają lub kasują, czekają na Twoje „tak”. Pytanie jest czytane na głos.", "akcja → pytanie → tak / nie"],
  voice: ["Głos — Alfred", "Najpierw natychmiastowe „Już się tym zajmuję”, potem krótka odpowiedź do ucha (ElevenLabs TTS).", "wynik → mowa"],
  memory: ["Pamięć sesji — OKF", "Zadania ze statusami, podsumowania sesji, fakty i dziennik zmian w plikach markdown. Na starcie sesji powstaje z nich briefing: co otwarte, co się zmieniło.", "tury i akcje → pliki OKF → briefing"],
  proactive: ["Tryb proaktywny", "Zadania z terminem, cron i rutyny uruchamiają się same. Przy zadaniach Jev najpierw ocenia, czy warto Ci przerwać — dopiero potem budzi się Claude.", "zegar → bramka Jev → router"],
};
const KIND_INFO = {
  module: "Moduł — płat mózgu. Pierwsze pytanie routera Jev wybiera moduł.",
  capability: "Możliwość — grupa narzędzi i kategoria routera Jev. Claude dostaje tylko narzędzia wybranych możliwości.",
  skill: "Umiejętność — procedura krok po kroku. Jev może ją wybrać bezpośrednio; korzysta z podanych możliwości.",
  tool: "Narzędzie, które Claude może wywołać.",
  mcp: "Serwer — miejsce, gdzie żyją narzędzia (serwer MCP, wbudowane narzędzia Alfreda albo narzędzia serwerowe Claude).",
  topic: "Temat z Twojej bazy wiedzy. Jev może rozpoznać temat i skierować pytanie prosto do biblioteki.",
  repo: "Pakiet kodu mózgu (brain/).",
  test: "Plik testów pytest.",
  routine: "Rutyna — Alfred robi to sam o ustalonej porze albo przy starcie (config/routines.yaml).",
  persona: "Część osobowości Alfreda (config/persona.md, zakładka „Osobowość”).",
  memory: "Wpis w pamięci Alfreda (data/memory).",
  folder: "Folder w tej części mózgu.",
};

const RX = 250, RY = 185, RZ = 105, HZ = 95, BAND = (2 * RY) / (REGIONS.length - 1);
const bandY = (i) => -RY + (i - 0.5) * BAND;
const levelAt = (y) => Math.max(1, Math.min(REGIONS.length - 1, 1 + Math.floor((y + RY) / BAND)));
const widthAt = (y) => { const t = Math.min(1, Math.abs(y) / RY); return y < 0 ? Math.cbrt(1 - t ** 3) : Math.sqrt(1 - t * t); };
const STEM_TOP = new THREE.Vector3(-45, -RY * 0.55, 0), STEM_BOTTOM = new THREE.Vector3(-85, -RY * 1.95, 0);

function shell() {
  const pos = [], lvl = [];
  const fold = (x, y, z) => Math.sin(0.055 * x + 2.1 * Math.sin(0.042 * y)) + Math.sin(0.06 * y + 1.9 * Math.sin(0.037 * z))
    + Math.sin(0.05 * z + 2 * Math.sin(0.04 * x));
  for (let k = 0; lvl.length < 9000 && k < 4e5; k++) {
    const h = k % 2 ? 1 : -1, y = RY * (2 * Math.random() - 1), a = 2 * Math.PI * Math.random(), w = widthAt(y);
    const x = RX * w * Math.cos(a), z = h * HZ + RZ * w * Math.sin(a);
    if (h * z < 6 || Math.abs(fold(x, y, z)) > 0.55) continue;
    pos.push(x, y, z); lvl.push(levelAt(y));
  }
  for (let k = 0, n = 0; n < 1600 && k < 1e5; k++) {
    const u = 2 * Math.random() - 1, a = 2 * Math.PI * Math.random(), r = Math.sqrt(1 - u * u);
    const x = -RX * 0.7 + 80 * r * Math.cos(a), y = -RY * 0.95 + 52 * u, z = 150 * r * Math.sin(a);
    if (Math.abs(Math.sin(0.32 * y + 0.04 * x)) > 0.3) continue;
    pos.push(x, y, z); lvl.push(1); n++;
  }
  for (let k = 0; k < 1100; k++) {
    const s = Math.random(), a = 2 * Math.PI * Math.random(), p = STEM_BOTTOM.clone().lerp(STEM_TOP, s), r = 22 + 12 * s;
    pos.push(p.x + r * Math.cos(a), p.y, p.z + r * Math.sin(a)); lvl.push(0);
  }
  return { pos: new Float32Array(pos), lvl };
}

let el, scene, camera, renderer, composer, labels, controls, root, sphere, framed = false;
let nodes = [], nodesById = {}, links = [], linkIndex = new Map(), adjacency = {}, linkGeo, shellGeo, shellLvl, rings = [];
let sparkGeo, sparks = [], packets = [], hover = null, focus = null, peek = null, hooks = {}, frameNo = 0, talking = false;
const act = Object.fromEntries(REGIONS.map((r) => [r.id, 0])), busy = new Set();
const pairKey = (a, b) => (a < b ? `${a}|${b}` : `${b}|${a}`);

function setup() {
  renderer = new THREE.WebGLRenderer({ antialias: true });
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
  el.appendChild(renderer.domElement);
  labels = new CSS2DRenderer();
  labels.domElement.className = "labels";
  el.appendChild(labels.domElement);
  scene = new THREE.Scene();
  scene.background = new THREE.Color("#03050b");
  camera = new THREE.PerspectiveCamera(45, 1, 1, 8000);
  controls = new OrbitControls(camera, renderer.domElement);
  Object.assign(controls, { enableDamping: true, autoRotate: true, autoRotateSpeed: 0.35, minDistance: 150, maxDistance: 3000 });
  renderer.domElement.addEventListener("pointerdown", () => (controls.autoRotate = false));
  composer = new EffectComposer(renderer);
  composer.addPass(new RenderPass(scene, camera));
  composer.addPass(new UnrealBloomPass(new THREE.Vector2(256, 256), 0.9, 0.5, 0.1));
  composer.addPass(new OutputPass());
  sphere = new THREE.SphereGeometry(1, 16, 12);
  const additive = { vertexColors: true, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending };

  const { pos, lvl } = shell();
  shellLvl = lvl;
  shellGeo = new THREE.BufferGeometry();
  shellGeo.setAttribute("position", new THREE.BufferAttribute(pos, 3));
  shellGeo.setAttribute("color", new THREE.BufferAttribute(new Float32Array(pos.length), 3));
  scene.add(new THREE.Points(shellGeo, new THREE.PointsMaterial({ size: 3.2, ...additive })));
  rings = REGIONS.slice(1).map((r, i) => {
    const y = bandY(i + 1), w = widthAt(y) * 0.97, pts = [];
    for (let k = 0; k < 128; k++) { const a = (k / 128) * 2 * Math.PI; pts.push(new THREE.Vector3(RX * w * Math.cos(a), y, (HZ + RZ * w) * Math.sin(a))); }
    const ring = new THREE.LineLoop(new THREE.BufferGeometry().setFromPoints(pts),
      new THREE.LineBasicMaterial({ color: r.rgb.clone(), transparent: true, depthWrite: false, blending: THREE.AdditiveBlending }));
    ring.userData.region = r;
    scene.add(ring);
    return ring;
  });
  sparkGeo = new THREE.BufferGeometry();
  sparkGeo.setAttribute("position", new THREE.BufferAttribute(new Float32Array(3 * 500), 3));
  sparkGeo.setAttribute("color", new THREE.BufferAttribute(new Float32Array(3 * 500), 3));
  scene.add(new THREE.Points(sparkGeo, new THREE.PointsMaterial({ size: 5, ...additive })));

  const canvas = renderer.domElement, tip = document.getElementById("tip");
  let down = null;
  canvas.addEventListener("pointermove", (ev) => {
    hover = pick(ev);
    tip.classList.toggle("hidden", !hover);
    if (!hover) return;
    const folder = nodesById[hover.folder];
    tip.innerHTML = `${esc((INFO[hover.id] || [hover.label])[0])}<small>${esc(REGION[hover.region].label)}${folder ? " › " + esc(folder.label) : ""}</small>`;
    tip.style.left = `${ev.offsetX + 14}px`;
    tip.style.top = `${ev.offsetY + 10}px`;
  });
  canvas.addEventListener("pointerleave", () => { hover = null; tip.classList.add("hidden"); });
  canvas.addEventListener("pointerdown", (ev) => (down = [ev.clientX, ev.clientY]));
  canvas.addEventListener("pointerup", (ev) => {
    if (!down || Math.hypot(ev.clientX - down[0], ev.clientY - down[1]) > 5) return;
    const n = pick(ev);
    if (n) n.kind === "hub" ? showRegion(n.region) : showInfo(n);
  });
  new ResizeObserver(() => {
    const w = el.clientWidth, h = el.clientHeight;
    if (!w || !h) return;
    renderer.setSize(w, h); composer.setSize(w, h); labels.setSize(w, h);
    camera.aspect = w / h; camera.updateProjectionMatrix();
    if (!framed) { frame(); framed = true; }
  }).observe(el);
  requestAnimationFrame(loop);
}

function pick(ev) {
  const r = renderer.domElement.getBoundingClientRect(), v = new THREE.Vector3();
  let best = null, bestD = 14;
  for (const n of nodes) {
    v.copy(n.p).project(camera);
    if (v.z > 1) continue;
    const d = Math.hypot(((v.x + 1) / 2) * r.width - (ev.clientX - r.left), ((1 - v.y) / 2) * r.height - (ev.clientY - r.top));
    if (d < bestD) { bestD = d; best = n; }
  }
  return best;
}

function frame() {
  const center = new THREE.Vector3(0, -150, 0), radius = 400;
  const half = Math.min((camera.fov * Math.PI) / 360, Math.atan(Math.tan((camera.fov * Math.PI) / 360) * camera.aspect));
  camera.position.copy(center).add(new THREE.Vector3(0.62, 0.18, 0.76).multiplyScalar(radius / Math.sin(half)));
  controls.target.copy(center);
}

function label(n, cls, text = n.label) {
  const div = document.createElement("div");
  div.className = `lbl ${cls}`;
  div.textContent = text;
  div.style.setProperty("--c", REGION[n.region].color);
  const o = new CSS2DObject(div);
  o.position.copy(n.p).y -= n.size + 8;
  root.add(o);
  return o;
}

function build(g) {
  if (root) { [...root.children].forEach((o) => root.remove(o)); scene.remove(root); }
  root = new THREE.Group();
  scene.add(root);
  nodes = [{ id: "user", label: "Ty", kind: "user" }, ...g.nodes.map((n) => ({ ...n }))];
  nodesById = Object.fromEntries(nodes.map((n) => [n.id, n]));
  const add = (n) => (nodesById[n.id] ||= (nodes.push(n), n));
  const folder = (region, name) => add({ id: `folder:${region}:${name}`, label: name, kind: "folder", region });
  const raw = [...g.edges, { source: "user", target: "ears" }, { source: "voice", target: "user" }];
  REGIONS.slice(1).forEach((r) => {
    add({ id: `hub:${r.id}`, label: r.label, kind: "hub", region: r.id });
    raw.push({ source: r.nerve, target: `hub:${r.id}` });
    (r.folders || []).forEach((f) => folder(r.id, f));
  });
  nodes.forEach((n) => (n.region ||= REGION_OF[n.kind] || "tech"));
  for (const n of [...nodes]) {
    if (!LABELLED.includes(n.kind)) n.folder = nodesById[folderOf(n)] ? folderOf(n) : folder(n.region, folderOf(n)).id;
  }
  layout();

  links = []; linkIndex = new Map(); adjacency = {};
  const link = (a, b, tree) => {
    const key = pairKey(a, b);
    if (a === b || linkIndex.has(key) || !nodesById[a] || !nodesById[b]) return;
    linkIndex.set(key, links.length);
    links.push({ a: nodesById[a], b: nodesById[b], tree, fire: 0 });
    (adjacency[a] ||= []).push(b); (adjacency[b] ||= []).push(a);
  };
  nodes.forEach((n) => {
    if (n.folder) link(n.folder, n.id, true);
    if (n.kind === "folder" || n.kind === "module" || n.kind === "mcp") link(`hub:${n.region}`, n.id, true);
  });
  raw.forEach((e) => link(e.source, e.target, false));
  const lp = new Float32Array(links.length * 6);
  links.forEach((l, i) => { l.a.p.toArray(lp, i * 6); l.b.p.toArray(lp, i * 6 + 3); });
  linkGeo = new THREE.BufferGeometry();
  linkGeo.setAttribute("position", new THREE.BufferAttribute(lp, 3));
  linkGeo.setAttribute("color", new THREE.BufferAttribute(new Float32Array(lp.length), 3));
  root.add(new THREE.LineSegments(linkGeo, new THREE.LineBasicMaterial({ vertexColors: true, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending })));

  const SIZE = { user: 9, hub: 8, core: 6.5, module: 5.8, mcp: 5.8, folder: 5.2, capability: 3.4 };
  for (const n of nodes) {
    n.size = SIZE[n.kind] || 2.8;
    n.glow = 0;
    n.base = new THREE.Color(n.status === "error" ? "#fb7185" : REGION[n.region].color);
    n.dim = n.enabled === false || ["disabled", "missing", "offline"].includes(n.status) ||
      (n.kind === "capability" && n.available === 0 && n.label !== "Talk without tools");
    n.mesh = new THREE.Mesh(sphere, new THREE.MeshBasicMaterial({ color: n.base.clone() }));
    n.mesh.position.copy(n.p);
    root.add(n.mesh);
    n.lbl = label(n, n.kind === "hub" ? "hub" : LABELLED.includes(n.kind) ? "folder" : "item", (INFO[n.id]?.[0] || n.label).split(" — ")[0]);
  }

  const ol = document.getElementById("levels");
  ol.innerHTML = [...REGIONS].reverse().map((r) => `<li data-r="${r.id}" style="--c:${r.color}"><i></i>${esc(r.label)}</li>`).join("");
  ol.querySelectorAll("li").forEach((li) => {
    li.onmouseenter = () => (peek = li.dataset.r);
    li.onmouseleave = () => (peek = null);
    li.onclick = () => {
      focus = focus === li.dataset.r ? null : li.dataset.r;
      ol.querySelectorAll("li").forEach((x) => x.classList.toggle("focus", x.dataset.r === focus));
      if (focus) showRegion(focus);
    };
  });
}

function layout() {
  const fib = (j, m) => { const y = 1 - (2 * (j + 0.5)) / m, r = Math.sqrt(1 - y * y), a = j * 2.39996; return [Math.cos(a) * r, y, Math.sin(a) * r]; };
  const set = (n, x, y, z) => (n.p = new THREE.Vector3(x, y, z));
  const order = ["ears", "shield", "router", "proactive", "guard", "executor", "voice", "memory"];
  const rank = (n) => (order.indexOf(n.id) + 1) || 99;
  const core = nodes.filter((n) => n.kind === "core").sort((a, b) => rank(a) - rank(b));
  core.forEach((n, k) => {
    const p = STEM_BOTTOM.clone().lerp(STEM_TOP, 0.1 + (0.52 * k) / Math.max(1, core.length - 1)), a = k * 2.3;
    set(n, p.x + 38 * Math.cos(a), p.y, p.z + 38 * Math.sin(a));
  });
  set(nodesById.user, STEM_BOTTOM.x, STEM_BOTTOM.y - 70, 0);
  REGIONS.forEach((r, i) => {
    if (!i) return;
    const y = bandY(i), w = widthAt(y);
    set(nodesById[`hub:${r.id}`], 0, y, 0);
    const folders = nodes.filter((n) => n.region === r.id && ["folder", "module", "mcp"].includes(n.kind));
    folders.forEach((f, k) => {
      const a = i * 2.39996 + (2 * Math.PI * k) / folders.length;
      set(f, RX * w * 0.58 * Math.cos(a), y + (k % 2 ? 6 : -6), (HZ + RZ) * w * 0.58 * Math.sin(a));
      const kids = nodes.filter((n) => n.folder === f.id), rr = 10 + 5 * Math.sqrt(kids.length);
      kids.forEach((n, j) => { const [dx, dy, dz] = fib(j, kids.length); set(n, f.p.x + dx * rr, f.p.y + dy * rr * 0.4, f.p.z + dz * rr); });
    });
  });
  nodes.forEach((n) => (n.p ||= new THREE.Vector3()));
}

const SPARK = new THREE.Color(0.45, 0.47, 0.55);
function spark(l, color, reverse = Math.random() < 0.5) {
  if (sparks.length < 500) sparks.push({ l, t: 0, v: 1.3 + Math.random() * 1.5, reverse, c: color });
}

let last = performance.now();
function loop(now) {
  requestAnimationFrame(loop);
  const dt = Math.min(0.25, (now - last) / 1000), t = now / 1000, visible = el.clientWidth > 0;
  last = now;
  if (!nodes.length) return;
  for (const r of REGIONS) {
    act[r.id] *= Math.exp(-dt / 1.6);
    if (busy.has(r.id)) act[r.id] = Math.max(act[r.id], 0.45 + 0.15 * Math.sin(t * 4));
  }
  if (talking && nodesById.voice) {
    nodesById.voice.glow = Math.max(nodesById.voice.glow, 0.55 + 0.45 * Math.sin(t * 9));
    act.persona = Math.max(act.persona, 0.5 + 0.2 * Math.sin(t * 9));
  }
  const lens = peek || focus, dimOf = (region) => (lens && lens !== region ? 0.2 : 1);
  for (const n of nodes) {
    n.glow *= Math.exp(-dt / 0.9);
    n.lbl.visible = n.glow > 0.15 || (lens === n.region && (LABELLED.includes(n.kind) || focus === n.region)) ||
      (hover && (hover.id === n.folder || (hover.kind === "hub" && hover.region === n.region && LABELLED.includes(n.kind))));
    const k = (n.dim ? 0.25 : 0.45 + 0.4 * act[n.region]) + 1.1 * n.glow + (n === hover ? 0.6 : 0);
    n.mesh.material.color.copy(n.base).multiplyScalar(k * dimOf(n.region));
    n.mesh.scale.setScalar(n.size * (1 + 0.7 * n.glow + (n === hover ? 0.35 : 0)));
  }
  const lc = linkGeo.attributes.color.array;
  links.forEach((l, i) => {
    const a = Math.max(act[l.a.region], act[l.b.region]);
    if (Math.random() < (0.04 + 0.8 * a) * dt) { l.fire = 1; if (Math.random() < 0.4) spark(l, SPARK); }
    l.fire *= Math.exp(-dt / 0.22);
    const v = ((l.tree ? 0.035 : 0.015) + 0.02 * a + 0.25 * l.fire + (hover && (l.a === hover || l.b === hover) ? 0.35 : 0))
      * Math.min(dimOf(l.a.region), dimOf(l.b.region));
    lc.fill(v, i * 6, i * 6 + 6);
  });
  linkGeo.attributes.color.needsUpdate = true;
  const sp = sparkGeo.attributes.position.array, sc = sparkGeo.attributes.color.array, v = new THREE.Vector3();
  sparks = sparks.filter((s) => (s.t += s.v * dt) < 1);
  sparks.forEach((s, i) => {
    v.lerpVectors(s.l.a.p, s.l.b.p, s.reverse ? 1 - s.t : s.t).toArray(sp, i * 3);
    s.c.toArray(sc, i * 3);
  });
  sparkGeo.setDrawRange(0, sparks.length);
  sparkGeo.attributes.position.needsUpdate = sparkGeo.attributes.color.needsUpdate = true;
  for (const p of packets) {
    p.t += dt * 1.1;
    if (p.t >= 1) {
      const l = links[linkIndex.get(pairKey(p.hops[p.seg].id, p.hops[p.seg + 1].id))];
      if (l) { l.fire = 1; spark(l, p.color, l.a !== p.hops[p.seg]); }
      flash(p.hops[p.seg + 1].id); p.seg += 1; p.t = 0;
    }
    if (p.seg >= p.hops.length - 1) { p.done = true; continue; }
    const k = p.t < 0.5 ? 2 * p.t * p.t : 1 - (-2 * p.t + 2) ** 2 / 2;
    p.mesh.position.lerpVectors(p.hops[p.seg].p, p.hops[p.seg + 1].p, k);
  }
  packets.filter((p) => p.done).forEach((p) => { p.tag && p.mesh.remove(p.tag); root.remove(p.mesh); });
  packets = packets.filter((p) => !p.done);
  if (!visible) return;
  const col = shellGeo.attributes.color.array;
  for (let i = 0; i < shellLvl.length; i++) {
    const r = REGIONS[shellLvl[i]], k = (0.14 + 0.8 * act[r.id]) * dimOf(r.id);
    col[i * 3] = r.rgb.r * k; col[i * 3 + 1] = r.rgb.g * k; col[i * 3 + 2] = r.rgb.b * k;
  }
  shellGeo.attributes.color.needsUpdate = true;
  rings.forEach((ring) => ring.material.color.copy(ring.userData.region.rgb).multiplyScalar((0.18 + 0.9 * act[ring.userData.region.id]) * dimOf(ring.userData.region.id)));
  if (frameNo++ % 6 === 0) document.querySelectorAll("#levels li").forEach((li) => {
    li.style.setProperty("--a", act[li.dataset.r].toFixed(2));
    li.classList.toggle("on", act[li.dataset.r] > 0.25);
  });
  controls.update();
  composer.render();
  labels.render(scene, camera);
}

function path(from, to) {
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

function send(from, to, text, color = C.route) {
  const hops = path(from, to);
  if (!root || hops.length < 2) { if (hops.length) flash(hops[0]); return; }
  const c = new THREE.Color(color);
  const mesh = new THREE.Mesh(sphere, new THREE.MeshBasicMaterial({ color: c.clone().multiplyScalar(1.8) }));
  mesh.scale.setScalar(5);
  mesh.position.copy(nodesById[hops[0]].p);
  let tag = null;
  if (text) {
    const div = document.createElement("div");
    div.className = "lbl packet";
    div.style.setProperty("--c", color);
    div.textContent = short(text);
    tag = new CSS2DObject(div);
    tag.position.set(0, 3.2, 0);
    mesh.add(tag);
  }
  root.add(mesh);
  flash(hops[0]);
  packets.push({ mesh, tag, color: c, hops: hops.map((id) => nodesById[id]), seg: 0, t: 0 });
}

function flash(id) {
  const n = nodesById[id];
  if (!n?.mesh) return;
  n.glow = 1;
  act[n.region] = Math.max(act[n.region], 0.9);
  if (nodesById[n.folder]) nodesById[n.folder].glow = Math.max(nodesById[n.folder].glow, 0.5);
}

function card(html) {
  const c = document.getElementById("node-info");
  c.innerHTML = `<button class="x" aria-label="Zamknij">×</button>${html}`;
  c.classList.remove("hidden");
  c.querySelector(".x").onclick = () => c.classList.add("hidden");
  return c;
}

function showRegion(id) {
  const r = REGION[id];
  const folders = nodes.filter((n) => n.region === id && ["folder", "module", "mcp"].includes(n.kind))
    .map((f) => `${f.label} (${nodes.filter((n) => n.folder === f.id).length})`);
  const members = id === "core" ? nodes.filter((n) => n.region === "core").map((n) => (INFO[n.id]?.[0] || n.label).split(" — ")[0]) : folders;
  card(`<b style="color:${r.color}">${esc(r.label)}</b><p>${esc(r.info)}</p>` +
    (members.length ? `<p class="rel">${id === "core" ? "Węzły" : "Foldery"}: ${members.map(esc).join(", ")}</p>` : ""));
  nodes.filter((n) => n.region === id && LABELLED.includes(n.kind)).forEach((n) => flash(n.id));
}

function showInfo(n) {
  if (!n) return;
  if (n.kind === "hub") return showRegion(n.region);
  const facts = [];
  if (n.kind === "tool") facts.push(`serwer: ${n.server}`, `efekt: ${n.side_effect}`, n.confirm ? "wymaga Twojej zgody" : "bez zgody", n.status);
  if (n.kind === "capability") facts.push(`${n.available} narzędzi online`, n.confirm ? "wymaga zgody" : "");
  if (n.kind === "mcp") facts.push(`status: ${n.status}`);
  const [title, text, io] = INFO[n.id] || [n.label, [KIND_INFO[n.kind], n.description].filter(Boolean).join(" "), facts.filter(Boolean).join(" · ")];
  const rel = (adjacency[n.id] || []).filter((x) => !["router", "executor"].includes(x) && !x.startsWith("hub:"))
    .map((x) => nodesById[x].label).slice(0, 12);
  const where = [REGION[n.region].label, nodesById[n.folder]?.label].filter(Boolean).join(" › ");
  const c = card(`<span class="crumb" style="color:${REGION[n.region].color}">${esc(where)}</span><b>${esc(title)}</b><p>${esc(text)}</p>` +
    (io ? `<code>${esc(io)}</code>` : "") +
    (rel.length ? `<p class="rel">Połączony z: ${rel.map(esc).join(", ")}</p>` : "") +
    (n.path ? `<button class="link" data-map="${esc(n.path)}">Otwórz stronę w mapie →</button>` : "") +
    (n.mem_path ? `<button class="link" data-mem="${esc(n.mem_path)}">Otwórz w pamięci →</button>` : ""));
  c.querySelector("[data-map]")?.addEventListener("click", () => hooks.openPage?.(n.path));
  c.querySelector("[data-mem]")?.addEventListener("click", () => hooks.openMemory?.(n.mem_path));
  flash(n.id);
}

const C = { text: "#e2e8f0", route: "#60a5fa", tool: "#4ade80", voice: "#c084fc", warn: "#fb7185" };
const routeOf = {};
let flowFor = null;
const flow = () => document.getElementById("flow-steps");
let flowTokens = 0;
const fmt = (n) => n.toLocaleString("pl-PL");
const flowTotal = () => { document.getElementById("flow-total").textContent = flowTokens ? `Σ ${fmt(flowTokens)} tok.` : ""; };
const newFlow = (rid) => { if (rid !== flowFor) { flow().innerHTML = ""; flowFor = rid; flowTokens = 0; flowTotal(); } };
const sum = (u) => Object.values(u || {}).reduce((s, v) => s + (typeof v === "number" ? v : 0), 0);
const toolNode = (tool) => (nodesById[`tool:${tool}`] ? `tool:${tool}` : "memory");
const serverOf = (tool) => nodesById[`tool:${tool}`]?.server;

function step(title, detail, node, tokens = 0) {
  const li = document.createElement("li");
  li.innerHTML = `${tokens ? `<em>${fmt(tokens)} tok.</em>` : ""}<b>${esc(title)}</b>${detail ? `<span>${esc(detail)}</span>` : ""}`;
  flowTokens += tokens; flowTotal();
  li.onclick = () => node && showInfo(nodesById[node]);
  flow().appendChild(li);
  flow().querySelectorAll("li").forEach((x) => x.classList.remove("now"));
  li.classList.add("now");
  flow().scrollTop = 1e9;
}

function event(ev) {
  if (!root) return;
  const d = ev.data || {}, rid = ev.request_id;
  const mod = routeOf[rid] || "executor";
  switch (ev.kind) {
    case "listening":
      newFlow(rid);
      send("user", "ears", "nagranie audio", C.text);
      step("Uszy odbierają nagranie", `${Math.round((d.bytes || 0) / 1024)} KB audio → ElevenLabs Scribe`, "ears");
      break;
    case "transcript": {
      if (d.confirmation) { send("user", "guard", `„${d.text}”`, C.text); step("Twoja odpowiedź trafia do strażnika", `„${d.text}”`, "guard"); break; }
      newFlow(rid);
      if (d.source === "proactive" || d.source === "routine") {
        const routine = nodes.find((n) => n.kind === "routine" && n.prompt === d.text);
        send(routine ? routine.id : "proactive", "router", routine ? `rutyna ${routine.label}` : "zadanie z harmonogramu", C.route);
        step("Alfred zaczyna sam", short(d.text, 90), routine ? routine.id : "proactive");
        break;
      }
      send("user", "ears", `„${d.text}”`, C.text);
      setTimeout(() => send("ears", "shield", `tekst · ${d.language || ""}`, C.text), 450);
      step("1 · Uszy: mowa → tekst", `„${short(d.text, 90)}” (${d.language || "?"})`, "ears");
      break;
    }
    case "shield":
      send("shield", d.breach ? "voice" : "router", d.breach ? "zablokowano" : "czyste", d.breach ? C.warn : C.text);
      step(`1b · Osłona Jev (${d.source}, ${d.ms} ms)`, d.breach ? "prompt injection — zapytanie zatrzymane"
        : `bezpieczne${d.probability != null ? ` · ryzyko ${Math.round(d.probability * 100)}%` : ""}`, "shield", d.tokens);
      break;
    case "classified": {
      const target = `module:${d.module}`;
      routeOf[rid] = target;
      send("router", target, `${d.module} ${Math.round(d.confidence * 100)}%`, C.route);
      (d.also || []).forEach((m) => send("router", `module:${m}`, `${m} (też)`, C.route));
      (d.capabilities || []).forEach((cap, i) => setTimeout(() => send(target, `cap:${cap}`,
        `${cap.split(".")[1]} ${Math.round((d.capability_probabilities?.[cap] || 0) * 100) || ""}%`.replace(/ %$/, ""), C.route), 500 + i * 150));
      if (d.skill) setTimeout(() => send(target, `skill:${d.skill}`, "procedura", C.route), 500);
      if (d.topic) setTimeout(() => send("router", d.topic, "temat", C.text), 400);
      const top = Object.entries(d.probabilities || {}).sort((a, b) => b[1] - a[1]).slice(0, 3)
        .map(([k, v]) => `${k} ${Math.round(v * 100)}%`).join(" · ");
      step(`2 · Router (${d.source}, ${d.latency_ms} ms) → ${d.module}`,
        `${top}${d.capabilities?.length ? ` · możliwości: ${d.capabilities.join(", ")}` : " · wszystkie możliwości modułu"}${d.skill ? ` · umiejętność: ${d.skill}` : ""}${d.topic ? ` · temat: ${d.topic.replace("topic:", "")}` : ""} · pilność ${(+d.urgency || 0).toFixed(1)} · akcja w świecie ${Math.round((d.acts_on_world || 0) * 100)}%`, "router",
        (d.usage?.input_tokens || 0) + (d.usage?.output_tokens || 0));
      break;
    }
    case "action_check":
      send("shield", "executor", d.breach ? "zablokowano" : d.tool, d.breach ? C.warn : C.text);
      step(`Osłona akcji (${d.source}, ${d.ms} ms) → ${d.tool}`, d.breach ? "niebezpieczna — nie wykonano"
        : `bezpieczna${d.probability != null ? ` · ryzyko ${Math.round(d.probability * 100)}%` : ""}`, "shield", d.tokens);
      break;
    case "executor_start":
      busy.add("core"); busy.add(nodesById[mod]?.region || "modules");
      send(mod, "executor", `${(d.tools || []).length} narzędzi`, C.route);
      (d.capabilities || []).slice(0, 4).forEach((cap) => flash(`cap:${cap}`));
      send("memory", "executor", "briefing", C.text);
      flash("hub:persona");
      step(`4 · Claude (${d.model}, ${d.backend === "subscription" ? "subskrypcja" : "API"}, wysiłek ${d.effort}) zaczyna`, `moduły: ${(d.modules || []).join(", ")} · narzędzia: ${(d.tools || []).slice(0, 6).join(", ")}${(d.tools || []).length > 6 ? "…" : ""}`, "executor");
      break;
    case "llm_call":
      flash("executor");
      step(`Claude myśli (runda ${d.round + 1}, ${d.ms} ms)`, `${d.stop_reason === "tool_use" ? "chce użyć narzędzia" : d.stop_reason === "end_turn" ? "ma odpowiedź" : d.stop_reason} · in ${fmt(d.usage?.input ?? 0)} / out ${fmt(d.usage?.output ?? 0)}${d.usage?.cache_read ? ` / cache ${fmt(d.usage.cache_read)}` : ""}`, "executor", sum(d.usage));
      break;
    case "tool_call":
      send("executor", toolNode(d.tool), d.tool.split("__").pop(), C.tool);
      if (serverOf(d.tool)) setTimeout(() => send(toolNode(d.tool), `mcp:${serverOf(d.tool)}`, "wywołanie", C.tool), 900);
      if (/^(task|memory)_/.test(d.tool)) flash("hub:memory");
      step(`Narzędzie: ${d.tool}`, short(JSON.stringify(d.input || {}), 110), toolNode(d.tool));
      break;
    case "tool_result":
      send(serverOf(d.tool) ? `mcp:${serverOf(d.tool)}` : toolNode(d.tool), "executor", d.is_error ? "błąd" : `wynik · ${d.ms} ms`, d.is_error ? C.warn : C.tool);
      step(`Wynik ${d.tool.split("__").pop()}${d.is_error ? " (błąd)" : ""}`, short(d.preview, 110), toolNode(d.tool));
      break;
    case "confirm_request":
      send("executor", "guard", "wymaga zgody", C.warn);
      setTimeout(() => send("guard", "user", "„potwierdzasz?”", C.warn), 600);
      step("Strażnik pyta o zgodę", d.text, "guard");
      break;
    case "confirm_result":
      send("guard", "executor", d.approved ? "zgoda" : "odmowa", d.approved ? C.tool : C.warn);
      step(d.approved ? "Zgoda — Claude kontynuuje" : "Odmowa — akcja wstrzymana", d.tool, "guard");
      break;
    case "answer":
      busy.clear();
      send("executor", "voice", "odpowiedź", C.voice);
      setTimeout(() => send("voice", "user", `„${d.text}”`, C.voice), 650);
      send("executor", "memory", "zapis tury", C.text);
      flash("folder:persona:Charakter");
      step("5 · Odpowiedź głosem", `„${short(d.text, 110)}” · in ${d.usage?.input ?? 0} / out ${d.usage?.output ?? 0} / cache ${d.usage?.cache_read ?? 0}${d.cost_usd != null ? ` · $${d.cost_usd.toFixed(4)}` : ""}`, "voice");
      step("6 · Pamięć sesji", (d.actions || []).length ? `zapisane akcje: ${d.actions.join("; ")}` : "tura dopisana do sesji", "memory");
      break;
    case "session_started": flash("memory"); break;
    case "session_closed":
      flash("memory"); flash("folder:memory:Sesje");
      step("Sesja zapisana do pamięci (OKF)", d.title || "", "memory");
      break;
    case "proactive_gate":
      send("proactive", "router", `bramka ${Math.round(d.probability * 100)}%`, d.fired ? C.route : C.warn);
      step(d.fired ? "Bramka Jev: warto przerwać" : "Bramka Jev: nie teraz", `${d.task} (${d.trigger})`, "proactive");
      break;
    case "calendar_sync": flash("mcp:google-calendar"); break;
    case "heartbeat": flash("proactive"); break;
    case "persona_updated": flash("hub:persona"); break;
    case "mcp_status": flash("hub:mcp"); break;
    case "map_built": ["hub:modules", "hub:mcp", "hub:tech", "hub:knowledge"].forEach(flash); break;
    case "error":
      busy.clear();
      flash(ev.node);
      step("Błąd", d.message, ev.node);
      break;
  }
}

function demo() {
  const rid = "demo-" + Date.now();
  const E = (kind, node, data) => ({ kind, node, request_id: rid, data });
  const script = [
    [0, E("listening", "ears", { bytes: 48000 })],
    [900, E("transcript", "ears", { text: "Zarezerwuj stolik dla dwóch w Nolicie na piątek na dziewiętnastą", language: "pl" })],
    [1900, E("classified", "router", { module: "bookings", skill: "bookings.restaurant-table", capabilities: ["bookings.browse", "memory.recall", "research.web", "bookings.confirm", "calendar.write", "memory.remember", "tasks.manage"], capability_probabilities: { "bookings.browse": 0.71, "research.web": 0.12 }, confidence: 0.86, source: "jev", latency_ms: 180, urgency: 1.1, acts_on_world: 0.94, probabilities: { bookings: 0.86, calendar: 0.09, research: 0.05 }, also: [] })],
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

function init(g, h = {}) {
  hooks = h;
  el = document.getElementById("graph");
  if (!renderer) setup();
  build(g);
}

window.Brain3D = { init, event, demo, flash, showInfo: (id) => showInfo(nodesById[id]), speaking: (on) => (talking = on) };
