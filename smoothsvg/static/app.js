const $ = (id) => document.getElementById(id);
const views = $("views"), layers = [$("inLayer"), $("svgBox")];
let view = { x: 0, y: 0, k: 1 }, size = null, file = null, svg = "", timer = null, seq = 0;
let refUrl = null, showRef = false, lastResult = null, drawingLock = false;
let usePreset = true; // first run per image/model: let the model choose colors and smoothness
const off = new Set(); // palette colors the user turned off
let groups = []; // manual merges [{from:[hex..], to:hex, neo?}]; "neo" = final color picked freely, not one of `from`

// "Remove small spots" moves in steps, because 1 px and 1000 px both matter.
const SPOTS = [1, 4, 8, 16, 32, 64, 128, 256, 512, 1024];
const SLIDERS = ["colors", "merge", "smooth", "corner", "curve", "spots", "tol"];
const LOCKED_BY_DRAWING = ["colors", "merge", "corner", "curve", "spots", "tol", "ellipses", "polygons"];

// ---------- controls ----------

function isAuto(id) { return $(id + "_auto")?.checked ?? false; }

// value sent to the server: 0 means "decide for me" for the controls that have an Auto box
function val(id) {
  if (isAuto(id)) return 0;
  const v = +$(id).value;
  return id === "spots" ? SPOTS[v] : v;
}

function show(id) {
  const out = $("v_" + id);
  if (isAuto(id)) out.textContent = ""; // the ticked Auto box already says it
  else if (id === "spots") out.textContent = SPOTS[+$(id).value] + " px";
  else if (id === "tol") out.textContent = $(id).value + " %";
  else out.textContent = $(id).value;
  $(id).disabled = isAuto(id) || (drawingLock && LOCKED_BY_DRAWING.includes(id));
}

function showAll() { SLIDERS.forEach(show); }

function setAuto(id, on) { if ($(id + "_auto")) $(id + "_auto").checked = on; }

function nearestSpots(px) {
  let best = 0;
  SPOTS.forEach((v, i) => { if (Math.abs(Math.log(v / px)) < Math.abs(Math.log(SPOTS[best] / px))) best = i; });
  return best;
}

function markLevel(level) {
  document.querySelectorAll("#levels button").forEach((b) => b.setAttribute("aria-pressed", b.dataset.level === level));
}

// One "Detail" choice moves several controls together.
function setLevel(level) {
  markLevel(level);
  off.clear();
  groups = [];
  setAuto("colors", true);
  setAuto("corner", true);
  if (level === "balanced") {
    usePreset = true; // colors and smoothness come from the image type again
    $("merge").value = 10;
    setAuto("curve", true);
    setAuto("spots", true);
  } else {
    usePreset = false;
    const simple = level === "simple";
    $("smooth").value = simple ? 4 : 1;
    $("merge").value = simple ? 20 : 6;
    setAuto("curve", false);
    $("curve").value = simple ? 10 : 1;
    setAuto("spots", false);
    const pixels = size ? size.w * size.h : 1e6;
    $("spots").value = simple ? nearestSpots(Math.max(16, pixels * 0.0005)) : 1;
  }
  showAll();
  run();
}

function resetAll() {
  $("model").value = "auto";
  $("bg").checked = false;
  $("denoise").checked = true;
  $("ellipses").checked = true;
  $("polygons").checked = false;
  $("tol").value = 3;
  setLevel("balanced");
}

function setDrawingLock(on) {
  drawingLock = on;
  $("drawingNote").hidden = !on;
  document.querySelectorAll("[data-locks]").forEach((el) => el.classList.toggle("muted", on));
  ["ellipses", "polygons", "colors_auto", "corner_auto", "curve_auto", "spots_auto"].forEach((id) => ($(id).disabled = on));
  showAll();
}

// ---------- view: zoom and pan ----------

// One shared transform drives both layers, so zoom and pan stay in sync.
function apply() {
  const tr = `translate(${view.x}px,${view.y}px) scale(${view.k})`;
  layers.forEach((l) => (l.style.transform = tr));
  $("zoomPct").textContent = Math.round(view.k * 100) + "%";
}

function paneWidth() {
  const r = views.getBoundingClientRect();
  return document.body.classList.contains("wipe") ? r.width : r.width / 2;
}

