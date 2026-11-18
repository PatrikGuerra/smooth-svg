const $ = (id) => document.getElementById(id);
const views = $("views"), layers = [$("inLayer"), $("svgBox")];
let view = { x: 0, y: 0, k: 1 }, size = null, file = null, svg = "", timer = null, seq = 0;
let refUrl = null, showRef = false, lastResult = null, drawingLock = false;
let usePreset = true; // first run per image/model: let the model choose colors and smoothness
const off = new Set(); // palette colors the user turned off

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

function drawPalette(palette) {
  $("palette").replaceChildren(...palette.map(([hex, share]) => {
    const b = document.createElement("button");
    b.type = "button";
    b.style.background = hex;
    b.title = `${hex} (${(share * 100).toFixed(1)}%)`;
    b.setAttribute("aria-label", t(off.has(hex) ? "show_color" : "hide_color", { hex }));
    b.setAttribute("aria-pressed", off.has(hex));
    b.classList.toggle("off", off.has(hex));
    b.disabled = drawingLock;
    b.onclick = () => { off.has(hex) ? off.delete(hex) : off.add(hex); run(); };
    return b;
  }));
  $("paletteHint").hidden = !palette.length || drawingLock;
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
    if (id === "colors" || id === "merge") off.clear(); // palette changes, old picks no longer match
    later();
  });
  $(id + "_auto")?.addEventListener("change", () => {
    show(id);
    markLevel(null);
    if (id === "colors") off.clear();
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
  showAll();
  if (lastResult) { showResult(); drawPalette(lastResult.palette); } else setStatus(t("no_image"));
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

applyI18n();
showAll();
setStatus(t("no_image"));
