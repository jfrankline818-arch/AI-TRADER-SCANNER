
import os
import re
import json

from dateutil import parser as date_parser


ASSET_PATTERNS = [

    r"\b[A-Z]{3}\s*/\s*[A-Z]{3}\b",

    r"\b[A-Z]{3,10}\s*/\s*(?:USDT|USD|BTC|ETH)\b",

    r"\b(?:XAUUSD|XAGUSD|US30|US500|NAS100|GER40|UK100|BTCUSD|ETHUSD)\b",

]


def parse_date(value):

    if not value:
        return None

    try:

        return date_parser.parse(
            str(value),
            fuzzy=True
        ).date().isoformat()

    except Exception:

        return None


def safe_float(value):

    if value in (
        None,
        "",
        "null"
    ):
        return None

    try:

        return float(value)

    except Exception:

        return None


def infer_market(asset):

    asset = (
        asset or ""
    ).upper().replace("/", "").replace(" ", "")

    if asset in (
        "XAUUSD",
        "XAGUSD",
        "WTI",
        "BRENT",
        "COPPER"
    ) or "GAS" in asset:

        return "Commodities"

    if asset in (
        "US30",
        "US500",
        "NAS100",
        "GER40",
        "UK100",
        "JP225",
        "US2000"
    ):

        return "Indices"

    if any(
        symbol in asset
        for symbol in (
            "USDT",
            "BTC",
            "ETH"
        )
    ):

        return "Cryptocurrency"

    if len(asset) == 6 and asset.isalpha():

        return "Forex"

    if asset.isalpha() and 1 <= len(asset) <= 6:

        return "Stocks"

    return "All markets"


def ai_extract(
    title,
    text,
    url,
    published=None
):

    api_key = os.getenv(
        "AI_API_KEY"
    )

    if not api_key:
        return None

    try:

        from openai import OpenAI

        base_url = (
            os.getenv("AI_BASE_URL")
            or None
        )

        client = OpenAI(
            api_key=api_key,
            base_url=base_url
        )

        model = os.getenv(
            "AI_MODEL",
            "gpt-4o-mini"
        )

        prompt = f"""
Extract explicit trading entries from the public page below.

Return ONLY a JSON object in this format:

{{
    "trades": [
        {{
            "trader": "Trader username or null",
            "asset": "EUR/USD",
            "market": "Forex",
            "entry_price": 1.08500,
            "direction": "BUY",
            "trade_type": "trade_idea",
            "trade_date": "2026-11-14",
            "date_basis": "publication_date",
            "stop_loss": 1.08000,
            "take_profit": 1.09500,
            "evidence": "Exact quotation from the source",
            "confidence": 85
        }}
    ]
}}

RULES:

1. Never invent missing information.

2. Direction must be BUY or SELL.

3. An explicit proposed entry is a trade_idea.

4. An execution_claim requires explicit language that
   the author entered, opened, bought, sold, filled
   or executed a position.

5. Do not claim that a trade is independently verified.

6. Evidence must be an exact substring from the source text.

7. Do not extract vague market predictions without an
   explicit entry price and trading direction.

8. Use null for missing trader names, SL, TP or dates.

9. Trade dates should represent the actual trade date
   only when the source explicitly provides it.

10. If only a publication date is known, use that date
    and label date_basis as publication_date.

11. Confidence must be between 0 and 100.

PUBLICATION DATE:
{published or "Unknown"}

SOURCE URL:
{url}

PAGE TITLE:
{title}

PAGE TEXT:
{text[:14000]}
"""

        response = client.chat.completions.create(

            model=model,

            temperature=0,

            response_format={
                "type": "json_object"
            },

            messages=[

                {
                    "role": "system",
                    "content": (
                        "You extract trading information "
                        "conservatively. Never fabricate."
                    )
                },

                {
                    "role": "user",
                    "content": prompt
                }

            ]

        )

        result = json.loads(
            response.choices[0].message.content
        )

        return result.get(
            "trades",
            []
        )

    except Exception:

        return None


