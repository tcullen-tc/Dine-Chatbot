import re
import sys
import time
import json
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from datetime import datetime, date
from typing import List, Dict, Any, Optional, Tuple, Set
import io
import threading
import logging
import os
import random

from flask import Flask, request, render_template_string

# Setup logging for Render
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create Flask app
app = Flask(__name__)

# Fun facts for loading screen
FUN_FACTS = [
    "💡 Did you know? The Navajo language has no curse words - Diné teachings emphasize respectful speech.",
    "💡 The word 'Navajo' comes from Tewa, meaning 'large planted fields.' The Diné call themselves Diné - 'The People.'",
    "💡 Traditional Navajo teachings emphasize listening over speaking - we learn by observing first.",
    "💡 The four sacred colors in Diné tradition are white (east), blue (south), yellow (west), and black (north).",
    "💡 Navajo weavings traditionally include a 'spirit line' - a small thread from the center to the edge to let the weaver's spirit escape.",
    "💡 The Navajo Nation spans over 27,000 square miles across Arizona, Utah, and New Mexico.",
    "💡 K'é (kinship) extends beyond blood relations to include all of creation - even the mountains and stars are relatives.",
    "💡 Hózhó is often translated as 'beauty' but encompasses harmony, balance, and wellness in all aspects of life.",
    "💡 Traditional Navajo hogans are built with the door facing east to greet the morning sun and receive blessings.",
    "💡 The Navajo Code Talkers developed an unbreakable code based on the Navajo language during WWII.",
]

# Did You Know facts for sidebar
DID_YOU_KNOW_FACTS = [
    "The Navajo language was used as a code during WWII by the famous Code Talkers - it was never broken!",
    "K'é (kinship) extends beyond blood relations to include all of creation - even the mountains are considered relatives.",
    "Hózhó is often translated as 'beauty' but encompasses harmony, balance, and wellness in all aspects of life.",
    "Traditional Navajo hogans are built with the door facing east to greet the morning sun and receive blessings.",
    "The four sacred mountains mark the boundaries of traditional Dinétah (Navajo homeland).",
    "Weaving was taught to the Navajo by Spider Woman, a holy being who showed them how to create beauty.",
    "The Navajo Nation is the largest Native American reservation in the United States, spanning over 27,000 square miles.",
    "In Diné tradition, the number four is sacred - representing the four directions, four seasons, and four sacred mountains.",
    "The Navajo creation story tells of the Diné emerging through four worlds before arriving in this one.",
    "Traditional Navajo names are often given in ceremonies and hold deep spiritual significance.",
]

# Pronunciation guide for Diné words
PRONUNCIATION_GUIDE = {
    "k'é": "k'-eh (glottal stop, like 'uh-oh')",
    "k'e": "k'-eh (glottal stop, like 'uh-oh')",
    "hózhó": "hoh-zhoh (with nasalized 'oh')",
    "hozho": "hoh-zhoh (with nasalized 'oh')",
    "diné": "di-nay (meaning 'the people')",
    "dine": "di-nay (meaning 'the people')",
    "nahasdzáán": "nah-has-dzahn (Mother Earth)",
    "yádiłhił": "yah-dilth (Father Sky)",
    "naalyéhé": "nah-lyay-hay (traditional Navajo medicine)",
    "hataałii": "hah-tah-ah-lee (traditional healer)",
}

def add_pronunciation_tooltips(text):
    """Add pronunciation tooltips to Diné words"""
    if not text:
        return text
    
    for word, pron in PRONUNCIATION_GUIDE.items():
        # Match whole words only (case insensitive)
        pattern = r'\b' + re.escape(word) + r'\b'
        replacement = f'<span title="Pronunciation: {pron}" style="border-bottom: 1px dotted #2c5f2d; cursor: help;">{word}</span>'
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    return text

