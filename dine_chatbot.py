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
import random
import os
import glob
from flask import Flask, request, render_template_string

# Create Flask app
app = Flask(__name__)

# Did You Know facts
DID_YOU_KNOW_FACTS = [
    "The Navajo language was used as a code during WWII by the famous Code Talkers - it was never broken!",
    "K'é (kinship) extends beyond blood relations to include all of creation.",
    "Hózhó is often translated as 'beauty' but encompasses harmony, balance, and wellness.",
    "Traditional Navajo hogans are built with the door facing east to greet the morning sun.",
    "The four sacred mountains mark the boundaries of traditional Dinétah (Navajo homeland).",
    "Weaving was taught to the Navajo by Spider Woman, a holy being.",
    "Coyote (Ma'ii) is an important trickster figure in Diné stories.",
]

# ----------------------------
# LOCAL DOCUMENTS FOLDER
# ----------------------------
def find_documents_folder():
    possible_paths = [
        os.path.join(os.path.dirname(__file__), "dine_documents"),
        os.path.join(os.getcwd(), "dine_documents"),
        "/opt/render/project/src/dine_documents",
        "/app/dine_documents",
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            print(f"✅ Found documents at: {path}")
            return path
    
    fallback_path = os.path.join(os.getcwd(), "dine_documents")
    os.makedirs(fallback_path, exist_ok=True)
    print(f"📁 Created documents folder at: {fallback_path}")
    return fallback_path

DOCUMENTS_FOLDER = find_documents_folder()

def load_local_documents():
    documents = []
    
    if not os.path.exists(DOCUMENTS_FOLDER):
        print(f"❌ Folder not found: {DOCUMENTS_FOLDER}")
        return documents
    
    txt_files = glob.glob(os.path.join(DOCUMENTS_FOLDER, "*.txt"))
    print(f"📂 Found {len(txt_files)} local text files")
    
    for file_path in txt_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            filename = os.path.basename(file_path)
            documents.append({
                "url": f"local:{filename}",
                "domain": "local-documents",
                "tier": "document",
                "trust": 1.00,
                "label": filename.replace('.txt', ''),
                "text": content,
                "source_type": "local"
            })
            print(f"   ✅ Loaded local: {filename} ({len(content)} chars)")
        except Exception as e:
            print(f"   ❌ Error loading {file_path}: {e}")
    
    return documents

# ----------------------------
# COMPLETE ALLOWED DOMAINS - FULL 39 DOMAINS
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

TRUSTED_MEDIA = []
ALLOWED_EXACT_URLS = {m["url"] for m in TRUSTED_MEDIA}

# --- Domain Trust Scores (complete) ---
DOMAIN_TRUST = {
    # Official Navajo Nation / Diné Government
    "navajo-nsn.gov": ("official", 1.00),
    "courts.navajo-nsn.gov": ("official", 1.00),
    "navajocourts.org": ("official", 1.00),
    "navajochapters.org": ("official", 0.95),
    "nnwo.org": ("official", 0.95),
    "navajopeople.org": ("official", 0.95),
    "navajo.org": ("official", 0.95),

    # Diné Education / Language
    "dinecollege.edu": ("education", 0.95),
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

    # Indigenous-led journalism
    "ictnews.org": ("indigenous_media", 0.82),
    "indiancountrytoday.com": ("indigenous_media", 0.82),
    "nativeamericannews.net": ("indigenous_media", 0.75),
    "ncai.org": ("indigenous_org", 0.80),

    # Museums / archives
    "americanindian.si.edu": ("museum", 0.80),
    "loc.gov": ("archive", 0.80),
    "pbs.org": ("public_media", 0.75),
    "smithsonianmag.com": ("museum_media", 0.70),
    
    # University Presses
    "unmpress.com": ("academic", 0.85),
    "upcolorado.com": ("academic", 0.85),
    "uapress.arizona.edu": ("academic", 0.85),
    
    # Academic resources
    "jstor.org": ("academic", 0.80),
    "anthrosource.onlinelibrary.wiley.com": ("academic", 0.80),
    "ehillerman.unm.edu": ("academic", 0.80),
    
    # Cultural sites
    "navajoculture.org": ("cultural", 0.80),
    "traditionalnavajoteachings.org": ("cultural", 0.80),
}

# --- Seasonal teaching mode ---
SEASONAL_MODE = True
HIBERNATION_MONTHS = {11, 12, 1, 2, 3}
ANIMAL_KEYWORDS = ["animal", "bear", "coyote", "wolf", "fox", "deer", "elk", "moose", "snake"]

def is_hibernation_season(today: date | None = None) -> bool:
    today = today or datetime.now().date()
    return today.month in HIBERNATION_MONTHS

def mentions_animals(text: str) -> bool:
    return any(k in text.lower() for k in ANIMAL_KEYWORDS)

USER_AGENT = "Mozilla/5.0 (iPhone; CPU iPhone OS like Mac OS X) AppleWebKit/605.1.15"

# ----------------------------
# HTML -> Text extractor
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
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="ignore")
    except Exception as e:
        print(f"Error fetching {url}: {e}")
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

