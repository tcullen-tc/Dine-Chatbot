import re
import sys
import time
import json
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from datetime import datetime, date
from typing import List, Dict, Any, Optional, Tuple, Set
import io  # Make sure this line is present
import io

from flask import Flask, request, render_template_string

# Create Flask app
app = Flask(__name__)

# Optional: OpenAI (only used if you have billing/credits enabled)
import os
import openai

try:
    # Try to load API key from file
   def load_openai_key():
    # First check environment variable (for Render)
    env_key = os.environ.get("OPENAI_API_KEY")
    if env_key:
        print("✅ Using OpenAI key from environment variable")
        return env_key
    
    # Fallback to file (for local development)
    try:
        with open(os.path.expanduser("~/openai_key.txt"), "r") as f:
            print("✅ Using OpenAI key from file")
            return f.read().strip()
    except:
        print("⚠️ No OpenAI key found")
        return None

OPENAI_API_KEY = load_openai_key()
    if OPENAI_API_KEY:
        openai.api_key = OPENAI_API_KEY
        OPENAI_AVAILABLE = True
        print("✅ OpenAI initialized with API key")
    else:
        OPENAI_AVAILABLE = False
        print("ℹ️ OpenAI key not found - using local knowledge base only")
except ImportError:
    OPENAI_AVAILABLE = False
    print("ℹ️ OpenAI not installed - using local knowledge base only")


# PDF Support Check
try:
    import PyPDF2
    PDF_SUPPORT = True
    print("✅ PyPDF2 found - PDF support enabled")
except ImportError:
    PyPDF2 = None
    PDF_SUPPORT = False
    print("❌ PyPDF2 NOT found - PDFs will show garbage")

# PDF Support - Using system packages
try:
    import PyPDF2
    PDF_SUPPORT = True
    print("✅ PDF support enabled (PyPDF2 from system packages)")
except ImportError:
    PyPDF2 = None
    PDF_SUPPORT = False
    print("⚠️  PyPDF2 not available. PDF text extraction will be limited.")

# pdfplumber might not be available via apt, so check gracefully
try:
    import pdfplumber
    PDFPLUMBER_SUPPORT = True
    print("✅ Advanced PDF support enabled (pdfplumber)")
except ImportError:
    pdfplumber = None
    PDFPLUMBER_SUPPORT = False
    print("ℹ️  pdfplumber not installed (optional). Using PyPDF2 only.")





def simple_summary(sources: List[Dict[str, Any]], max_sentences: int = 3) -> str:
    """
    Crude, rule‑of‑thumb summary of the fetched texts.
    Used only when OpenAI isn't available.
    """
    sentences: List[str] = []
    for s in sorted(sources, key=lambda x: x.get("trust", 0), reverse=True):
        text = (s.get("text") or "").strip()
        if not text:
            continue
        # split on ., ? or ! followed by whitespace
        parts = re.split(r'(?<=[\.\?\!])\s+', text)
        for p in parts:
            candidate = p.strip()
            if candidate and candidate not in sentences:
                sentences.append(candidate)
                break                 # only the first sentence per source
        if len(sentences) >= max_sentences:
            break
    return " ".join(sentences)

def load_api_key_from_file(path="openai_key.txt"):
    """Load OpenAI API key from file."""
    try:
        with open(path, "r") as f:
            return f.read().strip()
    except FileNotFoundError:
        print(f"Warning: API key file {path} not found")
        return ""
    except Exception as e:
        print(f"Warning: Could not read API key: {e}")
        return ""

