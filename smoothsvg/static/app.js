const $ = (id) => document.getElementById(id);
const views = $("views"), layers = [$("inLayer"), $("svgBox")];
let view = { x: 0, y: 0, k: 1 }, size = null, file = null, svg = "", timer = null, seq = 0;
const off = new Set(); // palette colors the user turned off

// One shared transform drives both layers, so zoom and pan stay in sync.
function apply() {
  const t = `translate(${view.x}px,${view.y}px) scale(${view.k})`;
  layers.forEach((l) => (l.style.transform = t));
}
function fit() {
  if (!size) return;
  const r = views.getBoundingClientRect();
  const w = document.body.classList.contains("wipe") ? r.width : r.width / 2;
  view.k = Math.min(w / size.w, r.height / size.h, 8) * 0.95;
  view.x = (w - size.w * view.k) / 2;
  view.y = (r.height - size.h * view.k) / 2;
  apply();
}

views.addEventListener("wheel", (e) => {
  e.preventDefault();
  const pane = e.target.closest(".pane");
  const r = (pane || views).getBoundingClientRect();
  const mx = e.clientX - r.left, my = e.clientY - r.top;
  const k = Math.min(Math.max(view.k * (e.deltaY < 0 ? 1.15 : 1 / 1.15), 0.02), 200);
  view.x = mx - ((mx - view.x) * k) / view.k;
  view.y = my - ((my - view.y) * k) / view.k;
  view.k = k;
  apply();
}, { passive: false });

let drag = null;
views.addEventListener("pointerdown", (e) => {
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
views.addEventListener("dblclick", fit);

async function run() {
  if (!file) return;
  const my = ++seq;
  $("stats").textContent = "Converting...";
  $("stats").classList.remove("err");
  const fd = new FormData();
  fd.append("file", file);
  fd.append("filter_speckle", $("speckle").value);
  fd.append("colors", $("colors").value);
  fd.append("disabled", [...off].join(","));
  fd.append("smooth", $("smooth").value);
  try {
    const res = await fetch("/api/convert", { method: "POST", body: fd });
    if (!res.ok) throw new Error((await res.json()).detail || res.statusText);
    const data = await res.json();
    if (my !== seq) return; // a newer run replaced this one
    svg = data.svg;
    $("svgBox").innerHTML = svg;
    const s = data.stats;
    $("stats").textContent = `${s.kb} KB | ${s.paths} paths | ${s.colors} colors | SSIM ${s.ssim} | ${s.ms} ms`;
    $("dl").disabled = $("cp").disabled = false;
    $("palette").replaceChildren(...data.palette.map(([hex, share]) => {
      const b = document.createElement("button");
      b.style.background = hex;
      b.title = `${hex} (${(share * 100).toFixed(1)}%)`;
      b.classList.toggle("off", off.has(hex));
      b.onclick = () => { off.has(hex) ? off.delete(hex) : off.add(hex); run(); };
      return b;
    }));
  } catch (e) {
    $("stats").textContent = e.message;
    $("stats").classList.add("err");
  }
}

function setFile(f) {
  if (!f) return;
  file = f;
  off.clear();
  $("drop").hidden = true;
  const img = $("inImg");
  img.onload = () => {
    size = { w: img.naturalWidth, h: img.naturalHeight };
    fit();
  };
  img.src = URL.createObjectURL(f);
  run();
}

$("file").onchange = (e) => setFile(e.target.files[0]);
window.addEventListener("dragover", (e) => e.preventDefault());
window.addEventListener("drop", (e) => { e.preventDefault(); setFile(e.dataTransfer.files[0]); });

[["speckle", "v_speckle"], ["colors", "v_colors"], ["smooth", "v_smooth"]].forEach(([i, v]) =>
  $(i).addEventListener("input", () => {
    $(v).textContent = $(i).value === "0" && i === "colors" ? "auto" : $(i).value;
    if (i === "colors") off.clear(); // palette changes, old picks no longer match
    clearTimeout(timer);
    timer = setTimeout(run, 300);
  }));

$("wipeBtn").onclick = () => {
  document.body.classList.toggle("wipe");
  $("wipe").hidden = !document.body.classList.contains("wipe");
  fit();
};
$("wipe").oninput = (e) => document.documentElement.style.setProperty("--wipe", e.target.value + "%");
$("themeBtn").onclick = () => {
  const d = document.documentElement;
  const dark = getComputedStyle(d).colorScheme.includes("dark") && d.dataset.theme !== "light";
  d.dataset.theme = dark ? "light" : "dark";
};
$("dl").onclick = () => {
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([svg], { type: "image/svg+xml" }));
  a.download = (file.name.replace(/\.\w+$/, "") || "image") + ".svg";
  a.click();
};
$("cp").onclick = () => navigator.clipboard.writeText(svg);
window.addEventListener("resize", fit);
