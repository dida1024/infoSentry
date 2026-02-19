"""URL canonicalization and topic key helpers."""

from __future__ import annotations

import hashlib
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

TRACKING_QUERY_KEYS = {
    "spm",
    "from",
    "ref",
    "source",
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
}


def canonicalize_url_for_topic(url: str) -> str:
    """Canonicalize URL for topic-level dedupe.

    Rules:
    - Remove fragment
    - Remove common tracking query params
    - Lowercase host/path
    - Trim trailing slash from non-root path
    - Collapse forum reply anchors to topic URL by dropping fragment (already covered)
    """
    raw = url.strip()
    if not raw:
        return ""

    split = urlsplit(raw)
    scheme = split.scheme.lower() or "https"
    netloc = split.netloc.lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]

    path = split.path.lower().rstrip("/")
    if not path:
        path = "/"

    cleaned_query_items: list[tuple[str, str]] = []
    for key, value in parse_qsl(split.query, keep_blank_values=True):
        key_lower = key.lower()
        if key_lower.startswith("utm_") or key_lower in TRACKING_QUERY_KEYS:
            continue
        cleaned_query_items.append((key_lower, value))
    cleaned_query_items.sort(key=lambda item: (item[0], item[1]))
    query = urlencode(cleaned_query_items, doseq=True)

    return urlunsplit((scheme, netloc, path, query, ""))


def build_topic_key(url: str) -> str:
    """Build stable topic key from canonical URL."""
    canonical = canonicalize_url_for_topic(url)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:32]

