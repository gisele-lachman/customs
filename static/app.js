// Customs front end. All text from the server is set with textContent (never as HTML).
const $ = (sel) => document.querySelector(sel);
const form = $("#ask"), box = $("#situation"), go = $("#go"), count = $("#count");
const loading = $("#loading"), errorBox = $("#error"), result = $("#result");
const mapWrap = $("#mapWrap"), backBtn = $("#back"), welcome = $("#welcome");
const PHONE = window.matchMedia("(max-width: 760px)");
let PLACES = [], FACTS = {};
let MAX = Number(box.getAttribute("maxlength"));

function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") node.className = v; else node.setAttribute(k, v);
  }
  for (const c of children) if (c != null) node.append(c);
  return node;
}

function isWikipediaUrl(url) {
  try { const u = new URL(url); return u.protocol === "https:" && u.hostname.endsWith(".wikipedia.org"); }
  catch { return false; }
}

const updateCount = () => { count.textContent = `${box.value.length} / ${MAX}`; };
box.addEventListener("input", updateCount);
box.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); form.requestSubmit(); }
});
document.querySelectorAll(".example").forEach((b) =>
  b.addEventListener("click", () => { box.value = b.textContent; updateCount(); form.requestSubmit(); }));

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const situation = box.value.trim();
  if (!situation) { showError("Please describe a situation first."); return; }
  errorBox.hidden = true; result.hidden = true; loading.hidden = false; go.disabled = true;
  showStage("cards");
  try {
    const resp = await fetch("/api/coach", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ situation }),
    });
    let data;
    try { data = await resp.json(); } catch { throw new Error(`The server sent an unreadable reply (HTTP ${resp.status}).`); }
    if (!resp.ok) { showError(data.error || `Something went wrong (HTTP ${resp.status}).`, data); return; }
    render(data);
  } catch (err) {
    showError(err instanceof TypeError ? "Couldn't reach the Customs server. Is it still running?" : err.message);
  } finally {
    loading.hidden = true; go.disabled = false;
  }
});

function showError(message, data) {
  if (data && data.visa) {  // a polite refusal (budget or limit), said by Visa
    errorBox.replaceChildren(visaSays(message, "refusal"));
    errorBox.classList.add("visa-refusal");
  } else {
    errorBox.replaceChildren(el("strong", {}, "Couldn't stamp this one. "), message);
    errorBox.classList.remove("visa-refusal");
  }
  errorBox.hidden = false;
  if (data && data.usage) {  // still show what the failed run cost
    result.replaceChildren(usagePanel(data.usage), trailPanel(data.trail || []));
    result.hidden = false;
  }
}

const HOST_REMINDER = "Practices differ by region, family and generation. Your host's own guidance always comes first.";

function visaSays(text, extraClass = "") {
  return el("div", { class: `visa-says ${extraClass}` },
    el("img", { src: "/static/visa.svg", alt: "Visa, your flight attendant", width: "56", height: "56", class: "visa-avatar" }),
    el("p", { class: "bubble" }, text));
}

function render({ card, usage, trail, coverage, check }) {
  const parts = [];
  if (!card.on_topic) {
    parts.push(visaSays(card.message || "Customs offers sourced etiquette tips for social situations."));
  } else {
    if (card.greeting) parts.push(visaSays(card.greeting, "greeting"));
    const head = el("div", { class: "card-head" }, el("h2", {}, card.title || "Customs"));
    if (card.message) head.append(el("p", { class: "card-note" }, card.message));
    const cardEl = el("article", { class: "card" }, head);
    if (check) cardEl.append(checkSummary(check));
    if (coverage && coverage.limited) {
      cardEl.append(el("div", { class: "coverage-note", role: "note" },
        el("img", { src: "/static/visa.svg", alt: "", width: "32", height: "32" }),
        el("p", {}, el("span", { class: "label" }, "A note from Visa"), el("br"), coverage.note)));
    }
    if (card.tips.length) {
      cardEl.classList.add("stamped");
      cardEl.append(el("div", { class: "stamp", "aria-hidden": "true" }, el("span", {}, "STAMPED")));
      for (const kind of ["do", "dont"]) {
        const tips = card.tips.filter((t) => t.kind === kind);
        if (!tips.length) continue;
        const list = el("ul", { class: "tips" }, ...tips.map(tipEl));
        cardEl.append(el("section", { class: `group ${kind}` },
          el("h3", {}, kind === "do" ? "✓ Do" : "✗ Don't"), list));
      }
    }
    cardEl.append(el("p", { class: "host-reminder" }, HOST_REMINDER));
    parts.push(cardEl);
    if (card.closing) parts.push(visaSays(card.closing, "closing"));
  }
  result.replaceChildren(...parts, usagePanel(usage), trailPanel(trail));
  result.hidden = false;
  // restart the fade-in each time
  result.style.animation = "none"; void result.offsetWidth; result.style.animation = "";
}

