// Problem 11 app check: drives the live Campus Customs site like a shopper (headless Google Chrome) and saves
// screenshots + what appeared on screen to output/app_check_images/. Needs both servers running:
//   backend/  uvicorn main:app --reload --port 8000      frontend/  npm run dev
// Then from frontend/:  npm run app-check
const puppeteer = require('puppeteer-core')
const fs = require('fs')
const path = require('path')

const SITE = 'http://localhost:5173'
const OUT = path.resolve(__dirname, '../../output/app_check_images')
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

async function openFreshChat(page) {
  if (!(await page.$('.chat-panel'))) await page.click('.chat-fab')
  await page.waitForSelector('.chat-panel')
  const newChat = await page.$$eval('.chat-link', (bs) => bs.findIndex((b) => b.innerText === 'New chat'))
  if (newChat >= 0) (await page.$$('.chat-link'))[newChat].click()
  await sleep(300)
}

async function ask(page, text) {
  const before = await page.$$eval('.chat-msg.bot', (m) => m.length)
  await page.type('.chat-input input', text, { delay: 15 })
  const t0 = Date.now()
  await page.click('.chat-input button[type=submit]')
  await page.waitForFunction((n) => document.querySelectorAll('.chat-msg.bot').length > n && !document.querySelector('.thinking'), { timeout: 120000 }, before)
  await sleep(1800) // let page navigation, cards and images settle
  return {
    seconds: +((Date.now() - t0) / 1000).toFixed(1),
    reply: await page.$$eval('.chat-msg.bot', (m) => m[m.length - 1].querySelector('.chat-text').innerText),
    chatCards: await page.$$eval('.chat-msg.bot', (m) =>
      [...m[m.length - 1].querySelectorAll('.chat-card')].map((c) => c.innerText.replace(/\n/g, ' · ')),
    ),
    suggestions: await page.$$eval('.chat-suggestion', (b) => b.map((x) => x.innerText)),
  }
}

async function pageState(page) {
  return page.evaluate(() => ({
    url: location.pathname + location.search,
    heading: document.querySelector('.chat-search-head h1, .page-head h1, .detail-info h1')?.innerText ?? null,
    chips: [...document.querySelectorAll('.chat-search-head .chip')].map((c) => c.innerText),
    resultBar: document.querySelector('.result-bar')?.innerText.split('\n')[0] ?? null,
    cards: [...document.querySelectorAll('.product-grid .product-card')].map((c) => ({
      name: c.querySelector('.product-name').innerText,
      meta: c.querySelector('.product-meta-line')?.innerText,
      price: c.querySelector('.product-price').innerText,
    })),
    activeFacets: [...document.querySelectorAll('.facet.active .facet-name, .size-chip.active')].map((e) => e.innerText),
    sort: document.querySelector('#sort-select')?.value ?? null,
  }))
}

;(async () => {
  const browser = await puppeteer.launch({
    executablePath: process.env.CHROME_PATH || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    headless: true,
    defaultViewport: { width: 1440, height: 900, deviceScaleFactor: 1 },
  })
  const page = await browser.newPage()
  const results = { ranAt: new Date().toISOString(), site: SITE, viewport: '1440x900', checks: {} }

  // 1. Chat checks the inventory level on an item (from that item's page)
  await page.goto(`${SITE}/products/yale-dad-crewneck`, { waitUntil: 'networkidle0' })
  await openFreshChat(page)
  const inv = await ask(page, 'How many of these are left in each size?')
  await page.screenshot({ path: `${OUT}/inventory.png` })
  results.checks.inventory = { question: 'How many of these are left in each size?', page: await pageState(page), ...inv }

  // 2. Dynamic search result cards after a category question
  await page.goto(`${SITE}/`, { waitUntil: 'networkidle0' })
  await openFreshChat(page)
  const cat = await ask(page, 'What crewnecks do you have?')
  await page.waitForSelector('.product-grid .product-card')
  await page.evaluate(() => Promise.all([...document.querySelectorAll('.product-grid img')].slice(0, 12).map((i) => (i.loading = 'eager', i.decode().catch(() => {})))))
  await sleep(800)
  await page.screenshot({ path: `${OUT}/category_search.png` })
  results.checks.category = { question: 'What crewnecks do you have?', page: await pageState(page), ...cat }

  // 3. Problem 9 usability feature: the sort & filter sidebar (and white, equal-size photo boxes)
  await page.goto(`${SITE}/products`, { waitUntil: 'networkidle0' })
  if (await page.$('.chat-panel')) await page.click('.chat-fab') // close chat for a clear view
  await page.select('#sort-select', 'price_high')
  await sleep(700)
  const clickFacet = async (group, value) => {
    await page.evaluate((g, v) => {
      const box = [...document.querySelectorAll('.filter-group')].find((x) => x.querySelector('.filter-label')?.innerText.toUpperCase() === g)
      ;[...box.querySelectorAll('.facet')].find((b) => b.querySelector('.facet-name').innerText === v).click()
    }, group, value)
    await sleep(700)
  }
  await clickFacet('CATEGORY', 'Hoodies')
  await clickFacet('COLOR', 'Navy')
  await page.evaluate(() => [...document.querySelectorAll('.size-chip')].find((b) => b.innerText === 'L').click())
  await sleep(1200)
  await page.evaluate(() => Promise.all([...document.querySelectorAll('.product-grid img')].map((i) => (i.loading = 'eager', i.decode().catch(() => {})))))
  await sleep(500)
  await page.screenshot({ path: `${OUT}/usability_sort_filter.png` })
  const s = await pageState(page)
  const boxes = await page.$$eval('.product-grid .product-card', (cs) => [...new Set(cs.map((c) => Math.round(c.getBoundingClientRect().height)))])
  const photos = await page.$$eval('.product-grid img', (imgs) =>
    imgs.map((img) => {
      const c = document.createElement('canvas')
      c.width = img.naturalWidth
      c.height = img.naturalHeight
      const x = c.getContext('2d')
      x.drawImage(img, 0, 0)
      const px = [[3, 3], [c.width - 4, 3], [3, c.height - 4], [c.width - 4, c.height - 4]].map(([a, b]) => x.getImageData(a, b, 1, 1).data)
      return px.every((p) => p[0] > 240 && p[1] > 240 && p[2] > 240)
    }),
  )
  results.checks.usability = {
    steps: ['Sort by: Price high to low', 'Category: Hoodies', 'Color: Navy', 'In stock in size: L'],
    page: s,
    cardHeights: boxes,
    whitePhotos: `${photos.filter(Boolean).length}/${photos.length}`,
    pricesDescending: s.cards.every((c, i, a) => i === 0 || parseFloat(a[i - 1].price.slice(1)) >= parseFloat(c.price.slice(1))),
  }

  fs.mkdirSync(OUT, { recursive: true })
  fs.writeFileSync(`${OUT}/results.json`, JSON.stringify(results, null, 2))
  console.log(JSON.stringify(results, null, 2))
  await browser.close()
})().catch((e) => {
  console.error(e)
  process.exit(1)
})
