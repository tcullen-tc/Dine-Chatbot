import re
import sys
import time
import json
import urllib.parse
import urllib.request
from html.parser import HTMLParser

# Optional: OpenAI (only used if you have billing/credits enabled)
try:
    import openai
except Exception:
    openai = None
def load_api_key_from_file(path="openai_key.txt"):
    with open(path, "r") as f:
        return f.read().strip()

# ----------------------------
# 1) Configure your allowlist
# ----------------------------
ALLOWED_DOMAINS = [
    # --- Official Navajo Nation / Diné Government ---
    "navajo-nsn.gov",
    "courts.navajo-nsn.gov",
    "navajocourts.org",
    "navajochapters.org",
    "nnwo.org",
    "navajopeople.org",

    # --- Diné Education & Language ---
    "dincollege.edu",
    "navajolanguageacademy.org",
    "roughrock.k12.az.us",

    # --- Diné Media & Community Organizations ---
    "navajotimes.com",
    "navajocodetalkers.org",
    "discovernavajo.com",

    # --- Indigenous Journalism (Native-led) ---
    "ictnews.org",
    "indiancountrytoday.com",
    "nativeamericannews.net",

    # --- Museums & Academic Institutions ---
    "americanindian.si.edu",
    "loc.gov",
    "pbs.org",
    "smithsonianmag.com",
] # example; verify legitimacy
# --- Trusted media (specific approved videos) ---
TRUSTED_MEDIA = [
    {
        "title": "Diné Teaching Video",
        "url": "https://youtu.be/waCH87_-Adk",
        "source": "YouTube"
    },
    {
        "title": "Diné Cultural Teaching",
        "url": "https://vimeo.com/749026655",
        "source": "Vimeo"
    }
]
ALLOWED_EXACT_URLS = {m["url"] for m in TRUSTED_MEDIA}
# Allow ONLY these exact media URLs (not the whole youtube/vimeo domains)

from datetime import datetime, date

# --- Seasonal teaching mode ---
SEASONAL_MODE = True  # turn off by setting False
HIBERNATION_MONTHS = {11, 12, 1, 2, 3}  # conservative "winter" window

# If asked about animals during winter, we avoid it (per your rule).
ANIMAL_KEYWORDS = [
    "animal", "bear", "coyote", "wolf", "fox", "deer", "elk", "moose", "snake",
    "lizard", "frog", "turtle", "owl", "eagle", "hawk", "bird", "dog", "cat",
    "horse", "buffalo", "bison", "rabbit", "hare", "squirrel", "bat"
]

def is_hibernation_season(today: date | None = None) -> bool:
    today = today or datetime.now().date()
    return today.month in HIBERNATION_MONTHS

def mentions_animals(text: str) -> bool:
    t = (text or "").lower()
    return any(k in t for k in ANIMAL_KEYWORDS)

# --- Trust tiers (simple, transparent scoring) ---
# Higher is more trusted/preferred when choosing sources.
DOMAIN_TRUST = {
    # Official Navajo Nation / Diné Government
    "navajo-nsn.gov": ("official", 1.00),
    "courts.navajo-nsn.gov": ("official", 1.00),
    "navajocourts.org": ("official", 1.00),
    "nnwo.org": ("official", 0.95),

    # Diné Education / Language
    "dincollege.edu": ("education", 0.95),
    "navajolanguageacademy.org": ("education", 0.92),
    "roughrock.k12.az.us": ("education", 0.88),

    # Diné media / orgs
    "navajotimes.com": ("dine_media", 0.85),
    "navajocodetalkers.org": ("dine_org", 0.88),
    "discovernavajo.com": ("tourism", 0.75),

    # Indigenous-led journalism
    "ictnews.org": ("indigenous_media", 0.82),
    "indiancountrytoday.com": ("indigenous_media", 0.82),
    "nativeamericannews.net": ("indigenous_media", 0.75),

    # Museums / archives
    "americanindian.si.edu": ("museum", 0.80),
    "loc.gov": ("archive", 0.80),
    "pbs.org": ("public_media", 0.75),
    "smithsonianmag.com": ("museum_media", 0.70),
}
# --- Trust boosts (higher = more trusted) ---
TRUST_BOOST = {
    # Official / government
    "navajo-nsn.gov": 40,
    "courts.navajo-nsn.gov": 40,
    "loc.gov": 35,

    # Education / museums / major public institutions
    "dincollege.edu": 35,
    "americanindian.si.edu": 35,
    "pbs.org": 20,

    # Indigenous journalism (Native-led)
    "ictnews.org": 20,

    # Known mixed / general media
    "smithsonianmag.com": 10,
}
def trust_for_url(url: str) -> tuple[str, float]:
    host = domain_of(url)
    # Prefer the most-specific match (longest domain string)
    best = ("other", 0.50)
    best_len = 0
    for d, (tier, score) in DOMAIN_TRUST.items():
        if host == d or host.endswith("." + d):
            if len(d) > best_len:
                best = (tier, score)
                best_len = len(d)
    return best
