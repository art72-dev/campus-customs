"""The Campus Customs chat agent: gpt-5.6-luna through Portkey, with database-backed tools."""

from __future__ import annotations

import json
import os
import re
import threading
import uuid
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic_ai import Agent, ModelRetry, RunContext, capture_run_messages
from pydantic_ai.exceptions import ModelHTTPError, UsageLimitExceeded
from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    RetryPromptPart,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)
from pydantic_ai.models.openai import OpenAIResponsesModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.usage import UsageLimits

import tools
from models import (
    AgentDeps,
    AuditEntry,
    AgentReply,
    CatalogListing,
    ChatRequest,
    ChatResponse,
    CustomerProfile,
    LookupMiss,
    PageResult,
    PageUpdate,
    PastExchange,
    ProductInfo,
    SearchResults,
    ShoppingContext,
    SizeCheck,
    SortOption,
    StockCount,
    StopReason,
)

HERE = Path(__file__).resolve().parent
load_dotenv(HERE.parent / ".env")  # hw4/.env (copy of .env.example)
load_dotenv(HERE.parent.parent / ".env")  # or the folder above hw4/

MODEL_NAME = "gpt-5.6-luna"
DEFAULT_PORTKEY_URL = "https://api.portkey.ai/v1"
MAX_MODEL_REQUESTS = 8  # caps tool-call loops per chat message (cost + runaway protection)
AUDIT_PATH = HERE.parent / "output" / "audit_trail.json"
_audit_lock = threading.Lock()

# Replies that claim the assistant changed something it can't: orders, sizes, holds, payments.
ORDER_CLAIM_RE = re.compile(
    r"\b(?:I|we)(?:'ve| have| just)?\s+(?:placed|submitted|processed|confirmed|completed|changed|updated|"
    r"modified|swapped|switched|cancel+ed|reserved|held|set aside|put aside|charged|refunded|added (?:it|them|\w+) to your (?:cart|order))\b"
    r"|\byour (?:order|purchase|reservation|size)\s+(?:has been|is now|was|is)\s+(?:placed|confirmed|changed|updated|"
    r"modified|cancel+ed|reserved|processed|on (?:its|the) way|shipped)\b",
    re.IGNORECASE,
)
SYSTEM_PROMPT = (HERE / "prompts" / "prompt.md").read_text()

PRICE_RE = re.compile(r"\$\s?(\d[\d,]*(?:\.\d{1,2})?)")
COUNT_RE = re.compile(
    r"\b(?:only\s+)?(\d+)\s+(?:units?|pieces?|left|remaining|available|in stock)\b", re.IGNORECASE
)
# "17 navy hoodies", "12 results", "4 Champion styles" (number + up to 3 words + a product noun)
PRODUCT_COUNT_RE = re.compile(
    r"\b(\d+)\s+(?:[\w&'-]+\s+){0,3}?(?:products|items|results|matches|styles|options|designs|pieces|"
    r"hoodies|crewnecks|sweatshirts|t-shirts|tees|shirts|quarter-zips|jackets|fleeces|long sleeves)\b",
    re.IGNORECASE,
)


@lru_cache(maxsize=1)
def get_model() -> OpenAIResponsesModel:
    api_key = os.getenv("PORTKEY_API_KEY")
    if not api_key:
        raise RuntimeError("PORTKEY_API_KEY is missing from the workspace-root .env")
    provider = OpenAIProvider(api_key=api_key, base_url=os.getenv("PORTKEY_BASE_URL", DEFAULT_PORTKEY_URL))
    return OpenAIResponsesModel(MODEL_NAME, provider=provider)