# ----------------------------
# 1) Configure your allowlist - UPDATED WITH NEW DOMAINS
# ----------------------------
ALLOWED_DOMAINS = [
    # --- Official Navajo Nation / Diné Government ---
    "navajo-nsn.gov",
    "courts.navajo-nsn.gov",
    "navajocourts.org",
    "navajochapters.org",
    "nnwo.org",
    "navajopeople.org",
    "navajo.org",

    # --- Diné Education & Language ---
    "dinecollege.edu",
    "navajolanguageacademy.org",
    "roughrock.k12.az.us",
    "nau.edu",
    "navajotech.edu",
    "unm.edu",

    # --- Diné Media & Community Organizations ---
    "navajotimes.com",
    "navajocodetalkers.org",
    "discovernavajo.com",
    "navajohopiobserver.com",
    "dineta.com",

    # --- Indigenous Journalism ---
    "ictnews.org",
    "indiancountrytoday.com",
    "nativeamericannews.net",
    "ncai.org",

    # --- Museums & Academic Institutions ---
    "americanindian.si.edu",
    "loc.gov",
    "pbs.org",
    "smithsonianmag.com",

    # --- University Presses (Academic Books) ---
    "unmpress.com",
    "upcolorado.com",
    "uapress.arizona.edu",
    
    # --- Academic & Cultural Resources ---
    "jstor.org",
    "anthrosource.onlinelibrary.wiley.com",
    "ehillerman.unm.edu",
    
    # --- Additional Cultural Sites ---
    "navajoculture.org",
    "traditionalnavajoteachings.org",
]
import os
import glob

# Document search configuration
DOCUMENTS_FOLDER = "/home/tony-cullen/dine_documents"

def load_documents_from_folder():
    """Load all text files from the documents folder."""
    documents = []
    
    # Create folder if it doesn't exist
    if not os.path.exists(DOCUMENTS_FOLDER):
        os.makedirs(DOCUMENTS_FOLDER)
        print(f"📁 Created folder: {DOCUMENTS_FOLDER}")
        print("   Add .txt files there to include them in searches")
        return documents
    
    # Find all .txt files
    txt_files = glob.glob(os.path.join(DOCUMENTS_FOLDER, "*.txt"))
    
    for file_path in txt_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            filename = os.path.basename(file_path)
            documents.append({
                "url": f"local:{filename}",
                "domain": "local-documents",
                "tier": "document",
                "trust": 0.95,  # High trust for your documents
                "label": f"📚 {filename}",
                "text": content
            })
            print(f"✅ Loaded document: {filename}")
        except Exception as e:
            print(f"❌ Error loading {file_path}: {e}")
    
    return documents

def search_documents(question, documents):
    """Search through local documents for relevant content."""
    if not documents:
        return []
    
    question_lower = question.lower()
    keywords = question_lower.split()
    
    # Remove common words
    stop_words = {'the', 'a', 'an', 'is', 'at', 'which', 'on', 'and', 'or', 'to', 'in', 'for', 'who', 'what', 'where', 'when', 'why', 'how'}
    keywords = [k for k in keywords if k not in stop_words and len(k) > 3]
    
    results = []
    for doc in documents:
        text_lower = doc['text'].lower()
        score = 0
        
        # Count keyword matches
        for keyword in keywords:
            score += text_lower.count(keyword)
        
        # Check for exact phrases
        if "black god" in question_lower and ("black god" in text_lower or "haashchʼééshzhiní" in text_lower):
            score += 50  # Big boost for exact match
        
        if score > 10:  # Minimum relevance threshold
            doc_copy = doc.copy()
            doc_copy['relevance'] = score
            results.append(doc_copy)
    
    # Sort by relevance
    results.sort(key=lambda x: x.get('relevance', 0), reverse=True)
    return results[:5]  # Return top 5


TRUSTED_MEDIA = [
    # Add trusted media entries as needed
    # {"title": "Example Video", "source": "YouTube", "url": "https://youtube.com/watch?v=..."}
]
ALLOWED_EXACT_URLS = {m["url"] for m in TRUSTED_MEDIA}

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
    """Check if current month is in hibernation season."""
    today = today or datetime.now().date()
    return today.month in HIBERNATION_MONTHS