def label_for_source(domain: str, tier: str) -> str:
    # Friendly labels for output/citations
    if tier == "navajo_nation":
        return "Navajo Nation"
    if tier == "dine_college":
        return "Diné College"
    if tier == "dine_education":
        return "Diné Education"
    if tier == "indigenous_journalism":
        return "Indigenous Journalism"
    if tier in ("museum", "museum_media"):
        return "Museum / Institution"
    if tier == "archive":
        return "Archive"
    if tier == "public_media":
        return "Public Media"

    # Fallback: just show the domain
    return domain
USER_AGENT = "Mozilla/5.0 (iPhone; CPU iPhone OS like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile Safari/604.1"


# ----------------------------
# 2) Minimal HTML -> Text
# ----------------------------
class TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self._chunks = []
        self._skip = False

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript"):
            self._skip = True
        if tag in ("p", "br", "div", "li", "h1", "h2", "h3"):
            self._chunks.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript"):
            self._skip = False
        if tag in ("p", "div", "li"):
            self._chunks.append("\n")

    def handle_data(self, data):
        if not self._skip:
            text = data.strip()
            if text:
                self._chunks.append(text + " ")

    def get_text(self):
        text = "".join(self._chunks)
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r"[ \t]{2,}", " ", text)
        return text.strip()


def fetch_url(url: str, timeout: int = 15) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        charset = resp.headers.get_content_charset() or "utf-8"
        return resp.read().decode(charset, errors="ignore")


def domain_of(url: str) -> str:
    try:
        return urllib.parse.urlparse(url).netloc.lower().lstrip("www.")
    except Exception:
        return ""


def is_allowed(url: str) -> bool:
    # Allow explicitly trusted media URLs
    if url in ALLOWED_EXACT_URLS:
        return True

    d = domain_of(url)
    return any(d == ad or d.endswith("." + ad) for ad in ALLOWED_DOMAINS)
def source_label(url: str) -> str:
    d = domain_of(url)

    # Highest priority: Diné / Navajo Nation institutions
    if d.endswith("navajo-nsn.gov") or d.endswith("courts.navajo-nsn.gov"):
        return "Navajo Nation (Official)"
    if d.endswith("dincollege.edu"):
        return "Diné College"
    if d.endswith("roughrock.k12.az.us"):
        return "Rough Rock (Diné Education)"

    # Strong Indigenous-led journalism / institutions
    if d.endswith("ictnews.org"):
        return "ICT News (Indigenous-led)"
    if d.endswith("indiancountrytoday.com"):
        return "Indian Country Today"
    if d.endswith("americanindian.si.edu"):
        return "Smithsonian NMAI / NK360"
    if d.endswith("loc.gov"):
        return "Library of Congress"
    if d.endswith("pbs.org"):
        return "PBS"

    # Your “allowed but general” bucket
    return d

# ----------------------------
# 3) DuckDuckGo HTML search
# ----------------------------
def ddg_search(query: str, max_results: int = 8):
    q = urllib.parse.quote_plus(query)
    url = f"https://duckduckgo.com/html/?q={q}"
    html = fetch_url(url)
    # DuckDuckGo HTML results contain links like: <a rel="nofollow" class="result__a" href="...">
    links = re.findall(r'class="result__a"[^>]*href="([^"]+)"', html)
    # Clean up redirect links
    cleaned = []
    for link in links:
        if "duckduckgo.com/l/?" in link:
            parsed = urllib.parse.urlparse(link)
            params = urllib.parse.parse_qs(parsed.query)
            if "uddg" in params:
                link = urllib.parse.unquote(params["uddg"][0])
        cleaned.append(link)

    # Deduplicate preserving order
    seen = set()
    results = []
    for u in cleaned:
        if u not in seen:
            seen.add(u)
            results.append(u)
        if len(results) >= max_results:
            break
    return results


