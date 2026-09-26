const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { pathToFileURL } = require('node:url');

const root = path.resolve(__dirname, '..');
const qa = path.join(__dirname, 'qa');
fs.mkdirSync(qa, { recursive: true });

async function canvasHasContent(page, selector) {
  const count = await page.locator(selector).evaluate(canvas => {
    const pixels = canvas.getContext('2d').getImageData(0, 0, canvas.width, canvas.height).data;
    let colored = 0;
    for (let i = 0; i < pixels.length; i += 4) {
      if (pixels[i + 3] > 100 && Math.max(pixels[i], pixels[i + 1], pixels[i + 2]) - Math.min(pixels[i], pixels[i + 1], pixels[i + 2]) > 30) colored++;
    }
    return colored;
  });
  assert(count > 300, `${selector} appears blank`);
  const tickCount = await page.locator(selector).evaluate(canvas => ({ count: Chart.getChart(canvas).scales.x.ticks.length, width: innerWidth }));
  if(tickCount.width < 600) assert(tickCount.count <= 4, 'Mobile date labels are too crowded');
}

async function noPageOverflow(page) {
  await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
  const size = await page.evaluate(() => ({ scroll: document.documentElement.scrollWidth, width: innerWidth, view: document.querySelector('.view:not([hidden])').id,
    offenders: Array.from(document.querySelectorAll('body *')).filter(e => !e.closest('.table-wrap') && e.getBoundingClientRect().right > innerWidth + 1).map(e => `${e.tagName}.${e.className}`).slice(0,8) }));
  if(size.scroll > size.width + 1) await page.screenshot({path:path.join(qa,'overflow.png'),fullPage:true});
  assert(size.scroll <= size.width + 1, `Page overflows: ${JSON.stringify(size)}`);
}

(async () => {
  const browser = await chromium.launch({ headless: true, channel: process.env.BROWSER_CHANNEL || 'msedge' });
  try {
    const page = await browser.newPage({ viewport: { width: 1440, height: 1080 }, deviceScaleFactor: 1 });
    const errors = [];
    const externalRequests = [];
    page.on('pageerror', e => errors.push(e.message));
    page.on('request', request => { if (/^https?:/.test(request.url())) externalRequests.push(request.url()); });
    await page.goto(pathToFileURL(path.join(root, 'dashboard', 'index.html')).href);
    await page.waitForFunction(() => typeof window.researchMetrics === 'function');
    assert.equal(await page.locator('#comparison tbody tr').count(), 3);
    await canvasHasContent(page, '#portfolio-chart');
    await noPageOverflow(page);

    const parity = await page.evaluate(() => {
      const d = window.RESEARCH_DATA;
      let count = 0;
      for (const row of d.sensitivity) {
        const actual = window.researchMetrics(d.scenarios[row.scenario][row.portfolio]);
        for (const metric of ['total_return', 'annualized_return', 'annualized_volatility', 'max_drawdown', 'sharpe_ratio']) {
          if (Math.abs(actual[metric] - row[metric]) > 1e-10) throw Error(`${row.scenario}/${row.portfolio}/${metric}`);
          count++;
        }
      }
      return count;
    });
    assert.equal(parity, 90);
    await page.screenshot({ path: path.join(root, 'results', 'dashboard_preview.png'), fullPage: true });
    const allReturn = await page.locator('#kpi-return').innerText();
    await page.locator('[name="period"][value="2022"]').check({ force: true });
    assert.notEqual(await page.locator('#kpi-return').innerText(), allReturn);
    const expected2022 = await page.evaluate(() => {
      const row = window.RESEARCH_DATA.periods.find(r => r.period === '2022 calendar year' && r.portfolio === 'diversified');
      return (row.total_return * 100).toFixed(1) + '%';
    });
    assert.equal(await page.locator('#kpi-return').innerText(), expected2022);
    await page.locator('#focus').selectOption('spy');
    assert.equal(await page.locator('#comparison tbody tr.selected td').first().innerText().then(s => s.split('\n')[0]), 'SPY only');
    await page.locator('[name="chartMode"][value="drawdown"]').check({ force: true });
    assert.match(await page.locator('#chart-title').innerText(), /Drawdown/);
    await canvasHasContent(page, '#portfolio-chart');
    await page.locator('#cost').selectOption('25');
    await page.locator('#rebalance').selectOption('buy_hold');

    const downloaded = page.waitForEvent('download');
    await page.getByRole('button', { name: 'Export filtered portfolio metrics' }).click();
    const download = await downloaded;
    const exportPath = path.join(qa, 'filtered.csv');
    await download.saveAs(exportPath);
    const csv = fs.readFileSync(exportPath, 'utf8');
    assert(csv.includes('buy_hold,25'));
    assert.equal(csv.trim().split('\n').length, 4);

    await page.locator('#start').fill('2025-01-01');
    await page.locator('#end').fill('2024-01-01');
    await page.locator('#end').dispatchEvent('change');
    assert.equal(await page.locator('#error').isVisible(), true);
    assert.equal(await page.locator('#export').isDisabled(), true);
    await page.locator('[name="period"][value="all"]').check({ force: true });
    assert.equal(await page.locator('#error').isVisible(), false);
    await page.getByRole('button', { name: 'Assets', exact: true }).click();
    await canvasHasContent(page, '#asset-chart');
    assert.equal(await page.locator('#correlation tbody tr').count(), 5);
    await page.locator('[name="asset"][value="QQQ"]').uncheck();
    assert.equal(await page.locator('#correlation tbody tr').count(), 4);
    await page.locator('#heatmap-year').selectOption('2020');
    assert.equal(await page.locator('#monthly-heatmap th').first().innerText(), '2020');
    await page.screenshot({ path: path.join(qa, 'assets-desktop.png'), fullPage: true });
    await page.getByRole('button', { name: 'Data & method' }).click();
    assert.equal(await page.locator('#quality tbody tr').count(), 5);
    assert((await page.locator('#flags tbody tr').count()) > 0);
    for (const href of await page.locator('.downloads a').evaluateAll(links => links.map(a => a.getAttribute('href')))) {
      assert(fs.existsSync(path.resolve(root, 'dashboard', href)), `Missing link target: ${href}`);
    }
    await page.evaluate(() => { window.print = () => { window.didPrint = true; }; });
    await page.getByRole('button', { name: 'Print current view' }).click();
    assert(await page.evaluate(() => window.didPrint));

    for (const width of [390, 320]) {
      await page.setViewportSize({ width, height: 844 });
      for (const name of ['Portfolios', 'Assets', 'Data & method']) {
        await page.getByRole('button', { name, exact: true }).click();
        await noPageOverflow(page);
        if (name === 'Portfolios') await canvasHasContent(page, '#portfolio-chart');
        if (name === 'Assets') await canvasHasContent(page, '#asset-chart');
        await page.screenshot({ path: path.join(qa, `${name.split(' ')[0]}-${width}.png`), fullPage: true });
      }
    }
    assert.deepEqual(errors, []);
    assert.deepEqual(externalRequests, []);
    console.log(`PASS: ${parity} metric comparisons, filters, views, CSV export, print, links, invalid dates, desktop/mobile layouts and nonblank charts. No external requests or JS errors.`);
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exit(1); });
