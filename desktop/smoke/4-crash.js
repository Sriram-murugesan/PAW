main(async () => {
  await page("Memory");
  await press("New memory");
  await until("dialog", () => document.querySelector("dialog[open]"));
  fill(field("Title"), "Typed before the crash");
  await raw("smoke_report", { report: "CRASH-NOW", exit: false });
  await until("bar", () => document.body.innerText.includes("restarting"));
  await until("back", () => !document.body.innerText.includes("restarting"), 30000);
  const kept = field("Title").value;
  fill(field("Text"), "Saved after the restart");
  await wait(100);
  await press("Save memory");
  await until("saved", () => document.querySelector("main")?.innerText.includes("Typed before the crash"));
  return { kept };
});