def remember(deps: AgentDeps, result):
    """Record every price, count and product id a tool returned, for the reply checkers."""
    if isinstance(result, SearchResults):
        deps.seen_counts.update({result.total_matches, result.in_stock_matches, len(result.products)})
        remember(deps, result.products)
        return result
    if isinstance(result, CatalogListing):
        deps.seen_counts.update({result.total, result.in_stock, len(result.products)})
        deps.seen_counts.update(f.count for facet in result.facets.values() for f in facet)
        for item in result.products:
            deps.seen_prices.add(item.price)
            deps.seen_product_ids.add(item.product_id)
        return result
    for item in result if isinstance(result, list) else [result]:
        if isinstance(item, (ProductInfo, SizeCheck)):
            deps.seen_prices.add(item.price)
            deps.seen_product_ids.add(item.product_id)
        elif isinstance(item, StockCount):
            deps.seen_product_ids.add(item.product_id)
            deps.seen_counts.update(s.quantity for s in item.sizes)
            deps.seen_counts.add(item.total_units)
    return result


def invented_numbers(reply: str, deps: AgentDeps, shopper_text: str, listed: set[int] | None = None) -> list[str]:
    """Prices and stock counts in the reply that no tool returned (and the shopper didn't say)."""
    shopper_numbers = {float(n.replace(",", "")) for n in re.findall(r"\d[\d,]*(?:\.\d+)?", shopper_text)}
    prices = deps.seen_prices
    # Allow simple totals the shopper may ask for: up to 10 of one item, or two different items together.
    allowed_prices = {round(p * k, 2) for p in prices for k in range(1, 11)} | {
        round(a + b, 2) for a in prices for b in prices
    }
    problems = []
    for raw in PRICE_RE.findall(reply):
        value = float(raw.replace(",", ""))
        if value not in allowed_prices and value not in shopper_numbers:
            problems.append(f"price ${raw}")
    for raw in COUNT_RE.findall(reply):
        value = int(raw)
        if value not in deps.seen_counts and value not in shopper_numbers:
            problems.append(f"stock count {raw}")
    for raw in PRODUCT_COUNT_RE.findall(reply):
        value = int(raw)
        if 1900 <= value <= 2100:  # a year in a product name, e.g. "2025 Yale vs Harvard"
            continue
        if value not in deps.seen_counts and value not in (listed or set()) and value not in shopper_numbers:
            problems.append(f"product count {raw}")
    return problems