def get_trust_badge(trust_score: float) -> str:
    """Generate trust badge HTML based on source trust score"""
    if trust_score >= 0.95:
        return '<span style="background: #2ecc71; color: white; padding: 2px 8px; border-radius: 12px; font-size: 11px; margin-left: 8px;">✓ Verified Source</span>'
    elif trust_score >= 0.80:
        return '<span style="background: #3498db; color: white; padding: 2px 8px; border-radius: 12px; font-size: 11px; margin-left: 8px;">📚 Trusted Source</span>'
    elif trust_score >= 0.65:
        return '<span style="background: #f39c12; color: white; padding: 2px 8px; border-radius: 12px; font-size: 11px; margin-left: 8px;">ℹ️ Informational</span>'
    else:
        return '<span style="background: #95a5a6; color: white; padding: 2px 8px; border-radius: 12px; font-size: 11px; margin-left: 8px;">📖 Reference</span>'

def get_related_questions(question: str) -> List[str]:
    """Suggest related questions based on the current question"""
    q_lower = question.lower()
    
    topic_map = {
        "k'é": [
            "What are the four clans of the Navajo?",
            "How do you introduce yourself in Navajo?",
            "What is kinship responsibility in Diné culture?",
            "How do Navajo clan relationships work?"
        ],
        "k'e": [
            "What are the four clans of the Navajo?",
            "How do you introduce yourself in Navajo?",
            "What is kinship responsibility in Diné culture?"
        ],
        "clan": [
            "What is k'é and how does it relate to clans?",
            "How do Navajo clans trace lineage?",
            "What are the original four clans?"
        ],
        "weav": [
            "What do Navajo rug patterns mean?",
            "Who was Spider Woman?",
            "How is wool prepared for weaving?",
            "What is the significance of the spirit line?"
        ],
        "hózhó": [
            "How do Diné people practice hózhó in daily life?",
            "What is the Hózhóójí ceremony?",
            "How does hózhó relate to health and wellness?"
        ],
        "hozho": [
            "How do Diné people practice hózhó in daily life?",
            "What is the Hózhóójí ceremony?"
        ],
        "code talker": [
            "How did the Code Talkers develop their code?",
            "Who were the original Navajo Code Talkers?",
            "Why was the Navajo language perfect for code?"
        ],
        "long walk": [
            "What led to the Long Walk?",
            "What was life like at Bosque Redondo?",
            "How did the Navajo people survive the Long Walk?"
        ],
        "spider woman": [
            "How did Spider Woman teach weaving?",
            "What is the story of Spider Woman?",
            "What is the significance of Spider Woman in Diné culture?"
        ]
    }
    
    for topic, suggestions in topic_map.items():
        if topic in q_lower:
            return suggestions
    
    # Default suggestions
    return [
        "What is the meaning of k'é?",
        "Tell me about Navajo weaving traditions",
        "What does hózhó mean?",
        "Who were the Navajo Code Talkers?",
        "What are the four sacred mountains?"
    ]

# Optional: OpenAI
try:
    import openai
    OPENAI_INSTALLED = True
except ImportError:
    OPENAI_INSTALLED = False
    logger.info("OpenAI not installed - using local knowledge base only")

OPENAI_AVAILABLE = False
if OPENAI_INSTALLED:
    try:
        env_key = os.environ.get("OPENAI_API_KEY")
        if env_key:
            openai.api_key = env_key
            OPENAI_AVAILABLE = True
            logger.info("OpenAI initialized with API key from environment")
        else:
            try:
                with open(os.path.expanduser("~/openai_key.txt"), "r") as f:
                    openai.api_key = f.read().strip()
                    OPENAI_AVAILABLE = True
                    logger.info("OpenAI initialized with API key from file")
            except:
                logger.warning("No OpenAI key found - using local knowledge base only")
    except Exception as e:
        logger.warning(f"Error initializing OpenAI: {e}")

# PDF Support Check
try:
    import PyPDF2
    PDF_SUPPORT = True
    logger.info("PyPDF2 found - PDF support enabled")