def trust_for_url(url: str) -> tuple:
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
        "official": "Navajo Nation (Official)",
        "education": "Diné Education",
        "dine_media": "Diné Media",
        "dine_org": "Diné Organization",
        "tourism": "Tourism / Information",
        "indigenous_media": "Indigenous Journalism",
        "indigenous_org": "Indigenous Organization",
        "museum": "Museum / Institution",
        "archive": "Archive",
        "public_media": "Public Media",
        "museum_media": "Museum Media",
        "academic": "Academic Press",
        "cultural": "Cultural Resource",
        "document": "Local Document",
    }
    return tier_labels.get(tier, domain)

# ----------------------------
# DuckDuckGo HTML search
# ----------------------------
def ddg_search(query: str, max_results: int = 8):
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

# ----------------------------
# Gather ALL sources (LOCAL + WEB)
# ----------------------------
def gather_all_sources(question: str, max_pages: int = 6):
    all_sources = []
    
    # STEP 1: Search local documents
    print("\n📚 Searching local documents...")
    local_docs = load_local_documents()
    
    question_lower = question.lower()
    
    for doc in local_docs:
        text_lower = doc['text'].lower()
        filename = doc['label'].lower()
        score = 0
        
        # Check what the question is about
        is_coyote_question = "coyote" in question_lower
        is_hero_question = "hero" in question_lower or "twin" in question_lower
        is_blackgod_question = "black god" in question_lower
        
        # COYOTE QUESTION - prioritize folklore files
        if is_coyote_question:
            # Boost for files that are ABOUT Coyote stories
            if "american_indian" in filename or "folklore" in filename or "fairy_tales" in filename:
                score += 5000
                print(f"   🦊 COYOTE STORY FILE: {doc['label']} (+5000)")
            
            # Count how many times "coyote" appears in the text
            coyote_count = text_lower.count("coyote")
            if coyote_count > 0:
                score += coyote_count * 200
                print(f"   📖 Found 'coyote' {coyote_count} times in {doc['label']}")
            
            # Penalize black_god file for Coyote questions (it only mentions Coyote briefly)
            if "black_god" in filename:
                score -= 1000
                print(f"   ⚠️ Penalizing black_god file for Coyote question (-1000)")
        
        # HERO QUESTION
        elif is_hero_question:
            if "hero_twins" in filename:
                score += 10000
            score += text_lower.count("hero") * 100
            score += text_lower.count("twin") * 100
        
        # BLACK GOD QUESTION
        elif is_blackgod_question:
            if "black_god" in filename:
                score += 10000
            score += text_lower.count("black god") * 200
        
        # General question - search for keywords
        else:
            words = [w for w in question_lower.split() if len(w) > 3]
            for word in words:
                score += text_lower.count(word) * 10
        
        if score > 10:
            doc['relevance'] = score
            all_sources.append(doc)
            print(f"   ✅ Match: {doc['label']} (score: {score})")
    
    # STEP 2: Search the web
    print("\n🌐 Searching web sources...")
    clean_q = question.strip()
    search_query = f"{clean_q} Navajo Diné"
    
    urls = ddg_search(search_query, max_results=8)
    allowed_urls = [u for u in urls if is_allowed(u)]
    allowed_urls = allowed_urls[:max_pages]
    
    for u in allowed_urls:
        tier, score = trust_for_url(u)
        try:
            html = fetch_url(u, timeout=15)
            if not html:
                continue
            parser = TextExtractor()
            parser.feed(html)
            text = parser.get_text()
            
            if text and len(text) > 200:
                all_sources.append({
                    "url": u,
                    "domain": domain_of(u),
                    "tier": tier,
                    "trust": score,
                    "label": label_for_source(domain_of(u), tier),
                    "text": text[:8000],
                    "source_type": "web"
                })
                print(f"   ✅ Web source: {domain_of(u)}")
        except Exception as e:
            print(f"   ❌ Error: {e}")
            continue
    
    # Sort by score/relevance
    all_sources.sort(key=lambda s: s.get("relevance", s.get("trust", 0)), reverse=True)
    return all_sources