@lru_cache(maxsize=1)
def get_agent() -> Agent[AgentDeps, AgentReply]:
    agent = Agent(
        get_model(),
        deps_type=AgentDeps,
        output_type=AgentReply,
        instructions=SYSTEM_PROMPT,
        retries=2,
    )

    @agent.instructions
    def shopper_and_context(ctx: RunContext[AgentDeps]) -> str:
        return describe_shopper_and_context(ctx.deps)

    @agent.tool
    def search_products(
        ctx: RunContext[AgentDeps], query: str, max_price: float | None = None, size: str | None = None
    ) -> SearchResults:
        """Search by words like garment type, color, college, sport, family role or brand.
        Returns total_matches (products containing ALL the words), in_stock_matches, exact_match, and the
        best products with real description, price, colors, brand and in-stock / sold-out sizes (no counts).

        Args:
            query: e.g. "navy hoodie", "Saybrook", "mom", "hockey t-shirt".
            max_price: optional budget cap in USD.
            size: optional; only count/show products in stock in this size (XS, S, M, L, XL, XXL).
        """
        return remember(ctx.deps, tools.search_products(query, max_price=max_price, size=size))

    @agent.tool
    def browse_catalog(
        ctx: RunContext[AgentDeps],
        sort_by: SortOption = "featured",
        category: str | None = None,
        color: str | None = None,
        brand: str | None = None,
        max_price: float | None = None,
        size: str | None = None,
    ) -> CatalogListing:
        """Sort and filter the whole catalogue. Use for "sort by price", "cheapest hoodies", "what brands do you
        carry?", "everything by Champion", "all gray items", "what's in stock in XL?".

        Args:
            sort_by: featured, price_low, price_high, name, color, brand, or category.
            category: T-shirts, Long sleeves, Quarter-zips, Hoodies (pullover + full-zip), Jackets & fleece, Crewnecks.
            color: Navy, Gray, White & cream, Coral (the garment's own color).
            brand: Champion, Under Armour, Brooks Brothers, District, Hype and Vice, Maplehouse, Campus Customs design.
            max_price: budget cap in USD.
            size: only products in stock in this size.

        Returns the total, how many are in stock, facet counts (categories/colors/brands available) and the
        first 10 products in that order.
        """
        listing = tools.catalog(sort_by, category, color, brand, max_price, size)
        return remember(ctx.deps, listing.model_copy(update={"products": listing.products[:10]}))

    @agent.tool
    def get_product_info(ctx: RunContext[AgentDeps], product_id: str) -> ProductInfo | LookupMiss:
        """Real description, price, colors and size availability (in stock / sold out) for one product_id."""
        return remember(ctx.deps, tools.get_product_info(product_id))

    @agent.tool
    def check_size(ctx: RunContext[AgentDeps], product_id: str, size: str) -> SizeCheck | LookupMiss:
        """Is one size (XS, S, M, L, XL, XXL) in stock? Yes/no plus the other sizes in stock. No count."""
        return remember(ctx.deps, tools.check_size(product_id, size))

    @agent.tool
    def get_stock_count(
        ctx: RunContext[AgentDeps], product_id: str, size: str | None = None
    ) -> StockCount | LookupMiss:
        """Exact number of units on hand, per size (or for one size). ONLY call this when the shopper
        explicitly asks how many are left / in stock / available."""
        return remember(ctx.deps, tools.get_stock_count(product_id, size))

    @agent.tool
    def price_list(ctx: RunContext[AgentDeps]) -> dict[str, list[float]]:
        """Every garment type in the catalogue and the price(s) it sells at."""
        result = tools.price_list()
        for prices in result.values():
            ctx.deps.seen_prices.update(prices)
        return result

    @agent.tool
    def find_similar(ctx: RunContext[AgentDeps], product_id: str) -> list[ProductInfo]:
        """Up to 4 other products that match or pair well with this product_id."""
        return remember(ctx.deps, tools.find_similar(product_id))

    @agent.tool
    def get_customer_profile(ctx: RunContext[AgentDeps]) -> CustomerProfile | LookupMiss:
        """Who the logged-in shopper is: first/last name, email, member since, and how many past chats.
        Use for "who am I?", "what email is my account?", or before personalising. Guests get found=false."""
        if ctx.deps.user_id is None:
            return LookupMiss(message="The shopper is a guest (not logged in). Suggest logging in to save chats.")
        return tools.get_customer_profile(ctx.deps.user_id)

    @agent.tool
    def recall_past_chats(ctx: RunContext[AgentDeps], query: str | None = None) -> list[PastExchange] | LookupMiss:
        """The shopper's earlier questions, your answers and the products shown, newest first (from past
        conversations). Use for "what did you show me before?", "that hoodie from yesterday", "like last time".

        Args:
            query: optional words to filter by, e.g. "hoodie", "Saybrook".
        """
        if ctx.deps.user_id is None:
            return LookupMiss(message="Guests have no saved chats. Suggest logging in so chats are remembered.")
        past = tools.recall_past_chats(
            ctx.deps.user_id, query=query, exclude_conversation=ctx.deps.conversation_id
        )
        return past or LookupMiss(message="No earlier chats match." if query else "No earlier chats yet.")

    @agent.output_validator
    def page_update_is_grounded(ctx: RunContext[AgentDeps], output: AgentReply) -> AgentReply:
        page = output.page
        if page is None:
            return output
        unseen = [pid for pid in page.product_ids if pid not in ctx.deps.seen_product_ids]
        if unseen:
            raise ModelRetry(
                f"page.product_ids {unseen} didn't come from a tool result this turn. Call search_products or "
                "get_product_info and use the ids it returns."
            )
        if page.action == "open_product" and len(page.product_ids) != 1:
            raise ModelRetry("For page.action='open_product' give exactly one product_id.")
        if page.action == "show_results" and not page.product_ids and not page.search_query:
            raise ModelRetry("For page.action='show_results' give product_ids and/or search_query.")
        return output

    @agent.output_validator
    def no_made_up_numbers(ctx: RunContext[AgentDeps], output: AgentReply) -> AgentReply:
        listed = {len(output.product_ids)} | ({len(output.page.product_ids)} if output.page else set())
        problems = invented_numbers(output.reply, ctx.deps, ctx.prompt if isinstance(ctx.prompt, str) else "", listed)
        if problems:
            raise ModelRetry(
                "Your reply states numbers no tool returned this turn: " + "; ".join(problems)
                + ". Look them up with the tools (get_stock_count only if the shopper asked how many), "
                "or remove them. Never estimate prices or stock."
            )
        return output

    @agent.output_validator
    def no_order_actions(ctx: RunContext[AgentDeps], output: AgentReply) -> AgentReply:
        claim = ORDER_CLAIM_RE.search(output.reply)
        if claim:
            raise ModelRetry(
                f"Your reply says {claim.group(0)!r}, but you cannot place, change, cancel or hold orders, change "
                "sizes, or take payment, and nothing was done. Rewrite it: say you can't do that in chat and point "
                "the shopper to the Campus Customs team at 57 Broadway."
            )
        return output

    return agent