def mentions_animals(text: str) -> bool:
    """Check if text mentions any animal keywords."""
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
    "dinecollege.edu": ("education", 0.95),  # Fixed: was "dincollege.edu"
    "navajolanguageacademy.org": ("education", 0.92),
    "roughrock.k12.az.us": ("education", 0.88),
    "nau.edu": ("education", 0.90),
    "navajotech.edu": ("education", 0.88),
    "unm.edu": ("education", 0.85),

    # Diné media / orgs
    "navajotimes.com": ("dine_media", 0.85),
    "navajocodetalkers.org": ("dine_org", 0.88),
    "discovernavajo.com": ("tourism", 0.75),
    "navajohopiobserver.com": ("dine_media", 0.85),
    "dineta.com": ("dine_media", 0.85),
    "ncai.org": ("indigenous_org", 0.80),

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

USER_AGENT = "Mozilla/5.0 (iPhone; CPU iPhone OS like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile Safari/604.1"

# ----------------------------
# 2) Minimal HTML -> Text
# ----------------------------
class TextExtractor(HTMLParser):
    """Extract text content from HTML, ignoring scripts and styles."""
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
        """Get cleaned text from parsed HTML."""
        text = "".join(self._chunks)
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r"[ \t]{2,}", " ", text)
        return text.strip()

# ===========================================
# PASTE STEP 3 FUNCTIONS HERE - RIGHT HERE!
# ===========================================

def extract_text_from_pdf(pdf_content: bytes) -> str:
    """
    Extract clean text from PDF binary content using PyPDF2.
    """
    text = ""
    
    # Use PyPDF2 (available via apt)
    if PDF_SUPPORT:
        try:
            with io.BytesIO(pdf_content) as pdf_file:
                pdf_reader = PyPDF2.PdfReader(pdf_file)
                pages = []
                for page_num, page in enumerate(pdf_reader.pages):
                    page_text = page.extract_text()
                    if page_text:
                        # Clean up common PDF artifacts
                        page_text = re.sub(r'\s+', ' ', page_text)  # Normalize whitespace
                        page_text = re.sub(r'[^\x20-\x7E\n\r\t]', '', page_text)  # Remove non-printable chars
                        pages.append(page_text)
                    else:
                        print(f"⚠️  Page {page_num + 1} yielded no text")
                
                text = "\n\n".join(pages)
                if text.strip():
                    print(f"✅ Successfully extracted {len(pages)} pages with PyPDF2")
                    return text
        except Exception as e:
            print(f"PyPDF2 extraction failed: {e}")
    
    return text

def clean_html_from_pdf(html_content: str) -> str:
    """
    Clean up HTML that contains embedded PDF data.
    This handles cases where the PDF is embedded in HTML.
    """
    # Remove PDF object markers and garbage
    lines = html_content.split('\n')
    clean_lines = []
    
    for line in lines:
        # Skip lines that are clearly PDF objects or metadata
        if re.match(r'\d+ \d+ obj', line):  # PDF object markers
            continue
        if re.match(r'<<.*>>', line):  # PDF dictionaries
            continue
        if re.match(r'stream|endstream', line):  # PDF stream markers
            continue
        if re.match(r'\/[A-Z][a-z]+', line):  # PDF commands
            continue
        if re.match(r'\[\d+ \d+ R\]', line):  # PDF references
            continue
        
        # Keep lines that look like readable text
        if len(line.strip()) > 20:  # Arbitrary threshold for meaningful content
            clean_lines.append(line)
    
    return '\n'.join(clean_lines)

# ===========================================
# YOUR EXISTING fetch_url FUNCTION STARTS HERE
# ===========================================

def fetch_url(url: str, timeout: int = 15) -> str:
    """Fetch URL content with proper error handling."""
    req = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT}
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="ignore")
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return ""

def extract_text_from_pdf(pdf_content: bytes) -> str:
    """
    Extract clean text from PDF binary content using PyPDF2.
    """
    if not PDF_SUPPORT:
        return ""
    
    try:
        with io.BytesIO(pdf_content) as pdf_file:
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            pages = []
            for page_num, page in enumerate(pdf_reader.pages):
                page_text = page.extract_text()
                if page_text:
                    # Clean up the text
                    page_text = re.sub(r'\s+', ' ', page_text)
                    page_text = re.sub(r'[^\x20-\x7E\n\r\t]', '', page_text)
                    pages.append(page_text)
            
            if pages:
                return "\n\n".join(pages)
            else:
                return ""
    except Exception as e:
        print(f"PDF extraction error: {e}")
        return ""