except ImportError:
    PyPDF2 = None
    PDF_SUPPORT = False
    logger.warning("PyPDF2 NOT found - PDFs will show garbage")

try:
    import pdfplumber
    PDFPLUMBER_SUPPORT = True
except ImportError:
    pdfplumber = None
    PDFPLUMBER_SUPPORT = False

# ----------------------------
# 1) Configure your allowlist
# ----------------------------
ALLOWED_DOMAINS = [
    "navajo-nsn.gov", "courts.navajo-nsn.gov", "navajocourts.org",
    "navajochapters.org", "nnwo.org", "navajopeople.org", "navajo.org",
    "dinecollege.edu", "navajolanguageacademy.org", "roughrock.k12.az.us",
    "nau.edu", "navajotech.edu", "unm.edu", "navajotimes.com",
    "navajocodetalkers.org", "discovernavajo.com", "navajohopiobserver.com",
    "dineta.com", "ictnews.org", "indiancountrytoday.com", "nativeamericannews.net",
    "ncai.org", "americanindian.si.edu", "loc.gov", "pbs.org", "smithsonianmag.com",
    "unmpress.com", "upcolorado.com", "uapress.arizona.edu", "jstor.org",
    "anthrosource.onlinelibrary.wiley.com", "ehillerman.unm.edu",
    "navajoculture.org", "traditionalnavajoteachings.org",
]

import glob
DOCUMENTS_FOLDER = "/home/tony-cullen/dine_documents"

def load_documents_from_folder():
    documents = []
    if not os.path.exists(DOCUMENTS_FOLDER):
        os.makedirs(DOCUMENTS_FOLDER)
        return documents
    
    txt_files = glob.glob(os.path.join(DOCUMENTS_FOLDER, "*.txt"))
    for file_path in txt_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            filename = os.path.basename(file_path)
            is_story = 'story' in filename.lower() or 'hero' in filename.lower()
            documents.append({
                "url": f"local:{filename}",
                "domain": "local-documents",
                "tier": "document",
                "trust": 1.00 if is_story else 0.98,
                "label": filename,
                "text": content
            })
        except Exception as e:
            logger.error(f"Error loading {file_path}: {e}")
    return documents

def search_documents(question, documents):
    if not documents:
        return []
    
    question_lower = question.lower()
    keywords = [k for k in question_lower.split() if len(k) > 3 and k not in {'the','a','an','is','at','which','on','and','or','to','in','for'}]
    
    results = []
    for doc in documents:
        text_lower = doc['text'].lower()
        score = sum(text_lower.count(k) for k in keywords)
        if "black god" in question_lower and ("black god" in text_lower or "haashch" in text_lower):
            score += 50
        if score > 10:
            doc_copy = doc.copy()
            doc_copy['relevance'] = score
            results.append(doc_copy)
    
    results.sort(key=lambda x: x.get('relevance', 0), reverse=True)
    return results[:5]

TRUSTED_MEDIA = []
ALLOWED_EXACT_URLS = {m["url"] for m in TRUSTED_MEDIA}

# Seasonal teaching mode
SEASONAL_MODE = True
HIBERNATION_MONTHS = {11, 12, 1, 2, 3}
ANIMAL_KEYWORDS = ["animal", "bear", "coyote", "wolf", "fox", "deer", "elk", "moose", "snake",
                   "lizard", "frog", "turtle", "owl", "eagle", "hawk", "bird", "dog", "cat",
                   "horse", "buffalo", "bison", "rabbit", "hare", "squirrel", "bat"]

def is_hibernation_season(today: date | None = None) -> bool:
    today = today or datetime.now().date()
    return today.month in HIBERNATION_MONTHS

def mentions_animals(text: str) -> bool:
    return any(k in text.lower() for k in ANIMAL_KEYWORDS)

