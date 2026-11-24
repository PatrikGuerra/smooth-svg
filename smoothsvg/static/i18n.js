// Page text in English (en-US) and Brazilian Portuguese (pt-BR).
// Elements use data-i18n (text), data-i18n-title (tooltip), data-i18n-label (aria-label)
// and data-tip-key (the "?" help bubble). app.js calls t() for text it builds itself.
const I18N = {
  en: {
    open: "Open image", sample: "Try with the logo", view: "View", side: "Side by side", wipe: "Wipe",
    compare: "Compare with an SVG…", compare_tip: "Load an SVG made by another tool and switch between the two.",
    showing_mine: "Showing: mine", showing_ref: "Showing: reference",
    lang: "Language", theme: "Switch between light and dark theme",
    level: "Detail", simple: "Simple", balanced: "Balanced", detailed: "Detailed",
    level_tip: "Sets several controls at once. Simple: fewer colors and rounder edges. Balanced: what the image type suggests. Detailed: keeps more of the picture.",
    sec_image: "Image", model: "Type of image",
    model_tip: "Auto looks at the picture and picks one. Logo: flat colors. Line drawing: dark lines on a light background. Pixel art: small images made of square pixels. Photo: best effort.",
    m_auto: "Auto", m_clipart: "Logo / clipart", m_drawing: "Line drawing", m_pixelart: "Pixel art", m_photo: "Photo",
    using: "Using: {m}",
    bg: "Remove background", bg_tip: "Makes the color around the edge of the picture transparent.",
    noise: "Clean noise", noise_tip: "Smooths out JPG noise before the colors are picked. Turn it off for crisp pixel art.",
    soft: "Soft edges", soft_tip: "Uses the soft, antialiased edge pixels of your picture to place each edge, so curves come out smoother. Turn it off to cut the edges from the flat colors only.",
    drawing_note: "Line drawing traces one ink shape, so the color, corner, file size, spot and shape controls are not used.",
    sec_colors: "Colors", colors: "Number of colors",
    colors_tip: "How many flat colors the SVG uses. Auto picks the smallest number that still looks right.",
    merge: "Join similar colors", merge_tip: "Colors closer than this become one. Higher means fewer colors.",
    palette_hint: "To hide or join colors, open Edit colors.",
    hide_color: "Hide {hex}", show_color: "Show {hex}",
    mg_open: "Edit colors…", mg_off: "Not available for line drawings.",
    mg_title: "Colors", mg_help: "Turn colors on or off. To join colors, tick two or more and press Join. The preview updates by itself.",
    mg_move: "Drag to move. Arrow keys also move it.", mg_close: "Close",
    mg_final: "Main color of the group", mg_main: "main", mg_new: "A new color…", mg_new_color: "Other color",
    mg_add: "Join ticked colors", mg_groups: "Joined colors", mg_none: "Nothing joined yet.", mg_undo: "Undo",
    mg_reset: "Back to default", mg_tick: "Pick {hex}",
    sec_edges: "Edges", smooth: "Smoothness", smooth_tip: "Higher gives rounder edges and drops more tiny details.",
    corner: "Sharp corners", corner_tip: "Bends sharper than this angle stay pointed. Auto follows Smoothness.",
    curve: "Smaller file", curve_tip: "Higher uses fewer curve points: a smaller file, a little less exact.",
    spots: "Remove small spots", spots_tip: "Spots smaller than this many pixels melt into the color around them.",
    sec_shapes: "Shapes", ellipses: "Exact circles and ellipses", ellipses_tip: "Round blobs become perfect circles and ellipses.",
    polygons: "Exact straight-edge shapes", polygons_tip: "Blobs with 3 to 8 straight sides become perfect polygons. Can flatten curvy pixel art.",
    tol: "Shape match", tol_tip: "How far a blob may differ from a perfect shape and still be replaced. Low is strict.",
    auto: "Auto", reset: "Back to default",
    keys: "Wheel: zoom · Drag: move · Double click: fit · Ctrl+V: paste an image · Ctrl+S: download",
    input: "Input", zoom_in: "Zoom in", zoom_out: "Zoom out", fit: "Fit", in_view: "Input view", in_orig: "Original", in_reduced: "Reduced colors", in_up: "Upscaled",
    in_down: "Shown smaller than the real image (over 8 MP)", wipe_pos: "Wipe position",
    drop_title: "Drop a PNG or JPG here", drop_sub: "It becomes a small, smooth SVG. Nothing leaves your computer.",
    drop_paste: "You can also paste an image with Ctrl+V.",
    download: "Download SVG", copy: "Copy SVG", copied: "Copied",
    upd_avail: "Version {v} is available.", upd_now: "Update", upd_later: "Later", upd_busy: "Downloading the update.",
    upd_fail: "The update failed. You can keep using this version.", upd_check: "Check for updates on start",
    no_image: "No image yet", converting: "Converting…", fidelity: "Fidelity {p} %",
    more: "{paths} paths · {colors} colors · {shapes} exact shapes · SSIM {ssim} · {ms} ms",
    err_big: "The file is over 20 MB.", err_bad: "This file could not be used: {d}",
    err_net: "The server did not answer. Is it still running?",
  },
  pt: {
    open: "Abrir imagem", sample: "Testar com o logo", view: "Visualização", side: "Lado a lado", wipe: "Sobrepor",
    compare: "Comparar com um SVG…", compare_tip: "Carregue um SVG feito por outra ferramenta e alterne entre os dois.",
    showing_mine: "Mostrando: o meu", showing_ref: "Mostrando: a referência",
    lang: "Idioma", theme: "Alternar entre tema claro e escuro",
    level: "Detalhe", simple: "Simples", balanced: "Equilibrado", detailed: "Detalhado",
    level_tip: "Ajusta vários controles de uma vez. Simples: menos cores e bordas mais redondas. Equilibrado: o que o tipo de imagem sugere. Detalhado: guarda mais da imagem.",
    sec_image: "Imagem", model: "Tipo de imagem",
    model_tip: "Auto olha a imagem e escolhe. Logo: cores chapadas. Desenho de linhas: traços escuros em fundo claro. Pixel art: imagens pequenas de pixels quadrados. Foto: melhor esforço.",
    m_auto: "Auto", m_clipart: "Logo / clipart", m_drawing: "Desenho de linhas", m_pixelart: "Pixel art", m_photo: "Foto",
    using: "Usando: {m}",
    bg: "Remover fundo", bg_tip: "Deixa transparente a cor que fica em volta da imagem.",
    noise: "Limpar ruído", noise_tip: "Suaviza o ruído do JPG antes de escolher as cores. Desligue para pixel art nítida.",
    soft: "Bordas suaves", soft_tip: "Usa os pixels suaves da borda da imagem para posicionar cada borda, e as curvas saem mais lisas. Desligue para cortar as bordas só pelas cores chapadas.",
    drawing_note: "Desenho de linhas traça uma forma só de tinta, então os controles de cor, cantos, tamanho, pontinhos e formas não são usados.",
    sec_colors: "Cores", colors: "Número de cores",
    colors_tip: "Quantas cores chapadas o SVG usa. Auto escolhe o menor número que ainda fica bom.",
    merge: "Juntar cores parecidas", merge_tip: "Cores mais próximas que isso viram uma só. Mais alto, menos cores.",
    palette_hint: "Para esconder ou juntar cores, abra Editar cores.",
    hide_color: "Esconder {hex}", show_color: "Mostrar {hex}",
    mg_open: "Editar cores…", mg_off: "Não vale para desenho de linhas.",
    mg_title: "Cores", mg_help: "Ligue ou desligue cores. Para juntar, marque duas ou mais e aperte Juntar. A prévia atualiza sozinha.",
    mg_move: "Arraste para mover. As setas também movem.", mg_close: "Fechar",
    mg_final: "Cor principal do grupo", mg_main: "principal", mg_new: "Uma cor nova…", mg_new_color: "Outra cor",
    mg_add: "Juntar as marcadas", mg_groups: "Cores juntadas", mg_none: "Nada juntado ainda.", mg_undo: "Desfazer",
    mg_reset: "Voltar ao padrão", mg_tick: "Marcar {hex}",
    sec_edges: "Bordas", smooth: "Suavidade", smooth_tip: "Mais alto deixa as bordas mais redondas e tira mais detalhes pequenos.",
    corner: "Cantos vivos", corner_tip: "Curvas mais fechadas que este ângulo continuam pontudas. Auto segue a Suavidade.",
    curve: "Arquivo menor", curve_tip: "Mais alto usa menos pontos de curva: arquivo menor, um pouco menos exato.",
    spots: "Remover pontinhos", spots_tip: "Pontinhos menores que esse número de pixels se misturam à cor em volta.",
    sec_shapes: "Formas", ellipses: "Círculos e elipses exatos", ellipses_tip: "Manchas redondas viram círculos e elipses perfeitos.",
    polygons: "Formas retas exatas", polygons_tip: "Manchas com 3 a 8 lados retos viram polígonos perfeitos. Pode achatar pixel art curva.",
    tol: "Encaixe da forma", tol_tip: "Quanto uma mancha pode diferir da forma perfeita e ainda ser trocada. Baixo é rígido.",
    auto: "Auto", reset: "Voltar ao padrão",
    keys: "Roda: zoom · Arrastar: mover · Duplo clique: ajustar · Ctrl+V: colar imagem · Ctrl+S: baixar",
    input: "Entrada", zoom_in: "Aproximar", zoom_out: "Afastar", fit: "Ajustar", in_view: "Imagem de entrada", in_orig: "Original", in_reduced: "Cores reduzidas", in_up: "Ampliada",
    in_down: "Mostrada menor que a imagem real (acima de 8 MP)", wipe_pos: "Posição da sobreposição",
    drop_title: "Solte um PNG ou JPG aqui", drop_sub: "Ele vira um SVG pequeno e suave. Nada sai do seu computador.",
    drop_paste: "Você também pode colar uma imagem com Ctrl+V.",
    download: "Baixar SVG", copy: "Copiar SVG", copied: "Copiado",
    upd_avail: "A versão {v} está disponível.", upd_now: "Atualizar", upd_later: "Depois", upd_busy: "Baixando a atualização.",
    upd_fail: "A atualização falhou. Você pode continuar usando esta versão.", upd_check: "Procurar atualizações ao abrir",
    no_image: "Nenhuma imagem ainda", converting: "Convertendo…", fidelity: "Fidelidade {p} %",
    more: "{paths} caminhos · {colors} cores · {shapes} formas exatas · SSIM {ssim} · {ms} ms",
    err_big: "O arquivo passa de 20 MB.", err_bad: "Não foi possível usar este arquivo: {d}",
    err_net: "O servidor não respondeu. Ele ainda está rodando?",
  },
};