def clean_pdf_garbage(html_content: str) -> str:
    """
    Remove PDF garbage and try to find readable text.
    """
    lines = html_content.split('\n')
    readable_lines = []
    
    for line in lines:
        line = line.strip()
        # Skip empty lines
        if not line:
            continue
        # Skip lines that are clearly PDF objects
        if re.match(r'\d+ \d+ obj', line):
            continue
        if re.match(r'<<.*>>', line):
            continue
        if 'stream' in line or 'endstream' in line:
            continue
        if re.match(r'\/[A-Z][a-z]+', line):
            continue
        if 'uuid:' in line:
            continue
        # Keep lines that look like English text
        if re.search(r'[a-zA-Z]{3,} [a-zA-Z]{3,}', line):
            readable_lines.append(line)
    
    return '\n'.join(readable_lines)


def fetch_url(url: str, timeout: int = 15) -> str:
    """Fetch URL content with PDF detection and extraction."""
    req = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT}
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            content_type = resp.headers.get('Content-Type', '')
            raw_content = resp.read()
            
            # Handle PDF files
            if 'application/pdf' in content_type or url.lower().endswith('.pdf'):
                print(f"📄 Processing PDF: {url}")
                
                # Try to extract text
                text = extract_text_from_pdf(raw_content)
                if text and len(text) > 100:
                    print(f"✅ Extracted {len(text)} characters from PDF")
                    return text
                else:
                    # Fall back to cleaning garbage
                    try:
                        decoded = raw_content.decode('utf-8', errors='ignore')
                        cleaned = clean_pdf_garbage(decoded)
                        if cleaned:
                            print(f"✅ Found {len(cleaned)} chars of readable text")
                            return cleaned
                        else:
                            return "[PDF content could not be extracted]"
                    except:
                        return "[PDF: Could not decode content]"
            
            # Handle HTML
            charset = resp.headers.get_content_charset() or "utf-8"
            return raw_content.decode(charset, errors="ignore")
            
    except urllib.error.URLError as e:
        print(f"Network error fetching {url}: {e}")
        return ""
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return ""


def domain_of(url: str) -> str:
    """Extract domain from URL."""
    try:
        return urllib.parse.urlparse(url).netloc.lower().lstrip("www.")
    except Exception:
        return ""


def is_allowed(url: str) -> bool:
    """Check if URL is from an allowed domain."""
    # Allow explicitly trusted media URLs
    if url in ALLOWED_EXACT_URLS:
        return True

    d = domain_of(url)
    return any(d == ad or d.endswith("." + ad) for ad in ALLOWED_DOMAINS)


def trust_for_url(url: str) -> tuple[str, float]:
    """Get trust tier and score for a URL."""
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
    """Get friendly label for a source based on its tier."""
    # Friendly labels for output/citations
    tier_labels = {
        "official": "Navajo Nation (Official)",
        "education": "Diné Education",
        "dine_media": "Diné Media",
        "dine_org": "Diné Organization",
        "tourism": "Tourism / Information",
        "indigenous_media": "Indigenous Journalism",
        "museum": "Museum / Institution",
        "archive": "Archive",
        "public_media": "Public Media",
        "museum_media": "Museum Media",
    }
    return tier_labels.get(tier, domain)


def source_label(url: str) -> str:
    """Legacy function - kept for compatibility."""
    d = domain_of(url)

    # Highest priority: Diné / Navajo Nation institutions
    if d.endswith("navajo-nsn.gov") or d.endswith("courts.navajo-nsn.gov"):
        return "Navajo Nation (Official)"
    
    if d.endswith("dinecollege.edu"):
        return "Diné College"
    
    if d.endswith("roughrock.k12.az.us"):
        return "Rough Rock (Diné Education)"
    
    if d.endswith("navajotech.edu"):
        return "Navajo Technical University"

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

    # Your "allowed but general" bucket
    return d

