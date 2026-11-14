
import os
import requests

from datetime import date

from scanner.db import (
    list_sources,
    save_trade
)

from scanner.crawler import crawl_source

from scanner.extractor import extract_trades


def discover_with_tavily(
    asset,
    limit=8
):

    api_key = os.getenv(
        "TAVILY_API_KEY"
    )

    if not api_key:
        return []

    try:

        response = requests.post(

            "https://api.tavily.com/search",

            json={

                "api_key": api_key,

                "query": (
                    f'public trading idea OR trade entry '
                    f'"{asset}" BUY SELL'
                ),

                "search_depth": "basic",

                "max_results": limit,

                "include_answer": False,

            },

            timeout=25

        )

        response.raise_for_status()

        data = response.json()

        results = []

        for item in data.get(
            "results",
            []
        ):

            url = item.get(
                "url",
                ""
            )

            if url.startswith(
                ("http://", "https://")
            ):

                results.append({

                    "id": None,

                    "url": url,

                    "source_type": "webpage",

                    "label": (
                        item.get("title")
                        or "Discovered public page"
                    )

                })

        return results

    except Exception:

        return []


def run_scan(
    asset,
    market,
    start_date,
    end_date,
    max_pages=8
):

    configured_sources = list_sources()

    discovered_sources = discover_with_tavily(
        asset
    )

    # Combine configured and discovered URLs.
    unique_sources = {
        source["url"]: source
        for source in configured_sources
    }

    for source in discovered_sources:

        unique_sources.setdefault(
            source["url"],
            source
        )

    pages_checked = 0

    saved = 0

    errors = []

    for source in unique_sources.values():

        try:

            pages = crawl_source(
                source,
                max_pages=max_pages
            )

            for page in pages:

                pages_checked += 1

                extracted_trades = extract_trades(
                    page
                )

                for trade in extracted_trades:

                    # A record without a usable date
                    # cannot be placed in the date window.
                    if not trade.get("trade_date"):
                        continue

                    trade_day = date.fromisoformat(
                        trade["trade_date"]
                    )

                    if not (
                        start_date
                        <= trade_day
                        <= end_date
                    ):
                        continue

                    wanted_asset = (
                        asset.upper()
                        .replace("/", "")
                        .replace(" ", "")
                    )

                    found_asset = (
                        trade["asset"].upper()
                        .replace("/", "")
                        .replace(" ", "")
                    )

                    if wanted_asset != found_asset:
                        continue

                    if (
                        market != "All markets"
                        and trade["market"] != market
                    ):
                        continue

                    if save_trade(trade):
                        saved += 1

        except Exception as error:

            errors.append(
                f"{source['url']}: "
                f"{type(error).__name__}: {error}"
            )

    return {

        "pages": pages_checked,

        "saved": saved,

        "errors": errors

    }