# ----------------------------
# Detect principles
# ----------------------------
def detect_principles(sources):
    def norm(s):
        return (s or "").lower().replace("’", "'")
    
    PRINCIPLES = {
        "k'é (kinship)": ["k'e", "k’é", "kinship", "clan", "relative"],
        "hózhó (harmony)": ["hozho", "hózhó", "harmony", "balance"],
        "community responsibility": ["community", "responsibility", "respect", "kindness"],
    }
    
    found = {}
    for s in sources:
        text = norm(s.get("text", ""))
        if not text:
            continue
        for pname, kws in PRINCIPLES.items():
            hits = sum(text.count(k) for k in kws)
            if hits > 0:
                if pname not in found:
                    found[pname] = {"hits": 0}
                found[pname]["hits"] += hits
    return found

# ----------------------------
# Generate answer from sources - SIMPLIFIED TO AVOID CRASHES
# ----------------------------
def generate_answer(question: str, sources):
    if not sources:
        return "<p>No sources found. Please try a different question.</p>"
    
    output = []
    output.append(f'<p><strong>📖 Question:</strong> {question}</p>')
    output.append('<hr>')
    
    # Separate sources
    local_sources = [s for s in sources if s.get('source_type') == 'local']
    web_sources = [s for s in sources if s.get('source_type') != 'local']
    
    # For Coyote questions, prioritize folklore files
    is_coyote = "coyote" in question.lower()
    if is_coyote:
        # Reorder local sources to put folklore files first
        local_sources.sort(key=lambda s: (
            0 if "american_indian" in s['label'].lower() or "folklore" in s['label'].lower() else 1,
            -s.get('relevance', 0)
        ))
    
    if local_sources:
        output.append('<p><strong>📚 Local Documents Found:</strong></p><ul>')
        for s in local_sources[:3]:
            output.append(f'<li><strong>{s["label"]}</strong> (Local)</li>')
        output.append('</ul>')
    
    if web_sources:
        output.append('<p><strong>🌐 Web Sources Found:</strong></p><ul>')
        for s in web_sources[:3]:
            output.append(f'<li><strong>{s["label"]}</strong>: <a href="{s["url"]}" target="_blank">{s["url"]}</a></li>')
        output.append('</ul>')
    
    output.append('<hr>')
    
    # Show content from best source
    best = sources[0]
    text = best.get('text', '')
    best_label = best.get('label', 'Source')
    
    # For Coyote, try to find the specific file with Coyote stories
    if is_coyote:
        for s in local_sources:
            if "american_indian" in s['label'].lower() or "folklore" in s['label'].lower():
                best = s
                text = s.get('text', '')
                best_label = s.get('label', 'Source')
                break
    
    if text:
        # Clean up text
        lines = text.split('\n')
        clean_lines = []
        start_collecting = False
        coyote_lines = []
        
        for line in lines:
            line_lower = line.lower()
            
            # For Coyote, specifically look for paragraphs with "coyote"
            if is_coyote and "coyote" in line_lower:
                coyote_lines.append(line.strip())
            
            # General content collection
            if not start_collecting:
                if any(word in line_lower for word in ['coyote', 'story', 'legend', 'tale', 'once', 'long ago', 'myth']):
                    start_collecting = True
            
            if start_collecting:
                if 'gutenberg' in line_lower or 'copyright' in line_lower:
                    break
                if len(line.strip()) > 40:
                    if line not in clean_lines:
                        clean_lines.append(line.strip())
        
        # Use coyote-specific lines if found
        if is_coyote and coyote_lines:
            content = ' '.join(coyote_lines[:4])
            if len(content) > 1000:
                content = content[:1000] + '...'
            output.append(f'<p><strong>📖 Information from {best_label}:</strong></p>')
            output.append(f'<blockquote style="background:#f9f9f9;padding:12px;border-left:3px solid #2c5f2d;">{content}</blockquote>')
        elif clean_lines:
            content = ' '.join(clean_lines[:5])
            if len(content) > 800:
                content = content[:800] + '...'
            output.append(f'<p><strong>📖 Information from {best_label}:</strong></p>')
            output.append(f'<blockquote style="background:#f9f9f9;padding:12px;border-left:3px solid #2c5f2d;">{content}</blockquote>')
    
    return '\n'.join(output)