# ----------------------------
# 3) DuckDuckGo HTML search
# ----------------------------
def ddg_search(query: str, max_results: int = 8) -> List[str]:
    """Search DuckDuckGo and return list of result URLs."""
    q = urllib.parse.quote_plus(query)
    url = f"https://duckduckgo.com/html/?q={q}"
    html = fetch_url(url)
    
    if not html:
        return []
    
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
def gather_sources(question: str, max_pages: int = 6) -> List[Dict[str, Any]]:
    """Gather sources from local documents AND allowed domains."""
    
    sources = []
    
    # STEP 1: Search local documents (instant, no internet needed)
    print("📚 Searching local documents...")
    documents = load_documents_from_folder()  # Load fresh each time
    doc_sources = search_documents(question, documents)
    
    if doc_sources:
        print(f"✅ Found {len(doc_sources)} relevant documents")
        sources.extend(doc_sources)
    else:
        print("📖 No relevant documents found")
    
    # STEP 2: Search the web (your existing code)
    print("\n🌐 Searching online sources...")
    clean_q = (
        question.replace("“", '"')
                .replace("”", '"')
                .replace("’", "'")
                .replace("‘", "'")
                .strip()
    )

    topic = clean_q.strip().lower()

    # Build search query based on question type
    kinship_terms = ["grandmother", "grandfather", "mother", "father",
                     "aunt", "uncle", "sister", "brother", "clan", "family", "relative"]
    story_terms = ["coyote", "black god", "holy people", "ceremony",
                   "creation", "monster slayer", "born for water", "story"]

    if any(word in topic for word in kinship_terms):
        search_query = f"{clean_q} Diné Navajo kinship term family relationship"
    elif any(word in topic for word in story_terms):
        search_query = f"{clean_q} Diné Navajo teaching story holy people meaning"
    elif len(topic) < 12:
        search_query = f"{clean_q} Diné Navajo culture kinship hózhó"
    else:
        search_query = f"{clean_q} Navajo Diné culture k'é hózhó"

    # First try: plain search
    urls = ddg_search(search_query, max_results=12)

    # Filter to allowlisted domains
    allowed_urls = [u for u in urls if is_allowed(u)]

    # If nothing passes allowlist, try per-domain site: queries
    if not allowed_urls:
        urls = []
        for d in sorted(ALLOWED_DOMAINS):
            q = f"site:{d} {clean_q} Navajo Diné k'é hózhó"
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

    for u in combined_urls:
        tier, score = trust_for_url(u)
        try:
            html = fetch_url(u, timeout=15)
            if not html:
                continue

            parser = TextExtractor()
            parser.feed(html)
            full_text = parser.get_text()

            paragraphs = [p.strip() for p in full_text.split("\n") if p.strip()]

            priority_terms = [
                "navajo", "diné", "dine", "k'e", "k’é", "kinship", "clan", "clans",
                "hozho", "hózhó", "harmony", "balance", "community", "responsibility"
            ]

            relevant_parts = []
            for p in paragraphs:
                p_low = p.lower()
                if any(term in p_low for term in priority_terms):
                    relevant_parts.append(p)

            if relevant_parts:
                text = "\n\n".join(relevant_parts)[:12000]
            else:
                text = full_text[:12000]

            # Skip if no relevant content
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
            print(f"Error processing {u}: {e}")
            continue

    # Sort all sources by trust
    sources.sort(key=lambda s: s.get("trust", 0), reverse=True)
    return sources