function fit() {
  if (!size) return;
  const h = views.getBoundingClientRect().height, w = paneWidth();
  view.k = Math.min(w / size.w, h / size.h, 8) * 0.95;
  view.x = (w - size.w * view.k) / 2;
  view.y = (h - size.h * view.k) / 2;
  apply();
}

function zoomAt(mx, my, factor) {
  const k = Math.min(Math.max(view.k * factor, 0.02), 200);
  view.x = mx - ((mx - view.x) * k) / view.k;
  view.y = my - ((my - view.y) * k) / view.k;
  view.k = k;
  apply();
}

function zoomCenter(factor) { zoomAt(paneWidth() / 2, views.getBoundingClientRect().height / 2, factor); }

views.addEventListener("wheel", (e) => {
  if (!file) return;
  e.preventDefault();
  const r = (e.target.closest(".pane") || views).getBoundingClientRect();
  zoomAt(e.clientX - r.left, e.clientY - r.top, e.deltaY < 0 ? 1.15 : 1 / 1.15);
}, { passive: false });

let drag = null;
views.addEventListener("pointerdown", (e) => {
  if (!file || e.target.closest("#drop, .zoombar")) return; // let their buttons get the click
  drag = { x: e.clientX - view.x, y: e.clientY - view.y };
  views.setPointerCapture(e.pointerId);
});
views.addEventListener("pointermove", (e) => {
  if (!drag) return;
  view.x = e.clientX - drag.x;
  view.y = e.clientY - drag.y;
  apply();
});
views.addEventListener("pointerup", () => (drag = null));
views.addEventListener("dblclick", (e) => { if (!e.target.closest(".zoombar")) fit(); });
$("zoomIn").onclick = () => zoomCenter(1.4);
$("zoomOut").onclick = () => zoomCenter(1 / 1.4);
$("zoomFit").onclick = fit;

function setWipe(on) {
  document.body.classList.toggle("wipe", on);
  $("viewSide").setAttribute("aria-pressed", !on);
  $("viewWipe").setAttribute("aria-pressed", on);
  $("wipe").hidden = !on;
  fit();
}
$("viewSide").onclick = () => setWipe(false);
$("viewWipe").onclick = () => setWipe(true);
$("wipe").oninput = (e) => document.documentElement.style.setProperty("--wipe", e.target.value + "%");

// ---------- conversion ----------

function kb(bytes) { return bytes >= 1024 * 1024 ? (bytes / 1024 / 1024).toFixed(1) + " MB" : Math.round(bytes / 1024) + " KB"; }

function setLoading(on) {
  document.body.classList.toggle("loading", on);
  $("status").classList.toggle("busy", on);
}

function setStatus(text, isError = false) {
  $("sizes").textContent = text;
  $("fid").textContent = "";
  $("status").title = "";
  $("status").classList.toggle("err", isError);
}

function showResult() {
  if (!lastResult) return;
  const { stats: s, used } = lastResult;
  $("sizes").textContent = `${kb(file.size)} → ${s.kb >= 1024 ? (s.kb / 1024).toFixed(1) + " MB" : Math.round(s.kb * 10) / 10 + " KB"}`;
  $("fid").textContent = "· " + t("fidelity", { p: Math.round(s.ssim * 100) });
  $("status").title = t("more", s);
  $("status").classList.remove("err");
  $("usedModel").textContent = t("using", { m: t("m_" + used.model) });
  $("refBtn").textContent = t(showRef ? "showing_ref" : "showing_mine");
}