DOMAIN_TRUST = {
    "navajo-nsn.gov": ("official", 1.00), "courts.navajo-nsn.gov": ("official", 1.00),
    "navajocourts.org": ("official", 1.00), "nnwo.org": ("official", 0.95),
    "dinecollege.edu": ("education", 0.95), "navajolanguageacademy.org": ("education", 0.92),
    "roughrock.k12.az.us": ("education", 0.88), "nau.edu": ("education", 0.90),
    "navajotech.edu": ("education", 0.88), "unm.edu": ("education", 0.85),
    "navajotimes.com": ("dine_media", 0.85), "navajocodetalkers.org": ("dine_org", 0.88),
    "discovernavajo.com": ("tourism", 0.75), "navajohopiobserver.com": ("dine_media", 0.85),
    "dineta.com": ("dine_media", 0.85), "ncai.org": ("indigenous_org", 0.80),
    "ictnews.org": ("indigenous_media", 0.82), "indiancountrytoday.com": ("indigenous_media", 0.82),
    "nativeamericannews.net": ("indigenous_media", 0.75), "americanindian.si.edu": ("museum", 0.80),
    "loc.gov": ("archive", 0.80), "pbs.org": ("public_media", 0.75),
    "smithsonianmag.com": ("museum_media", 0.70),
}

USER_AGENT = "Mozilla/5.0 (iPhone; CPU iPhone OS like Mac OS X) AppleWebKit/605.1.15"

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

def extract_text_from_pdf(pdf_content: bytes) -> str:
    if not PDF_SUPPORT:
        return ""
    try:
        with io.BytesIO(pdf_content) as pdf_file:
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            pages = []
            for page in pdf_reader.pages:
                page_text = page.extract_text()
                if page_text:
                    page_text = re.sub(r'\s+', ' ', page_text)
                    page_text = re.sub(r'[^\x20-\x7E\n\r\t]', '', page_text)
                    pages.append(page_text)
            return "\n\n".join(pages) if pages else ""
    except Exception as e:
        logger.error(f"PDF extraction error: {e}")
        return ""

def clean_pdf_garbage(html_content: str) -> str:
    lines = html_content.split('\n')
    readable_lines = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if re.match(r'\d+ \d+ obj', line) or re.match(r'<<.*>>', line):
            continue
        if 'stream' in line or 'endstream' in line:
            continue
        if re.match(r'\/[A-Z][a-z]+', line) or 'uuid:' in line:
            continue
        if re.search(r'[a-zA-Z]{3,} [a-zA-Z]{3,}', line):
            readable_lines.append(line)
    return '\n'.join(readable_lines)

def fetch_url(url: str, timeout: int = 15) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            content_type = resp.headers.get('Content-Type', '')
            raw_content = resp.read()
            
            if 'application/pdf' in content_type or url.lower().endswith('.pdf'):
                text = extract_text_from_pdf(raw_content)
                if text and len(text) > 100:
                    return text
                try:
                    decoded = raw_content.decode('utf-8', errors='ignore')
                    cleaned = clean_pdf_garbage(decoded)
                    return cleaned if cleaned else "[PDF content could not be extracted]"
                except:
                    return "[PDF: Could not decode content]"
            
            charset = resp.headers.get_content_charset() or "utf-8"
            return raw_content.decode(charset, errors="ignore")
    except Exception as e:
        logger.error(f"Error fetching {url}: {e}")
        return ""

def domain_of(url: str) -> str:
    try:
        return urllib.parse.urlparse(url).netloc.lower().lstrip("www.")
    except:
        return ""

def is_allowed(url: str) -> bool:
    if url in ALLOWED_EXACT_URLS:
        return True
    d = domain_of(url)
    return any(d == ad or d.endswith("." + ad) for ad in ALLOWED_DOMAINS)

def trust_for_url(url: str) -> tuple[str, float]:
    host = domain_of(url)
    best = ("other", 0.50)
    best_len = 0
    for d, (tier, score) in DOMAIN_TRUST.items():
        if host == d or host.endswith("." + d):
            if len(d) > best_len:
                best = (tier, score)
                best_len = len(d)
    return best