# ----------------------------------------
# 5) (Optional) Ask OpenAI using ONLY sources
# ----------------------------------------
def answer_with_openai(question: str, sources: List[Dict[str, Any]], principles: Dict[str, Any]) -> str:
    """Generate answer using OpenAI API based on provided sources."""
    if not OPENAI_AVAILABLE or openai is None:
        raise RuntimeError("OpenAI package not installed in this environment.")

    api_key = load_api_key_from_file()
    if not api_key:
        raise RuntimeError("OpenAI API key not found or empty.")
    
    openai.api_key = api_key

    src_lines = []
    for i, s in enumerate(sources, start=1):
        label = s.get("label") or s.get("tier", "other")
        url = s.get("url", "")
        text = (s.get("text") or "").strip()

        if not text:
            continue

        snippet = " ".join(text.split())[:1000]

        src_lines.append(
            f"[{i}] {label} ({url})\n"
            f"Snippet: {snippet}"
        )

    if not src_lines:
        return "No valid sources found with content to answer the question."

    sources_block = "\n\n".join(src_lines)

    system = (
        "You are a helpful assistant that answers ONLY using the provided sources.\n"
        "Begin your response with a brief (2–3 sentence) summary, "
        "then expand with details and cite sources like [1], [2].\n"
    )

    principles_text = ", ".join(principles.keys()) if principles else "none detected"

    prompt = (
        f"Question: {question}\n\n"
        f"Detected Diné cultural principles: {principles_text}\n\n"
        f"Allowed sources:\n{sources_block}\n\n"
        "Answer using ONLY the sources above. If cultural principles apply, explain them. Include citations like [1]."
    )

    try:
        response = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
        )
        return response["choices"][0]["message"]["content"]
    except Exception as e:
        raise RuntimeError(f"OpenAI API call failed: {e}")