def describe_shopper_and_context(deps: AgentDeps) -> str:
    """Per-turn instructions: who the shopper is, where they are, and what they're shopping for."""
    lines = []
    if deps.user_id is None:
        lines.append("The shopper is a GUEST (not logged in). Their chat is not saved.")
    else:
        name = " ".join(n for n in [deps.first_name, deps.last_name] if n)
        lines.append(
            f"The shopper is logged in as {name} <{deps.email}>. Greet them by first name now and then. "
            "Their chats are saved; call recall_past_chats when they refer to earlier conversations."
        )
    if deps.current_product_id:
        lines.append(f"The shopper is viewing the product page for product_id={deps.current_product_id}.")
    c = deps.context
    if c.is_empty():
        lines.append("Shopping context: nothing yet.")
    else:
        parts = []
        if c.garment:
            parts.append(f"garment={c.garment}")
        if c.colors:
            parts.append(f"colors={', '.join(c.colors)}")
        if c.other_keywords:
            parts.append(f"also={', '.join(c.other_keywords)}")
        if c.size:
            parts.append(f"size={c.size}")
        if c.max_price:
            parts.append(f"budget<=${c.max_price:g}")
        if c.product_ids:
            parts.append(f"products in discussion={', '.join(c.product_ids)}")
        lines.append(
            "Shopping context from earlier turns: " + "; ".join(parts) + ". Use it to understand follow-ups "
            "(e.g. 'do you have it in blue?' keeps the garment and changes the color)."
        )
    return "\n".join(lines)


def to_message_history(request: ChatRequest) -> list[ModelMessage]:
    history: list[ModelMessage] = []
    for turn in request.history:
        if turn.role == "user":
            history.append(ModelRequest(parts=[UserPromptPart(content=turn.content)]))
        else:
            history.append(ModelResponse(parts=[TextPart(content=turn.content)]))
    return history


# ---------------------------------------------------------------------------
# Audit trail: output/audit_trail.json, append-only (one entry per step of the agent loop)
# ---------------------------------------------------------------------------

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
CARD_RE = re.compile(r"\b(?:\d[ -]?){13,19}\b")


def redact(text: str, limit: int) -> str:
    """Shorten, and strip emails and card-like numbers, before anything is written to the audit file."""
    text = CARD_RE.sub("[number removed]", EMAIL_RE.sub("[email removed]", " ".join(str(text).split())))
    return text if len(text) <= limit else text[: limit - 1] + "…"