def label_for_source(domain: str, tier: str) -> str:
    tier_labels = {
        "official": "Navajo Nation (Official)", "education": "Diné Education",
        "dine_media": "Diné Media", "dine_org": "Diné Organization",
        "tourism": "Tourism / Information", "indigenous_media": "Indigenous Journalism",
        "museum": "Museum / Institution", "archive": "Archive",
        "public_media": "Public Media", "museum_media": "Museum Media",
    }
    return tier_labels.get(tier, domain)

def ddg_search(query: str, max_results: int = 8) -> List[str]:
    q = urllib.parse.quote_plus(query)
    url = f"https://duckduckgo.com/html/?q={q}"
    html = fetch_url(url)
    if not html:
        return []
    
    links = re.findall(r'class="result__a"[^>]*href="([^"]+)"', html)
    cleaned = []
    for link in links:
        if "duckduckgo.com/l/?" in link:
            parsed = urllib.parse.urlparse(link)
            params = urllib.parse.parse_qs(parsed.query)
            if "uddg" in params:
                link = urllib.parse.unquote(params["uddg"][0])
        cleaned.append(link)
    
    seen = set()
    results = []
    for u in cleaned:
        if u not in seen:
            seen.add(u)
            results.append(u)
        if len(results) >= max_results:
            break
    return results

def gather_sources(question: str, max_pages: int = 6) -> List[Dict[str, Any]]:
    sources = []
    
    # Local documents
    documents = load_documents_from_folder()
    doc_sources = search_documents(question, documents)
    if doc_sources:
        sources.extend(doc_sources)
    
    # Web search
    clean_q = question.replace("“", '"').replace("”", '"').replace("’", "'").replace("‘", "'").strip()
    topic = clean_q.lower()
    
    kinship_terms = ["grandmother", "grandfather", "mother", "father", "aunt", "uncle", "sister", "brother", "clan", "family", "relative"]
    story_terms = ["coyote", "black god", "holy people", "ceremony", "creation", "monster slayer", "born for water", "story"]
    
    if any(w in topic for w in kinship_terms):
        search_query = f"{clean_q} Diné Navajo kinship term family relationship"
    elif any(w in topic for w in story_terms):
        search_query = f"{clean_q} Diné Navajo teaching story holy people meaning"
    elif len(topic) < 12:
        search_query = f"{clean_q} Diné Navajo culture kinship hózhó"
    else:
        search_query = f"{clean_q} Navajo Diné culture k'é hózhó"
    
    urls = ddg_search(search_query, max_results=12)
    allowed_urls = [u for u in urls if is_allowed(u)]
    
    if not allowed_urls:
        urls = []
        for d in sorted(ALLOWED_DOMAINS):
            q = f"site:{d} {clean_q} Navajo Diné k'é hózhó"
            urls.extend(ddg_search(q, max_results=8))
        allowed_urls = [u for u in urls if is_allowed(u)]
    
    allowed_urls = allowed_urls[:max_pages]
    
    combined_urls = []
    seen = set()
    for u in (list(ALLOWED_EXACT_URLS) + allowed_urls):
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
            priority_terms = ["navajo", "diné", "dine", "k'e", "k’é", "kinship", "clan", "hozho", "hózhó", "harmony", "balance"]
            
            relevant_parts = [p for p in paragraphs if any(term in p.lower() for term in priority_terms)]
            text = "\n\n".join(relevant_parts)[:12000] if relevant_parts else full_text[:12000]
            
            t = text.lower()
            if ("navajo" in t) or ("diné" in t) or ("dine" in t):
                sources.append({
                    "url": u, "domain": domain_of(u), "tier": tier,
                    "trust": score, "label": label_for_source(domain_of(u), tier),
                    "text": text,
                })
        except Exception as e:
            logger.error(f"Error processing {u}: {e}")
            continue
    
    sources.sort(key=lambda s: s.get("trust", 0), reverse=True)
    return sources

