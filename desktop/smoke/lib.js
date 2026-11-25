const wait = (ms) => new Promise((r) => setTimeout(r, ms));
async function until(what, check, ms = 15000) {
  const end = Date.now() + ms;
  for (;;) {
    const found = check();
    if (found) return found;
    if (Date.now() > end) throw new Error("timed out: " + what);
    await wait(50);
  }
}
const buttons = () => [...document.querySelectorAll("button")];
const button = (text) => buttons().filter((b) => b.textContent.trim().startsWith(text)).at(-1);
const press = async (text) => (await until("button " + text, () => button(text))).click();
const page = async (name) => {
  await until("nav", () => document.querySelector("nav"));
  [...document.querySelectorAll("nav button")].find((b) => b.textContent.startsWith(name)).click();
  await wait(300);
};
const fill = (element, value) => {
  const proto = element.tagName === "TEXTAREA" ? HTMLTextAreaElement : HTMLInputElement;
  Object.getOwnPropertyDescriptor(proto.prototype, "value").set.call(element, value);
  element.dispatchEvent(new Event("input", { bubbles: true }));
};
const field = (label) =>
  document.getElementById([...document.querySelectorAll("label")].find((l) => l.textContent === label).htmlFor);
const raw = (cmd, args) => window.__TAURI_INTERNALS__.invoke(cmd, args);
const api = (method, path, body = null) => raw("api_request", { method, path, query: {}, body });
const refused = (p) =>
  Promise.resolve(p).then(
    () => "ALLOWED",
    (e) => "refused: " + (typeof e === "string" ? e : (e?.message ?? String(e))),
  );
const violations = [];
document.addEventListener("securitypolicyviolation", (e) => violations.push(e.violatedDirective + " " + e.blockedURI));
const report = (result, exit = true) =>
  raw("smoke_report", { report: JSON.stringify(result), exit });
async function main(work, exit = true) {
  if (window.__smoke) return;
  window.__smoke = true;
  try {
    await until("ready", () => document.querySelector("nav"), 30000);
    await report({ ok: true, ...(await work()) }, exit);
  } catch (e) {
    await report({ ok: false, error: String(e), text: document.body.innerText.slice(0, 300) }, true);
  }
}