def detect_principles(sources: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Very simple keyword-based detector.
    Returns a dict like {"k'e": {"hits": 3, "evidence": [...]}, ...}
    """
    # Normalize text for matching
    def norm(s):
        return (s or "").lower().replace("’", "'")

    # Principle keywords you care about (expand any time)
    PRINCIPLES = {
        "k'é (kinship / relational responsibility)": [
            "k'e", "k’é", "kinship", "clan", "clans", "affiliation",
            "relative", "relatives", "relationship", "relationships"
        ],
        "hózhó (balance / harmony)": [
            "hozho", "hózhó", "harmony", "balance", "beauty", "order"
        ],
        "community responsibility": [
            "community", "responsibility", "solidarity", "respect",
            "kindness", "generosity", "peaceful", "care", "support", "cooperation", "mutual", "sharing" 
        ],
        "matrilineal / matrilocal (family structure)": [
            "matrilineal", "matrilocal", "descent", "mother", "household", "maternal"
        ],
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


def generate_better_summary(source: Dict[str, Any], question: str) -> str:
    """Generate a multi-paragraph summary from the most relevant source."""
    text = source.get('text', '')
    if not text:
        return "No content available."
    
    # Define question_lower here
    question_lower = question.lower()
    
    # Split into paragraphs
    all_paragraphs = text.split('\n\n')
    
    # Skip Gutenberg header (first few paragraphs)
    start_idx = 0
    for i, p in enumerate(all_paragraphs[:15]):
        p_lower = p.lower()
        if "project gutenberg" in p_lower or "ebook" in p_lower or "www.gutenberg" in p_lower:
            start_idx = i + 1
    
    # Get content paragraphs (skip header)
    content_paragraphs = all_paragraphs[start_idx:]
    
    # Find paragraphs relevant to the question
    question_words = set(question_lower.split())
    stop_words = {'the', 'a', 'an', 'is', 'at', 'which', 'on', 'and', 'or', 'to', 'in', 'for', 'describe', 'traditional', 'what', 'how', 'why', 'does'}
    keywords = [w for w in question_words if w not in stop_words and len(w) > 3]
    
    # Score each paragraph for relevance
    scored_paragraphs = []
    for p in content_paragraphs:
        if len(p) < 100:  # Skip very short paragraphs
            continue
            
        p_lower = p.lower()
        
        # SKIP paragraphs that look like Table of Contents
        if re.search(r'plate\s+\d+|fig\.\s+\d+|page\s+\d+|^\d+$', p_lower):
            continue
            
        # SKIP lines with lots of numbers or dashes (TOC formatting)
        if len(re.findall(r'\d+', p)) > 5:
            continue
            
        score = 0
        
        # Count keyword matches
        for keyword in keywords:
            score += p_lower.count(keyword) * 2
        
        # Boost score for paragraphs with topic-specific terms
        if "weav" in question_lower:
            weaving_terms = ["weav", "loom", "blanket", "wool", "spindle", "warp", "weft", "heald", "diagonal", "pattern", "design", "thread", "yarn"]
            for term in weaving_terms:
                if term in p_lower:
                    score += 3
        
        # Boost for paragraphs with substantial length (real content)
        if len(p) > 300:
            score += 2
        
        if score > 0:
            scored_paragraphs.append((score, p))
    
    # Sort by relevance
    scored_paragraphs.sort(reverse=True)
    
    # Build a multi-paragraph summary
    summary_paragraphs = []
    
    if scored_paragraphs:
        # Take top 3 most relevant paragraphs
        for i in range(min(3, len(scored_paragraphs))):
            para = scored_paragraphs[i][1].strip()
            # Clean up the paragraph
            para = re.sub(r'\s+', ' ', para)
            para = re.sub(r'[ \t]+', ' ', para)
            summary_paragraphs.append(para)
    else:
        # Fallback: take first 3 substantial paragraphs (skipping TOC)
        count = 0
        for p in content_paragraphs:
            # Skip TOC-like paragraphs
            if re.search(r'plate\s+\d+|fig\.\s+\d+', p.lower()):
                continue
            if len(p) > 200 and count < 3:
                clean_p = re.sub(r'\s+', ' ', p.strip())
                summary_paragraphs.append(clean_p)
                count += 1
    
    # Format the summary with paragraph breaks
    if summary_paragraphs:
        formatted_summary = "\n\n".join(summary_paragraphs)
        return formatted_summary
    else:
        # Ultimate fallback - take any paragraph with weaving-related terms
        for p in content_paragraphs:
            if "weav" in p.lower() and len(p) > 150:
                return re.sub(r'\s+', ' ', p.strip())
        
        return "Information about Navajo weaving found in sources."

def extract_relevant_excerpt(source: Dict[str, Any], question: str) -> str:
    """Extract a relevant excerpt from the source."""
    text = source.get('text', '')
    if not text:
        return "No excerpt available."
    
    # Split into sentences (simple approach)
    sentences = re.split(r'[.!?]+', text)
    
    # Find sentences with question keywords
    keywords = [w for w in question.lower().split() if len(w) > 3]
    scored_sentences = []
    
    for i, sentence in enumerate(sentences):
        sentence = sentence.strip()
        if len(sentence) < 20 or "project gutenberg" in sentence.lower():
            continue
        
        score = 0
        for keyword in keywords:
            if keyword in sentence.lower():
                score += 1
        
        if score > 0:
            scored_sentences.append((score, sentence))
    
    if scored_sentences:
        # Sort by relevance and return the best one
        scored_sentences.sort(reverse=True)
        return scored_sentences[0][1] + "."
    
    # Fallback: return first substantial sentence
    for sentence in sentences:
        if len(sentence) > 50 and "project gutenberg" not in sentence.lower():
            return sentence.strip() + "..."
    
    return "See sources for more information."

def print_fallback_answer(question: str, sources: List[Dict[str, Any]]):
    """
    Prints a structured answer without OpenAI, using only extracted sources.
    Prioritizes the most relevant source for the summary.
    """
    principles = detect_principles(sources)

    print("\n=== Diné-principled fallback (no OpenAI) ===\n")
    print("Question:", question.strip(), "\n")

    if not sources:
        print("I couldn't retrieve any sources from the allowed domains.")
        return

    # Find the most relevant source for this question
    primary_source = sources[0]  # First source is usually most relevant
    question_lower = question.lower()
    
    # Check for specific topics to prioritize the right document
    if "weav" in question_lower:
        for source in sources:
            url = source.get('url', '').lower()
            if "weaver" in url or "weav" in url:
                primary_source = source
                print(f"📌 Prioritized weaving document for this question")
                break
    
    if "black god" in question_lower or "haashch" in question_lower:
        for source in sources:
            url = source.get('url', '').lower()
            if "black_god" in url or "legend" in url:
                primary_source = source
                print(f"📌 Prioritized Black God document for this question")
                break
    
    # Extract a better summary from the primary source
    print("Quick summary:")
    print(generate_better_summary(primary_source, question))
    print()

    # List all sources used
    print("Sources used:")
    for i, s in enumerate(sources, start=1):
        source_name = s.get('url', 'Unknown')
        if source_name.startswith('local:'):
            # Clean up the display name
            display_name = source_name.replace('local:', '📚 ')
        else:
            display_name = source_name
        # Mark the primary source
        if s == primary_source:
            print(f"[{i}] {display_name} ⭐ (primary source)")
        else:
            print(f"[{i}] {display_name}")
    print()

    # Flask web app for Render deployment
    # Show a relevant excerpt from the primary source
    print("Relevant excerpt:")
    excerpt = extract_relevant_excerpt(primary_source, question)
    # Wrap excerpt for better display
    words = excerpt.split()
    lines = []
    current_line = []
    for word in words:
        current_line.append(word)
        if len(' '.join(current_line)) > 70:
            lines.append(' '.join(current_line))
            current_line = []
    if current_line:
        lines.append(' '.join(current_line))
    
    for line in lines:
        print(f"  {line}")
    print()

    # If we found no principles, say so plainly
    if not principles:
        print("I found sources, but they didn't contain clear Diné principle terms.")
        return

    # Show what principles were detected
    print("Cultural principles detected in sources:")
    for p, data in principles.items():
        print(f"  • {p}: {data['hits']} occurrences")
    print()

def answer_with_openai(question: str, sources: List[Dict[str, Any]]) -> str:
    """Generate a synthesized answer using OpenAI based on local documents."""
    if not OPENAI_AVAILABLE:
        return "OpenAI is not available."
    
    # Build context from your top sources
    context = ""
    for i, source in enumerate(sources[:3]):  # Use top 3 sources
        label = source.get('label', source.get('url', f'Source {i+1}'))
        excerpt = source.get('text', '')[:1500]  # First 1500 chars each
        context += f"\n--- {label} ---\n{excerpt}\n"
    



# HTML template for the web interface
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Diné Cultural Chatbot</title>
    <style>
        body { font-family: Arial; max-width: 800px; margin: 0 auto; padding: 20px; }
        .question { margin: 20px 0; }
        textarea { width: 100%; height: 100px; }
        button { padding: 10px 20px; background: #4CAF50; color: white; border: none; cursor: pointer; }
        .answer { background: #f9f9f9; padding: 20px; border-radius: 5px; margin-top: 20px; }
        .sources { font-size: 0.9em; color: #666; }
    </style>
</head>
<body>
    <h1>Diné Cultural Chatbot</h1>
    <div class="question">
        <form method="POST">
            <textarea name="question" placeholder="Ask about Diné culture...">{{ question }}</textarea><br>
            <button type="submit">Ask</button>
        </form>
    </div>
    {% if answer %}
    <div class="answer">
        <h3>Answer:</h3>
        {{ answer | safe }}
    </div>
    {% endif %}
</body>
</html>
"""

@app.route('/', methods=['GET', 'POST'])
def home():
    question = ""
    answer = ""
    
    if request.method == 'POST':
        question = request.form.get('question', '')
        
        # Check seasonal restrictions
        if SEASONAL_MODE and is_hibernation_season() and mentions_animals(question):
            answer = "During winter months (November-March), we avoid discussing certain animals per Diné tradition. Please ask about other aspects of Diné culture."
        else:
            # Gather sources
            sources = gather_sources(question)
            principles = detect_principles(sources)
            
            # Generate answer
            if OPENAI_AVAILABLE and client is not None:
                answer = answer_with_openai(question, sources)
            else:
                # Capture print_fallback_answer output
                import io
                import sys
                captured = io.StringIO()
                sys.stdout = captured
                print_fallback_answer(question, sources)
                sys.stdout = sys.__stdout__
                answer = captured.getvalue().replace('\n', '<br>')
    
    return render_template_string(HTML_TEMPLATE, question=question, answer=answer)

if __name__ == "__main__":
    # This is for local development only
    # Render uses gunicorn to run the app
    app.run(host='0.0.0.0', port=5000, debug=True)
