main(async () => {
  await wait(1000);
  const appViolations = [...violations];
  await page("Memory");
  await press("New memory");
  await until("dialog", () => document.querySelector("dialog[open]"));
  await wait(200);
  const focus = document.activeElement === field("Title");
  fill(field("Title"), "Kept through the app");
  fill(field("Text"), "Written in the real window");
  await wait(100);
  await press("Save memory");
  await until("row", () => document.querySelector("main li")?.innerText.includes("Kept through the app"));
  const dialogColor = getComputedStyle(document.body).backgroundColor;
  const security = {
    dialogPlugin: await refused(raw("plugin:dialog|open", { options: {} })),
    windowPlugin: await refused(raw("plugin:window|close", { label: "main" })),
    webviewPlugin: await refused(raw("plugin:webview|create_webview_window", { options: { label: "x", url: "/" } })),
    emit: await refused(raw("plugin:event|emit", { event: "backend-status", payload: { state: "ready" } })),
    pathPlugin: await refused(raw("plugin:path|resolve_directory", { directory: 1 })),
    unknownCommand: await refused(raw("run_shell", { cmd: "id" })),
    health: await refused(api("GET", "/health")),
    traversal: await refused(api("GET", "/api/../health")),
    method: await refused(api("PATCH", "/api/memory")),
    fetchOut: await refused(fetch("https://example.com/")),
    fetchLoopback: await refused(fetch("http://127.0.0.1:9/")),
    inlineScript: await (async () => {
      const s = document.createElement("script");
      s.textContent = "window.__ran = true";
      document.body.append(s);
      await wait(100);
      return window.__ran ? "ALLOWED" : "refused";
    })(),
    image: await new Promise((r) => {
      const i = new Image();
      i.onload = () => r("ALLOWED");
      i.onerror = () => r("refused");
      i.src = "https://example.com/x.png";
    }),
    navigate: await (async () => {
      location.href = "https://example.com/";
      await wait(800);
      return location.hostname === "localhost" ? "refused" : "ALLOWED";
    })(),
  };
  return { blocked: violations, focus, styled: dialogColor, appViolations, security, pageViolations: violations.length, origin: location.origin };
});