# ----------------------------
# 4) Gather Diné-only sources
# ----------------------------
def gather_sources(question: str, max_pages: int = 6):
    clean_q = (
    question.replace("“", '"')
            .replace("”", '"')
            .replace("’", "'")
            .replace("‘", "'")
            .strip()
)

    # Build a Diné-focused search query (helps short questions)
    topic = clean_q.strip()
    if len(topic) < 12:
        topic = f"{topic} Diné Navajo"
    search_query = f"{topic} meaning Diné Navajo culture kinship hózhó"

    # First try: plain search
    urls = ddg_search(search_query, max_results=12)

    # Filter to allowlisted domains
    allowed_urls = [u for u in urls if is_allowed(u)]

    # If nothing passes allowlist, try per-domain site: queries
    if not allowed_urls:
        urls = []
        for d in sorted(ALLOWED_DOMAINS):
            q = f"site:{d} {clean_q}"
            urls.extend(ddg_search(q, max_results=8))
        allowed_urls = [u for u in urls if is_allowed(u)]

    # Limit how many pages we fetch
    allowed_urls = allowed_urls[:max_pages]

    # Always include explicitly trusted media URLs (exact match only)
    trusted_urls = list(ALLOWED_EXACT_URLS)

    # Combine trusted + search results (dedupe)
    combined_urls = []
    seen = set()
    for u in (trusted_urls + allowed_urls):
        if u not in seen:
            seen.add(u)
            combined_urls.append(u)

    sources = []
    for u in combined_urls:
        tier, score = trust_for_url(u)
        try:
            html = fetch_url(u, timeout=15)
            parser = TextExtractor()
            parser.feed(html)
            text = parser.get_text()[:6000]

            # Diné filter (keep short so iOS won't wrap)
            t = text.lower()
            if ("navajo" not in t) and ("diné" not in t) and ("dine" not in t):
                continue

            sources.append({
                "url": u,
                "domain": domain_of(u),
                "tier": tier,
                "trust": score,
                "label": label_for_source(domain_of(u), tier),
                "text": text,
            })
        except Exception as e:
            sources.append({
                "url": u,
                "domain": domain_of(u),
                "tier": tier,
                "trust": score,
                "label": label_for_source(domain_of(u), tier),
                "text": "",
                "error": str(e),
            })
    sources.sort(key=lambda s: s.get("trust", 0), reverse=True)
    return sources
# ----------------------------------------
# 5) (Optional) Ask OpenAI using ONLY sources
# ----------------------------------------

def answer_with_openai(question: str, sources):
    if openai is None:
        raise RuntimeError("openai package not installed in this environment.")

    openai.api_key = load_api_key_from_file()

    # Build a compact sources context (WITH text snippets)
    src_lines = []
    for i, s in enumerate(sources, start=1):
        label = s.get("label") or s.get("tier", "other")
        url = s.get("url", "")
        text = (s.get("text") or "").strip()

        if not text:
            continue

        snippet = " ".join(text.split())[:1500]

        src_lines.append(
            f"[{i}] {label} ({url})\n"
            f"Snippet: {snippet}"
        )

    sources_block = "\n\n".join(src_lines)

    system = (
        "You are a helpful assistant that answers ONLY using the provided sources.\n"
        "If the sources contain partial information, synthesize an answer from them.\n"
        "Cite sources like [1], [2] in your answer.\n"
    )

    prompt = (
        f"Question: {question}\n\n"
        f"Allowed sources:\n{sources_block}\n\n"
        "Answer using ONLY the sources above. Include citations like [1]."
    )

    response = openai.ChatCompletion.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
    )
    print("Sending prompt to OpenAI...")
    print(prompt[:1000])
    return response["choices"][0]["message"]["content"]