def answer_with_openai(question: str, sources: List[Dict[str, Any]], principles: Dict[str, Any]) -> Optional[str]:
    if not OPENAI_AVAILABLE:
        return None
    
    src_lines = []
    for i, s in enumerate(sources[:5], 1):
        text = (s.get("text") or "").strip()
        if not text:
            continue
        snippet = " ".join(text.split())[:800]
        src_lines.append(f"[{i}] {s.get('label', 'Source')} ({s.get('url', '')})\n{snippet}")
    
    if not src_lines:
        return None
    
    prompt = f"Question: {question}\n\nSources:\n{chr(10).join(src_lines)}\n\nAnswer based ONLY on these sources. Be detailed and cite sources like [1]."
    
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that answers using only the provided sources."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=500
        )
        return response["choices"][0]["message"]["content"]
    except Exception as e:
        logger.error(f"OpenAI error: {e}")
        return None

def detect_principles(sources: List[Dict[str, Any]]) -> Dict[str, Any]:
    def norm(s): return (s or "").lower().replace("’", "'")
    
    PRINCIPLES = {
        "k'é (kinship / relational responsibility)": ["k'e", "k’é", "kinship", "clan", "relative", "relationship"],
        "hózhó (balance / harmony)": ["hozho", "hózhó", "harmony", "balance", "beauty"],
        "community responsibility": ["community", "responsibility", "respect", "kindness", "generosity", "cooperation"],
        "matrilineal / matrilocal": ["matrilineal", "matrilocal", "descent", "mother", "maternal"],
    }
    
    found = {}
    for s in sources:
        text = norm(s.get("text", ""))
        for pname, kws in PRINCIPLES.items():
            hits = sum(text.count(norm(k)) for k in kws)
            if hits > 0:
                if pname not in found:
                    found[pname] = {"hits": 0, "evidence": []}
                found[pname]["hits"] += hits
    return dict(sorted(found.items(), key=lambda x: x[1]["hits"], reverse=True))

def generate_summary(source: Dict[str, Any], question: str) -> str:
    text = source.get('text', '')
    if not text:
        return "No content available."
    
    paragraphs = [p for p in text.split('\n\n') if len(p) > 100 and not re.search(r'plate\s+\d+|fig\.\s+\d+|page\s+\d+', p.lower())]
    
    # Find relevant paragraphs
    keywords = [w for w in question.lower().split() if len(w) > 3 and w not in {'the','what','how','why','does','tell'}]
    scored = [(sum(p.lower().count(k) for k in keywords), p) for p in paragraphs]
    scored.sort(reverse=True)
    
    summary = "\n\n".join([p for _, p in scored[:3]])
    return summary if summary else paragraphs[0][:500] if paragraphs else "Information found in sources."

def extract_excerpt(source: Dict[str, Any], question: str) -> str:
    text = source.get('text', '')
    if not text:
        return "No excerpt available."
    
    sentences = re.split(r'[.!?]+', text)
    keywords = [w for w in question.lower().split() if len(w) > 3]
    
    scored = [(sum(k in s.lower() for k in keywords), s.strip()) for s in sentences if len(s.strip()) > 40]
    if scored:
        scored.sort(reverse=True)
        return scored[0][1] + "."
    
    for s in sentences:
        if len(s.strip()) > 50:
            return s.strip() + "..."
    return "See sources for more information."

