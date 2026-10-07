# Campus Customs: Usability Improvements (Problem 9)

Each improvement below lists what changed, why it helps the shopper, and how it was checked. Every item was tested in the running site (browser at desktop width) and/or against the live agent, and every number was compared with `data/campus_customs.db`.

## Summary

| # | Improvement | Where | Verified |
|---|---|---|---|
| 1 | Navigation order: Home · About Us · Products · Log in | Navbar | ✓ |
| 2 | Every product photo on a white background | Products, Home, item pages, chat cards | ✓ 102/102 |
| 3 | All product boxes the same size | Products, Home | ✓ 102/102 |
| 4 | Sort & filter panel on the left of the Products page | Products page | ✓ |
| 5 | One sort tool shared by the page and the chatbot | Backend `tools.catalog` + agent `browse_catalog` | ✓ |
| 6 | Chatbot tells you how many items match and how many are available | Agent | ✓ |
| 7 | "In stock in your size" search and filter | Agent + sidebar | ✓ |
| 8 | Sort, filter and browse the page from the chat | Agent → page | ✓ |
| 9 | Honest brand and color answers | Agent + cards | ✓ |
| 10 | Suggested next questions + starter questions | Chat | ✓ |
| 11 | "Try again" when a message fails | Chat | ✓ |
| 12 | Clean formatting of key facts (bold) | Chat | ✓ |
| 13 | Consistent counts everywhere (one "hoodie" definition) | Backend | ✓ |

---

## Front end

### 1. Navigation order: Home · About Us · Products · Log in (· Create account)

- **What changed:** "About Us" moved before "Products" in `Navbar.tsx`. Create account stays last as the main call to action.
- **Why it helps:** it follows the order a new visitor thinks in: who is this shop → what do they sell → sign in. The account links stay together on the right, where people expect them.
- **Checked:** the navbar reads `Home | About Us | Products | Log in | Create account`.

### 2. Every product photo on a white background

