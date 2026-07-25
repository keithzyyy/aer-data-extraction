"""Helpers for discovering Category Analysis RIN workbook landing pages."""

import re
from urllib.parse import urljoin, urlsplit

import pandas as pd
import requests
from bs4 import BeautifulSoup


MANIFEST_COLUMNS = [
    "business",
    "reporting_period",
    "document_title",
    "landing_page_url",
    "source_page_url",
    "review_status",
    "attachment_url",
    "download_status",
    "local_filename",
    "notes",
]

MANUAL_COLUMN_DEFAULTS = {
    "review_status": "pending",
    "attachment_url": "",
    "download_status": "not_started",
    "local_filename": "",
    "notes": "",
}


def fetch_page(url):
    """Request one AER page with a timeout and return its HTML."""
    print(f"[fetch] Requesting {url}")

    # Fail visibly if the page cannot be retrieved instead of returning partial results.
    response = requests.get(url, timeout=30)
    print(f"[fetch] Received HTTP {response.status_code}")
    response.raise_for_status()

    return response.text


def parse_candidates(html, business, source_page_url):
    """Return unique Category Analysis RIN landing-page records from one page."""
    print(f"[parse] Inspecting results for {business} on {source_page_url}")

    # Inspect document links and collect them by URL so repeated anchors are collapsed.
    soup = BeautifulSoup(html, "html.parser")
    candidates_by_url = {}

    for link in soup.find_all("a", href=True):
        href = link["href"].strip()
        document_title = " ".join(link.get_text(" ", strip=True).split())
        landing_page_url = urljoin(source_page_url, href).split("#", 1)[0]

        # Match both title and URL text to tolerate differences in AER punctuation.
        searchable_text = re.sub(
            r"[^a-z0-9]+",
            " ",
            f"{document_title} {landing_page_url}".lower(),
        )
        required_terms = ("category", "analysis", "rin", "template")

        if not all(term in searchable_text for term in required_terms):
            continue

        # Retain document landing pages and exclude direct attachment links.
        if "/documents/" not in urlsplit(landing_page_url).path.lower():
            continue

        # Extract the reporting period when it is present in the title or URL.
        period_match = re.search(
            r"\b((?:19|20)\d{2})\s*[-\u2013\u2014]\s*(\d{2})\b",
            f"{document_title} {landing_page_url}",
        )
        reporting_period = (
            f"{period_match.group(1)}-{period_match.group(2)}"
            if period_match
            else ""
        )

        candidate = {
            "business": business,
            "reporting_period": reporting_period,
            "document_title": document_title,
            "landing_page_url": landing_page_url,
            "source_page_url": source_page_url,
        }

        # Prefer the duplicate anchor carrying the most descriptive visible title.
        existing_candidate = candidates_by_url.get(landing_page_url)
        if (
            existing_candidate is None
            or len(document_title) > len(existing_candidate["document_title"])
        ):
            candidates_by_url[landing_page_url] = candidate

    candidates = list(candidates_by_url.values())
    print(f"[parse] Found {len(candidates)} unique candidate(s)")

    return candidates


def crawl_author(business, author_url):
    """Follow an AER author's Next links and combine all candidate records."""
    print(f"[crawl] Starting {business}: {author_url}")

    # Track visited pages so malformed pagination cannot create an infinite loop.
    discoveries = []
    visited = set()
    next_url = author_url.split("#", 1)[0]

    while next_url:
        if next_url in visited:
            print(f"[crawl] Warning: pagination loop detected at {next_url}; stopping")
            break

        visited.add(next_url)

        # Retrieve and parse the current author-results page.
        html = fetch_page(next_url)
        discoveries.extend(parse_candidates(html, business, next_url))

        # Follow the site's explicit Next link; its absence is normal completion.
        soup = BeautifulSoup(html, "html.parser")
        next_link = soup.select_one('a[rel~="next"]')
        if next_link is None:
            next_link = soup.select_one(".pager__item--next a[href]")

        next_href = next_link.get("href") if next_link else None
        next_url = (
            urljoin(next_url, next_href).split("#", 1)[0]
            if next_href
            else None
        )

    print(
        f"[crawl] Finished {business}: "
        f"{len(visited)} page(s), {len(discoveries)} candidate(s)"
    )

    return discoveries


def update_manifest(existing_manifest, discoveries):
    """Add discoveries to a manifest while preserving
    existing manual decisions."""
    print("[manifest] Preparing manifest update")

    # Work on a copy so the caller's existing DataFrame is not changed in place.
    if existing_manifest is None:
        existing = pd.DataFrame(columns=MANIFEST_COLUMNS)
    elif isinstance(existing_manifest, pd.DataFrame):
        existing = existing_manifest.copy()
    else:
        raise TypeError("existing_manifest must be a pandas DataFrame or None")

    # Bring older or empty manifests up to the agreed column structure.
    for column in MANIFEST_COLUMNS:
        if column not in existing.columns:
            existing[column] = MANUAL_COLUMN_DEFAULTS.get(column, "")
    existing = existing[MANIFEST_COLUMNS]

    # Convert the latest discoveries and initialise fields intended for manual work.
    discovered = pd.DataFrame(discoveries)
    for column in MANIFEST_COLUMNS:
        if column not in discovered.columns:
            discovered[column] = MANUAL_COLUMN_DEFAULTS.get(column, "")
    discovered = discovered[MANIFEST_COLUMNS]

    # Keep existing rows first so rediscovery cannot overwrite manual decisions.
    existing_urls = set(existing["landing_page_url"].dropna().astype(str))
    discovered_urls = set(discovered["landing_page_url"].dropna().astype(str))
    newly_discovered_urls = discovered_urls - existing_urls

    manifest = pd.concat([existing, discovered], ignore_index=True)
    manifest = manifest.drop_duplicates(subset="landing_page_url", keep="first")
    manifest = manifest.reset_index(drop=True)

    print(
        f"[manifest] Existing: {len(existing)}, "
        f"discovered: {len(discovered)}, "
        f"new: {len(newly_discovered_urls)}, "
        f"final: {len(manifest)}"
    )

    return manifest