def summarize_result(content) -> str:
    """One short line describing a tool result."""
    names = lambda items: ", ".join(i.name for i in items[:3]) + ("…" if len(items) > 3 else "")
    if isinstance(content, SearchResults):
        return (f"{content.total_matches} match, {content.in_stock_matches} in stock, exact={content.exact_match}; "
                f"top: {names(content.products)}")
    if isinstance(content, CatalogListing):
        return f"{content.total} products ({content.in_stock} in stock), sort={content.sort}; first: {names(content.products)}"
    if isinstance(content, ProductInfo):
        return (f"{content.name} ${content.price:.2f}; in stock {', '.join(content.in_stock_sizes) or 'none'}; "
                f"sold out {', '.join(content.sold_out_sizes) or 'none'}")
    if isinstance(content, SizeCheck):
        return f"{content.name} {content.size}: {'in stock' if content.in_stock else 'sold out'}"
    if isinstance(content, StockCount):
        return f"{content.name}: " + ", ".join(f"{x.size}={x.quantity}" for x in content.sizes) + f" (total {content.total_units})"
    if isinstance(content, LookupMiss):
        return f"not found: {content.message}"
    if isinstance(content, CustomerProfile):
        return f"profile returned (member since {content.member_since}, {content.past_questions} past questions)"
    if isinstance(content, list):
        if content and isinstance(content[0], ProductInfo):
            return f"{len(content)} products: {names(content)}"
        if content and isinstance(content[0], PastExchange):
            return f"{len(content)} past exchanges"
        return f"{len(content)} items"
    if isinstance(content, dict):
        return f"{len(content)} entries"
    return redact(content, 160)


def short_args(args) -> dict | None:
    if args is None:
        return None
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except json.JSONDecodeError:
            return {"raw": redact(args, 120)}
    return {k: redact(v, 80) if isinstance(v, str) else v for k, v in args.items()}


def build_audit_entries(
    messages: list[ModelMessage], run_id: str, deps: AgentDeps, question: str, end: StopReason | None, note: str | None
) -> list[AuditEntry]:
    """Walk this run's messages: one entry per tool call, rejection, and the final answer (or stop event)."""
    common = dict(
        run_id=run_id, conversation_id=deps.conversation_id,
        shopper="guest" if deps.user_id is None else f"user #{deps.user_id}",
    )
    entries: list[AuditEntry] = []
    calls: dict[str, ToolCallPart] = {}
    model_call = 0
    last_time = datetime.now(timezone.utc)

    def add(**fields) -> None:
        entries.append(AuditEntry(step=len(entries) + 1, model_call=model_call, **common, **fields))

    for msg in messages:
        if isinstance(msg, ModelResponse):
            model_call += 1
            last_time = msg.timestamp
            for part in msg.parts:
                if isinstance(part, ToolCallPart):
                    calls[part.tool_call_id] = part
                    if part.tool_name == "final_result":
                        args = part.args_as_dict()
                        page = args.get("page") or {}
                        summary = redact(args.get("reply", ""), 200)
                        if page:
                            summary += f" [page: {page.get('action')} '{redact(page.get('title', ''), 40)}']"
                        if args.get("product_ids"):
                            summary += f" [{len(args['product_ids'])} cards]"
                        add(timestamp=msg.timestamp.isoformat(), tool_name=None, result_summary=summary,
                            stop_reason="final_answer")
        elif isinstance(msg, ModelRequest):
            for part in msg.parts:
                if isinstance(part, ToolReturnPart) and part.tool_name != "final_result":
                    call = calls.get(part.tool_call_id)
                    add(timestamp=part.timestamp.isoformat(), tool_name=part.tool_name,
                        tool_args=short_args(call.args if call else None),
                        result_summary=summarize_result(part.content), stop_reason="tool_result")
                elif isinstance(part, RetryPromptPart):
                    call = calls.get(part.tool_call_id) if part.tool_call_id else None
                    is_output = part.tool_name in (None, "final_result")
                    if is_output and entries and entries[-1].stop_reason == "final_answer":
                        entries.pop()  # that reply was rejected, so it wasn't really the final answer
                    add(timestamp=part.timestamp.isoformat(), tool_name=None if is_output else part.tool_name,
                        tool_args=None if is_output else short_args(call.args if call else None),
                        result_summary=redact(part.content if isinstance(part.content, str) else str(part.content), 220),
                        stop_reason="output_rejected" if is_output else "tool_retry")
    if end:
        add(timestamp=datetime.now(timezone.utc).isoformat(), tool_name=None, result_summary=note, stop_reason=end)
    if entries:
        entries[0].question = redact(question, 150)
    return entries


