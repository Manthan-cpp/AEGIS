"""SerpAPI client for live, authentic web grounding across India-scoped legal authorities."""

from __future__ import annotations

import html
import logging
import os
import re
import threading
import time
import urllib.parse
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from services.legal_search import LegalChunk

logger = logging.getLogger(__name__)

SERPAPI_SEARCH_URL = "https://serpapi.com/search.json"
CACHE_TTL_SECONDS = 3600.0  # 1 hour in-memory cache
REQUEST_TIMEOUT_SECONDS = 4.5

# Domains to exclude from citations (social media, video platforms, discussion forums)
EXCLUDED_DOMAINS = {
    "facebook.com", "instagram.com", "twitter.com", "x.com", "youtube.com",
    "tiktok.com", "pinterest.com", "reddit.com", "quora.com", "linkedin.com",
}

# Major Indian states, UTs, and key districts for location-sensitive routing
INDIAN_LOCATIONS = {
    "pune", "mumbai", "delhi", "new delhi", "bengaluru", "bangalore", "lucknow",
    "kolkata", "chennai", "hyderabad", "ahmedabad", "jaipur", "patna", "bhopal",
    "chandigarh", "noida", "gurgaon", "gurugram", "thane", "nagpur", "kanpur",
    "surat", "indore", "varanasi", "allahabad", "prayagraj", "agra", "ghaziabad",
    "ludhiana", "amritsar", "ranchi", "raipur", "guwahati", "shimla", "dehradun",
    "jammu", "srinagar", "kochi", "coimbatore", "mysore", "maharashtra",
    "uttar pradesh", "karnataka", "tamil nadu", "west bengal", "gujarat",
    "rajasthan", "kerala", "madhya pradesh", "bihar", "punjab", "haryana",
    "telangana", "andhra pradesh", "odisha", "assam", "uttarakhand", "himachal",
    "goa", "jharkhand", "chattisgarh",
}

LEGAL_INSTITUTIONS: list[tuple[str, str]] = [
    ("dlsa", "DLSA District Legal Services Authority"),
    ("slsa", "SLSA State Legal Services Authority"),
    ("tlsc", "Taluka Legal Services Committee"),
    ("nalsa", "NALSA National Legal Services Authority"),
    ("protection officer", "Protection Officer domestic violence"),
    ("one stop centre", "One Stop Centre Sakhi"),
    ("sakhi centre", "Sakhi One Stop Centre"),
    ("family court", "family court"),
    ("district court", "district court"),
    ("high court", "high court"),
    ("legal aid clinic", "legal aid clinic authority"),
    ("mahila thana", "women police station mahila thana"),
    ("cyber cell", "cyber crime police portal"),
]


@dataclass(frozen=True)
class SerpWebResult:
    title: str
    link: str
    snippet: str
    source_name: str
    displayed_link: str = ""


_CACHE_LOCK = threading.Lock()
_CACHE: dict[str, tuple[float, list[SerpWebResult]]] = {}
MAX_CACHE_ENTRIES = 500

# Circuit breaker state
_CIRCUIT_LOCK = threading.RLock()
_CONSECUTIVE_FAILURES: int = 0
_CIRCUIT_BREAKER_OPEN: bool = False
_CIRCUIT_RESET_TIME: float = 0.0
FAILURE_THRESHOLD: int = 3
CIRCUIT_COOLDOWN_SECONDS: float = 60.0


def serpapi_enabled() -> bool:
    """Check if a valid SerpAPI API key is configured."""
    return bool(os.getenv("SERPAPI_API_KEY", "").strip())


def is_circuit_open() -> bool:
    """Return True if the circuit breaker is currently open (blocking external calls)."""
    global _CIRCUIT_BREAKER_OPEN, _CIRCUIT_RESET_TIME, _CONSECUTIVE_FAILURES
    with _CIRCUIT_LOCK:
        if not _CIRCUIT_BREAKER_OPEN:
            return False
        # Cooldown period expired; transition to half-open to probe external service
        if time.time() >= _CIRCUIT_RESET_TIME:
            _CIRCUIT_BREAKER_OPEN = False
            return False
        return True


def record_success() -> None:
    """Record a successful remote SerpAPI query, resetting failure counters."""
    global _CONSECUTIVE_FAILURES, _CIRCUIT_BREAKER_OPEN
    with _CIRCUIT_LOCK:
        _CONSECUTIVE_FAILURES = 0
        _CIRCUIT_BREAKER_OPEN = False