function drawPalette(palette) { // view only: turning colors on and off lives in the Colors panel
  $("palette").replaceChildren(...palette.map(([hex, share]) => {
    const b = document.createElement("span");
    b.style.background = hex;
    b.title = `${hex} (${(share * 100).toFixed(1)}%)`;
    b.classList.toggle("off", off.has(hex));
    return b;
  }));
  $("paletteHint").hidden = !palette.length || drawingLock;
  $("mergeBtn").disabled = drawingLock || !palette.length;
  $("mergeBtn").title = drawingLock ? t("mg_off") : "";
}
async function run() {
  if (!file) return;
  const my = ++seq;
  setLoading(true);
  setStatus(t("converting"));
  const fd = new FormData();
  fd.append("file", file);
  fd.append("model", $("model").value);
  fd.append("preset", usePreset);
  fd.append("colors", val("colors"));
  fd.append("merge_de", val("merge"));
  fd.append("smooth", val("smooth"));
  fd.append("corner", val("corner"));
  fd.append("detail", val("curve"));
  fd.append("min_area", val("spots"));
  fd.append("shape_tol", val("tol"));
  fd.append("disabled", [...off].join(","));
  fd.append("merge_groups", groups.length ? JSON.stringify(groups.map(({ from, to }) => ({ from, to }))) : "");
  fd.append("remove_bg", $("bg").checked);
  fd.append("denoise", $("denoise").checked);
  fd.append("ellipses", $("ellipses").checked);
  fd.append("polygons", $("polygons").checked);
  try {
    let res;
    try { res = await fetch("/api/convert", { method: "POST", body: fd }); }
    catch { throw new Error(t("err_net")); }
    if (!res.ok) {
      const detail = (await res.json().catch(() => ({}))).detail || res.statusText;
      throw new Error(res.status === 413 ? t("err_big") : t("err_bad", { d: detail }));
    }
    const data = await res.json();
    if (my !== seq) return; // a newer run replaced this one
    svg = data.svg;
    showRef = false;
    $("svgBox").innerHTML = svg;
    if (usePreset) { // show what the image type picked, then hand control to the sliders
      setAuto("colors", !data.used.colors);
      if (data.used.colors) $("colors").value = data.used.colors;
      $("smooth").value = data.used.smooth;
      usePreset = false;
    }
    lastResult = data;
    setDrawingLock(data.used.model === "drawing");
    showResult();
    drawPalette(data.palette);
    renderMerge();
    $("dl").disabled = $("cp").disabled = false;
    document.body.dataset.ready = "1";
  } catch (e) {
    if (my !== seq) return;
    setStatus(e.message, true);
  } finally {
    if (my === seq) setLoading(false); // only the newest request ends the loading state
  }
}

function later() { clearTimeout(timer); timer = setTimeout(run, 300); }

function setFile(f) {
  if (!f) return;
  if (!/^image\/(png|jpeg)$/.test(f.type)) { setStatus(t("err_bad", { d: f.name || f.type }), true); return; }
  file = f;
  usePreset = true;
  off.clear();
  groups = [];
  markLevel("balanced");
  $("drop").hidden = true;
  $("zoombar").hidden = false;
  const img = $("inImg");
  img.onload = () => {
    size = { w: img.naturalWidth, h: img.naturalHeight };
    fit();
  };
  img.src = URL.createObjectURL(f);
  run();
}

// ---------- events ----------

$("file").onchange = (e) => setFile(e.target.files[0]);
$("file2").onchange = (e) => setFile(e.target.files[0]);
window.addEventListener("dragover", (e) => { e.preventDefault(); document.body.classList.add("dragging"); });
window.addEventListener("dragleave", () => document.body.classList.remove("dragging"));
window.addEventListener("drop", (e) => {
  e.preventDefault();
  document.body.classList.remove("dragging");
  setFile(e.dataTransfer.files[0]);
});
window.addEventListener("paste", (e) => {
  const item = [...(e.clipboardData?.items || [])].find((i) => /^image\/(png|jpeg)$/.test(i.type));
  if (item) setFile(item.getAsFile());
});
window.addEventListener("keydown", (e) => {
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "s") {
    e.preventDefault();
    if (svg) $("dl").click();
  }
});

// the sample logo comes from branding/ in the repository; hide the button if it is missing
fetch("/sample.png", { method: "HEAD" }).then((r) => { $("sample").hidden = !r.ok; }).catch(() => {});
$("sample").onclick = async () => {
  const blob = await (await fetch("/sample.png")).blob();
  setFile(new File([blob], "Logo+name.png", { type: "image/png" }));
};

SLIDERS.forEach((id) => {
  $(id).addEventListener("input", () => {
    show(id);
    markLevel(null); // hand-tuned: no level button is pressed any more
    if (id === "colors" || id === "merge") { off.clear(); groups = []; } // palette changes, old picks no longer match
    later();
  });
  $(id + "_auto")?.addEventListener("change", () => {
    show(id);
    markLevel(null);
    if (id === "colors") { off.clear(); groups = []; }
    run();
  });
});
document.querySelectorAll("#levels button").forEach((b) => (b.onclick = () => setLevel(b.dataset.level)));
["bg", "denoise", "ellipses", "polygons"].forEach((id) => ($(id).onchange = run));
$("model").onchange = () => setLevel("balanced");
$("reset").onclick = resetAll;