function tipEl(t) {
  const source = isWikipediaUrl(t.source_url)
    ? el("a", { href: t.source_url, target: "_blank", rel: "noopener noreferrer" }, `Wikipedia: ${t.source_title}`)
    : el("span", {}, `Source: ${t.source_title}`);
  return el("li", { class: "tip" }, el("div", { class: "tip-inner" },
    el("p", { class: "tip-text" }, t.tip),
    el("p", { class: "tip-why" }, el("b", {}, "Why: "), t.why),
    t.evidence ? el("blockquote", { class: "tip-quote" }, `“${t.evidence}”`) : null,
    el("div", { class: "tip-meta" }, source, el("span", { class: "tag" }, t.variation),
      t.support === "partly" ? el("span", { class: "tag tag-partly" }, "partly supported") : null),
  ));
}

function checkSummary(c) {
  const box = el("div", { class: "check-summary" });
  if (!c.enabled) {
    box.append(el("p", {}, "Checker is off: these tips were not checked against Wikipedia."));
    return box;
  }
  const removed = c.removed.length;
  let line = c.fully_checked
    ? `Checked against Wikipedia: ${c.kept} of ${c.before} tips verified`
    : `Checked against Wikipedia word for word: ${c.kept} of ${c.before} tips passed`;
  if (removed) line += `, ${removed} removed`;
  box.append(el("p", {}, el("span", { class: "check-mark", "aria-hidden": "true" }, "✓ "), line));
  if (!c.fully_checked)
    box.append(el("p", { class: "check-warn" },
      "Not fully checked: the second check didn't finish, so these tips passed only the word-for-word check."));
  if (removed) {
    const items = c.removed.map((r) => el("li", {},
      el("span", { class: "removed-tip" }, r.tip), " ",
      el("span", { class: "removed-why" }, `(${r.stage === "code" ? "source check" : "content check"}: ${r.reason})`)));
    box.append(el("details", { class: "removed" }, el("summary", {}, `Removed tips (${removed})`), el("ul", {}, ...items)));
  }
  return box;
}

function usagePanel(u) {
  const stat = (k, v) => el("div", {}, el("dt", {}, k), el("dd", {}, String(v)));
  return el("section", { class: "panel" }, el("h3", {}, "Tokens and cost"),
    el("dl", { class: "stats" },
      stat("Input", u.input.toLocaleString()), stat("Cached", u.cached.toLocaleString()),
      stat("Output", u.output.toLocaleString()), stat("Cost", `$${u.cost_usd.toFixed(5)}`),
      stat("Model", u.models.join(", ") || "none"), stat("Tool calls", u.tool_calls)),
    u.checker ? el("p", { class: "checker-usage" }, el("span", { class: "label" }, "Checker"), " ",
      `input ${u.checker.input.toLocaleString()} · cached ${u.checker.cached.toLocaleString()} · ` +
      `output ${u.checker.output.toLocaleString()} · $${u.checker.cost_usd.toFixed(5)} (included above)`) : null);
}

function trailPanel(trail) {
  const items = trail.map((s) => {
    let text;
    if (s.tool === "search") text = `Searched “${s.query}”` + (s.results ? ` → ${s.results.length} results` : "");
    else text = `Read “${s.page_title || s.title}”` + (s.section ? ` (section: ${s.section})` : "");
    const li = el("li", {}, text);
    if (s.tool === "fetch" && s.url && isWikipediaUrl(s.url))
      li.append(" · ", el("a", { href: s.url, target: "_blank", rel: "noopener noreferrer" }, "open"));
    if (s.error) li.append(" ", el("span", { class: "err" }, `(${s.error})`));
    if (s.tool === "fetch" && s.found === false) li.append(" ", el("span", { class: "err" }, "(page not found)"));
    return li;
  });
  return el("details", { class: "panel" }, el("summary", {}, el("h3", { style: "display:inline" }, "How I found this")),
    items.length ? el("ol", { class: "trail" }, ...items) : el("p", {}, "No Wikipedia lookups were needed."));
}

// ---- map <-> cards ----
function showStage(stage) {
  const cards = stage === "cards";
  mapWrap.hidden = cards;
  backBtn.hidden = !cards;
  welcome.classList.toggle("compact", cards);  // let the card be the focus
  if (cards && PHONE.matches) $("#factsDetails").open = false;  // keep the cards first on phones
  if (!cards) { result.hidden = true; errorBox.hidden = true; $("#factsDetails").open = true; }
}
backBtn.addEventListener("click", () => { showStage("map"); mapWrap.scrollIntoView({ block: "start" }); });

// ---- choosing a place (A-to-Z list or map): fill + focus only; the user presses Go ----
function selectPlace(entry, { focusBox = true } = {}) {
  const place = entry.the ? `the ${entry.name}` : entry.name;
  box.value = `I'm visiting ${place}. What customs and etiquette should I know?`;
  updateCount();
  document.querySelectorAll(".place.selected, .country.selected").forEach((n) => n.classList.remove("selected"));
  const item = document.querySelector(`.place[data-name="${CSS.escape(entry.name)}"]`);
  if (item) {
    item.classList.add("selected");
    const list = $("#placeList");
    if ($("#places").open) list.scrollTo({ top: item.offsetTop - list.offsetTop - list.clientHeight / 3, behavior: "smooth" });
  }
  if (entry.code) document.querySelector(`.country[data-code="${entry.code}"]`)?.classList.add("selected");
  showFacts(entry);
  if (focusBox) { box.focus({ preventScroll: PHONE.matches }); box.setSelectionRange(box.value.length, box.value.length); }
}

