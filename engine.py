"""AEO scan engine — 26-point Answer Engine Optimization rubric."""

import ipaddress
import json
import re
import socket
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

USER_AGENT = "Mozilla/5.0 (compatible; AEOScanner/2026.05; +https://example.local/scanner)"
TIMEOUT = 12

AI_BOTS = [
    "GPTBot",
    "OAI-SearchBot",
    "ChatGPT-User",
    "ClaudeBot",
    "Claude-User",
    "Claude-SearchBot",
    "PerplexityBot",
    "Perplexity-User",
    "Google-Extended",
    "Google-Agent",
    "Applebot-Extended",
    "Meta-ExternalAgent",
    "CCBot",
    "Bingbot",
]

SCHEMA_URL = "http://schema.org"

# ---------------------------------------------------------------------------
# Fetching
# ---------------------------------------------------------------------------


def normalize_url(raw: str) -> str:
    raw = raw.strip()
    if not raw:
        raise ValueError("empty url")
    if not re.match(r"^https?://", raw, re.I):
        raw = "https://" + raw
    parsed = urlparse(raw)
    if not parsed.hostname:
        raise ValueError("invalid url")
    return f"{parsed.scheme}://{parsed.hostname}{parsed.path or '/'}{('?' + parsed.query) if parsed.query else ''}"


def _is_public(host: str) -> bool:
    try:
        infos = socket.getaddrinfo(host, None)
    except OSError:
        return False
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            return False
    return True


def fetch(url: str) -> requests.Response:
    host = urlparse(url).hostname
    if not host or not _is_public(host):
        raise ValueError("blocked host")
    return requests.get(url, timeout=TIMEOUT, headers={"User-Agent": USER_AGENT}, allow_redirects=True)


def try_fetch(url: str):
    try:
        return fetch(url)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------


def _jsonld_blocks(soup: BeautifulSoup) -> list:
    blocks = []
    for script in soup.find_all("script", attrs={"type": re.compile(r"ld\+json", re.I)}):
        text = script.string or script.get_text() or ""
        text = text.strip()
        if not text:
            continue
        try:
            data = json.loads(text)
        except Exception:
            # try to repair trailing commas, a common CMS bug
            try:
                data = json.loads(re.sub(r",\s*([}\]])", r"\1", text))
            except Exception:
                continue
        if isinstance(data, list):
            blocks.extend(data)
        elif isinstance(data, dict):
            blocks.append(data)
    return blocks


def _flatten_types(blocks: list) -> list:
    """Flatten @graph containers and return (type_name, node) pairs."""
    out = []

    def walk(node):
        if not isinstance(node, dict):
            return
        t = node.get("@type")
        types = t if isinstance(t, list) else [t] if t else []
        if types:
            out.append((types, node))
        for v in node.values():
            if isinstance(v, dict):
                walk(v)
            elif isinstance(v, list):
                for item in v:
                    walk(item)

    for b in blocks:
        walk(b)
    return out


def _has_type(typed, *names) -> bool:
    wanted = {n.lower() for n in names}
    for types, _ in typed:
        for t in types:
            t = str(t).lower().split("/")[-1]
            if t in wanted:
                return True
    return False


def _parse_robots(text: str) -> dict:
    """Return {user_agent: [disallow_paths]} merged across groups."""
    groups: dict[str, list[str]] = {}
    current: list[str] = []
    in_rules = False
    for line in text.splitlines():
        line = line.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        field, _, value = line.partition(":")
        field = field.strip().lower()
        value = value.strip()
        if field == "user-agent":
            if in_rules:
                current = []
                in_rules = False
            current.append(value)
            groups.setdefault(value, [])
        elif field == "disallow":
            in_rules = True
            for ua in current:
                groups[ua].append(value)
        elif field == "allow":
            in_rules = True
    return groups


def _bot_blocked(robots_text: str, bot: str) -> bool | None:
    """True if bot is disallowed site-wide, False if not, None if unknown."""
    groups = _parse_robots(robots_text)
    for ua, disallows in groups.items():
        if ua == "*":
            continue
        if bot.lower() in ua.lower():
            return any(d in ("", "/") for d in disallows)
    # fall back to the wildcard group
    wildcard = groups.get("*", [])
    return any(d in ("", "/") for d in wildcard)


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------

FEED_PATHS = ["/feed", "/feed.xml", "/rss.xml", "/atom.xml", "/index.xml", "/feed.json", "/rss", "/.rss"]