// Reference SVG is drawn through <img>, so any script inside it cannot run.
$("ref").onchange = (e) => {
  const f = e.target.files[0];
  if (!f) return;
  if (refUrl) URL.revokeObjectURL(refUrl);
  refUrl = URL.createObjectURL(f.slice(0, f.size, "image/svg+xml"));
  $("refBtn").hidden = false;
  showRef = false;
  $("refBtn").click();
};
$("refBtn").onclick = () => {
  if (!refUrl || !svg) return;
  showRef = !showRef;
  $("refBtn").textContent = t(showRef ? "showing_ref" : "showing_mine");
  $("svgBox").innerHTML = showRef ? `<img src="${refUrl}" width="${size.w}" height="${size.h}" alt="">` : svg;
};

$("themeBtn").onclick = () => {
  const d = document.documentElement;
  const dark = d.dataset.theme ? d.dataset.theme === "dark" : matchMedia("(prefers-color-scheme: dark)").matches;
  d.dataset.theme = dark ? "light" : "dark";
};
$("lang").value = LANG;
$("lang").onchange = (e) => {
  setLang(e.target.value);
  showUpd();
  showAll();
  if (lastResult) { showResult(); drawPalette(lastResult.palette); renderMerge(); } else setStatus(t("no_image"));
};
$("dl").onclick = () => {
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([svg], { type: "image/svg+xml" }));
  a.download = (file.name.replace(/\.\w+$/, "") || "image") + ".svg";
  a.click();
};
$("cp").onclick = async () => {
  await navigator.clipboard.writeText(svg);
  $("cp").textContent = t("copied");
  setTimeout(() => ($("cp").textContent = t("copy")), 1500);
};
window.addEventListener("resize", fit);

// Auto update: only the desktop app serves /api/update; under --ui it is a 404 and nothing shows.
let updVersion = null;
function showUpd() { if (updVersion) $("updmsg").textContent = t("upd_avail", { v: updVersion }); }
async function updPoll(tries = 0) {
  let s;
  try {
    const r = await fetch("/api/update");
    if (!r.ok) return;
    s = await r.json();
  } catch { return; }
  if (s.disabled_by_env) return;
  $("updOpt").hidden = false;
  $("updCheck").checked = s.check_updates;
  if (s.update) { updVersion = s.update.version; showUpd(); $("updbar").hidden = false; }
  else if (!s.checked && s.check_updates && tries < 10) setTimeout(() => updPoll(tries + 1), 3000);
}
$("updCheck").onchange = (e) =>
  fetch("/api/update/settings", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ check_updates: e.target.checked }) });
$("updLater").onclick = () => ($("updbar").hidden = true);
$("updNow").onclick = async () => {
  $("updNow").disabled = $("updLater").disabled = true;
  $("updmsg").textContent = t("upd_busy");
  let ok = false;
  try { ok = (await fetch("/api/update/install", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ confirm: true }) })).ok; } catch { /* app may already be closing */ }
  if (ok) return; // the app closes itself once the installer has started
  $("updmsg").textContent = t("upd_fail");
  $("updNow").disabled = $("updLater").disabled = false;
};
updPoll();

// ---------- Colors panel (floating, not modal) ----------
// Turns colors on or off and joins them. Every change shows in the preview by itself.
// The server applies the groups after its own automatic merge, on the colors left over.
// shortcut: groups are flat and only join colors of the server's base palette, so no group
// contains another group; undo a group to change it.

const mgChecked = new Set();
let mgOpener = null, mgTimer = null, mgSig = "";

const mgIsOpen = () => !$("mgDlg").hidden;

function swatch(hex, small) {
  const s = document.createElement("span");
  s.className = small ? "sw sm" : "sw";
  s.style.background = hex;
  return s;
}

function mgSwitch(hex, key) {
  const sw = document.createElement("input");
  sw.type = "checkbox";
  sw.setAttribute("role", "switch");
  sw.checked = !off.has(hex);
  sw.disabled = drawingLock;
  sw.dataset.k = key;
  sw.setAttribute("aria-label", t("show_color", { hex }));
  sw.onchange = () => { sw.checked ? off.delete(hex) : off.add(hex); mgChanged(); };
  return sw;
}

