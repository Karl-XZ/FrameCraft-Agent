import { chromium } from 'playwright';
import { mkdirSync } from 'fs';

mkdirSync('/tmp/framecraft_screenshots', { recursive: true });

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });

const routes = [
  { url: 'http://localhost:5173/', name: 'landing' },
  { url: 'http://localhost:5173/studio', name: 'studio-upload' },
  { url: 'http://localhost:5173/studio?step=analyze', name: 'studio-analyze' },
  { url: 'http://localhost:5173/studio?step=plan', name: 'studio-plan' },
  { url: 'http://localhost:5173/studio?step=generate', name: 'studio-generate' },
  { url: 'http://localhost:5173/studio?step=result', name: 'studio-result' },
];

for (const r of routes) {
  console.log(`Capturing: ${r.name}...`);
  await page.goto(r.url, { waitUntil: 'networkidle', timeout: 20000 });
  await page.waitForTimeout(2500);
  await page.screenshot({ path: `/tmp/framecraft_screenshots/${r.name}.png`, fullPage: false });
  console.log(`  ✓ Saved to /tmp/framecraft_screenshots/${r.name}.png`);
}

await browser.close();
console.log('Done!');