function pickLang() {
  const q = new URLSearchParams(location.search).get("lang");
  const saved = localStorage.getItem("lang");
  const want = q || saved || navigator.language || "en";
  return want.toLowerCase().startsWith("pt") ? "pt" : "en";
}

let LANG = pickLang();

function t(key, vars = {}) {
  const s = I18N[LANG][key] ?? I18N.en[key] ?? key;
  return s.replace(/\{(\w+)\}/g, (_, k) => vars[k] ?? "");
}

function applyI18n() {
  document.documentElement.lang = LANG === "pt" ? "pt-BR" : "en-US";
  document.querySelectorAll("[data-i18n]").forEach((el) => (el.textContent = t(el.dataset.i18n)));
  document.querySelectorAll("[data-i18n-title]").forEach((el) => {
    el.title = t(el.dataset.i18nTitle);
    el.setAttribute("aria-label", el.title);
  });
  document.querySelectorAll("[data-i18n-label]").forEach((el) => el.setAttribute("aria-label", t(el.dataset.i18nLabel)));
  document.querySelectorAll("[data-tip-key]").forEach((el) => {
    el.dataset.tip = t(el.dataset.tipKey);
    el.setAttribute("aria-label", el.dataset.tip);
  });
}

function setLang(lang) {
  LANG = lang === "pt" ? "pt" : "en";
  localStorage.setItem("lang", LANG);
  applyI18n();
}