def detect_principles(sources):
    """
    Very simple keyword-based detector.
    Returns a dict like {"k'e": {"hits": 3, "evidence": [...]}, ...}
    """
    # Normalize text for matching
    def norm(s):
        return (s or "").lower().replace("’", "'")

    # Principle keywords you care about (expand any time)
    PRINCIPLES = {
        "k'é (kinship / relational responsibility)": ["k'e", "k’é", "kinship", "clan", "clans", "affiliation"],
        "hózhó (balance / harmony)": ["hozho", "hózhó", "harmony", "balance"],
        "community responsibility": ["community", "responsibility", "solidarity", "respect", "kindness", "generosity", "peaceful"],
        "matrilineal / matrilocal (family structure)": ["matrilineal", "matrilocal", "descent", "mother", "household"],
    }

    found = {}
    for s in sources:
        text = norm(s.get("text", ""))
        if not text:
            continue

        for pname, kws in PRINCIPLES.items():
            hits = sum(text.count(norm(k)) for k in kws if k.strip())
            if hits > 0:
                if pname not in found:
                    found[pname] = {"hits": 0, "evidence": []}
                found[pname]["hits"] += hits

                # Save a short evidence snippet (first match area)
                for k in kws:
                    k2 = norm(k)
                    idx = text.find(k2)
                    if idx != -1:
                        start = max(0, idx - 120)
                        end = min(len(text), idx + 240)
                        snippet = text[start:end].strip()
                        # avoid duplicates
                        if snippet and snippet not in found[pname]["evidence"]:
                            found[pname]["evidence"].append(snippet)
                        break

    # Sort by hits
    found = dict(sorted(found.items(), key=lambda kv: kv[1]["hits"], reverse=True))
    return found


def print_fallback_answer(question: str, sources):
    """
    Prints a structured answer without OpenAI, using only extracted sources.
    """
    principles = detect_principles(sources)

    print("\n=== Diné-principled fallback (no OpenAI) ===\n")
    print("Question:", question.strip(), "\n")

    if not sources:
        print("I couldn't retrieve any sources from the allowed domains.")
        return

    # List sources (citations)
    print("Sources used:")
    for i, s in enumerate(sources, start=1):
        print(f"[{i}] {s.get('url')}")
    print()

    # If we found no principles, say so plainly
    if not principles:
        print("I found sources, but they didn't contain clear Diné principle terms (k’é, hózhó, clan/kinship, etc.).")
        print("Try asking a more culturally-anchored question (e.g., 'How does k’é guide relationships?').")
        return

    # Show what principles were detected
    for p, data in principles.items():
        print(f"\n• {p}")
        print(f"  hits: {data['hits']}")

    # Build an application template based on principles (generic but grounded)
    print("How these principles can be applied to your question:")
    if "k'é (kinship / relational responsibility)" in principles:
        print("- Practice k’é in action: lead with kindness, friendliness, generosity, and peacefulness, and treat relationships as responsibilities, not transactions. [1]")
    if "hózhó (balance / harmony)" in principles:
        print("- Aim for hózhó: choose approaches that build harmony and balance in the relationship and the wider community. [1]")
    if "community responsibility" in principles:
        print("- Show up consistently in community spaces: trust grows from repeated respectful presence and helpfulness over time. [1]")
    if "matrilineal / matrilocal (family structure)" in principles:
        print("- Be respectful of family structures and elders: relationships deepen when you honor household/community context, not just one-on-one interaction. [1]")

    print("\nEvidence snippets (for transparency):")
    for pname, meta in list(principles.items())[:3]:
        if meta["evidence"]:
            print(f"\n- {pname}:")
            print("  ...", meta["evidence"][0][:400].replace("\n", " "), "...")

def main():
    question = input("Ask a question: ")

    # Reset variables for each new question
    sources = []
    principles = {}

    print("\nSearching allowed Diné sources...\n")
    sources = gather_sources(question)

    print(f"Found {len(sources)} sources\n")
    for i, s in enumerate(sources, start=1):
        print(f"[{i}] {s.get('url','')}")

    print("\nGenerating answer...\n")
    answer = answer_with_openai(question, sources)

    print("\n--- Answer ---\n")
    print(answer)
    print("\n--- Trusted Media ---")

    for media in TRUSTED_MEDIA:
        print(f"{media['title']} ({media['source']}): {media['url']}")

    principles = detect_principles(sources)

    print("\n--- Cultural Principles Detected ---\n")
    print(principles)


if __name__ == "__main__":
    main()
