"""Tools the chat agent calls. Every answer comes from data/campus_customs.db, never from the model's memory."""

from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path

from models import (
    ChatHistoryMessage,
    CatalogItem,
    CatalogListing,
    ChatResponse,
    Conversation,
    CustomerProfile,
    FacetCount,
    LookupMiss,
    PastExchange,
    ProductCard,
    ProductInfo,
    SearchResults,
    SizeAvailability,
    SizeCheck,
    SizeStock,
    StockCount,
)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DB_PATH = DATA_DIR / "campus_customs.db"
RAW_PHOTOS = DATA_DIR / "products"  # from the data pack, never modified
WEB_PHOTOS = DATA_DIR / "products_web"  # white-background, same-size copies the site serves
PHOTO_VERSION = 0  # newest web photo's timestamp; set by refresh_photo_version()


def refresh_photo_version() -> None:
    """Version photo URLs by the newest web photo, so browsers fetch fresh copies after photos are rebuilt.
    (The folder's own timestamp doesn't change when files are overwritten.)"""
    global PHOTO_VERSION
    PHOTO_VERSION = max((int(f.stat().st_mtime) for f in WEB_PHOTOS.glob("*.jpg")), default=0)


def photo_url(image_file_path: str) -> str:
    """URL for a product photo (image_file_path is stored as "products/<file>.jpg")."""
    return f"/media/{Path(image_file_path).name}?v={PHOTO_VERSION}"


SIZE_ORDER = ["XS", "S", "M", "L", "XL", "XXL"]
STOP_WORDS = {
    "a", "an", "the", "and", "or", "for", "in", "of", "with", "do", "you", "have", "any", "me", "show", "some",
    "i", "my", "need", "want", "looking", "something", "gift", "gifts", "under", "below", "less", "than", "cheap",
    "items", "stuff", "things", "merch", "gear", "please", "what", "is", "are", "your", "got", "find",
}

COLOR_WORDS = {
    "blue", "navy", "gray", "grey", "charcoal", "heather", "white", "black", "red", "green", "pink",
    "purple", "yellow", "orange", "maroon", "brown", "cream", "gold",
}
# What else a shopper's word should match in the catalogue.
SYNONYMS = {
    "blue": ["blue", "navy"],
    "grey": ["gray", "grey"],
    "gray": ["gray", "grey"],
    "tee": ["tee", "t-shirt"],
    "tshirt": ["t-shirt", "tee"],
    "t-shirt": ["t-shirt", "tee"],
    "shirt": ["shirt", "tee"],
    "sweatshirt": ["sweatshirt", "crewneck"],
    "crew": ["crewneck", "crew"],
    "hoody": ["hoodie", "hood"],
    "quarterzip": ["quarter-zip", "1/4 zip"],
    "quarter-zip": ["quarter-zip", "1/4 zip"],
    "fleece": ["fleece"],
}


# Brands named in product names/descriptions (the catalogue has no brand column).
BRANDS = [
    ("Champion", ["champion"]),
    ("Under Armour", ["under armour", "ua-"]),
    ("Brooks Brothers", ["brooks brothers", "brooks-brothers"]),
    ("District", ["district"]),
    ("Hype and Vice", ["hype and vice", "hype-and-vice"]),
    ("Maplehouse", ["maplehouse"]),
]
HOUSE_BRAND = "Campus Customs design"

# garment_type is free text with 22 variants; map it to the 7 categories shoppers browse by (checked in order).
CATEGORIES = [
    ("T-shirts", ["t-shirt", "t shirt", "tee"]),
    ("Long sleeves", ["long-sleeve", "long sleeve"]),
    ("Quarter-zips", ["quarter-zip", "1/4 zip"]),
    ("Hoodies", ["hood"]),  # pullover and full-zip hoodies: shoppers count both as hoodies
    ("Jackets & fleece", ["jacket", "fleece"]),
    ("Crewnecks", ["crew", "mockneck", "sweatshirt"]),
]
COLOR_FAMILIES = [
    ("Navy", ["navy"]),
    ("Gray", ["gray", "grey", "charcoal", "heather"]),
    ("White & cream", ["white", "cream", "ivory"]),
    ("Coral", ["coral"]),
]
NO_COLOR = "Not listed"


def brand_of(row: sqlite3.Row) -> str:
    text = f"{row['product_id']} {row['name']} {row['description']}".lower()
    return next((brand for brand, keys in BRANDS if any(k in text for k in keys)), HOUSE_BRAND)


def category_of(row: sqlite3.Row) -> str:
    garment = row["garment_type"].lower()
    return next((cat for cat, keys in CATEGORIES if any(k in garment for k in keys)), "Other")


def color_family_of(colors: list[str]) -> str:
    """The garment's own color (colors[0]); the rest of the list are print colors."""
    if not colors:
        return NO_COLOR
    main = colors[0].lower()
    return next((fam for fam, keys in COLOR_FAMILIES if any(k in main for k in keys)), colors[0].title())


def _word_matches(word: str, main_color: str, text: str) -> bool:
    """Color words must match the garment's own color (colors[0]), not a print color.
    e.g. a heather gray hoodie with navy lettering is not a "navy hoodie"."""
    haystack = main_color if word in COLOR_WORDS else text
    return any(alt in haystack for alt in SYNONYMS.get(word, [word]))


def _keywords(query: str) -> list[str]:
    """Lowercase search words without filler, numbers or plural endings ("hoodies" -> "hoodie")."""
    words = []
    for w in re.findall(r"[a-z0-9-]+", query.lower()):
        if w in STOP_WORDS or w.strip("$").isdigit():
            continue
        if len(w) > 4 and w.endswith("ies") and not w.endswith("hoodies"):
            w = w[:-3] + "y"
        elif len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
            w = w[:-1]
        words.append(w)
    return words