def run_scan(raw_url: str) -> dict:
    url = normalize_url(raw_url)
    root = f"{urlparse(url).scheme}://{urlparse(url).hostname}"

    resp = fetch(url)
    html = resp.text
    soup = BeautifulSoup(html, "html.parser")
    final_url = str(resp.url)
    typed = _flatten_types(_jsonld_blocks(soup))
    has_jsonld = bool(typed)

    headers = {k.lower(): v for k, v in resp.headers.items()}

    checks = []

    def add(cid, category, name, passed, weight, detail, fix, severity="medium"):
        checks.append({
            "id": cid, "category": category, "name": name,
            "passed": bool(passed), "weight": weight, "severity": severity,
            "detail": detail, "fix": fix,
        })

    # ---- Foundations -------------------------------------------------------
    add("https", "Foundations", "HTTPS",
        final_url.startswith("https://"), 3,
        "Site served over HTTPS." if final_url.startswith("https://") else "Site is served over plain HTTP.",
        "Serve the site over HTTPS and redirect all HTTP traffic.")

    title = (soup.title.string or "").strip() if soup.title and soup.title.string else ""
    add("title", "Foundations", "Title tag",
        0 < len(title) <= 70, 3,
        f"Title: “{title}”" if title else "No <title> tag found.",
        "Add a unique, descriptive title of 10–70 characters.")

    meta_desc = ""
    md = soup.find("meta", attrs={"name": "description"})
    if md and md.get("content"):
        meta_desc = md["content"].strip()
    add("meta-desc", "Foundations", "Meta description",
        0 < len(meta_desc) <= 165, 3,
        f"Description set ({len(meta_desc)} chars)." if meta_desc else "No meta description found.",
        "Add <meta name=\"description\"> with a 70–160 character summary.")

    canonical = soup.find("link", rel=lambda v: v and "canonical" in [x.lower() for x in v])
    canon_href = canonical.get("href", "") if canonical else ""
    add("canonical", "Foundations", "Canonical URL",
        bool(canon_href), 2,
        f"Canonical: {canon_href}" if canon_href else "No canonical link tag.",
        "Add <link rel=\"canonical\"> to prevent duplicate-content confusion.")

    viewport = soup.find("meta", attrs={"name": "viewport"})
    add("viewport", "Foundations", "Mobile viewport",
        bool(viewport and viewport.get("content")), 2,
        "Viewport meta present." if viewport else "No viewport meta tag.",
        "Add <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">.")

    lang = soup.html.get("lang") if soup.html else None
    add("lang", "Foundations", "HTML lang attribute",
        bool(lang), 1,
        f"lang=\"{lang}\"." if lang else "No lang attribute on <html>.",
        "Set <html lang=\"en\"> (or your language) for language-aware AI retrieval.")

    h1s = soup.find_all("h1")
    h2s = soup.find_all("h2")
    add("headings", "Foundations", "Heading structure",
        len(h1s) == 1 and len(h2s) >= 1, 3,
        f"{len(h1s)} H1, {len(h2s)} H2 tags.",
        "Use exactly one H1 and at least one H2 to structure answers.")

    imgs = soup.find_all("img")
    with_alt = [i for i in imgs if (i.get("alt") or "").strip()]
    alt_ratio = (len(with_alt) / len(imgs)) if imgs else 1.0
    add("img-alt", "Foundations", "Image alt text",
        alt_ratio >= 0.8 and len(imgs) > 0, 2,
        f"{len(with_alt)}/{len(imgs)} images have alt text." if imgs else "No images on page.",
        "Add descriptive alt attributes to every meaningful image.")

    # ---- Social & preview --------------------------------------------------
    og_tags = soup.find_all("meta", attrs={"property": re.compile(r"^og:", re.I)})
    og_keys = {m.get("property", "").lower() for m in og_tags}
    og_ok = {"og:title", "og:description", "og:image"} <= og_keys
    add("ogp", "Social & Preview", "Open Graph tags",
        og_ok, 3,
        f"Found: {', '.join(sorted(og_keys)) or 'none'}.",
        "Add og:title, og:description and og:image for rich AI/LLM previews.")

    # ---- Structured data ---------------------------------------------------
    add("jsonld", "Structured Data", "JSON-LD structured data",
        has_jsonld, 5,
        f"{len(typed)} schema node(s) found." if has_jsonld else "No JSON-LD blocks found.",
        "Add <script type=\"application/ld+json\"> with Organization, WebSite and content schemas.")

    org_ok = _has_type(typed, "Organization", "LocalBusiness", "Corporation", "Store", "NGO")
    add("org-schema", "Structured Data", "Organization / LocalBusiness schema",
        org_ok, 4,
        "Organization-type schema present." if org_ok else "No Organization or LocalBusiness schema.",
        "Declare your organization with name, url, logo and contactPoint.")

    person_ok = False
    person_detail = "No authored-entity (Person) schema found."
    for types, node in typed:
        if any(str(t).lower().split("/")[-1] == "person" for t in types):
            same_as = node.get("sameAs") or []
            if isinstance(same_as, str):
                same_as = [same_as]
            if same_as:
                person_ok = True
                person_detail = f"Person schema with {len(same_as)} sameAs link(s)."
                break
            person_detail = "Person schema found but no sameAs links."
    add("person-schema", "Structured Data", "Authored entity (Person + sameAs)",
        person_ok, 4, person_detail,
        "Add a Person schema with sameAs links to LinkedIn, Wikidata, etc. (E-E-A-T).")

    add("breadcrumb", "Structured Data", "BreadcrumbList schema",
        _has_type(typed, "BreadcrumbList"), 2,
        "Breadcrumb schema present." if _has_type(typed, "BreadcrumbList") else "No BreadcrumbList schema.",
        "Add BreadcrumbList schema so AI engines understand page hierarchy.")

    add("faq-schema", "Structured Data", "FAQPage schema",
        _has_type(typed, "FAQPage"), 4,
        "FAQPage schema present." if _has_type(typed, "FAQPage") else "No FAQPage schema.",
        "Mark up your FAQ content with FAQPage schema for direct-answer extraction.")

    add("howto-schema", "Structured Data", "HowTo schema",
        _has_type(typed, "HowTo"), 3,
        "HowTo schema present." if _has_type(typed, "HowTo") else "No HowTo schema.",
        "Add HowTo schema for step-based content AI Mode surfaces.")

    add("qa-schema", "Structured Data", "QAPage schema",
        _has_type(typed, "QAPage", "Question"), 3,
        "QAPage/Question schema present." if _has_type(typed, "QAPage", "Question") else "No QAPage schema.",
        "Add QAPage schema for question-and-answer content patterns.")

    add("product-schema", "Structured Data", "Product schema",
        _has_type(typed, "Product", "Offer", "AggregateOffer"), 4,
        "Product/Offer schema present." if _has_type(typed, "Product", "Offer", "AggregateOffer") else "No Product schema.",
        "Add Product schema with price, availability and reviews for generative-UI widgets.")

    add("speakable", "Structured Data", "Speakable schema",
        _has_type(typed, "SpeakableSpecification") or '"speakable"' in html.lower(), 3,
        "Speakable markup detected." if (_has_type(typed, "SpeakableSpecification") or '"speakable"' in html.lower()) else "No speakable markup.",
        "Add SpeakableSpecification so AI Mode / voice can cite key passages.")

    gu_types = ("Event", "Service", "Recipe", "Course", "Movie", "Book")
    gu_ok = _has_type(typed, *gu_types)
    add("generative-ui", "Structured Data", "Generative-UI schema (Event/Service/Recipe)",
        gu_ok, 2,
        f"Found: {', '.join(gu_types)}-type schema." if gu_ok else "No Event/Service/Recipe-style schema.",
        "Add rich entity schemas Google can render as generative-UI widgets.")

    # ---- Agents & discoverability ------------------------------------------
    robots_resp = try_fetch(urljoin(root, "/robots.txt"))
    robots_text = robots_resp.text if robots_resp is not None and robots_resp.ok else ""
    add("robots", "Agents & Discovery", "robots.txt",
        bool(robots_text.strip()), 3,
        "robots.txt found." if robots_text.strip() else "No robots.txt at site root.",
        "Publish a robots.txt at your root domain.")

    if robots_text.strip():
        blocked = [b for b in AI_BOTS if _bot_blocked(robots_text, b) is True]
        allowed = [b for b in AI_BOTS if b not in blocked]
        ratio = len(allowed) / len(AI_BOTS)
        crawler_ok = ratio >= 0.9
        detail = f"{len(allowed)}/{len(AI_BOTS)} AI crawlers allowed." + (f" Blocked: {', '.join(blocked)}." if blocked else "")
        fix = "Remove Disallow rules for AI/search crawlers (GPTBot, ClaudeBot, PerplexityBot, Google-Agent, etc.)."
    else:
        crawler_ok = False
        detail = "Cannot evaluate AI crawler access without robots.txt."
        fix = "Publish a robots.txt that does not block AI crawlers."
    add("ai-crawlers", "Agents & Discovery", "AI crawler allowlist (2026 fleet)",
        crawler_ok, 5, detail, fix)

    sitemap_resp = try_fetch(urljoin(root, "/sitemap.xml"))
    sitemap_ok = sitemap_resp is not None and sitemap_resp.ok and "sitemap" in sitemap_resp.text[:500].lower()
    add("sitemap", "Agents & Discovery", "XML sitemap",
        sitemap_ok, 3,
        "sitemap.xml found." if sitemap_ok else "No sitemap.xml at site root.",
        "Publish an XML sitemap and reference it from robots.txt.")

    llms_resp = try_fetch(urljoin(root, "/llms.txt"))
    llms_ok = llms_resp is not None and llms_resp.ok and llms_resp.text.strip().startswith("#")
    add("llms-txt", "Agents & Discovery", "llms.txt",
        llms_ok, 4,
        "llms.txt found." if llms_ok else "No llms.txt at site root.",
        "Add /llms.txt — a markdown overview of your site for LLM ingestion.")

    mcp_resp = try_fetch(urljoin(root, "/.well-known/mcp.json"))
    mcp_ok = False
    if mcp_resp is not None and mcp_resp.ok:
        try:
            mcp_data = mcp_resp.json()
            mcp_ok = isinstance(mcp_data, dict) and bool(mcp_data)
        except Exception:
            mcp_ok = False
    add("mcp-card", "Agents & Discovery", "MCP server card (/.well-known/mcp.json)",
        mcp_ok, 3,
        "MCP server card published." if mcp_ok else "No /.well-known/mcp.json.",
        "Publish an MCP server card so AI assistants can auto-connect to your services.")

    feed_found = ""
    for path in FEED_PATHS:
        r = try_fetch(urljoin(root, path))
        if r is not None and r.ok and len(r.text) > 40:
            head = r.text[:600].lower()
            if any(s in head for s in ("<rss", "<feed", "atom", "channel", "items", "\"version\"")):
                feed_found = path
                break
    add("feeds", "Agents & Discovery", "Subscribable feed (RSS/Atom/JSON)",
        bool(feed_found), 2,
        f"Feed found at {feed_found}." if feed_found else "No RSS/Atom/JSON feed detected.",
        "Publish an RSS/Atom/JSON feed — what information agents subscribe to.")

    last_mod = headers.get("last-modified", "")
    date_in_schema = '"dateModified"' in html or '"datePublished"' in html
    time_tag = soup.find("time") is not None
    fresh_ok = bool(last_mod or date_in_schema or time_tag)
    fresh_bits = []
    if last_mod:
        fresh_bits.append(f"Last-Modified: {last_mod}")
    if date_in_schema:
        fresh_bits.append("dateModified/datePublished in schema")
    if time_tag:
        fresh_bits.append("<time> element")
    add("freshness", "Agents & Discovery", "Freshness signals",
        fresh_ok, 2,
        "; ".join(fresh_bits) if fresh_bits else "No Last-Modified, dateModified or <time> signals.",
        "Expose dateModified in schema and Last-Modified headers so agents trust recency.")

    # ---- Score --------------------------------------------------------------
    total = sum(c["weight"] for c in checks)
    earned = sum(c["weight"] for c in checks if c["passed"])
    score = round(earned / total * 100) if total else 0

    categories = {}
    for c in checks:
        cat = categories.setdefault(c["category"], {"earned": 0, "total": 0, "passed": 0, "count": 0})
        cat["count"] += 1
        cat["total"] += c["weight"]
        if c["passed"]:
            cat["earned"] += c["weight"]
            cat["passed"] += 1
    for c in checks:
        if c["weight"] >= 4:
            c["severity"] = "high"
        elif c["weight"] >= 3:
            c["severity"] = "medium"
        else:
            c["severity"] = "low"

    for cat in categories.values():
        cat["score"] = round(cat["earned"] / cat["total"] * 100) if cat["total"] else 0

    return {
        "url": url,
        "final_url": final_url,
        "domain": urlparse(final_url).hostname,
        "score": score,
        "grade": _grade(score),
        "earned": earned,
        "max": total,
        "checks": checks,
        "categories": categories,
        "scanned_at": datetime.now(timezone.utc).isoformat(),
        "engine": "AEOScanner/2026.05",
    }


def _grade(score: int) -> str:
    if score >= 90:
        return "A"
    if score >= 80:
        return "B"
    if score >= 65:
        return "C"
    if score >= 50:
        return "D"
    return "F"