// ---- passport-style facts panel (static facts.json built from Wikidata/Wikipedia) ----
function showFacts(entry) {
  const panel = $("#factsPanel"), f = entry.code && FACTS[entry.code];
  $("#layout").classList.toggle("has-facts", Boolean(entry.code));
  if (!entry.code) { panel.hidden = true; return; }  // regions just fill the box
  $("#factsName").textContent = entry.name;
  const body = [];
  body.push(el("img", { class: "flag", src: `/static/flags/${entry.code.toLowerCase()}.svg`, alt: `Flag of ${entry.name}`,
    width: "120", height: "90" }));
  const rows = [];
  const add = (k, v) => { if (v) rows.push(el("div", {}, el("dt", {}, k), el("dd", {}, v))); };
  if (f) {
    add("Capital", list(f.capital));
    add("Languages", list(f.languages, 4));
    add("Currency", list(f.currency));
    if (f.population) add("Population", f.population.value.toLocaleString("en") + (f.population.year ? ` (${f.population.year})` : ""));
    if (f.driving_side) add("Drives on the", list(f.driving_side.map(cap)));
    if (f.dish) add("Signature dish", f.dish.name);
  }
  body.push(rows.length ? el("dl", { class: "facts-list" }, ...rows) : el("p", { class: "facts-empty" }, "No facts on file for this place."));
  if (f && f.wikipedia_url && isWikipediaUrl(f.wikipedia_url))
    body.push(el("a", { class: "facts-link", href: f.wikipedia_url, target: "_blank", rel: "noopener noreferrer" },
      `Read about ${entry.name} on Wikipedia`));
  if (f && f.dish) body.push(el("p", { class: "facts-source" }, "Signature dish from Wikipedia's “National dish” list."));
  $("#facts").replaceChildren(...body);
  panel.hidden = false;
}
const cap = (s) => s.charAt(0).toUpperCase() + s.slice(1);
function list(values, max = 3) {
  if (!values || !values.length) return null;
  const shown = values.slice(0, max).join(", ");
  return values.length > max ? `${shown} and ${values.length - max} more` : shown;
}

// ---- "Where to next?" A-to-Z panel ----
function buildPlaces() {
  const list = $("#placeList"), letters = $("#letters");
  const sorted = [...PLACES].sort((a, b) => a.name.localeCompare(b.name, "en"));
  const groups = new Map();
  for (const p of sorted) {
    const letter = p.name.normalize("NFD")[0].toUpperCase();
    if (!groups.has(letter)) groups.set(letter, []);
    groups.get(letter).push(p);
  }
  for (const [letter, entries] of groups) {
    const id = `places-${letter}`;
    letters.append(el("a", { href: `#${id}`, "aria-label": `Places starting with ${letter}` }, letter));
    list.append(el("h3", { id, class: "place-letter" }, letter),
      el("ul", {}, ...entries.map((p) => el("li", {}, placeButton(p)))));
  }
  letters.addEventListener("click", (e) => {
    const a = e.target.closest("a"); if (!a) return;
    e.preventDefault();
    const target = document.getElementById(a.getAttribute("href").slice(1));
    list.scrollTo({ top: target.offsetTop - list.offsetTop, behavior: "smooth" });
  });
  const sync = () => { $("#places").open = !PHONE.matches; };
  sync(); PHONE.addEventListener("change", sync);
}

function placeButton(entry) {
  const b = el("button", { type: "button", class: "place", "data-name": entry.name }, entry.name);
  b.addEventListener("click", () => selectPlace(entry));
  return b;
}

// ---- world map (static SVG built from Natural Earth; inserted inline so countries are interactive) ----
async function buildMap() {
  const byCode = new Map(PLACES.filter((p) => p.code).map((p) => [p.code, p]));
  const svgText = await (await fetch("/static/map.svg")).text();
  $("#map").innerHTML = svgText;  // our own static file
  $("#map").querySelectorAll(".country").forEach((path) => {
    const entry = byCode.get(path.dataset.code);
    if (!entry) return;
    path.addEventListener("click", () => selectPlace(entry));
    path.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") { e.preventDefault(); selectPlace(entry, { focusBox: false }); }
    });
  });
}

async function init() {
  try {  // the length limit lives in app/config.py; the page follows it
    const lim = await (await fetch("/api/limits")).json();
    if (lim.max_situation_chars) { MAX = lim.max_situation_chars; box.setAttribute("maxlength", String(MAX)); }
  } catch { /* keep the default */ }
  updateCount();
  try {
    [PLACES, FACTS] = await Promise.all([
      fetch("/static/places.json").then((r) => r.json()),
      fetch("/static/facts.json").then((r) => (r.ok ? r.json() : {})).catch(() => ({})),
    ]);
  } catch { PLACES = []; }
  buildPlaces();
  try { await buildMap(); } catch { mapWrap.hidden = true; }
}
init();