def print_fallback_answer(question: str, sources: List[Dict[str, Any]]) -> str:
    output = []
    
    if not sources:
        return "I couldn't find any relevant sources about that topic. Please try rephrasing your question."
    
    primary = sources[0]
    summary = generate_summary(primary, question)
    excerpt = extract_excerpt(primary, question)
    
    output.append(f'<div style="line-height: 1.6;">')
    output.append(f'<p><strong>📖 Summary:</strong></p>')
    output.append(f'<p>{summary}</p>')
    output.append(f'<hr style="margin: 15px 0;">')
    output.append(f'<p><strong>📝 Key Excerpt:</strong></p>')
    output.append(f'<p style="background: #f5f5f5; padding: 12px; border-left: 3px solid #2c5f2d; font-style: italic;">"{excerpt}"</p>')
    output.append(f'<p><strong>📚 Sources:</strong></p>')
    output.append(f'<ul>')
    for i, s in enumerate(sources[:3], 1):
        url = s.get('url', 'Unknown')
        trust_badge = get_trust_badge(s.get('trust', 0.5))
        display_url = url.replace('local:', '📄 ') if url.startswith('local:') else url
        output.append(f'<li style="margin-bottom: 8px;">[{i}] {display_url} {trust_badge}</li>')
    output.append(f'</ul>')
    output.append(f'</div>')
    
    return '\n'.join(output)

# Enhanced HTML template with all features
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Diné Cultural Learning Bot</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', Arial, sans-serif;
            background: linear-gradient(135deg, #f5f7fa 0%, #e9ecef 100%);
            min-height: 100vh;
            padding: 20px;
            transition: background 0.3s, color 0.3s;
        }
        body.dark-mode {
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            color: #eee;
        }
        .container {
            max-width: 900px;
            margin: 0 auto;
            background: white;
            border-radius: 20px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.1);
            overflow: hidden;
            transition: background 0.3s;
        }
        body.dark-mode .container {
            background: #1e2a3a;
        }
        .header {
            background: linear-gradient(135deg, #2c5f2d 0%, #1e3a1e 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }
        .header h1 { font-size: 2em; margin-bottom: 8px; }
        .header p { opacity: 0.9; font-size: 1.1em; }
        .theme-toggle {
            position: fixed;
            top: 30px;
            right: 30px;
            background: rgba(44, 95, 45, 0.9);
            border: none;
            font-size: 24px;
            cursor: pointer;
            padding: 10px 15px;
            border-radius: 50px;
            backdrop-filter: blur(10px);
            box-shadow: 0 2px 10px rgba(0,0,0,0.2);
            transition: transform 0.2s;
            z-index: 1000;
        }
        .theme-toggle:hover { transform: scale(1.05); }
        .content { padding: 30px; }
        .protocol-box {
            background: #fdf2e9;
            border-left: 4px solid #d35400;
            padding: 15px;
            border-radius: 10px;
            margin-bottom: 25px;
            font-size: 14px;
        }
        body.dark-mode .protocol-box {
            background: #2d2a1e;
            border-left-color: #e67e22;
        }
        .welcome-box {
            background: #e8f5e9;
            padding: 20px;
            border-radius: 12px;
            margin-bottom: 25px;
        }
        body.dark-mode .welcome-box {
            background: #1e3a2f;
        }
        .example-buttons {
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
            margin-top: 15px;
        }
        .example-btn {
            background: white;
            border: 1px solid #2c5f2d;
            color: #2c5f2d;
            padding: 8px 16px;
            border-radius: 25px;
            cursor: pointer;
            font-size: 13px;
            transition: all 0.3s;
        }
        .example-btn:hover {
            background: #2c5f2d;
            color: white;
            transform: translateY(-2px);
        }
        body.dark-mode .example-btn {
            background: #2c5f2d;
            color: white;
            border-color: #4cae4c;
        }
        textarea {
            width: 100%;
            padding: 15px;
            border: 2px solid #e0e0e0;
            border-radius: 12px;
            font-size: 16px;
            font-family: inherit;
            resize: vertical;
            transition: border-color 0.3s;
        }
        textarea:focus {
            outline: none;
            border-color: #2c5f2d;
        }
        body.dark-mode textarea {
            background: #2d3e2d;
            color: white;
            border-color: #4cae4c;
        }
        button.submit-btn {
            background: #2c5f2d;
            color: white;
            border: none;
            padding: 12px 30px;
            border-radius:
