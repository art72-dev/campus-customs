"""Pydantic / PydanticAI structured types for the Campus Customs chat agent."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

# ---------------------------------------------------------------------------
# Tool results: what the agent's tools return, straight from the database
# ---------------------------------------------------------------------------


Size = Literal["XS", "S", "M", "L", "XL", "XXL"]
StockStatus = Literal["in_stock", "partly_sold_out", "sold_out"]


class SizeAvailability(BaseModel):
    """Whether one size can be bought. Deliberately has no count (counts only via get_stock_count)."""

    size: Size
    in_stock: bool


class ProductInfo(BaseModel):
    """One catalogue product: real description, price and availability, with no stock numbers."""

    product_id: str
    name: str
    garment_type: str
    description: str = Field(description="Exact catalogue description; don't embellish it")
    colors: list[str]
    color_family: str = Field(description="Garment's own color group: Navy, Gray, White & cream, Coral, or 'Not listed'")
    brand: str = Field(description="Brand named in the catalogue, or 'Campus Customs design' when no maker is named")
    category: str
    price: float = Field(description="Real price in USD from the catalogue table")
    sizes: list[SizeAvailability]
    in_stock_sizes: list[Size]
    sold_out_sizes: list[Size] = Field(description="Sizes with 0 units. Say these are sold out, clearly.")
    stock_status: StockStatus = Field(
        description="in_stock = every size available; partly_sold_out = some sizes at 0; sold_out = every size at 0"
    )


class SizeCheck(BaseModel):
    """Answer to 'do you have <product> in <size>?' (yes/no, no count)."""

    product_id: str
    name: str
    price: float
    size: Size
    in_stock: bool
    other_sizes_in_stock: list[Size] = Field(description="Alternatives to offer when this size is sold out")


class SizeStock(BaseModel):
    size: Size
    quantity: int = Field(ge=0)


class StockCount(BaseModel):
    """Exact units on hand, from the inventory table. Only for when the shopper asks how many."""

    product_id: str
    name: str
    sizes: list[SizeStock] = Field(description="Units per size; only the requested size if one was given")
    total_units: int = Field(description="Sum of the sizes listed")
    sold_out_sizes: list[Size]
    stock_status: StockStatus


class SearchResults(BaseModel):
    """search_products result: how many products match, how many can be bought, and the best ones."""

    query: str
    total_matches: int = Field(description="Products containing ALL the search words (and within budget/size)")
    in_stock_matches: int = Field(description="Of those, how many have at least one size in stock (or the requested size)")
    exact_match: bool = Field(description="False = nothing matched every word; `products` are only close matches")
    products: list[ProductInfo] = Field(description="Best matches first (a sample, not necessarily all of them)")


SortOption = Literal["featured", "price_low", "price_high", "name", "color", "brand", "category"]


class CatalogItem(BaseModel):
    """One product as listed on the Products page / returned by the sort tool."""

    product_id: str
    name: str
    garment_type: str
    category: str
    brand: str
    color_family: str
    description: str
    price: float
    image_url: str
    in_stock_sizes: list[Size]
    stock_status: StockStatus


class FacetCount(BaseModel):
    value: str
    count: int


class CatalogListing(BaseModel):
    """Sorted + filtered catalogue (the Products page and the browse_catalog tool)."""

    sort: SortOption
    total: int = Field(description="Products after filters")
    in_stock: int = Field(description="Of those, how many have at least one size in stock (or the filtered size)")
    products: list[CatalogItem]
    facets: dict[str, list[FacetCount]] = Field(
        default_factory=dict, description="category / color / brand options with product counts, for the sidebar"
    )


class LookupMiss(BaseModel):
    """Returned instead of data when a product id or size doesn't exist. Never fill the gap with a guess."""

    found: Literal[False] = False
    message: str


# ---------------------------------------------------------------------------
# Agent output and per-run context
# ---------------------------------------------------------------------------


class PageUpdate(BaseModel):
    """Tells the website to change the main page in response to the chat."""

    action: Literal["show_results", "open_product", "browse"] = Field(
        description="show_results = search results grid; open_product = one product's page; "
        "browse = the whole catalogue with sort/filters (no ids needed)"
    )
    title: str = Field(max_length=60, description="Short heading for the results, e.g. 'Navy hoodies under $70'")
    keywords: list[str] = Field(
        default_factory=list,
        max_length=6,
        description="Key words picked out of the shopper's message (color, garment, college, sport, family role, budget)",
    )
    product_ids: list[str] = Field(
        default_factory=list,
        max_length=30,
        description="Ids from this turn's tool results, your best matches first. Exactly 1 for open_product; empty for browse.",
    )
    search_query: str | None = Field(
        default=None,
        description="show_results only: the search words (e.g. 'navy hoodie'); the site adds every product matching all of them",
    )
    max_price: float | None = Field(default=None, description="Budget cap the shopper gave, in USD")
    sort: SortOption | None = Field(default=None, description="How to order the page, if the shopper asked")
    category: str | None = Field(default=None, description="browse only: a category from browse_catalog facets")
    color: str | None = Field(default=None, description="browse only: a color family from browse_catalog facets")
    brand: str | None = Field(default=None, description="browse only: a brand from browse_catalog facets")
    size: str | None = Field(default=None, description="Only show products in stock in this size")


class ShoppingContext(BaseModel):
    """What the shopper is currently looking for, carried from turn to turn so follow-ups make sense
    ("do you have it in blue?" after asking about sweatshirts = a blue sweatshirt)."""

    garment: str | None = Field(default=None, description="Garment being discussed, e.g. 'sweatshirt', 'hoodie', 't-shirt'")
    colors: list[str] = Field(default_factory=list, max_length=4, description="Colors the shopper asked for")
    other_keywords: list[str] = Field(
        default_factory=list, max_length=6, description="Other criteria: college, school, sport, family role, brand"
    )
    size: str | None = Field(default=None, description="Size the shopper mentioned, e.g. 'M'")
    max_price: float | None = Field(default=None, description="Budget the shopper gave, in USD")
    product_ids: list[str] = Field(
        default_factory=list, max_length=6, description="Products currently under discussion, most relevant first"
    )

    def is_empty(self) -> bool:
        return not any([self.garment, self.colors, self.other_keywords, self.size, self.max_price, self.product_ids])


class CustomerProfile(BaseModel):
    """Who the logged-in shopper is (tool result). Only ever about the shopper themselves."""

    first_name: str | None
    last_name: str | None
    email: str
    member_since: str
    past_conversations: int
    past_questions: int


class PastExchange(BaseModel):
    """One logged question + Audrey's answer and the products shown (tool result)."""

    asked_at: str
    question: str
    answer: str = Field(description="Audrey's reply, shortened")
    products_shown: list[str] = Field(description="'Name ($price)' of products shown with that answer")


class AgentReply(BaseModel):
    """What the agent must return each turn."""

    reply: str = Field(description="The message shown to the shopper, in the Campus Customs voice")
    product_ids: list[str] = Field(
        default_factory=list,
        max_length=6,
        description="product_id values from tool results to show as product cards (0-6). Never invent ids.",
    )
    page: PageUpdate | None = Field(
        default=None,
        description="Set when the shopper is searching/browsing (show_results) or asks to see one product (open_product); else null",
    )
    context: ShoppingContext = Field(
        default_factory=ShoppingContext,
        description="The updated shopping context after this turn: keep what still applies, add what's new, clear it if they change topic",
    )
    suggestions: list[str] = Field(
        default_factory=list,
        max_length=3,
        description="Up to 3 short next questions the shopper could tap (each under 45 characters), written as the shopper",
    )


@dataclass
class AgentDeps:
    """Per-request context the agent can see, plus the facts its tools returned this turn."""

    user_id: int | None = None  # None = guest
    first_name: str | None = None
    last_name: str | None = None
    email: str | None = None
    current_product_id: str | None = None
    conversation_id: str | None = None
    context: ShoppingContext = field(default_factory=ShoppingContext)
    # Filled in by the tools; the reply checker only allows $ prices / stock counts that appear here.
    seen_prices: set[float] = field(default_factory=set)
    seen_counts: set[int] = field(default_factory=set)
    seen_product_ids: set[str] = field(default_factory=set)


# ---------------------------------------------------------------------------
# Chat API (FastAPI request/response)
# ---------------------------------------------------------------------------


class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=4000)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1000)
    history: list[ChatTurn] = Field(default_factory=list, max_length=20, description="Earlier turns, oldest first")
    current_product_id: str | None = Field(default=None, description="Product page the shopper is viewing, if any")
    conversation_id: str | None = Field(default=None, max_length=64, description="Groups messages into one chat")
    context: ShoppingContext | None = Field(default=None, description="Shopping context returned by the last reply")


class ProductCard(BaseModel):
    """A product card shown under a chat reply."""

    product_id: str
    name: str
    price: float
    image_url: str
    garment_type: str
    in_stock_sizes: list[str]


class PageResult(BaseModel):
    """A validated PageUpdate sent to the browser (unknown ids removed)."""

    action: Literal["show_results", "open_product", "browse"]
    title: str
    keywords: list[str]
    product_ids: list[str] = Field(default_factory=list)
    sort: SortOption | None = None
    category: str | None = None
    color: str | None = None
    brand: str | None = None
    max_price: float | None = None
    size: str | None = None


class ChatResponse(BaseModel):
    reply: str
    products: list[ProductCard] = Field(default_factory=list)
    page: PageResult | None = None
    context: ShoppingContext = Field(default_factory=ShoppingContext)
    suggestions: list[str] = Field(default_factory=list)
    conversation_id: str | None = None
    saved: bool = Field(default=False, description="True when the exchange was logged to the shopper's history")


class ChatHistoryMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str
    products: list[ProductCard] = Field(default_factory=list)
    page: PageResult | None = None
    context: ShoppingContext | None = None
    created_at: str


class Conversation(BaseModel):
    """One past chat for the History view."""

    conversation_id: str
    title: str = Field(description="The first question asked")
    started_at: str
    last_message_at: str
    messages: list[ChatHistoryMessage]


# ---------------------------------------------------------------------------
# Website API: accounts and product pages (used by main.py)
# ---------------------------------------------------------------------------


class SignupRequest(BaseModel):
    """Create account form. Checked again here even though the browser checks it too."""

    first_name: str = Field(min_length=1, max_length=50)
    last_name: str = Field(min_length=1, max_length=50)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    confirm_password: str

    @field_validator("first_name", "last_name")
    @classmethod
    def strip_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("can't be blank")
        return v

    @model_validator(mode="after")
    def passwords_match(self) -> "SignupRequest":
        if self.password != self.confirm_password:
            raise ValueError("Passwords don't match")
        return self


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(max_length=128)


class User(BaseModel):
    """What the API returns about an account: never the password hash."""

    id: int
    first_name: str | None
    last_name: str | None
    email: str


class ProductDetail(BaseModel):
    """One product's page: everything shown next to the large photo."""

    product_id: str
    name: str
    garment_type: str
    description: str
    price: float
    image_url: str
    colors: list[str]
    sizes: list[SizeStock]
    total_stock: int


# ---------------------------------------------------------------------------
# Audit trail (output/audit_trail.json, append-only)
# ---------------------------------------------------------------------------

StopReason = Literal[
    "tool_result",  # a tool ran and its result went back to the model; the loop continues
    "tool_retry",  # a tool call was rejected (bad arguments) and the model was asked to try again
    "output_rejected",  # a safety/honesty check rejected the reply (made-up number, unseen id, order claim)
    "final_answer",  # the model returned its reply; the run ended normally
    "content_filter",  # the AI provider's content filter blocked the message
    "usage_limit",  # the loop hit MAX_MODEL_REQUESTS and was stopped
    "error",  # anything else went wrong
]


class AuditEntry(BaseModel):
    """One step of the agent loop. Every step of every chat message is appended, never rewritten."""

    timestamp: str = Field(description="When this step happened (UTC, ISO 8601)")
    run_id: str = Field(description="Groups the steps of one chat message")
    conversation_id: str | None = Field(default=None, description="Which chat the message belonged to")
    shopper: str = Field(description="'guest' or 'user #<id>'; never a name or email")
    step: int = Field(description="Order of this step within the run, from 1")
    model_call: int = Field(description="Which model request in the loop produced this step (max MAX_MODEL_REQUESTS)")
    question: str | None = Field(default=None, description="The shopper's message (first step only, shortened, redacted)")
    tool_name: str | None = Field(default=None, description="Tool called; null for the final answer or a stop event")
    tool_args: dict | None = Field(default=None, description="Arguments passed to the tool (shortened, redacted)")
    result_summary: str | None = Field(default=None, description="Short summary of the tool result, rejection or reply")
    stop_reason: StopReason