- **What changed:** 73 of the 102 original photos had a black background baked into the JPG, so CSS alone couldn't fix it. The photo cleanup (`backend/prepare_images.py` at the time; now `tools.prepare_product_photos()`, run automatically on first start) flood-fills the background from the photo's edges and turns it white. It keeps garments intact (backgrounds are near-pure black, 0–10; the darkest navy garment pixels are 30+), removes the dark edge halo, and writes cleaned copies to `data/products_web/`. The originals in `data/products/` are untouched. `main.py` serves the cleaned copies.
- **Cache fix:** photo URLs now carry a version (`/media/<file>.jpg?v=…`) that changes whenever the photos are regenerated. Without it, browsers that had visited before kept showing the old black photos; this was caught during testing.
- **Why it helps:** a mix of black and white tiles looks messy and pulls the eye to the background instead of the clothes. A uniform white background looks like a real store and makes garments easy to compare.
- **Checked:** the browser read the corner pixels of all 102 photos on the Products page. **102/102 white**, 0 dark corners. The Home page's featured photos and the item page photo are also white.
- **Follow-up fix (found in Problem 11 testing):** checking corners alone missed black gaps *enclosed* by a garment (e.g. between the Yale Dad Crewneck's arm and body). The cleanup now also whitens large, flat, pure-black enclosed areas while keeping dark navy fabric and black crest prints. All 102 photos were re-scanned for leftover black areas, and the photo URL version now updates whenever files are rewritten. See `output/app_check.html`.

### 3. All product boxes the same size

- **What changed:**
  - **Same garment size:** the cleanup trims each photo to the garment and centers it on an identical 900×900 canvas with the same 7% margin. The originals came in 30+ different sizes, with garments filling anywhere from about half to all of the frame, and small photos are now scaled *up* as well as down.
  - **Same text block:** cards use a fixed square photo area, a brand · color line, a 2-line name, a 2-line description, and the price pinned to the bottom.
- **Why it helps:** equal boxes make the grid easy to scan and compare; nothing jumps out just because its photo was bigger or its name was longer.
- **Checked:**
  - All 102 photos are 900×900.
  - At 1280px wide, all 102 cards are exactly **366px** tall with identical **203×203** photo boxes.

### 4. Sort & filter panel on the left of the Products page

- **What changed:** a sticky left sidebar on `ProductsPage.tsx`:

  | Control | Options |
  |---|---|
  | **Sort by** | Featured (or "Best match" for chat results), Price low → high, Price high → low, Name A → Z, Color, Brand, Category |
  | **Category** | T-shirts, Long sleeves, Quarter-zips, Hoodies, Jackets & fleece, Crewnecks, each with a product count |
  | **Color** | Navy, Gray, White & cream, Coral, Not listed, with color swatches and counts |
  | **Brand** | Champion, Under Armour, Brooks Brothers, District, Hype and Vice, Maplehouse, Campus Customs design, with counts |
  | **Price** | Any, or under $35 / $50 / $60 / $75 / $100 |
  | **In stock in size** | XS · S · M · L · XL · XXL |

  Above the grid, a result bar reads e.g. "11 products in stock in L · sorted by price: high to low". There's also a "Clear filters (n)" button and an empty state with a clear link. Every choice is stored in the URL (`?sort=price_high&category=Hoodies&color=Navy&size=L`), so refresh, sharing and the chat all work with it. On narrow screens the sidebar stacks above the grid.
- **Why it helps:** shoppers can narrow 102 products to what they actually want in a couple of clicks. The counts show what's available before clicking, so there are no dead ends. The size filter hides things they can't buy in their size.
- **Checked:**
  - **Sort:** Price high → low puts the $98 jackets first, and all 102 prices are in descending order.
  - **Combined filters:** Hoodies + Navy + L shows the count and keeps the price sort.
  - **Brand sort:** named brands come first, then house designs.
  - **Clear filters:** resets to 102 and keeps the sort.
  - **Layout:** the sidebar is on the left of the grid (sidebar at x = 72–302, grid starts at x = 334).

## Back end and chatbot

### 5. One sort tool shared by the page and the chatbot

- **What changed:** `tools.catalog(sort, category, color, brand, max_price, size, ids)` is the single sort/filter function. It powers both `GET /api/products?sort=…&category=…` (the sidebar) and the agent's new **`browse_catalog`** tool. It adds three fields the database doesn't have, from rules in `tools.py`:
  - **Brand:** from product names/descriptions; the 86 unbranded items are "Campus Customs design".
  - **Color family:** from the garment's own color, `colors[0]`.
  - **Category:** the 22 messy `garment_type` labels grouped into 6.
- **Why it helps:** the page and Audrey can never disagree. "Sort by price" in the sidebar and in the chat produce the same order and the same counts.
- **Checked:**
  - **Facet counts match the Problem 2 analysis:** Champion 4, Under Armour 2, Brooks Brothers 2, District 5, Hype and Vice 2, Maplehouse 1, Campus Customs design 86.
  - **Totals:** categories add up to 102.

### 6. The chatbot tells you how many items match and how many are available

- **What changed:** `search_products` now returns `SearchResults` with `total_matches` (products containing *all* the search words, within budget), `in_stock_matches` (how many have stock, or stock in the requested size) and `exact_match`. `browse_catalog` returns `total` / `in_stock`. The prompt's new "Always say how many match" rule has Audrey state these numbers every time. The number checker also catches made-up *product* counts ("20 navy hoodies") as well as unit counts.
- **Why it helps:** "We have 17 navy hoodies, all 17 in stock" tells the shopper right away how much choice they have. They don't have to scroll to find out, and the number is guaranteed to be real.
- **Checked:**

  | Question | Audrey said | Database |
  |---|---|---|
  | "Show me navy hoodies" | "We have **17 navy hoodies**, and all **17 are in stock**" | 17 ✓ |
  | "Which of those come in large?" | "**12** navy hoodie styles are available in Large" | 12 ✓ |
  | "Which are in medium?" | "13 of our 17 navy hoodies are in stock in Medium" | 13 ✓ |
  | "Show me everything by Champion" | "**4 Champion products**, all 4 in stock" | 4 ✓ |
  | "Do you have a pink hoodie?" | "We don't carry a pink hoodie", closest navy/gray options | 0 ✓ |

  The number checker passes "17 navy hoodies, 12 in medium" (both seen) and rejects "20 navy hoodies" (never returned by a tool).

### 7. "In stock in your size" search and filter

- **What changed:** `search_products(…, size=)`, `browse_catalog(…, size=)`, `PageUpdate.size` and the sidebar's size chips all filter to products that can actually be bought in that size.
- **Why it helps:** nothing is more frustrating than finding the perfect hoodie and then discovering it's sold out in your size. Shoppers now only see what they can buy.
- **Checked:** "Which of those come in large?" → page "Navy hoodies in Large" showed 12 products. The sidebar's Navy + Hoodies + L filter also shows 12 (see #13).

### 8. Sort, filter and browse the page from the chat

- **What changed:** the agent's page update gains a **`browse`** action (whole catalogue with sort/category/color/brand/price/size) and an optional `sort` on search results. The chat widget turns these into URL parameters, so the sidebar's controls update to match what Audrey did.
- **Why it helps:** shoppers can just say "sort those by price, cheapest first" or "show me everything by Champion" instead of hunting for the controls, and they can still adjust things by hand afterwards.
- **Checked in the browser:**
  - **Sort from chat:** "Sort those by price, cheapest first" re-sorted the 17 navy hoodies in ascending price, and the sidebar's Sort menu switched to "Price: low to high".
  - **Browse from chat:** "Show me everything by Champion" switched the page to the Champion filter, with the Champion facet highlighted. It also kept the size M from earlier in the conversation, so the shopping context carries into browsing.

### 9. Honest brand and color answers

- **What changed:** every product the agent sees now includes `brand`, `color_family` and `category`. The prompt says six brands are named in the catalogue, everything else is a "Campus Customs design" whose maker isn't listed, and print colors don't count (a gray hoodie with navy letters is gray). Cards show "Brand · Color" too.
- **Why it helps:** shoppers often ask "is this Champion?" or "who makes this?" Answers now come from the data, and Audrey says so when the maker isn't listed instead of guessing.
- **Checked:** "What brands do you carry?" lists exactly the 6 named brands plus Campus Customs designs. The Champion answer ("charcoal full-zip, two gray crewnecks, navy Reverse Weave hoodie; the full-zip has every size, the others have some sold out") matches the database exactly.

### 10. Suggested next questions + starter questions

- **What changed:** `AgentReply.suggestions` holds up to 3 short follow-ups the agent writes for *this* conversation (e.g. after navy hoodies: "Any under $70?", "Which are in medium?", "Show me matching crewnecks"). They appear as tappable chips under the latest reply. A new chat shows 3 starters: "Show me navy hoodies", "Gifts for my dad under $60", "What brands do you carry?".
- **Why it helps:** shoppers don't have to think of what to type, and the chips show what the assistant can do. One tap is faster than typing, especially on a phone.
- **Checked:** starters showed on a new chat; tapping "Show me navy hoodies" ran the search and updated the page; 3 relevant suggestions appeared; tapping "Which are in medium?" sent it as the shopper's message and filtered the page.

### 11. "Try again" when a message fails

- **What changed:** if the assistant can't answer (e.g. the AI service is briefly down), the error now has a **Try again** button that re-sends the same question without typing it again or adding a duplicate message.
- **Why it helps:** shoppers don't lose their question to a temporary error.
- **Checked:** one chat request was forced to fail. The error showed "Audrey is momentarily unavailable… Try again". Clicking it re-sent the question (1 user message, not 2), got the right answer (2 Champion hoodies, $68 and $88, both in Medium ✓), and cleared the error.

### 12. Clean formatting of key facts

- **What changed:** Audrey bolds key facts with `**…**`. The chat used to show the asterisks literally; it now renders them as **bold**.
- **Why it helps:** counts and prices stand out at a glance.
- **Checked:** replies show bold "17 navy hoodies" and "17 are in stock", with no literal `**` left in the text.

### 13. Consistent counts everywhere

- **What changed:** testing found the sidebar said **11** navy hoodies in Large while Audrey said **12**. The navy Brooks Brothers *full-zip* hoodie was in its own "Full-zip hoodies" category. Since shoppers count full-zip hoodies as hoodies, they're now one "Hoodies" category.
- **Why it helps:** the chat and the page now say the same number. A mismatch makes shoppers distrust both.
- **Checked:** the sidebar (Hoodies + Navy) shows 17, and 12 in L. Audrey's search says 17, and 12 in L.

---

## Files changed

| Area | Files |
|---|---|
| Photos | photo cleanup (now `tools.prepare_product_photos()`), `data/products_web/` (generated), `backend/main.py` (serves cleaned photos), `tools.photo_url` (versioned URLs) |
| Sort tool & counts | `backend/tools.py` (`catalog`, `brand_of`, `category_of`, `color_family_of`, counted `search_products`, `matching_ids`), `backend/models.py` (`SearchResults`, `CatalogItem`, `CatalogListing`, `FacetCount`, `SortOption`, `PageUpdate`/`PageResult` browse + filters, `AgentReply.suggestions`) |
| Agent | `backend/agent.py` (`browse_catalog` tool, size-aware search, product-count checker, browse page action, suggestions), `backend/prompts/prompt.md` ("Always say how many match", "Brands and colors", browse rows, "Suggested next questions") |
| Front end | `Navbar.tsx` (order), `ProductsPage.tsx` (sidebar), `ProductCard.tsx` (equal boxes, brand · color), `ChatWidget.tsx` (starters, suggestions, browse/sort navigation, retry, bold), `HomePage.tsx`, `types.ts`, `api/client.ts`, `index.css` |
| Dependencies | `requirements.txt` (+ `pillow`, `numpy`, `scipy` for the photo script) |
