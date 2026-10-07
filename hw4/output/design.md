# Campus Customs: Website Design (Problem 10)

> **The pitch:** Campus Customs is a site that's **easy to navigate**, **easy on the eye**, and **keeps shoppers engaged with the lingo**. That's what keeps people browsing long enough to find their fit and buy it.

This document records the design we landed on, what changed to get there, and why each choice keeps customers around and buying. The current colors, fonts and bulldogs are the final look; no style code changed in Problem 10.

---

## 1. The design at a glance

| Element | Choice | Where it lives |
|---|---|---|
| Background | Clean white (`#ffffff`), soft blue-gray panels (`#f3f6fb`) | `frontend/src/index.css` `:root` |
| Accent | **Yale blue** `#00356b` (buttons, prices, links, active filters), lighter `#286dc0` for small labels | `--accent`, `--accent-soft` |
| Text | Deep navy-black `#0f1b2d`; secondary gray `#5b6b80` | `--text`, `--muted` |
| Font | The device's own system font: San Francisco on Mac/iPhone, Segoe UI on Windows, Roboto on Android (the stylesheet lists "Inter" first, but it isn't loaded, so the system font is what shoppers see) | `font-family` in `:root` |
| Shapes | Rounded 14px cards and panels, pill-shaped buttons and chips, thin `#dbe3ee` borders | `--radius`, `.btn`, `.chip` |
| Product photos | All 102 on white, garment centered on an identical 900×900 square | `tools.prepare_product_photos()` → `data/products_web/` (automatic on first start) |
| Mascot | Two hand-built HTML/CSS bulldogs (one in a Yale cap on Home, one tilting its head on About Us) | `components/Bulldog.tsx`, `.bulldog` CSS |
| Motion | Gentle and short: bulldog bob + blink, fade-in for chat results, card lift on hover, typing dots. All off for "reduce motion" users | `@keyframes`, `prefers-reduced-motion` |
| Voice | Site copy in playful Gen Z lingo; the chat assistant "Audrey" in an elegant, Audrey Hepburn-inspired voice | Page components, `backend/prompts/prompt.md` |

---

## 2. What we changed (and when)

| When | Change | Before → after |
|---|---|---|
| Problem 3 | First build of Home, Products, item, About, Log in / Create account pages and the floating chat | Black-and-pink theme (the project default in `AGENTS.md`) |
| Problem 3 | Home and About copy rewritten in an exciting, Gen Z tone | Based on the real store's story (family-run, 57 Broadway, since the '70s), never copied word for word |
| Problem 5 follow-up (design prompt, logged under Problem 10) | **Theme switched to white + Yale blue.** Pink variables renamed to `--accent*`, so the whole site changed from one place | Dark background, pink accents → white background, Yale-blue accents |
| Same prompt | **Bulldogs added**, drawn entirely in HTML/CSS shapes (no images or emoji), per the project's "creatures in HTML" rule | None → bulldog in a Yale cap (Home), head-tilting bulldog (About Us) |
| Same prompt | `AGENTS.md` left unchanged: white/blue applies to **this site only** | |
| Problem 5 | Chat assistant given the "Audrey" voice: gracious, witty, polished | Generic bot → a host with personality |
| Problem 9 | **All product photos white and the same size**; equal-height cards; brand · color line on each card | 73 black + 29 white photos in 30+ sizes → 102 matching white 900×900 photos |
| Problem 9 | Navbar reordered; sort & filter sidebar; chat suggestion chips and starter questions; bold key facts | See `output/usability.md` |
| Problem 10 | **Kept the current colors, fonts and bulldogs** as the final look; documented the design (this file) | No code change |

---

## 3. Why customers stick around and buy

### 3.1 Easy to navigate

A shopper who can't find something leaves. Every step from "I'm curious" to "this is the one" is short:

- **A navbar that reads like a story:** Home · About Us · Products · Log in · Create account. Who we are, what we sell, then sign in. It stays pinned to the top on every page.
- **Two clicks to the right product:** the left sidebar narrows 102 products by category, color, brand, price and "in stock in my size", with counts next to every option so there are no dead ends. A "Clear filters" button is always one click away.
- **Or just ask:** "show me navy hoodies" in the chat fills the page with exactly those (17 of them), and "take me to the Yale Grandma Hoodie" opens it. Tappable suggestion chips mean you don't even have to type.
- **Every card works the same way:** photo, brand · color, name, short description, price; tap anywhere to open the item page (big photo on the left, details on the right). There's always a "← Back to products" link.
- **The page remembers where you are:** filters and chat searches live in the URL, so Back, Refresh and sharing a link all work.
- **No surprises at checkout time:** sold-out sizes are crossed out on the item page, and the size filter hides what you can't buy.