def connect(write: bool = False) -> sqlite3.Connection:
    """A fresh connection per call (agent tools run in worker threads; sqlite connections can't cross threads).

    Read-only by default: every product, stock and price tool opens the database with SQLite's mode=ro, so
    no tool can create, change or cancel an order, change a size, or alter stock, even by mistake. Only
    saving chat history (save_exchange) and the one-time column migration ask for write access."""
    if write:
        conn = sqlite3.connect(DB_PATH)
    else:
        conn = sqlite3.connect(f"{DB_PATH.as_uri()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _stock(conn: sqlite3.Connection, product_id: str) -> list[SizeStock]:
    rows = conn.execute("SELECT size, quantity FROM inventory WHERE product_id = ?", (product_id,)).fetchall()
    sizes = [SizeStock(size=r["size"], quantity=r["quantity"]) for r in rows]
    return sorted(sizes, key=lambda s: SIZE_ORDER.index(s.size))


def _status(sizes: list[SizeStock]) -> str:
    in_stock = sum(1 for s in sizes if s.quantity > 0)
    if in_stock == 0:
        return "sold_out"
    return "in_stock" if in_stock == len(sizes) else "partly_sold_out"


def _to_info(conn: sqlite3.Connection, row: sqlite3.Row) -> ProductInfo:
    sizes = _stock(conn, row["product_id"])
    return ProductInfo(
        product_id=row["product_id"],
        name=row["name"],
        garment_type=row["garment_type"],
        description=row["description"],
        colors=json.loads(row["colors"]),
        color_family=color_family_of(json.loads(row["colors"])),
        brand=brand_of(row),
        category=category_of(row),
        price=row["price"],
        sizes=[SizeAvailability(size=s.size, in_stock=s.quantity > 0) for s in sizes],
        in_stock_sizes=[s.size for s in sizes if s.quantity > 0],
        sold_out_sizes=[s.size for s in sizes if s.quantity == 0],
        stock_status=_status(sizes),
    )


def _row(conn: sqlite3.Connection, product_id: str) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM catalogue WHERE product_id = ?", (product_id,)).fetchone()


def _normalize_size(size: str) -> str:
    size = size.strip().upper()
    aliases = {"EXTRA SMALL": "XS", "SMALL": "S", "MEDIUM": "M", "LARGE": "L", "EXTRA LARGE": "XL", "2XL": "XXL"}
    return aliases.get(size, size)


def _rank(
    conn: sqlite3.Connection, query: str, max_price: float | None, size: str | None, match_all: bool
) -> list[sqlite3.Row]:
    """Products ranked by how many query words they contain (name hits count double)."""
    words = _keywords(query)
    size = _normalize_size(size) if size else None
    scored = []
    for row in conn.execute("SELECT * FROM catalogue").fetchall():
        if max_price is not None and row["price"] > max_price:
            continue
        if size and not conn.execute(
            "SELECT 1 FROM inventory WHERE product_id = ? AND size = ? AND quantity > 0", (row["product_id"], size)
        ).fetchone():
            continue
        name = row["name"].lower()
        colors = json.loads(row["colors"])
        main_color = colors[0].lower() if colors else ""
        text = " ".join([name, row["garment_type"], row["description"], *colors, row["search_tags"]]).lower()
        hits = [w for w in words if _word_matches(w, main_color, text)]
        if match_all and len(hits) < len(words):
            continue
        score = sum(2 if w in name else 1 for w in hits) if words else 1
        if score > 0:
            scored.append((score, row))
    scored.sort(key=lambda pair: (-pair[0], pair[1]["name"]))
    return [row for _, row in scored]


def search_products(
    query: str, max_price: float | None = None, size: str | None = None, limit: int = 8
) -> SearchResults:
    """Count every product matching ALL the words (within budget / in stock in `size`), and return the best ones.
    If nothing matches every word, return the closest partial matches and say so (exact_match=False)."""
    with connect() as conn:
        exact = _rank(conn, query, max_price, None, match_all=True)
        in_size = _rank(conn, query, max_price, size, match_all=True) if size else exact
        rows = in_size if size else exact
        exact_match = bool(rows)
        if not rows:
            rows = _rank(conn, query, max_price, size, match_all=False)
        infos = [_to_info(conn, row) for row in rows[: max(1, min(limit, 12))]]
        in_stock = sum(1 for r in in_size if _status(_stock(conn, r["product_id"])) != "sold_out")
    return SearchResults(
        query=query, total_matches=len(exact), in_stock_matches=in_stock, exact_match=exact_match, products=infos
    )


def matching_ids(query: str, max_price: float | None = None, size: str | None = None) -> list[str]:
    """Every product id that contains all the search words (used to complete the results page)."""
    with connect() as conn:
        return [row["product_id"] for row in _rank(conn, query, max_price, size, match_all=True)]


SORT_KEYS = {
    "price_low": lambda i: (i.price, i.name),
    "price_high": lambda i: (-i.price, i.name),
    "name": lambda i: i.name,
    "color": lambda i: ([f for f, _ in COLOR_FAMILIES].index(i.color_family) if i.color_family in dict(COLOR_FAMILIES) else 99, i.name),
    "brand": lambda i: (i.brand == HOUSE_BRAND, i.brand, i.name),  # named brands first, then house designs
    "category": lambda i: ([c for c, _ in CATEGORIES].index(i.category) if i.category in dict(CATEGORIES) else 99, i.price, i.name),
}


def catalog(
    sort: str = "featured",
    category: str | None = None,
    color: str | None = None,
    brand: str | None = None,
    max_price: float | None = None,
    size: str | None = None,
    ids: list[str] | None = None,
) -> CatalogListing:
    """Sort and filter the catalogue. `ids` limits it to a set of products (chat search results, kept in
    that order for sort='featured'). Facet counts describe the set before the category/color/brand filters."""
    size = _normalize_size(size) if size else None
    with connect() as conn:
        rows = conn.execute("SELECT * FROM catalogue ORDER BY name").fetchall()
        stock = {}
        for r in conn.execute("SELECT product_id, size, quantity FROM inventory"):
            stock.setdefault(r["product_id"], []).append(SizeStock(size=r["size"], quantity=r["quantity"]))
    if ids is not None:
        order = {pid: i for i, pid in enumerate(ids)}
        rows = sorted((r for r in rows if r["product_id"] in order), key=lambda r: order[r["product_id"]])
    items = []
    for r in rows:
        sizes = sorted(stock.get(r["product_id"], []), key=lambda x: SIZE_ORDER.index(x.size))
        items.append(CatalogItem(
            product_id=r["product_id"], name=r["name"], garment_type=r["garment_type"], category=category_of(r),
            brand=brand_of(r), color_family=color_family_of(json.loads(r["colors"])), description=r["description"],
            price=r["price"], image_url=photo_url(r["image_file_path"]),
            in_stock_sizes=[x.size for x in sizes if x.quantity > 0], stock_status=_status(sizes),
        ))
    if max_price is not None:
        items = [i for i in items if i.price <= max_price]
    if size:
        items = [i for i in items if size in i.in_stock_sizes]

    def facet(attr: str, order: list[str]) -> list[FacetCount]:
        counts: dict[str, int] = {}
        for i in items:
            counts[getattr(i, attr)] = counts.get(getattr(i, attr), 0) + 1
        return [FacetCount(value=v, count=counts[v]) for v in sorted(counts, key=lambda v: (v not in order, order.index(v) if v in order else 0, v))]

    facets = {
        "category": facet("category", [c for c, _ in CATEGORIES]),
        "color": facet("color_family", [f for f, _ in COLOR_FAMILIES]),
        "brand": facet("brand", [b for b, _ in BRANDS] + [HOUSE_BRAND]),
    }
    if category:
        items = [i for i in items if i.category.lower() == category.lower()]
    if color:
        items = [i for i in items if i.color_family.lower() == color.lower()]
    if brand:
        items = [i for i in items if i.brand.lower() == brand.lower()]
    sort = sort if sort in SORT_KEYS or sort == "featured" else "featured"
    if sort in SORT_KEYS:
        items.sort(key=SORT_KEYS[sort])
    return CatalogListing(
        sort=sort, total=len(items), in_stock=sum(1 for i in items if i.stock_status != "sold_out"),
        products=items, facets=facets,
    )


def get_product_info(product_id: str) -> ProductInfo | LookupMiss:
    with connect() as conn:
        row = _row(conn, product_id)
        if row is None:
            return LookupMiss(message=f"No product with id {product_id!r}. Search for it instead of guessing.")
        return _to_info(conn, row)


def check_size(product_id: str, size: str) -> SizeCheck | LookupMiss:
    size = _normalize_size(size)
    if size not in SIZE_ORDER:
        return LookupMiss(message=f"{size!r} isn't a size we carry. Sizes are XS, S, M, L, XL, XXL.")
    with connect() as conn:
        row = _row(conn, product_id)
        if row is None:
            return LookupMiss(message=f"No product with id {product_id!r}.")
        sizes = _stock(conn, product_id)
    qty = next((s.quantity for s in sizes if s.size == size), 0)
    return SizeCheck(
        product_id=product_id, name=row["name"], price=row["price"], size=size, in_stock=qty > 0,
        other_sizes_in_stock=[s.size for s in sizes if s.quantity > 0 and s.size != size],
    )


def get_stock_count(product_id: str, size: str | None = None) -> StockCount | LookupMiss:
    with connect() as conn:
        row = _row(conn, product_id)
        if row is None:
            return LookupMiss(message=f"No product with id {product_id!r}.")
        sizes = _stock(conn, product_id)
    listed = sizes
    if size:
        size = _normalize_size(size)
        listed = [s for s in sizes if s.size == size]
        if not listed:
            return LookupMiss(message=f"{size!r} isn't a size we carry. Sizes are XS, S, M, L, XL, XXL.")
    return StockCount(
        product_id=product_id, name=row["name"], sizes=listed, total_units=sum(s.quantity for s in listed),
        sold_out_sizes=[s.size for s in sizes if s.quantity == 0], stock_status=_status(sizes),
    )


def price_list() -> dict[str, list[float]]:
    """Every garment type and the prices it sells at, for 'how much are your hoodies?' questions."""
    with connect() as conn:
        rows = conn.execute("SELECT garment_type, price FROM catalogue").fetchall()
    out: dict[str, set[float]] = {}
    for r in rows:
        out.setdefault(r["garment_type"], set()).add(r["price"])
    return {k: sorted(v) for k, v in sorted(out.items())}


def find_similar(product_id: str, limit: int = 4) -> list[ProductInfo]:
    """Other products sharing the most tags/colors with this one (same garment type ranks higher)."""
    with connect() as conn:
        base = conn.execute("SELECT * FROM catalogue WHERE product_id = ?", (product_id,)).fetchone()
        if base is None:
            return []
        base_tags = {t.lower() for t in json.loads(base["search_tags"])}
        base_colors = {c.lower() for c in json.loads(base["colors"])}
        scored = []
        for row in conn.execute("SELECT * FROM catalogue WHERE product_id != ?", (product_id,)):
            tags = {t.lower() for t in json.loads(row["search_tags"])}
            colors = {c.lower() for c in json.loads(row["colors"])}
            score = 2 * len(tags & base_tags) + len(colors & base_colors) + (3 if row["garment_type"] == base["garment_type"] else 0)
            if score:
                scored.append((score, row))
        scored.sort(key=lambda pair: (-pair[0], pair[1]["name"]))
        return [_to_info(conn, row) for _, row in scored[: max(1, min(limit, 8))]]


def product_cards(product_ids: list[str]) -> list[ProductCard]:
    """Turn the agent's chosen ids into cards, dropping any id that isn't really in the catalogue."""
    cards: list[ProductCard] = []
    with connect() as conn:
        for pid in dict.fromkeys(product_ids):
            row = conn.execute("SELECT * FROM catalogue WHERE product_id = ?", (pid,)).fetchone()
            if row is None:
                continue
            info = _to_info(conn, row)
            cards.append(ProductCard(
                product_id=info.product_id,
                name=info.name,
                price=info.price,
                image_url=photo_url(row["image_file_path"]),
                garment_type=info.garment_type,
                in_stock_sizes=info.in_stock_sizes,
            ))
    return cards


def existing_product_ids(product_ids: list[str]) -> list[str]:
    """The ids (in order, de-duplicated) that really exist in the catalogue."""
    ids = list(dict.fromkeys(product_ids))
    if not ids:
        return []
    with connect() as conn:
        rows = conn.execute(
            f"SELECT product_id FROM catalogue WHERE product_id IN ({','.join('?' * len(ids))})", ids
        ).fetchall()
    found = {r["product_id"] for r in rows}
    return [pid for pid in ids if pid in found]


# ---------------------------------------------------------------------------
# Customer memory: who the shopper is and what they asked before
# ---------------------------------------------------------------------------


def ensure_chat_schema() -> None:
    """Add chat_messages.conversation_id (nullable) so messages can be grouped into chats."""
    with connect(write=True) as conn:
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(chat_messages)")}
        if "conversation_id" not in cols:
            conn.execute("ALTER TABLE chat_messages ADD COLUMN conversation_id TEXT")


def get_customer_profile(user_id: int) -> CustomerProfile | LookupMiss:
    with connect() as conn:
        user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if user is None:
            return LookupMiss(message="No account found.")
        stats = conn.execute(
            "SELECT COUNT(*) AS questions, COUNT(DISTINCT COALESCE(conversation_id, date(created_at))) AS chats "
            "FROM chat_messages WHERE user_id = ? AND role = 'user'",
            (user_id,),
        ).fetchone()
    return CustomerProfile(
        first_name=user["first_name"], last_name=user["last_name"], email=user["email"],
        member_since=user["created_at"][:10], past_conversations=stats["chats"], past_questions=stats["questions"],
    )


def _parse_saved(products_json: str | None) -> tuple[list[dict], dict | None, dict | None]:
    """products_json is a list of product dicts (seed rows) or {"cards", "page", "context"} (our rows)."""
    if not products_json:
        return [], None, None
    data = json.loads(products_json)
    if isinstance(data, list):
        return data, None, None
    return data.get("cards", []), data.get("page"), data.get("context")


def recall_past_chats(
    user_id: int, query: str | None = None, limit: int = 5, exclude_conversation: str | None = None
) -> list[PastExchange]:
    """The shopper's earlier questions with Audrey's answers and the products shown, newest first."""
    with connect() as conn:
        rows = conn.execute(
            "SELECT role, content, products_json, created_at, conversation_id FROM chat_messages "
            "WHERE user_id = ? ORDER BY id",
            (user_id,),
        ).fetchall()
    exchanges: list[PastExchange] = []
    for q, a in zip(rows, rows[1:]):
        if q["role"] != "user" or a["role"] != "assistant":
            continue
        if exclude_conversation and q["conversation_id"] == exclude_conversation:
            continue
        cards, _, _ = _parse_saved(a["products_json"])
        shown = [f"{c['name']} (${c['price']:.2f})" for c in cards if "name" in c and "price" in c]
        exchanges.append(PastExchange(
            asked_at=q["created_at"], question=q["content"],
            answer=a["content"] if len(a["content"]) <= 300 else a["content"][:297] + "...",
            products_shown=shown,
        ))
    if query:
        words = _keywords(query)
        exchanges = [
            e for e in exchanges
            if any(w in " ".join([e.question, e.answer, *e.products_shown]).lower() for w in words)
        ]
    return list(reversed(exchanges))[: max(1, min(limit, 10))]


def save_exchange(user_id: int, conversation_id: str, question: str, response: ChatResponse) -> None:
    """Log the shopper's question and the full result (reply, cards, page results, context)."""
    saved = {
        "cards": [c.model_dump() for c in response.products],
        "page": response.page.model_dump() if response.page else None,
        "context": response.context.model_dump(),
    }
    with connect(write=True) as conn:
        conn.execute(
            "INSERT INTO chat_messages (user_id, role, content, conversation_id) VALUES (?, 'user', ?, ?)",
            (user_id, question, conversation_id),
        )
        conn.execute(
            "INSERT INTO chat_messages (user_id, role, content, products_json, conversation_id) "
            "VALUES (?, 'assistant', ?, ?, ?)",
            (user_id, response.reply, json.dumps(saved), conversation_id),
        )


def _card_from_saved(p: dict) -> ProductCard:
    # Seed rows saved image_url as "/media/products/<file>"; we serve "/media/<file>".
    image = Path((p.get("image_url") or p.get("image_file_path", "")).split("?")[0]).name
    sizes = p.get("in_stock_sizes")
    if sizes is None:
        sizes = [s["size"] for s in p.get("inventory", []) if s["quantity"] > 0]
    return ProductCard(
        product_id=p["product_id"], name=p["name"], price=p["price"], image_url=photo_url(image),
        garment_type=p.get("garment_type", ""), in_stock_sizes=sizes,
    )


def load_conversations(user_id: int, limit: int = 20) -> list[Conversation]:
    """The shopper's chats, newest first. Seed messages without a conversation_id are grouped by day."""
    with connect() as conn:
        rows = conn.execute(
            "SELECT role, content, products_json, created_at, conversation_id FROM chat_messages "
            "WHERE user_id = ? ORDER BY id",
            (user_id,),
        ).fetchall()
    grouped: dict[str, list[ChatHistoryMessage]] = {}
    for r in rows:
        key = r["conversation_id"] or f"earlier-{r['created_at'][:10]}"
        cards, page, context = _parse_saved(r["products_json"])
        grouped.setdefault(key, []).append(ChatHistoryMessage(
            role=r["role"], content=r["content"], created_at=r["created_at"],
            products=[_card_from_saved(c) for c in cards if {"product_id", "name", "price"} <= c.keys()],
            page=page, context=context,
        ))
    conversations = []
    for cid, msgs in grouped.items():
        first_q = next((m.content for m in msgs if m.role == "user"), "Chat")
        conversations.append(Conversation(
            conversation_id=cid, title=first_q if len(first_q) <= 60 else first_q[:57] + "...",
            started_at=msgs[0].created_at, last_message_at=msgs[-1].created_at, messages=msgs,
        ))
    conversations.sort(key=lambda c: c.last_message_at, reverse=True)
    return conversations[:limit]

# ---------------------------------------------------------------------------
# Product photos: white background, garment centered, same size (run once on first start)
# ---------------------------------------------------------------------------
# 73 of the 102 data-pack photos have black backgrounds baked into the JPG. These functions flood-fill the
# background white from the edges (and flat black gaps enclosed by sleeves), trim to the garment, and center
# it on an identical square. Originals in data/products/ are never changed.

PHOTO_SIZE = 900
PHOTO_MARGIN = 0.07  # empty space around the garment, as a share of the canvas
PHOTO_BLACK_THRESHOLD = 20  # backgrounds are ~0-10; the darkest navy garment pixels are ~30+
PHOTO_WHITE_THRESHOLD = 235
PHOTO_MAGIC = (255, 0, 255)  # temporary flood-fill color that never appears in the photos
PHOTO_MIN_HOLE = 150  # enclosed near-black areas at least this big (px) are background too, e.g. the gap under an arm
PHOTO_HOLE_MAX_MEAN = 5  # real background gaps average ~2 (flat black); dark navy fabric shadows average 11-15
PHOTO_FRINGE_THRESHOLD = 45  # dark JPEG speckles within 2px of the background get whitened


def _background_mask(im):
    """True where a pixel is background: near-black or near-white AND connected to the photo's edge."""
    import numpy as np
    from PIL import ImageDraw
    from scipy import ndimage

    filled = im.copy()
    w, h = im.size
    seeds = [(x, y) for x in range(0, w, max(1, w // 20)) for y in (0, h - 1)]
    seeds += [(x, y) for y in range(0, h, max(1, h // 20)) for x in (0, w - 1)]
    for xy in seeds:
        px = filled.getpixel(xy)
        if px == PHOTO_MAGIC:
            continue
        if max(px) <= PHOTO_BLACK_THRESHOLD or min(px) >= PHOTO_WHITE_THRESHOLD:
            ImageDraw.floodfill(filled, xy, PHOTO_MAGIC, thresh=PHOTO_BLACK_THRESHOLD)
    edge_bg = np.all(np.asarray(filled) == PHOTO_MAGIC, axis=-1)
    brightness = np.asarray(im).max(axis=-1)
    if not edge_bg.any() or np.median(brightness[edge_bg]) > PHOTO_BLACK_THRESHOLD:
        return edge_bg  # white-background photo: nothing black to chase inside the garment
    # Background trapped inside the garment's outline (between an arm and the body) isn't connected to the
    # edge, so the flood fill can't reach it. Such gaps are big, flat, pure black; fabric shadows are not.
    labels, n = ndimage.label((brightness <= PHOTO_BLACK_THRESHOLD) & ~edge_bg)
    if n:
        index = np.arange(1, n + 1)
        sizes = ndimage.sum(np.ones_like(labels), labels, index=index)
        means = ndimage.mean(brightness, labels, index=index)
        keep = index[(sizes >= PHOTO_MIN_HOLE) & (means <= PHOTO_HOLE_MAX_MEAN)]
        edge_bg |= np.isin(labels, keep)
    return edge_bg


def _clean_photo(path: Path):
    import numpy as np
    from PIL import Image, ImageFilter

    im = Image.open(path).convert("RGB")
    mask = _background_mask(im)
    # Grow the mask 2px into dark anti-aliased edge pixels so no black halo is left around the garment.
    grown = np.asarray(Image.fromarray(mask.astype(np.uint8) * 255).filter(ImageFilter.MaxFilter(5))) > 0
    arr = np.asarray(im).astype(np.int16)
    edge_dark = grown & ~mask & (arr.max(axis=-1) < PHOTO_FRINGE_THRESHOLD)
    out = arr.copy()
    out[mask | edge_dark] = 255
    out_im = Image.fromarray(out.astype(np.uint8))

    # Trim to the garment and center it on a square white canvas with the same margin for every photo.
    garment = ~(mask | edge_dark)
    ys, xs = np.nonzero(garment)
    if len(xs):
        out_im = out_im.crop((xs.min(), ys.min(), xs.max() + 1, ys.max() + 1))
    inner = int(PHOTO_SIZE * (1 - 2 * PHOTO_MARGIN))
    scale = inner / max(out_im.size)  # up or down, so every garment ends up the same size
    out_im = out_im.resize((round(out_im.width * scale), round(out_im.height * scale)), Image.LANCZOS)
    canvas = Image.new("RGB", (PHOTO_SIZE, PHOTO_SIZE), (255, 255, 255))
    canvas.paste(out_im, ((PHOTO_SIZE - out_im.width) // 2, (PHOTO_SIZE - out_im.height) // 2))
    return canvas


def prepare_product_photos(force: bool = False) -> int:
    """Write cleaned copies of any photos missing from data/products_web/ (all of them if force). Returns count."""
    WEB_PHOTOS.mkdir(exist_ok=True)
    todo = [p for p in sorted(RAW_PHOTOS.glob("*.jpg")) if force or not (WEB_PHOTOS / p.name).exists()]
    for path in todo:
        _clean_photo(path).save(WEB_PHOTOS / path.name, quality=90, optimize=True)
    refresh_photo_version()
    return len(todo)


if __name__ == "__main__":  # rebuild every photo: python tools.py
    print(f"Prepared {prepare_product_photos(force=True)} photos in {WEB_PHOTOS}")