def rule_extract(
    title,
    text,
    url,
    published=None
):

    content = (
        f"{title}\n{text}"
    )

    upper = content.upper()

    asset = None

    for pattern in ASSET_PATTERNS:

        match = re.search(
            pattern,
            upper
        )

        if match:

            asset = re.sub(
                r"\s+",
                "",
                match.group(0)
            )

            break

    if not asset:
        return []

    direction_match = re.search(
        r"\b(BUY|LONG|SELL|SHORT)\b",
        upper
    )

    if not direction_match:
        return []

    direction = (
        "BUY"
        if direction_match.group(1) in (
            "BUY",
            "LONG"
        )
        else "SELL"
    )

    price_patterns = [

        r"(?:ENTRY|ENTER(?:ED)?|BUY(?:ING)?|SELL(?:ING)?|AT|PRICE)\s*(?:PRICE)?\s*[:=@]?\s*([0-9]+(?:\.[0-9]+)?)",

        r"@\s*([0-9]+(?:\.[0-9]+)?)",

    ]

    price = None

    for pattern in price_patterns:

        match = re.search(
            pattern,
            upper
        )

        if match:

            try:

                price = float(
                    match.group(1)
                )

                break

            except ValueError:

                pass

    if price is None:
        return []

    explicit_execution = bool(
        re.search(
            r"\b(I ENTERED|I OPENED|POSITION OPENED|TRADE FILLED|EXECUTED|I BOUGHT|I SOLD)\b",
            upper
        )
    )

    publication_date = parse_date(
        published
    )

    return [

        {

            "trader": None,

            "asset": asset,

            "market": infer_market(asset),

            "entry_price": price,

            "direction": direction,

            "trade_type": (
                "execution_claim"
                if explicit_execution
                else "trade_idea"
            ),

            "trade_date": publication_date,

            "date_basis": (
                "publication_date"
                if publication_date
                else "unknown"
            ),

            "stop_loss": None,

            "take_profit": None,

            "evidence": content[:400],

            "confidence": 35,

        }

    ]


def extract_trades(page):

    title = page.get(
        "title",
        ""
    )

    text = page.get(
        "text",
        ""
    ) or ""

    url = page.get(
        "url",
        ""
    )

    published = page.get(
        "published"
    )

    extracted = ai_extract(
        title,
        text,
        url,
        published
    )

    if extracted is None:

        extracted = rule_extract(
            title,
            text,
            url,
            published
        )

    cleaned = []

    for item in extracted:

        try:

            direction = str(
                item.get("direction", "")
            ).upper()

            if direction == "LONG":
                direction = "BUY"

            if direction == "SHORT":
                direction = "SELL"

            if direction not in (
                "BUY",
                "SELL"
            ):
                continue

            price = item.get(
                "entry_price"
            )

            if price is None:
                continue

            price = float(price)

            evidence = str(
                item.get("evidence") or ""
            ).strip()

            if not evidence:
                continue

            source_text = (
                f"{title}\n{text}"
            )

            # Reject unsupported AI claims.
            if evidence not in source_text:
                continue

            trade_date = (
                parse_date(item.get("trade_date"))
                or parse_date(published)
            )

            date_basis = (
                item.get("date_basis")
                or (
                    "publication_date"
                    if published
                    else "unknown"
                )
            )

            kind = item.get(
                "trade_type",
                "trade_idea"
            )

            if kind not in (
                "trade_idea",
                "execution_claim"
            ):

                kind = "trade_idea"

            verification = (
                "source_claim_execution"
                if kind == "execution_claim"
                else "published_idea"
            )

            asset = str(
                item.get("asset") or ""
            ).upper().replace(" ", "")

            if not asset:
                continue

            confidence = float(
                item.get("confidence", 40)
            )

            confidence = max(
                0,
                min(100, confidence)
            ) / 100.0

            cleaned.append({

                "trader": item.get("trader"),

                "asset": asset,

                "market": (
                    item.get("market")
                    or infer_market(asset)
                ),

                "entry_price": price,

                "direction": direction,

                "trade_type": kind,

                "trade_date": trade_date,

                "date_basis": date_basis,

                "stop_loss": safe_float(
                    item.get("stop_loss")
                ),

                "take_profit": safe_float(
                    item.get("take_profit")
                ),

                "verification_status": verification,

                "confidence": confidence,

                "evidence": evidence[:1000],

                "source_url": url,

            })

        except Exception:

            continue

    return cleaned
