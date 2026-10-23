"use strict";

const LABELS = {
  styles: {
    none: "No style", photo: "Photo", illustration: "Illustration", sketch: "Sketch",
    watercolor: "Watercolor", "3d": "3D", flat: "Flat",
  },
  formats: {
    source: "Like source", "1:1": "Square 1:1", "16:9": "Slide 16:9", "4:3": "Landscape 4:3",
    "3:4": "Portrait 3:4", "9:16": "Portrait 9:16",
  },
  sizes: { small: "Small", medium: "Medium", large: "Large" },
  qualities: { draft: "Draft", standard: "Standard", high: "High" },
  tasks: { describe: "Describe", text: "Read text", question: "Own question" },
  submits: { describe: "Describe image", text: "Read out text", question: "Ask question" },
  quickEdits: { white: "White background", sketch: "As a sketch", no_text: "Remove text", vivid: "Stronger colors" },
  languages: { en: "English", de: "German" },
  placeholders: {
    generate: "Write a prompt and create your first image.",
    edit: "Pick an image below that you want to edit.",
    describe: "Pick an image below that you want described.",
  },
  busy: { generate: "Creating…", edit: "Editing…", describe: "Reading…" },
};

const $ = (id) => document.getElementById(id);
const state = {
  tab: "generate",
  options: null,
  images: [],          // {key, blob, url, prompt, modelPrompt, info, sourceUrl, answers}
  selected: "",
  choice: {
    style: "none", generateFormat: "16:9", generateSize: "medium", generateQuality: "standard",
    generateVariants: 1, editFormat: "source", editSize: "medium", editQuality: "standard",
    editVariants: 1, task: "describe", language: "en",
  },
  busy: false,
};

function toast(text) {
  const box = $("toast");
  box.textContent = text;
  box.hidden = false;
  setTimeout(() => { box.hidden = true; }, 1800);
}

function message(text) {
  const box = $("message");
  box.textContent = text || "";
  box.hidden = !text;
}

function chips(host, values, labels, current, onPick) {
  host.textContent = "";
  for (const value of values) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "chip";
    button.textContent = labels[value] ?? String(value);
    button.setAttribute("aria-pressed", String(value === current));
    button.disabled = state.busy;
    button.addEventListener("click", () => onPick(value));
    host.appendChild(button);
  }
}

function numbers(limit) {
  const values = [];
  for (let n = 1; n <= limit; n += 1) values.push(n);
  return values;
}

function pixelText(format, size) {
  const table = state.options.pixels[format];
  return table ? table[size].replace("x", " × ") : "";
}

function selected() {
  return state.images.find((image) => image.key === state.selected) || null;
}

// -- Drawing ------------------------------------------------------------------

function drawForm() {
  const o = state.options;
  const c = state.choice;
  chips($("generate-style"), o.styles, LABELS.styles, c.style, (v) => { c.style = v; drawForm(); });
  chips($("generate-format"), o.formats, LABELS.formats, c.generateFormat, (v) => { c.generateFormat = v; drawForm(); });
  chips($("generate-size"), o.sizes, LABELS.sizes, c.generateSize, (v) => { c.generateSize = v; drawForm(); });
  chips($("generate-quality"), o.qualities, LABELS.qualities, c.generateQuality, (v) => { c.generateQuality = v; drawForm(); });
  chips($("generate-variants"), numbers(o.variants.generate), {}, c.generateVariants, (v) => { c.generateVariants = v; drawForm(); });
  $("generate-pixels").textContent = pixelText(c.generateFormat, c.generateSize);
  $("generate-no-text").disabled = state.busy;

  const editFormats = [o.source_format].concat(o.formats);
  chips($("edit-format"), editFormats, LABELS.formats, c.editFormat, (v) => { c.editFormat = v; drawForm(); });
  chips($("edit-size"), o.sizes, LABELS.sizes, c.editSize, (v) => { c.editSize = v; drawForm(); });
  chips($("edit-quality"), o.qualities, LABELS.qualities, c.editQuality, (v) => { c.editQuality = v; drawForm(); });
  chips($("edit-variants"), numbers(o.variants.edit), {}, c.editVariants, (v) => { c.editVariants = v; drawForm(); });
  $("edit-pixels").textContent = c.editFormat === o.source_format ? "" : pixelText(c.editFormat, c.editSize);

  chips($("describe-task"), o.tasks, LABELS.tasks, c.task, (v) => { c.task = v; drawForm(); });
  chips($("describe-language"), ["en", "de"], LABELS.languages, c.language, (v) => { c.language = v; drawForm(); });
  $("question-box").hidden = c.task !== "question";
  $("describe-button").textContent = LABELS.submits[c.task];

  const n = Number(c.generateVariants);
  $("generate-button").textContent = n > 1 ? `Create ${n} images` : "Create image";
  $("generate-button").disabled = state.busy || !$("prompt").value.trim();
  $("enhance-button").disabled = state.busy || !$("prompt").value.trim();
  $("edit-button").disabled = state.busy || !selected() || !$("edit-prompt").value.trim();
  $("describe-button").disabled = state.busy || !selected()
    || (c.task === "question" && !$("question").value.trim());
}