def append_audit(entries: list[AuditEntry]) -> None:
    """Add entries to output/audit_trail.json without ever removing earlier ones."""
    if not entries:
        return
    with _audit_lock:
        AUDIT_PATH.parent.mkdir(exist_ok=True)
        existing = json.loads(AUDIT_PATH.read_text()) if AUDIT_PATH.exists() else []
        existing.extend(e.model_dump() for e in entries)
        tmp = AUDIT_PATH.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(existing, indent=2, ensure_ascii=False))
        tmp.replace(AUDIT_PATH)  # atomic: a crash mid-write can't leave a half-written file


FILTERED_REPLY = (
    "I'm afraid that's not something I can help with. I'm here for all things Campus Customs, "
    "though: shall I help you find a hoodie, check a size, or compare prices?"
)


async def run_chat(
    request: ChatRequest,
    user_id: int | None = None,
    first_name: str | None = None,
    last_name: str | None = None,
    email: str | None = None,
) -> ChatResponse:
    context = request.context or ShoppingContext()
    deps = AgentDeps(
        user_id=user_id, first_name=first_name, last_name=last_name, email=email,
        current_product_id=request.current_product_id, conversation_id=request.conversation_id, context=context,
    )
    run_id = uuid.uuid4().hex[:12]
    history = to_message_history(request)
    with capture_run_messages() as messages:
        try:
            result = await get_agent().run(
                request.message,
                deps=deps,
                message_history=history,
                usage_limits=UsageLimits(request_limit=MAX_MODEL_REQUESTS),
            )
        except ModelHTTPError as exc:
            # The provider's content filter blocks jailbreak/harmful prompts before the model answers.
            if "content_filter" in str(exc.body):
                append_audit(build_audit_entries(messages[len(history):], run_id, deps, request.message,
                                                 "content_filter", "Blocked by the AI provider's content filter; polite refusal sent"))
                return ChatResponse(reply=FILTERED_REPLY, context=context)
            append_audit(build_audit_entries(messages[len(history):], run_id, deps, request.message, "error",
                                             f"ModelHTTPError {exc.status_code}"))
            raise
        except UsageLimitExceeded as exc:
            append_audit(build_audit_entries(messages[len(history):], run_id, deps, request.message, "usage_limit",
                                             redact(str(exc), 160)))
            raise
        except Exception as exc:
            append_audit(build_audit_entries(messages[len(history):], run_id, deps, request.message, "error",
                                             f"{type(exc).__name__}: {redact(str(exc), 140)}"))
            raise
    append_audit(build_audit_entries(result.new_messages(), run_id, deps, request.message, None, None))
    reply = result.output
    new_context = reply.context.model_copy(
        update={"product_ids": tools.existing_product_ids(reply.context.product_ids)}
    )
    return ChatResponse(
        reply=reply.reply,
        products=tools.product_cards(reply.product_ids),
        page=to_page_result(reply.page),
        context=new_context,
        suggestions=[q.strip() for q in reply.suggestions if q.strip()][:3],
    )


def to_page_result(page: PageUpdate | None) -> PageResult | None:
    """Validate the agent's page update against the catalogue and complete search results."""
    if page is None:
        return None
    common = dict(
        title=page.title, keywords=page.keywords, sort=page.sort, max_price=page.max_price,
        size=page.size, category=page.category, color=page.color, brand=page.brand,
    )
    if page.action == "browse":
        return PageResult(action="browse", **common)
    ids = tools.existing_product_ids(page.product_ids)
    if page.action == "open_product":
        return PageResult(action="open_product", product_ids=ids[:1], **common) if ids else None
    if page.search_query:
        # Complete the list deterministically: every product matching all the search words, with the
        # agent's picks (that really match) first. Same function the search tool counted with.
        strict = tools.matching_ids(page.search_query, page.max_price, page.size)
        if strict:
            picks = [pid for pid in ids if pid in strict]
            ids = list(dict.fromkeys(picks + strict))
    return PageResult(action="show_results", product_ids=ids, **common) if ids else None
