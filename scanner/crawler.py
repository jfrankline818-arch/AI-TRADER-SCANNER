
import time
import urllib.robotparser

from urllib.parse import urlparse, urljoin

import requests
import feedparser
import trafilatura

from bs4 import BeautifulSoup


USER_AGENT = (
    "TraderActivityResearchBot/1.0 "
    "(public-page research; contact: configure-your-contact)"
)

TIMEOUT = 20


def robots_allowed(url):

    try:

        parsed = urlparse(url)

        robots_url = (
            f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        )

        parser = urllib.robotparser.RobotFileParser()

        parser.set_url(robots_url)

        parser.read()

        return parser.can_fetch(
            USER_AGENT,
            url
        )

    except Exception:

        # Fail closed when access rules cannot be checked.
        return False


def fetch_page(url):

    if not robots_allowed(url):

        raise PermissionError(
            "Website robots policy disallows this URL "
            "or could not be checked."
        )

    response = requests.get(
        url,
        headers={
            "User-Agent": USER_AGENT
        },
        timeout=TIMEOUT
    )

    response.raise_for_status()

    content_type = response.headers.get(
        "content-type",
        ""
    )

    if (
        content_type
        and "text/html" not in content_type
    ):

        raise ValueError(
            f"Unsupported content type: {content_type}"
        )

    extracted_text = trafilatura.extract(
        response.text,
        include_comments=True,
        include_tables=True,
        favor_precision=True
    )

    soup = BeautifulSoup(
        response.text,
        "html.parser"
    )

    if not extracted_text:

        extracted_text = soup.get_text(
            " ",
            strip=True
        )

    title = ""

    if soup.title:

        title = soup.title.get_text(
            " ",
            strip=True
        )

    return {
        "url": url,
        "title": title,
        "text": extracted_text or "",
        "html": response.text
    }


def fetch_rss(url, limit=30):

    if not robots_allowed(url):

        raise PermissionError(
            "RSS feed access is disallowed or could not be checked."
        )

    feed = feedparser.parse(url)

    pages = []

    for entry in feed.entries[:limit]:

        link = getattr(
            entry,
            "link",
            ""
        )

        if not link:
            continue

        summary = (
            getattr(entry, "summary", "")
            or getattr(entry, "description", "")
        )

        title = getattr(
            entry,
            "title",
            ""
        )

        published = (
            getattr(entry, "published", "")
            or getattr(entry, "updated", "")
        )

        pages.append({

            "url": link,

            "title": title,

            "text": BeautifulSoup(
                summary,
                "html.parser"
            ).get_text(" ", strip=True),

            "published": published

        })

    return pages


def same_domain_links(page, limit=8):

    soup = BeautifulSoup(
        page["html"],
        "html.parser"
    )

    base = urlparse(
        page["url"]
    )

    links = []

    seen = set()

    blocked_paths = [
        "login",
        "signup",
        "register",
        "account",
        "privacy",
        "terms",
    ]

    for anchor in soup.find_all(
        "a",
        href=True
    ):

        absolute = urljoin(
            page["url"],
            anchor["href"]
        )

        parsed = urlparse(absolute)

        if parsed.scheme not in (
            "http",
            "https"
        ):
            continue

        if parsed.netloc != base.netloc:
            continue

        if any(
            blocked in parsed.path.lower()
            for blocked in blocked_paths
        ):
            continue

        clean_url = absolute.split("#")[0]

        if clean_url == page["url"]:
            continue

        if clean_url in seen:
            continue

        seen.add(clean_url)

        links.append(clean_url)

        if len(links) >= limit:
            break

    return links


def crawl_source(source, max_pages=8):

    if source["source_type"] == "rss":

        return fetch_rss(
            source["url"],
            limit=max_pages
        )

    first_page = fetch_page(
        source["url"]
    )

    pages = [
        first_page
    ]

    links = same_domain_links(
        first_page,
        limit=max(0, max_pages - 1)
    )

    for link in links:

        try:

            # Basic rate limiting.
            time.sleep(1)

            page = fetch_page(link)

            pages.append(page)

        except Exception:

            continue

    return pages