### 3.2 Easy on the eye

A calm, consistent page keeps attention on the clothes, and the clothes are what sell.

- **White + Yale blue:** a crisp, collegiate palette that matches the merch itself (most of it is navy, gray and white), so products look at home instead of clashing with a loud background.
- **Every photo on the same white square:** before, 73 photos had black backgrounds and the rest white, in 30+ sizes. Now the grid looks like a real storefront and garments are easy to compare side by side.
- **Equal boxes:** every card is the same height with the same photo size, so the eye moves across the grid in a clean rhythm and nothing looks "bigger" just because its photo was.
- **Readable for everyone:** every text color clears WCAG accessibility contrast:

  | Text | Contrast | Standard |
  |---|---|---|
  | Body text on white | 17.3 : 1 | AAA |
  | Yale blue on white (prices, headings) | 12.2 : 1 | AAA |
  | White on Yale blue (buttons) | 12.2 : 1 | AAA |
  | Light blue labels on white | 5.2 : 1 | AA |
  | Gray secondary text on white | 5.4 : 1 | AA |

- **Familiar, fast type:** the device's own system font looks native on every phone and laptop, loads instantly (nothing to download), and stays sharp at small sizes.
- **Soft shapes, light motion:** rounded corners and pill buttons feel friendly; animations are brief and subtle and switch off for anyone who prefers reduced motion.

### 3.3 Keeps shoppers engaged with the lingo (and a little bulldog charm)

People stay where they're having fun, and they buy from brands that feel like *them*.

- **Talks like campus:** the copy sounds like a friend, not a catalogue:

  | Where | Line |
  |---|---|
  | Home headline | "Your Yale fit **starts here.**" |
  | Home intro | "Hoodies, crewnecks, tees and quarter-zips that **hit different**… we've got **the drip**." |
  | Home perks | "**Family-run, fr**" · "Made in-house" · "merch that actually **slaps**" |
  | Featured products | "**Certified bangers**" |
  | Home call to action | "**Main character energy**, Yale edition." · "find the piece that's **lowkey** you" |
  | About Us | "**posted up** on Broadway, right across from Yale, since the '70s" · "that elevated, **old-money-but-make-it-campus** look" |
  | Create account | "**Join the squad**" |

- **A host with personality:** the chat assistant, Audrey, balances the slang with old-Hollywood grace ("A navy hoodie is the little black dress of New Haven"). She's warm, quick, and always honest about prices and stock. That contrast makes chatting feel like a boutique, not a search box.
- **The bulldogs:** a Yale-capped bulldog greets shoppers on Home and another tilts its head on About Us. They blink and gently bob, tying the site to Yale's mascot (Handsome Dan) and giving the brand a face people remember and come back to.
- **Engagement that leads to buying:** suggestion chips ("Which are in medium?", "Show me matching crewnecks") keep the conversation going toward a specific product in a specific size, which is the moment someone decides to buy.

---

## 4. Design rules to keep (for future changes)

1. **Keep the palette:** white backgrounds, Yale blue for anything clickable or important (prices, buttons, active filters). Change it through the `--accent*` variables, never hard-coded colors.
2. **Every product photo goes through `tools.prepare_product_photos()`** (it runs automatically for any new photo when the backend starts) so new products also land on a white 900×900 square.
3. **Cards stay identical:** photo, brand · color, 2-line name, 2-line description, price at the bottom.
4. **Bulldogs and any other creatures are built in HTML/CSS** (project rule), and no more than one per page so they stay special.
5. **Lingo on the site, grace in the chat:** playful Gen Z copy in headings and buttons; Audrey's elegant voice in the assistant. Slang never replaces clear information: prices, sizes and stock are always stated plainly.
6. **Accessibility is part of the look:** keep text contrast at WCAG AA or better and keep animations off for reduced-motion users.
7. **This theme is specific to the Campus Customs site.** `AGENTS.md` still sets black-and-pink as the default for other web apps.