// the panel changes at once; the preview follows after a short pause (run() keeps only the newest)
function mgChanged() {
  renderMerge();
  clearTimeout(mgTimer);
  mgTimer = setTimeout(run, 250);
}

function moveOff(from, to) { if (off.delete(from)) off.add(to); }

function renderMerge() {
  if (!mgIsOpen() || !lastResult) return;
  const taken = new Set(groups.flatMap((g) => g.from));
  const plain = lastResult.base.filter(([h]) => !taken.has(h));
  [...mgChecked].forEach((c) => { if (!plain.some(([h]) => h === c)) mgChecked.delete(c); });
  const sig = JSON.stringify([lastResult.base, groups, [...off], [...mgChecked], drawingLock, LANG]);
  if (sig === mgSig) return; // nothing to redraw: keeps a color picker that is open
  mgSig = sig;
  const key = document.activeElement?.dataset?.k;
  $("mgNote").hidden = !drawingLock;
  $("mgColors").replaceChildren(...plain.map(([hex, share]) => {
    const li = document.createElement("li"), lab = document.createElement("label"), cb = document.createElement("input");
    li.classList.toggle("off", off.has(hex));
    lab.className = "pick";
    cb.type = "checkbox";
    cb.checked = mgChecked.has(hex);
    cb.disabled = drawingLock;
    cb.dataset.k = "t" + hex;
    cb.setAttribute("aria-label", t("mg_tick", { hex }));
    cb.onchange = () => { cb.checked ? mgChecked.add(hex) : mgChecked.delete(hex); renderMerge(); };
    lab.append(cb, swatch(hex), `${hex} · ${(share * 100).toFixed(1)}%`);
    li.append(lab, mgSwitch(hex, "s" + hex));
    return li;
  }));
  $("mgAdd").disabled = drawingLock || mgChecked.size < 2;
  $("mgReset").disabled = !groups.length && !off.size;
  $("mgGroups").replaceChildren(...(groups.length ? groups.map((g, i) => {
    const li = document.createElement("li"), undo = document.createElement("button"), box = document.createElement("div");
    li.className = "grp";
    li.classList.toggle("off", off.has(g.to));
    box.className = "opts";
    box.setAttribute("role", "radiogroup");
    box.setAttribute("aria-label", t("mg_final"));
    const area = new Map(lastResult.base);
    const sorted = [...g.from].sort((x, y) => (area.get(y) ?? 0) - (area.get(x) ?? 0)); // biggest area first; stable
    const pick = (hex, neo) => {
      const old = g.to;
      g.neo = neo;
      g.to = hex;
      moveOff(old, g.to);
      mgChanged();
    };
    const btns = sorted.map((h, j) => {
      const b = document.createElement("button"), on = !g.neo && g.to === h;
      b.type = "button";
      b.className = "opt";
      b.setAttribute("role", "radio");
      b.setAttribute("aria-checked", on);
      b.tabIndex = on || (g.neo && j === 0) ? 0 : -1;
      b.dataset.k = "o" + i + h;
      b.disabled = drawingLock;
      b.setAttribute("aria-label", `${h} ${((area.get(h) ?? 0) * 100).toFixed(1)}%`);
      const dot = document.createElement("span"), pc = document.createElement("span"), tag = document.createElement("span");
      dot.className = "dot";
      dot.style.background = h;
      pc.textContent = `${h} ${((area.get(h) ?? 0) * 100).toFixed(1)}%`;
      tag.className = "mtag";
      tag.textContent = on ? t("mg_main") : "";
      b.append(dot, pc, tag);
      b.onclick = () => pick(h, false);
      b.onkeydown = (e) => {
        const d = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 }[e.key];
        if (!d) return;
        e.preventDefault();
        const n = btns[(j + d + btns.length) % btns.length];
        n.focus();
        pick(sorted[btns.indexOf(n)], false);
      };
      return b;
    });
    // the "+" swatch: a free color; once picked it becomes the main color
    const plus = document.createElement("label"), pd = document.createElement("span"), c = document.createElement("input"), pt = document.createElement("span");
    plus.className = "opt plus";
    plus.classList.toggle("on", !!g.neo);
    pd.className = "dot";
    pd.append(g.neo ? "" : "+");
    if (g.neo) pd.style.background = g.to;
    pt.className = "mtag";
    pt.textContent = g.neo ? t("mg_main") : t("mg_new_color");
    c.type = "color";
    c.value = (g.neo ? g.to : sorted[0]).toLowerCase();
    c.dataset.k = "c" + i;
    c.disabled = drawingLock;
    c.setAttribute("aria-label", t("mg_new_color"));
    c.oninput = () => { // no redraw here: it would close the open picker
      const old = g.to;
      g.neo = true;
      g.to = c.value.toUpperCase();
      moveOff(old, g.to);
      pd.style.background = g.to;
      pd.firstChild?.nodeType === 3 && pd.firstChild.remove();
      plus.classList.add("on");
      pt.textContent = t("mg_main");
      btns.forEach((b) => { b.setAttribute("aria-checked", false); b.lastChild.textContent = ""; });
      mgSig = JSON.stringify([lastResult.base, groups, [...off], [...mgChecked], drawingLock, LANG]);
      clearTimeout(mgTimer);
      mgTimer = setTimeout(run, 250);
    };
    pd.append(c);
    plus.append(pd, pt);
    box.append(...btns, plus);
    li.append(box);
    undo.type = "button";
    undo.textContent = t("mg_undo");
    undo.dataset.k = "u" + i;
    undo.disabled = drawingLock;
    undo.onclick = () => { if (g.neo) off.delete(g.to); groups.splice(i, 1); mgChanged(); };
    li.append(mgSwitch(g.to, "g" + i), undo);
    return li;
  }) : [Object.assign(document.createElement("li"), { textContent: t("mg_none"), className: "hint" })]));
  if (key) document.querySelector(`#mgDlg [data-k="${CSS.escape(key)}"]`)?.focus();
}

