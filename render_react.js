// render_react.js <component.jsx> <output.png>
// Bundles a self-contained React function-component file with esbuild,
// mounts it in a headless Chromium page via Playwright, and screenshots
// the rendered result. The component file must default-export (or be the
// sole named export of) a function component with no required props.
const path = require("path");
const esbuild = require("esbuild");
const { chromium } = require("playwright");

async function main() {
  const [, , srcPath, outPath] = process.argv;
  if (!srcPath || !outPath) {
    console.error("usage: node render_react.js <component.jsx> <output.png>");
    process.exit(1);
  }

  // Wrap the user's component so it renders regardless of export style.
  const wrapperEntry = `
    import React from "react";
    import { createRoot } from "react-dom/client";
    import * as Mod from ${JSON.stringify(path.resolve(srcPath))};
    const Component = Mod.default || Mod[Object.keys(Mod)[0]];
    const root = createRoot(document.getElementById("root"));
    root.render(React.createElement(Component));
  `;

  const bundle = await esbuild.build({
    stdin: {
      contents: wrapperEntry,
      resolveDir: path.dirname(path.resolve(srcPath)),
      loader: "jsx",
    },
    bundle: true,
    write: false,
    format: "iife",
    jsx: "automatic",
  });
  const js = bundle.outputFiles[0].text;

  const html = `<!doctype html><html><body><div id="root"></div><script>${js}</script></body></html>`;

  // Launch flakes on this machine -- looks like Windows Defender
  // transiently locking/scanning the browser exe right after a fresh
  // process spawns it. Retry generously with backoff before giving up.
  let browser;
  const maxAttempts = 8;
  for (let attempt = 1; attempt <= maxAttempts; attempt++) {
    try {
      browser = await chromium.launch();
      break;
    } catch (e) {
      if (attempt === maxAttempts)
        throw new Error(
          `chromium.launch() failed after ${maxAttempts} attempts. Last error: ${e && e.stack || e}`
        );
      await new Promise((r) => setTimeout(r, 2500));
    }
  }
  const page = await browser.newPage({ viewport: { width: 900, height: 600 } });
  const errors = [];
  page.on("pageerror", (e) => errors.push(String(e)));
  page.on("console", (msg) => {
    if (msg.type() === "error") errors.push(msg.text());
  });
  await page.setContent(html);
  await page.waitForTimeout(300); // let effects/render settle
  await page.screenshot({ path: outPath });
  await browser.close();

  if (errors.length) {
    console.error("RENDER_ERRORS:\n" + errors.join("\n"));
    process.exit(1);
  }
  console.log("RENDERED_OK");
}

main().catch((e) => {
  console.error("RENDER_FAILED: " + (e && e.stack || e));
  process.exit(1);
});