function drawStage() {
  const image = selected();
  $("placeholder").hidden = Boolean(image);
  $("shown").hidden = !image;
  $("placeholder-text").textContent = LABELS.placeholders[state.tab];
  $("busy").hidden = !state.busy;
  $("busy-text").textContent = LABELS.busy[state.tab];
  if (!image) return;

  $("large").src = image.url;
  $("compare").hidden = !image.sourceUrl || state.tab !== "edit";
  if (image.sourceUrl) {
    $("before").src = image.sourceUrl;
    $("after-image").src = image.url;
  }
  $("large").hidden = Boolean(image.sourceUrl) && state.tab === "edit";
  $("promptbox").hidden = !image.prompt;
  $("copy-prompt").hidden = !image.prompt;
  $("shown-prompt").textContent = image.prompt || "";
  $("model-prompt-box").hidden = !image.modelPrompt || image.modelPrompt === image.prompt;
  $("shown-model-prompt").textContent = image.modelPrompt || "";
  $("shown-info").textContent = image.info || "";

  const answers = $("answers");
  answers.textContent = "";
  for (const answer of image.answers) {
    const box = document.createElement("div");
    box.className = "answer";
    const title = document.createElement("h3");
    title.textContent = answer.title;
    const text = document.createElement("pre");
    text.textContent = answer.text;
    const copy = document.createElement("button");
    copy.type = "button";
    copy.className = "btn";
    copy.textContent = "Copy";
    copy.addEventListener("click", () => copyText(answer.text));
    box.append(title, text, copy);
    answers.appendChild(box);
  }
}

function drawHistory() {
  const strip = $("strip");
  strip.textContent = "";
  for (const image of state.images) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "thumb";
    button.setAttribute("aria-pressed", String(image.key === state.selected));
    button.title = image.prompt || image.name;
    const thumb = document.createElement("img");
    thumb.src = image.url;
    thumb.alt = image.prompt || image.name;
    button.appendChild(thumb);
    button.addEventListener("click", () => {
      state.selected = state.selected === image.key ? "" : image.key;
      draw();
    });
    strip.appendChild(button);
  }
  $("history-empty").hidden = state.images.length > 0;
  $("history-count").textContent = state.images.length ? `(${state.images.length})` : "";
}

function draw() {
  drawForm();
  drawStage();
  drawHistory();
}

// -- Pictures -----------------------------------------------------------------

let counter = 0;

function add(blob, extra) {
  counter += 1;
  const image = Object.assign({
    key: `image-${counter}`,
    blob,
    url: URL.createObjectURL(blob),
    name: `image-${counter}.png`,
    prompt: "",
    modelPrompt: "",
    info: "",
    sourceUrl: "",
    answers: [],
  }, extra || {});
  state.images.unshift(image);
  return image;
}

async function fetchImage(id) {
  const response = await fetch(`/api/image/${id}`);
  if (!response.ok) throw new Error("The image is gone.");
  return response.blob();
}

function save(blob, name) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = name;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