# ----------------------------
# HTML Template
# ----------------------------
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Diné Cultural Learning Bot</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        .container {
            max-width: 900px;
            margin: 0 auto;
            background: white;
            border-radius: 20px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            overflow: hidden;
        }
        .header {
            background: linear-gradient(135deg, #2c5f2d 0%, #1e3a1e 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }
        .header h1 { font-size: 2em; margin-bottom: 10px; }
        .content { padding: 30px; }
        .protocol-box {
            background: #fef3c7;
            border-left: 4px solid #f59e0b;
            padding: 15px;
            border-radius: 10px;
            margin-bottom: 20px;
            font-size: 14px;
        }
        textarea {
            width: 100%;
            padding: 15px;
            border: 2px solid #e0e0e0;
            border-radius: 12px;
            font-size: 16px;
            font-family: inherit;
            resize: vertical;
        }
        textarea:focus { outline: none; border-color: #2c5f2d; }
        .submit-btn {
            background: #2c5f2d;
            color: white;
            border: none;
            padding: 12px 30px;
            border-radius: 25px;
            font-size: 16px;
            cursor: pointer;
            margin-top: 15px;
        }
        .submit-btn:hover:not(:disabled) { background: #1e3a1e; }
        .submit-btn:disabled { background: #95a5a6; cursor: not-allowed; }
        .example-buttons {
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
            margin: 20px 0;
        }
        .example-btn {
            background: white;
            border: 1px solid #2c5f2d;
            color: #2c5f2d;
            padding: 8px 16px;
            border-radius: 25px;
            cursor: pointer;
            font-size: 13px;
        }
        .example-btn:hover { background: #2c5f2d; color: white; }
        .loading-spinner {
            display: inline-block;
            width: 20px;
            height: 20px;
            border: 3px solid #f3f3f3;
            border-top: 3px solid #2c5f2d;
            border-radius: 50%;
            animation: spin 1s linear infinite;
            margin-right: 8px;
            vertical-align: middle;
        }
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        .answer {
            background: #f9f9f9;
            padding: 25px;
            border-radius: 12px;
            margin-top: 20px;
            border-left: 4px solid #2c5f2d;
        }
        .answer blockquote { margin: 10px 0; padding: 10px; background: #f0f0f0; border-left: 3px solid #2c5f2d; }
        .fact-box {
            background: #fff3e0;
            padding: 15px;
            border-radius: 10px;
            margin-top: 20px;
            font-size: 14px;
        }
        .footer {
            background: #f5f5f5;
            padding: 20px;
            text-align: center;
            color: #666;
            font-size: 12px;
        }
        hr { margin: 15px 0; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🌾 Diné Cultural Learning Bot</h1>
            <p>Ask any question about Navajo traditions, language, and values</p>
        </div>
        <div class="content">
            <div class="protocol-box">
                🌄 <strong>Cultural Note:</strong> Some Diné traditions contain sacred knowledge not shared publicly.
            </div>
            
            <form method="POST" id="questionForm">
                <textarea name="question" placeholder="Example: Who are the Hero Twins? Who is Coyote? What is k'é?" rows="4">{{ question }}</textarea>
                <div>
                    <button type="submit" class="submit-btn" id="submitBtn">🔍 Ask Question</button>
                    <div id="loadingIndicator" style="display: none; margin-left: 15px;">
                        <span class="loading-spinner"></span> Searching...
                    </div>
                </div>
            </form>
            
            <div class="example-buttons">
                <button class="example-btn" data-question="Who are the Hero Twins?">🏹 Hero Twins</button>
                <button class="example-btn" data-question="Who is Black God?">⭐ Black God</button>
                <button class="example-btn" data-question="Who is Coyote?">🦊 Coyote</button>
                <button class="example-btn" data-question="What is k'é?">🤝 What is k'é?</button>
            </div>
            
            {% if answer %}
            <div class="answer">
                {{ answer | safe }}
            </div>
            {% endif %}
            
            <div class="fact-box">
                💡 <strong>Did You Know?</strong><br>
                {{ random_fact }}
            </div>
        </div>
        <div class="footer">
            🌄 Searching {{ doc_count }} local documents + {{ domain_count }} trusted web sources
        </div>
    </div>
    <script>
        document.querySelectorAll('.example-btn').forEach(btn => {
            btn.addEventListener('click', function() {
                document.getElementById('questionInput').value = this.dataset.question;
                document.getElementById('submitBtn').disabled = true;
                document.getElementById('loadingIndicator').style.display = 'inline-block';
                document.getElementById('questionForm').submit();
            });
        });
        document.getElementById('questionForm').addEventListener('submit', function() {
            document.getElementById('submitBtn').disabled = true;
            document.getElementById('loadingIndicator').style.display = 'inline-block';
        });
    </script>
</body>
</html>
"""

# ----------------------------
# Flask Routes
# ----------------------------
@app.errorhandler(Exception)
def handle_exception(e):
    print(f"Error: {e}")
    return f"An error occurred: {str(e)}. Please try again.", 500

@app.route('/', methods=['GET', 'POST'])
def home():
    question = ""
    answer = ""
    random_fact = random.choice(DID_YOU_KNOW_FACTS)
    local_docs = load_local_documents()
    
    if request.method == 'POST':
        question = request.form.get('question', '').strip()
        
        if question:
            try:
                if SEASONAL_MODE and is_hibernation_season() and mentions_animals(question):
                    answer = "<p>During winter months, traditional Diné teachings advise against discussing certain animals.</p>"
                else:
                    print(f"\nQUESTION: {question}")
                    
                    sources_result = []
                    def gather():
                        sources_result.append(gather_all_sources(question))
                    
                    thread = threading.Thread(target=gather)
                    thread.start()
                    thread.join(timeout=30)
                    
                    if thread.is_alive():
                        answer = "Search is taking longer than expected. Please try again."
                    else:
                        sources = sources_result[0] if sources_result else []
                        answer = generate_answer(question, sources)
                        
            except Exception as e:
                print(f"Error: {e}")
                answer = f"Error: {str(e)}"
    
    return render_template_string(HTML_TEMPLATE, 
                                   question=question, 
                                   answer=answer, 
                                   random_fact=random_fact,
                                   doc_count=len(local_docs),
                                   domain_count=len(ALLOWED_DOMAINS))

if __name__ == "__main__":
    print(f"\nStarting Diné Cultural Learning Bot...")
    print(f"Documents folder: {DOCUMENTS_FOLDER}")
    print(f"Allowed domains: {len(ALLOWED_DOMAINS)}")
    app.run(host='0.0.0.0', port=5000, debug=True)