def record_failure() -> None:
    """Record a failed remote SerpAPI query; trip open if threshold is reached."""
    global _CONSECUTIVE_FAILURES, _CIRCUIT_BREAKER_OPEN, _CIRCUIT_RESET_TIME
    with _CIRCUIT_LOCK:
        _CONSECUTIVE_FAILURES += 1
        if _CONSECUTIVE_FAILURES >= FAILURE_THRESHOLD:
            _CIRCUIT_BREAKER_OPEN = True
            _CIRCUIT_RESET_TIME = time.time() + CIRCUIT_COOLDOWN_SECONDS
            logger.warning(
                "SerpAPI circuit breaker tripped open after %d consecutive failures. Cooling down for %.0fs.",
                _CONSECUTIVE_FAILURES,
                CIRCUIT_COOLDOWN_SECONDS,
            )


def reset_circuit_breaker_for_tests() -> None:
    """Reset circuit breaker counters and state for test harnesses."""
    global _CONSECUTIVE_FAILURES, _CIRCUIT_BREAKER_OPEN, _CIRCUIT_RESET_TIME
    with _CIRCUIT_LOCK:
        _CONSECUTIVE_FAILURES = 0
        _CIRCUIT_BREAKER_OPEN = False
        _CIRCUIT_RESET_TIME = 0.0


def get_serpapi_status() -> dict[str, Any]:
    """Return health telemetry for SerpAPI integration."""
    circuit_status = is_circuit_open()
    with _CIRCUIT_LOCK:
        consecutive_fails = _CONSECUTIVE_FAILURES
    with _CACHE_LOCK:
        cache_size = len(_CACHE)
    return {
        "enabled": serpapi_enabled(),
        "circuit_open": circuit_status,
        "consecutive_failures": consecutive_fails,
        "cached_entries": cache_size,
    }


def _cache_get(key: str) -> list[SerpWebResult] | None:
    """Retrieve unexpired results from the in-memory cache."""
    now = time.time()
    with _CACHE_LOCK:
        if key in _CACHE:
            cached_time, cached_results = _CACHE[key]
            if now - cached_time < CACHE_TTL_SECONDS:
                return cached_results
    return None


def _cache_put(key: str, results: list[SerpWebResult]) -> None:
    """Store results in memory cache with bounded eviction."""
    now = time.time()
    with _CACHE_LOCK:
        if len(_CACHE) >= MAX_CACHE_ENTRIES:
            # First purge expired entries
            expired_keys = [k for k, (t, _) in _CACHE.items() if now - t >= CACHE_TTL_SECONDS]
            for k in expired_keys:
                _CACHE.pop(k, None)
            # If still over or at capacity, prune the oldest entries
            if len(_CACHE) >= MAX_CACHE_ENTRIES:
                sorted_keys = sorted(_CACHE.keys(), key=lambda k: _CACHE[k][0])
                for k in sorted_keys[:100]:
                    _CACHE.pop(k, None)
        _CACHE[key] = (now, results)


def clear_cache_for_tests() -> None:
    """Clear cache storage for test isolation."""
    with _CACHE_LOCK:
        _CACHE.clear()