// keep the title bar on screen; the position lasts for this browser session
function mgPlace(x, y) {
  if (x === undefined) {
    try { [x, y] = JSON.parse(sessionStorage.getItem("mgPos")) ?? []; } catch { /* no saved position */ }
    if (x === undefined) return;
  }
  x = Math.min(Math.max(0, x), innerWidth - 80);
  y = Math.min(Math.max(0, y), innerHeight - 40);
  $("mgDlg").style.setProperty("--mx", x + "px");
  $("mgDlg").style.setProperty("--my", y + "px");
  try { sessionStorage.setItem("mgPos", JSON.stringify([x, y])); } catch { /* storage blocked */ }
}

function openMerge() {
  if (!lastResult) return;
  mgOpener = document.activeElement;
  mgChecked.clear();
  mgSig = "";
  $("mgDlg").hidden = false;
  mgPlace();
  renderMerge();
  $("mgDlg").focus();
}

function closeMerge() {
  $("mgDlg").hidden = true;
  mgOpener?.focus();
}

$("mergeBtn").onclick = () => (mgIsOpen() ? closeMerge() : openMerge());
$("mgClose").onclick = closeMerge;
$("mgAdd").onclick = () => {
  const from = lastResult.base.map(([h]) => h).filter((h) => mgChecked.has(h)); // base is sorted by area
  groups.push({ from, to: from[0] }); // the largest one is the default final color
  mgChecked.clear();
  mgChanged();
};
$("mgReset").onclick = () => { groups = []; off.clear(); mgChecked.clear(); mgChanged(); };

let mgDrag = null;
$("mgBar").addEventListener("pointerdown", (e) => {
  if (e.target.closest("button")) return;
  const r = $("mgDlg").getBoundingClientRect();
  mgDrag = { x: e.clientX - r.left, y: e.clientY - r.top };
  $("mgBar").setPointerCapture(e.pointerId);
});
$("mgBar").addEventListener("pointermove", (e) => { if (mgDrag) mgPlace(e.clientX - mgDrag.x, e.clientY - mgDrag.y); });
$("mgBar").addEventListener("pointerup", () => (mgDrag = null));
$("mgBar").addEventListener("keydown", (e) => { // the same move for keyboard users
  const d = { ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1] }[e.key];
  if (!d || e.target !== $("mgBar")) return;
  e.preventDefault();
  const r = $("mgDlg").getBoundingClientRect(), step = e.shiftKey ? 80 : 20;
  mgPlace(r.left + d[0] * step, r.top + d[1] * step);
});
document.addEventListener("keydown", (e) => { if (e.key === "Escape" && mgIsOpen() && !e.defaultPrevented) closeMerge(); });
window.addEventListener("resize", () => { if (mgIsOpen()) mgPlace(); });

applyI18n();
showAll();
setStatus(t("no_image"));
