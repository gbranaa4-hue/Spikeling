// screenshot_url.js <url> <output.png>
// Loads a real URL in headless Chromium and screenshots it.
const SPIKELING_VERSION = "1.0";
const { chromium } = require("playwright");

async function main() {
  const [, , url, outPath] = process.argv;
  if (!url || !outPath) {
    console.error("usage: node screenshot_url.js <url> <output.png>");
    process.exit(1);
  }
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
  const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
  await page.goto(url, { waitUntil: "load", timeout: 25000 });
  await page.waitForTimeout(500);
  await page.screenshot({ path: outPath, fullPage: false });
  await browser.close();
  console.log("SCREENSHOT_OK");
}

main().catch((e) => {
  console.error("SCREENSHOT_FAILED: " + (e && e.stack || e));
  process.exit(1);
});