async function asJpg(blob) {
  const picture = await createImageBitmap(blob);
  const canvas = document.createElement("canvas");
  canvas.width = picture.width;
  canvas.height = picture.height;
  const context = canvas.getContext("2d");
  // JPG has no transparency, a white ground keeps transparent parts from turning black.
  context.fillStyle = "#fff";
  context.fillRect(0, 0, canvas.width, canvas.height);
  context.drawImage(picture, 0, 0);
  return new Promise((resolve, reject) =>
    canvas.toBlob((result) => (result ? resolve(result) : reject(new Error("jpg"))), "image/jpeg", 0.9));
}

async function copyText(text) {
  if (navigator.clipboard && window.isSecureContext) {
    await navigator.clipboard.writeText(text);
  } else {
    const field = document.createElement("textarea");
    field.value = text;
    field.style.position = "fixed";
    field.style.opacity = "0";
    document.body.appendChild(field);
    field.select();
    document.execCommand("copy");
    field.remove();
  }
  toast("Copied");
}

// -- Calls --------------------------------------------------------------------

function withSettings(form, visionModel) {
  const baseUrl = $("set-base-url").value.trim();
  const model = (visionModel ? $("set-vision-model").value : $("set-model").value).trim();
  const key = $("set-api-key").value.trim();
  if (baseUrl) form.append("base_url", baseUrl);
  if (model) form.append("model", model);
  if (key) form.append("api_key", key);
  return form;
}

async function call(path, form) {
  const response = await fetch(path, { method: "POST", body: form });
  const text = await response.text();
  if (!response.ok) throw new Error(text || `The server answered ${response.status}.`);
  return JSON.parse(text);
}

async function busy(run) {
  state.busy = true;
  message("");
  draw();
  try {
    await run();
  } catch (error) {
    message(String(error.message || error));
  } finally {
    state.busy = false;
    draw();
  }
}

function runEnhance() {
  return busy(async () => {
    const form = withSettings(new FormData(), false);
    form.append("prompt", $("prompt").value);
    const data = await call("/api/enhance", form);
    $("enhanced").value = data.prompt;
    $("enhanced-box").hidden = false;
  });
}

function runGenerate() {
  return busy(async () => {
    const c = state.choice;
    const form = withSettings(new FormData(), false);
    form.append("prompt", $("prompt").value);
    form.append("model_prompt", $("enhanced").value);
    form.append("style", c.style);
    form.append("format", c.generateFormat);
    form.append("size", c.generateSize);
    form.append("quality", c.generateQuality);
    form.append("variants", String(c.generateVariants));
    form.append("no_text", String($("generate-no-text").checked));
    const data = await call("/api/generate", form);
    let first = true;
    for (const id of data.images) {
      const image = add(await fetchImage(id), {
        prompt: data.prompt,
        modelPrompt: data.model_prompt,
        info: `${LABELS.styles[data.style]}, ${LABELS.formats[data.format]}, `
          + `${data.size.replace("x", " × ")} px, ${LABELS.qualities[data.quality]}`,
      });
      if (first) { state.selected = image.key; first = false; }
    }
  });
}

function runEdit() {
  const image = selected();
  if (!image) return Promise.resolve();
  return busy(async () => {
    const c = state.choice;
    const form = withSettings(new FormData(), false);
    form.append("image", new File([image.blob], image.name, { type: image.blob.type || "image/png" }));
    form.append("prompt", $("edit-prompt").value);
    form.append("format", c.editFormat);
    form.append("size", c.editSize);
    form.append("quality", c.editQuality);
    form.append("variants", String(c.editVariants));
    const data = await call("/api/edit", form);
    const sourceUrl = URL.createObjectURL(await fetchImage(data.source));
    let first = true;
    for (const id of data.images) {
      const made = add(await fetchImage(id), {
        prompt: data.prompt,
        sourceUrl,
        info: `${LABELS.formats[data.format]}, ${LABELS.qualities[data.quality]}`,
      });
      if (first) { state.selected = made.key; first = false; }
    }
  });
}