def sanitize_query(query: str) -> str:
    """Sanitize user query to remove PII (names, phones, Aadhaar, emails, addresses, distress cries)."""
    text = query

    # 1. Strip Indian Aadhaar numbers (12 digits, optional spaces or hyphens)
    text = re.sub(r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}\b", "", text)

    # 2. Strip Indian phone numbers (+91, 10-12 digits, leading 0)
    text = re.sub(r"(?:\+?91[\s-]?)?0?[6-9]\d{4}[\s-]?\d{5}\b", "", text)
    text = re.sub(r"\b\d{10,12}\b", "", text)

    # 3. Strip email addresses
    text = re.sub(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", "", text)

    # 4. Strip contact/phone/Aadhaar labels
    text = re.sub(
        r"\b(?:my\s+)?(?:phone|mobile|cell|contact|number|call|whatsapp|aadhaar|aadhar|uidai)\s*(?:is|at|:)?\b",
        "",
        text,
        flags=re.I,
    )

    # 5. Strip specific address components (flat, plot, house no, street, colony)
    text = re.sub(
        r"\b(?:flat|house|room|plot|apt|apartment|sector|phase|street|road|gali|lane|colony|nagar)\s*(?:no\.?|number)?\s*[\w\d/-]+",
        "",
        text,
        flags=re.I,
    )

    # 6. Normalize distress statements and Hindi distress cries into legal/shelter topic searches
    distress_replacements: list[tuple[str, str]] = [
        (r"\b(?:my\s+husband(?:\s+[A-Za-z]+)?|pati)\s+(?:beat|beats|beaten|abused|assaulted)\s+me\b", "domestic violence assault"),
        (r"\b(?:mera\s+pati|mere\s+pati)\s+(?:mujhe\s+)?(?:maarta|peetta|gali\s+deta|torture\s+karta)\b", "domestic violence assault"),
        (r"\b(?:i\s+was|i\s+am)\s+(?:raped|sexually\s+assaulted|molested)\b", "sexual assault rape legal reporting"),
        (r"\b(?:my\s+in[- ]laws|sasural)\s+(?:harassing|torturing)\s+me\b", "in laws domestic harassment"),
        (r"\b(?:sasural\s+wale|saas\s+sasur)\s+(?:mujhe\s+)?(?:pareshan|satate|maarte|torture)\b", "in laws domestic harassment"),
        (r"\b(?:marpeet|maar\s+peet)\b", "domestic violence assault"),
        (r"\b(?:threatened|threatening)\s+to\s+kill\s+me\b", "criminal intimidation threat to life"),
        (r"\b(?:am\s+being\s+confined|being\s+confined|locked|confined)(?:\s+me)?\s+in\s+a\s+room\b", "wrongful confinement domestic violence"),
        (r"\b(?:mujhe\s+)?(?:ghar\s+se\s+nikal\s+diya|chhod\s+diya)\b", "abandoned kicked out shelter"),
        (r"\b(?:where\s+can\s+i\s+find|how\s+to\s+contact|how\s+do\s+i\s+contact|who\s+is\s+the)\b", ""),
        (r"\b(?:please\s+help\s+me|help\s+me|what\s+should\s+i\s+do|i\s+need\s+help|urgently|urgent)\b", ""),
        (r"\b(?:bachao|bachaao|madad\s+karo|meri\s+madad\s+karo)\b", ""),
    ]
    for pattern, repl in distress_replacements:
        text = re.sub(pattern, repl, text, flags=re.I)

    # 7. Strip specific names following relationship or identification words
    text = re.sub(r"\b(?:husband|wife|father|brother|named|called|accused)\s+[A-Z][a-z]+\b", "", text)

    # 8. Clean punctuation and multiple spaces
    text = re.sub(r"[^\w\s-]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def is_legal_web_candidate(query: str) -> bool:
    """Determine whether a legal query asks for geographic, institutional, or directory information."""
    lowered = query.casefold()

    # Institutional keywords
    institutional_patterns = [
        r"\b(?:dlsa|slsa|tlsc|nalsa)\b",
        r"\b(?:legal\s+services\s+authority|legal\s+aid\s+clinic)\b",
        r"\b(?:protection\s+officer|one\s+stop\s+cent(?:er|re)|sakhi\s+cent(?:er|re))\b",
        r"\b(?:family\s+court|district\s+court|high\s+court|police\s+station|mahila\s+thana|cyber\s+cell)\b",
        r"\b(?:contact\s+details?|office\s+address|helpline\s+number|official\s+portal|official\s+website)\b",
        r"\b(?:where\s+is|where\s+can\s+i\s+find|how\s+to\s+reach|how\s+to\s+contact|who\s+is\s+the\s+officer)\b",
        r"\b(?:directory|portal|online\s+application|apply\s+online)\b",
    ]
    for pat in institutional_patterns:
        if re.search(pat, lowered):
            return True

    # Geographic / District keywords combined with help/legal words
    has_location = any(re.search(rf"\b{re.escape(loc)}\b", lowered) for loc in INDIAN_LOCATIONS)
    has_legal_or_help = bool(re.search(
        r"\b(?:court|legal|lawyer|aid|police|officer|complaint|helpline|centre|center|station|"
        r"justice|fir|report|rights|confin\w*|locked|shelter|abuse|action|escape)\b",
        lowered,
    ))

    return has_location and has_legal_or_help


def formulate_legal_search_query(query: str) -> str:
    """Formulate a targeted, privacy-preserving search query for SerpAPI."""
    sanitized = sanitize_query(query)
    lowered = sanitized.casefold()

    found_locations = [loc for loc in INDIAN_LOCATIONS if re.search(rf"\b{re.escape(loc)}\b", lowered)]
    found_inst: list[str] = []
    for key, expanded in LEGAL_INSTITUTIONS:
        if re.search(rf"\b{re.escape(key)}\b", lowered):
            found_inst.append(expanded)

    loc_str = " ".join(found_locations[:2]).title()
    inst_str = " ".join(found_inst[:2])

    if found_inst and found_locations:
        return f"{inst_str} {loc_str} official portal contact India"
    if found_inst:
        return f"{inst_str} India official legal portal"
    if found_locations:
        if not found_inst and re.search(r"\b(?:justice|police|fir|confin\w*|locked|escape|abuse|beaten)\b", lowered):
            return f"District Legal Services Authority DLSA police legal aid {loc_str} official portal contact India"
        # Strip generic stopwords
        cleaned = re.sub(r"\b(?:i|me|my|we|us|he|she|they|am|is|are|was|were|want|please|tell)\b", "", sanitized, flags=re.I)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return f"{cleaned} {loc_str} official legal aid India"

    cleaned = re.sub(r"\b(?:i|me|my|we|us|he|she|they|am|is|are|was|were|want|please|tell)\b", "", sanitized, flags=re.I)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return f"{cleaned} official India legal"


def _is_allowed_link(link: str) -> bool:
    if not link or not link.startswith(("http://", "https://")):
        return False
    try:
        netloc = urllib.parse.urlparse(link).netloc.casefold()
        return not any(excl in netloc for excl in EXCLUDED_DOMAINS)
    except Exception:
        return False


def _clean_text(raw: str) -> str:
    if not raw:
        return ""
    unescaped = html.unescape(raw)
    without_tags = re.sub(r"<[^<]+?>", "", unescaped)
    return " ".join(without_tags.split()).strip()


def _extract_source_name(link: str, source_from_api: str = "") -> str:
    if source_from_api:
        return source_from_api.strip()
    try:
        domain = urllib.parse.urlparse(link).netloc.casefold()
        return domain.removeprefix("www.")
    except Exception:
        return "Official Legal Web Resource"


def _fetch_from_serpapi(search_query: str, max_results: int = 3) -> list[SerpWebResult]:
    api_key = os.getenv("SERPAPI_API_KEY", "").strip()
    if not api_key:
        return []

    if is_circuit_open():
        logger.warning("SerpAPI circuit breaker is open; skipping remote query to maintain 0ms response.")
        return []

    params = {
        "engine": "google",
        "q": search_query,
        "gl": "in",
        "hl": "en",
        "num": max(max_results + 2, 5),
        "api_key": api_key,
    }

    try:
        # Prefer requests if installed, otherwise fallback to urllib
        try:
            import requests

            resp = requests.get(
                SERPAPI_SEARCH_URL,
                params=params,
                headers={"User-Agent": "Aegis-Assistant/1.0"},
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
            if resp.status_code != 200:
                logger.warning("SerpAPI HTTP %d: %s", resp.status_code, resp.text[:200])
                record_failure()
                return []
            data = resp.json()
        except ImportError:
            url = f"{SERPAPI_SEARCH_URL}?{urllib.parse.urlencode(params)}"
            req = urllib.request.Request(url, headers={"User-Agent": "Aegis-Assistant/1.0"})
            with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT_SECONDS) as response:
                import json

                data = json.loads(response.read().decode("utf-8"))

        organic_results = data.get("organic_results", [])
        results: list[SerpWebResult] = []

        for item in organic_results:
            link = str(item.get("link", "")).strip()
            if not _is_allowed_link(link):
                continue

            title = _clean_text(str(item.get("title", "")))
            snippet = _clean_text(str(item.get("snippet", "")))
            source_name = _extract_source_name(link, str(item.get("source", "")))
            displayed_link = str(item.get("displayed_link", ""))

            if not title or not snippet:
                continue

            results.append(
                SerpWebResult(
                    title=title,
                    link=link,
                    snippet=snippet,
                    source_name=source_name,
                    displayed_link=displayed_link,
                )
            )
            if len(results) >= max_results:
                break

        record_success()
        return results

    except Exception as exc:
        record_failure()
        logger.warning("SerpAPI search failed gracefully: %s", exc)
        return []


def search_legal_web(query: str, max_results: int = 3) -> list[SerpWebResult]:
    """Search Google via SerpAPI with caching, PII sanitization, and graceful fallback."""
    if not serpapi_enabled():
        return []

    search_query = formulate_legal_search_query(query)
    if not search_query.strip():
        return []

    cache_key = f"legal:{search_query.casefold()}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    # Fetch live results
    results = _fetch_from_serpapi(search_query, max_results=max_results)
    _cache_put(cache_key, results)
    return results


def legal_web_results_to_chunks(results: list[SerpWebResult]) -> list[LegalChunk]:
    """Convert SerpWebResult items into Aegis LegalChunk instances for grounded retrieval."""
    from services.legal_search import LegalChunk

    chunks: list[LegalChunk] = []
    for index, res in enumerate(results, start=1):
        # Format a clean section title based on source domain/title
        section = f"Portal / Directory: {res.source_name}"
        chunks.append(
            LegalChunk(
                chunk_id=f"serpapi-web-{index}",
                title=res.title,
                section=section,
                text=res.snippet,
                source=res.source_name,
                source_url=res.link,
                score=0.92,
                status="Verified Live Official Web Source",
            )
        )
    return chunks


CRISIS_PATTERNS = [
    r"\b(?:shelter\s+home|safe\s+house|safe\s+haven|women\s+shelter|night\s+shelter|short\s+stay\s+home|swadhar\s+greh|ujjawala)\b",
    r"\b(?:sakhi\s+(?:cent(?:er|re)|osc)|one\s+stop\s+cent(?:er|re)|distress\s+cent(?:er|re))\b",
    r"\b(?:tele[- ]?manas|kiran\s+helpline|mental\s+health\s+helpline|suicide\s+prevention\s+helpline|counselling\s+helpline|vandrevala)\b",
    r"\b(?:kicked\s+out|thrown\s+out|nowhere\s+to\s+go|no\s+place\s+to\s+stay|need\s+a\s+place\s+to\s+stay|where\s+can\s+i\s+go\s+tonight)\b",
    r"\b(?:safe\s+place\s+to\s+stay|emergency\s+shelter|safe\s+accommodation)\b",
]


def is_crisis_support_candidate(query: str) -> bool:
    """Determine whether a companion message asks for safe havens, shelters, or crisis helplines."""
    lowered = query.casefold()
    return any(re.search(pat, lowered) for pat in CRISIS_PATTERNS)


def formulate_crisis_search_query(query: str) -> str:
    """Formulate a targeted, privacy-preserving search query for crisis support / shelters."""
    sanitized = sanitize_query(query)
    lowered = sanitized.casefold()
    found_locations = [loc for loc in INDIAN_LOCATIONS if re.search(rf"\b{re.escape(loc)}\b", lowered)]
    loc_str = " ".join(found_locations[:2]).title() if found_locations else ""

    mental_health = bool(re.search(r"\b(?:mental\s+health|suicid|counsel|depress|anxiety|tele[- ]?manas|kiran|vandrevala)\b", lowered))
    shelter = bool(re.search(r"\b(?:shelter|stay|kicked\s+out|thrown\s+out|safe\s+place|haven|sakhi|one\s+stop)\b", lowered))

    if mental_health and loc_str:
        return f"Tele-MANAS mental health crisis counselling helpline {loc_str} official 14416"
    if mental_health:
        return "Tele-MANAS mental health crisis counselling helpline India official 14416"
    if shelter and loc_str:
        return f"Sakhi One Stop Centre women shelter home {loc_str} official contact India"
    if shelter:
        return "Sakhi One Stop Centre Swadhar Greh women shelter official helpline India"
    if loc_str:
        return f"Women crisis shelter helpline {loc_str} official India"
    return "Women crisis shelter helpline Sakhi One Stop Centre official India"


def search_crisis_support_web(query: str, max_results: int = 2) -> list[SerpWebResult]:
    """Search Google via SerpAPI for authentic crisis safe havens, shelters, or helplines."""
    if not serpapi_enabled():
        return []

    search_query = formulate_crisis_search_query(query)
    if not search_query.strip():
        return []

    cache_key = f"crisis:{search_query.casefold()}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    results = _fetch_from_serpapi(search_query, max_results=max_results)
    _cache_put(cache_key, results)
    return results


def format_crisis_support_context(results: list[SerpWebResult]) -> str:
    """Format crisis support results for model context."""
    if not results:
        return ""
    lines = []
    for index, res in enumerate(results, start=1):
        lines.append(f"- Resource {index}: {res.title} ({res.source_name}) — {res.snippet} [Link: {res.link}]")
    return "\n".join(lines)


HEALTH_FACILITY_PATTERNS = [
    r"\b(?:phc|chc|primary\s+health\s+cent(?:er|re)|community\s+health\s+cent(?:er|re))\b",
    r"\b(?:jan\s+aushadhi|pmbjk|janaushadhi|generic\s+medicines?|suvidha\s+pad)\b",
    r"\b(?:sanitary\s+(?:pads?|napkins?)|menstrual\s+(?:cups?|pads?))\b",
    r"\b(?:emergency\s+contracepti\w*|i[- ]?pill|morning\s+after\s+pill|72\s+hours?\s+pill|unwanted[- ]?72)\b",
    r"\b(?:sti\s+clinic|std\s+clinic|ictc\s+cent(?:er|re)|naco|hiv\s+test(?:ing)?\s+cent(?:er|re))\b",
    r"\b(?:government\s+hospital|district\s+hospital|civil\s+hospital|maternity\s+cent(?:er|re)|reproductive\s+health\s+clinic)\b",
    r"\b(?:nearest\s+hospital|nearest\s+clinic|where\s+can\s+i\s+(?:buy|find|get)|where\s+to\s+(?:buy|find|get)|where\s+to\s+get\s+tested)\b",
]


def is_health_facility_candidate(query: str) -> bool:
    """Determine whether a health question asks about facilities, PHCs, generic stores, or clinics."""
    lowered = query.casefold()
    return any(re.search(pat, lowered) for pat in HEALTH_FACILITY_PATTERNS)


def formulate_health_search_query(query: str) -> str:
    """Formulate a targeted, privacy-preserving search query for public health facilities."""
    sanitized = sanitize_query(query)
    lowered = sanitized.casefold()
    found_locations = [loc for loc in INDIAN_LOCATIONS if re.search(rf"\b{re.escape(loc)}\b", lowered)]
    loc_str = " ".join(found_locations[:2]).title() if found_locations else ""

    sanitary = bool(re.search(r"\b(?:sanitary|pads?|napkins?|menstrual)\b", lowered))
    jan_aushadhi = bool(re.search(r"\b(?:jan\s+aushadhi|pmbjk|janaushadhi|suvidha|generic)\b", lowered)) or sanitary
    sti_hiv = bool(re.search(r"\b(?:sti|std|ictc|naco|hiv)\b", lowered))
    ecp = bool(re.search(r"\b(?:emergency\s+contracept|i[- ]?pill|morning\s+after|72\s+hour|unwanted)\b", lowered))

    if jan_aushadhi and loc_str:
        return f"Pradhan Mantri Bhartiya Janaushadhi Kendra PMBJK {loc_str} official store locator"
    if jan_aushadhi:
        return "Pradhan Mantri Bhartiya Janaushadhi Pariyojana official store locator India"
    if sti_hiv and loc_str:
        return f"ICTC NACO HIV STI government testing centre {loc_str} official India"
    if sti_hiv:
        return "ICTC NACO HIV STI government testing centre official India"
    if ecp and loc_str:
        return f"emergency contraceptive pill availability PHC government hospital {loc_str} official India"
    if ecp:
        return "emergency contraceptive pill guidelines National Health Mission NHM India official"
    if loc_str:
        return f"Primary Health Centre PHC CHC government hospital {loc_str} official NHM India"
    return "Primary Health Centre Community Health Centre official portal NHM India"


def search_health_facility_web(query: str, max_results: int = 2) -> list[SerpWebResult]:
    """Search Google via SerpAPI for authentic Indian health facilities, Jan Aushadhi Kendras, or PHCs."""
    if not serpapi_enabled():
        return []

    search_query = formulate_health_search_query(query)
    if not search_query.strip():
        return []

    cache_key = f"health:{search_query.casefold()}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    results = _fetch_from_serpapi(search_query, max_results=max_results)
    _cache_put(cache_key, results)
    return results


def format_health_facility_context(results: list[SerpWebResult]) -> str:
    """Format health facility results for model context."""
    if not results:
        return ""
    lines = []
    for index, res in enumerate(results, start=1):
        lines.append(f"- Facility {index}: {res.title} ({res.source_name}) — {res.snippet} [Portal: {res.link}]")
    return "\n".join(lines)