function runDescribe() {
  const image = selected();
  if (!image) return Promise.resolve();
  return busy(async () => {
    const c = state.choice;
    const form = withSettings(new FormData(), true);
    form.append("image", new File([image.blob], image.name, { type: image.blob.type || "image/png" }));
    form.append("prompt", c.task === "question" ? $("question").value : "");
    form.append("task", c.task);
    form.append("language", c.language);
    const data = await call("/api/describe", form);
    image.answers = image.answers.concat([{
      title: data.question || LABELS.tasks[data.task],
      text: data.text,
    }]);
  });
}

// -- Page ---------------------------------------------------------------------

function pickTab(tab) {
  state.tab = tab;
  for (const button of document.querySelectorAll(".tab")) {
    const active = button.dataset.tab === tab;
    button.classList.toggle("active", active);
    button.setAttribute("aria-selected", String(active));
    $(`panel-${button.dataset.tab}`).hidden = !active;
  }
  draw();
}

function uploadFile(file) {
  const ext = `.${(file.name.split(".").pop() || "").toLowerCase()}`;
  if (![".png", ".jpg", ".jpeg"].includes(ext)) {
    message("Only PNG and JPG are allowed.");
    return;
  }
  if (file.size > state.options.max_image_mb * 1024 * 1024) {
    message(`The image is larger than ${state.options.max_image_mb} MB.`);
    return;
  }
  message("");
  const image = add(file, { name: file.name });
  state.selected = image.key;
  draw();
}

async function start() {
  state.options = await (await fetch("/api/options")).json();
  const missing = Object.entries(state.options.configured)
    .filter(([, ready]) => !ready).map(([kind]) => kind);
  $("settings-hint").textContent = missing.length
    ? "No server is set for: " + missing.join(", ") + ". Fill the fields below or set the environment variables."
    : "The server and the models come from the environment. A field below overrides them for this page.";
  if (missing.length) {
    $("settings").hidden = false;
    $("settings-button").setAttribute("aria-expanded", "true");
  }

  const quick = $("quick-edits");
  for (const [key, text] of Object.entries(state.options.quick_edits)) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "btn";
    button.textContent = LABELS.quickEdits[key] || key;
    button.addEventListener("click", () => { $("edit-prompt").value = text; draw(); });
    quick.appendChild(button);
  }

  for (const button of document.querySelectorAll(".tab")) {
    button.addEventListener("click", () => pickTab(button.dataset.tab));
  }
  $("settings-button").addEventListener("click", () => {
    const box = $("settings");
    box.hidden = !box.hidden;
    $("settings-button").setAttribute("aria-expanded", String(!box.hidden));
  });
  $("prompt").addEventListener("input", draw);
  $("edit-prompt").addEventListener("input", draw);
  $("question").addEventListener("input", draw);
  $("enhance-button").addEventListener("click", runEnhance);
  $("generate-button").addEventListener("click", runGenerate);
  $("edit-button").addEventListener("click", runEdit);
  $("describe-button").addEventListener("click", runDescribe);
  $("new-image").addEventListener("click", () => { state.selected = ""; draw(); });
  $("copy-prompt").addEventListener("click", () => { const i = selected(); if (i) copyText(i.prompt); });
  $("download-png").addEventListener("click", () => {
    const image = selected();
    if (image) save(image.blob, image.name.replace(/\.[^.]+$/, "") + ".png");
  });
  $("download-jpg").addEventListener("click", async () => {
    const image = selected();
    if (image) save(await asJpg(image.blob), image.name.replace(/\.[^.]+$/, "") + ".jpg");
  });
  $("upload").addEventListener("change", (event) => {
    const file = event.target.files[0];
    if (file) uploadFile(file);
    event.target.value = "";
  });

  document.addEventListener("dragover", (event) => { event.preventDefault(); document.body.classList.add("dragging"); });
  document.addEventListener("dragleave", (event) => { if (!event.relatedTarget) document.body.classList.remove("dragging"); });
  document.addEventListener("drop", (event) => {
    event.preventDefault();
    document.body.classList.remove("dragging");
    const file = event.dataTransfer.files[0];
    if (file) uploadFile(file);
  });

  draw();
}

start();
