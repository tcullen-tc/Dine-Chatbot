import re
import sys
import time
import json
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from datetime import datetime, date
from typing import List, Dict, Any, Optional, Tuple, Set
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
    "Black God (Haashchʼééshzhiní) placed the stars in the sky, but Coyote scattered them randomly.",
    "The Hero Twins Monster Slayer and Born for Water rid the world of monsters using their father the Sun's weapons.",
]

# ----------------------------
# DOCUMENTS FOLDER - YOUR LOCAL TEXT FILES
# ----------------------------
DOCUMENTS_FOLDER = "/home/tony-cullen/dine_documents"

def load_documents_from_folder():
    """Load all text files from the documents folder"""
    documents = []
    
    if not os.path.exists(DOCUMENTS_FOLDER):
        os.makedirs(DOCUMENTS_FOLDER)
        print(f"📁 Created folder: {DOCUMENTS_FOLDER}")
        return documents
    
    txt_files = glob.glob(os.path.join(DOCUMENTS_FOLDER, "*.txt"))
    print(f"Found {len(txt_files)} text files in {DOCUMENTS_FOLDER}")
    
    for file_path in txt_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            filename = os.path.basename(file_path)
            
            # Set trust based on filename
            trust = 0.98
            if 'hero' in filename.lower() or 'twin' in filename.lower():
                trust = 1.00
            if 'black_god' in filename.lower():
                trust = 1.00
            
            documents.append({
                "url": f"local:{filename}",
                "domain": "local-documents",
                "tier": "document",
                "trust": trust,
                "label": filename.replace('.txt', ''),
                "text": content
            })
            print(f"✅ Loaded: {filename} ({len(content)} chars)")
        except Exception as e:
            print(f"Error loading {file_path}: {e}")
    
    return documents

def search_documents(question, documents):
    """Search through local documents for relevant content - FIXED VERSION"""
    if not documents:
        return []
    
    question_lower = question.lower()
    print(f"\n🔍 Searching documents for: '{question_lower}'")
    
    # Remove common words
    stop_words = {'the', 'a', 'an', 'is', 'at', 'which', 'on', 'and', 'or', 'to', 'in', 'for', 
                  'who', 'what', 'where', 'when', 'why', 'how', 'are', 'were', 'was', 'be', 'by',
                  'of', 'from', 'with', 'without', 'about', 'tell', 'me', 'please', 'can', 'you',
                  'does', 'do', 'did', 'have', 'has', 'had', 'been', 'being', 'would', 'could', 'should'}
    
    keywords = [k for k in question_lower.split() if k not in stop_words and len(k) > 2]
    
    # Add related terms based on question topic
    if "hero" in question_lower or "twin" in question_lower or "monster" in question_lower:
        keywords.extend(["hero twin", "hero twins", "monster slayer", "born for water", 
                        "naayéé", "neizghání", "twin", "twins", "monster", "yé'iitsoh"])
    if "black god" in question_lower:
        keywords.extend(["black god", "haashch", "fire god", "haashch'ééshzhiní", "stars", "nightway"])
    if "star" in question_lower:
        keywords.extend(["star", "stars", "constellation", "pleiades", "sky", "coyote", "ma'ii"])
    if "weav" in question_lower:
        keywords.extend(["weav", "weaver", "weaving", "blanket", "rug", "loom", "spider woman"])
    if "k'é" in question_lower or "k'e" in question_lower:
        keywords.extend(["k'é", "k'e", "kinship", "clan", "family", "relative"])
    
    print(f"   Keywords: {keywords}")
    
    results = []
    for doc in documents:
        text_lower = doc['text'].lower()
        filename = doc.get('label', '').lower()
        score = 0
        
        # Boost for filename matches
        for kw in keywords:
            if kw in filename:
                score += 50
                print(f"   📁 Filename match: '{kw}' in {filename}")
        
        # Count keyword matches in content
        for keyword in keywords:
            count = text_lower.count(keyword)
            if count > 0:
                score += count * 5
        
        # SPECIAL BOOST for exact file matches
        if "hero" in question_lower and "hero_twins" in filename:
            score += 500
            print(f"   ⭐ SPECIAL BOOST: hero_twins file matched (+500)")
        if "black god" in question_lower and "black_god" in filename:
            score += 500
            print(f"   ⭐ SPECIAL BOOST: black_god file matched (+500)")
        
        # Check for story content
        if "hero" in question_lower and ("monster slayer" in text_lower or "yé'iitsoh" in text_lower):
            score += 200
            print(f"   📖 Found Hero Twins story content (+200)")
        if "black god" in question_lower and ("haashch" in text_lower or "nightway" in text_lower):
            score += 200
            print(f"   🌟 Found Black God story content (+200)")
        
        if score > 10:
            doc_copy = doc.copy()
            doc_copy['relevance'] = score
            results.append(doc_copy)
            print(f"   ✅ MATCH: {filename} (score: {score})")
    
    # Sort by relevance
    results.sort(key=lambda x: x.get('relevance', 0), reverse=True)
    print(f"\n📊 Found {len(results)} matching documents\n")
    return results[:5]

# ----------------------------
# 1) Configure your allowlist
# ----------------------------
ALLOWED_DOMAINS = [
    "navajo-nsn.gov",
    "courts.navajo-nsn.gov",
    "navajocourts.org",
    "navajochapters.org",
    "nnwo.org",
    "navajopeople.org",
    "dinecollege.edu",
    "navajolanguageacademy.org",
    "roughrock.k12.az.us",
    "navajotimes.com",
    "navajocodetalkers.org",
    "discovernavajo.com",
    "ictnews.org",
    "indiancountrytoday.com",
    "nativeamericannews.net",
    "americanindian.si.edu",
    "loc.gov",
    "pbs.org",
    "smithsonianmag.com",
    "navajoculture.org",
]

TRUSTED_MEDIA = [
    {"title": "Diné Teaching Video", "url": "https://youtu.be/waCH87_-Adk", "source": "YouTube"},
    {"title": "Diné Cultural Teaching", "url": "https://vimeo.com/749026655", "source": "Vimeo"}
]
ALLOWED_EXACT_URLS = {m["url"] for m in TRUSTED_MEDIA}

# --- Seasonal teaching mode ---
SEASONAL_MODE = True
HIBERNATION_MONTHS = {11, 12, 1, 2, 3}
ANIMAL_KEYWORDS = ["animal", "bear", "coyote", "wolf", "fox", "deer", "elk", "moose", "snake"]

def is_hibernation_season(today: date | None = None) -> bool:
    today = today or datetime.now().date()
    return today.month in HIBERNATION_MONTHS

def mentions_animals(text: str) -> bool:
    t = (text or "").lower()
    return any(k in t for k in ANIMAL_KEYWORDS)

# --- Trust tiers ---
DOMAIN_TRUST = {
    "navajo-nsn.gov": ("official", 1.00),
    "courts.navajo-nsn.gov": ("official", 1.00),
    "navajocourts.org": ("official", 1.00),
    "nnwo.org": ("official", 0.95),
    "dinecollege.edu": ("education", 0.95),
    "navajolanguageacademy.org": ("education", 0.92),
    "roughrock.k12.az.us": ("education", 0.88),
    "navajotimes.com": ("dine_media", 0.85),
    "navajocodetalkers.org": ("dine_org", 0.88),
    "discovernavajo.com": ("tourism", 0.75),
    "ictnews.org": ("indigenous_media", 0.82),
    "indiancountrytoday.com": ("indigenous_media", 0.82),
    "nativeamericannews.net": ("indigenous_media", 0.75),
    "americanindian.si.edu": ("museum", 0.80),
    "loc.gov": ("archive", 0.80),
    "pbs.org": ("public_media", 0.75),
    "smithsonianmag.com": ("museum_media", 0.70),
}

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

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
    except Exception:
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
        "museum": "Museum / Institution",
        "archive": "Archive",
        "public_media": "Public Media",
        "document": "Local Document"
    }
    return tier_labels.get(tier, domain)

def ddg_search(query: str, max_results: int = 5):
    try:
        q = urllib.parse.quote_plus(query)
        url = f"https://html.duckduckgo.com/html/?q={q}"
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
    except Exception as e:
        print(f"Search error: {e}")
        return []

def gather_sources(question: str, max_pages: int = 3):
    """Gather sources from local documents AND web"""
    sources = []
    
    # STEP 1: Search local documents
    print("📚 Searching local documents...")
    documents = load_documents_from_folder()
    doc_sources = search_documents(question, documents)
    
    if doc_sources:
        print(f"✅ Found {len(doc_sources)} relevant documents")
        sources.extend(doc_sources)
    else:
        print("📖 No relevant documents found")
    
    # STEP 2: Search the web (limited since local docs should answer most questions)
    print("🌐 Searching online sources...")
    clean_q = question.strip()
    
    search_queries = [
        f"{clean_q} Navajo",
    ]
    
    all_urls = []
    for search_query in search_queries:
        urls = ddg_search(search_query, max_results=3)
        all_urls.extend(urls)
    
    allowed_urls = [u for u in all_urls if is_allowed(u)]
    allowed_urls = list(dict.fromkeys(allowed_urls))
    allowed_urls = allowed_urls[:max_pages]
    
    print(f"Found {len(allowed_urls)} web sources")
    
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
                sources.append({
                    "url": u,
                    "domain": domain_of(u),
                    "tier": tier,
                    "trust": score,
                    "label": label_for_source(domain_of(u), tier),
                    "text": text[:4000],
                })
        except Exception as e:
            print(f"Error processing {u}: {e}")
            continue
    
    sources.sort(key=lambda s: s.get("trust", 0), reverse=True)
    return sources

def generate_answer(question: str, sources):
    """Generate answer showing actual source content"""
    output = []
    output.append('<div style="line-height: 1.6;">')
    
    if not sources:
        output.append("<p><strong>📖 No sources found.</strong></p>")
        output.append("<p>I couldn't find any sources for your question.</p>")
        output.append("</div>")
        return '\n'.join(output)
    
    output.append(f'<p><strong>📖 Question:</strong> {question}</p>')
    output.append(f'<p><strong>📚 Found {len(sources)} source(s):</strong></p>')
    output.append('<hr>')
    
    for i, s in enumerate(sources, start=1):
        text = s.get('text', '')
        url = s.get('url', 'Unknown')
        label = s.get('label', 'Source')
        trust_score = s.get('trust', 0.5)
        
        trust_badge = ''
        if trust_score >= 0.95:
            trust_badge = '<span style="background: #2ecc71; color: white; padding: 2px 8px; border-radius: 12px; font-size: 11px; margin-left: 8px;">✓ Verified</span>'
        elif trust_score >= 0.80:
            trust_badge = '<span style="background: #3498db; color: white; padding: 2px 8px; border-radius: 12px; font-size: 11px; margin-left: 8px;">📚 Trusted</span>'
        
        if url.startswith('local:'):
            display_url = f"📄 Local: {label}"
        else:
            display_url = url
        
        output.append(f'<p><strong>Source {i}: {label}</strong> {trust_badge}<br>')
        if url.startswith('local:'):
            output.append(f'<span style="color: #2c5f2d;">{display_url}</span></p>')
        else:
            output.append(f'<a href="{url}" target="_blank" style="color: #2c5f2d;">{display_url}</a></p>')
        
        if text and len(text) > 100:
            # Split into paragraphs and show relevant ones
            paragraphs = text.split('\n')
            relevant_paragraphs = []
            
            question_lower = question.lower()
            keywords = [w for w in question_lower.split() if len(w) > 3]
            
            for para in paragraphs:
                para = para.strip()
                if len(para) > 80:
                    para_lower = para.lower()
                    if any(k in para_lower for k in keywords):
                        relevant_paragraphs.append(para)
            
            if not relevant_paragraphs:
                # Take first few substantial paragraphs
                for para in paragraphs:
                    if len(para) > 100:
                        relevant_paragraphs.append(para)
                        if len(relevant_paragraphs) >= 3:
                            break
            
            for para in relevant_paragraphs[:4]:
                clean_para = re.sub(r'\s+', ' ', para)
                if len(clean_para) > 600:
                    clean_para = clean_para[:600] + "..."
                output.append(f'<blockquote style="background: #f9f9f9; padding: 12px; border-left: 3px solid #2c5f2d; margin: 10px 0;">{clean_para}</blockquote>')
        else:
            output.append('<p><em>No readable text extracted.</em></p>')
        
        if i < len(sources):
            output.append('<hr>')
    
    output.append('</div>')
    return '\n'.join(output)

# HTML Template (condensed for brevity - same as before)
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
        .header p { opacity: 0.9; font-size: 1.1em; }
        .content { padding: 30px; }
        .protocol-box {
            background: #fef3c7;
            border-left: 4px solid #f59e0b;
            padding: 15px;
            border-radius: 10px;
            margin-bottom: 20px;
            font-size: 14px;
        }
        .ask-section { margin-bottom: 25px; }
        .ask-label {
            font-size: 18px;
            font-weight: 600;
            color: #2c5f2d;
            margin-bottom: 10px;
            display: block;
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
            font-weight: 500;
        }
        .submit-btn:hover:not(:disabled) { background: #1e3a1e; transform: translateY(-2px); }
        .submit-btn:disabled { background: #95a5a6; cursor: not-allowed; }
        .suggestions-section {
            background: #e8f5e9;
            padding: 20px;
            border-radius: 12px;
            margin-bottom: 25px;
        }
        .suggestions-title {
            font-weight: 600;
            color: #2c5f2d;
            margin-bottom: 12px;
            font-size: 14px;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        .example-buttons {
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
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
        .divider {
            text-align: center;
            margin: 20px 0;
            position: relative;
        }
        .divider:before {
            content: "";
            position: absolute;
            top: 50%;
            left: 0;
            right: 0;
            height: 1px;
            background: #e0e0e0;
        }
        .divider span {
            background: white;
            padding: 0 15px;
            position: relative;
            color: #999;
            font-size: 12px;
        }
        .loading-container {
            display: inline-block;
            margin-left: 15px;
            vertical-align: middle;
        }
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
        .searching-message {
            display: inline-block;
            color: #2c5f2d;
            font-style: italic;
            vertical-align: middle;
        }
        .answer-section {
            margin-top: 30px;
            margin-bottom: 20px;
        }
        .answer-header {
            background: #2c5f2d;
            color: white;
            padding: 12px 20px;
            border-radius: 12px 12px 0 0;
            font-weight: bold;
            font-size: 18px;
        }
        .answer-header:before {
            content: "📖";
            margin-right: 10px;
        }
        .answer {
            background: #f9f9f9;
            padding: 25px;
            border-radius: 0 0 12px 12px;
            border-left: 4px solid #2c5f2d;
            border-right: 1px solid #e0e0e0;
            border-bottom: 1px solid #e0e0e0;
            line-height: 1.6;
        }
        .answer p { margin-bottom: 12px; }
        .answer ul, .answer ol { margin-left: 25px; margin-bottom: 12px; }
        .answer li { margin-bottom: 6px; }
        .answer blockquote { margin: 10px 0; }
        .fact-box {
            background: #fff3e0;
            padding: 15px;
            border-radius: 10px;
            margin-top: 20px;
            font-size: 14px;
            border-left: 4px solid #f59e0b;
        }
        .footer {
            background: #f5f5f5;
            padding: 20px;
            text-align: center;
            color: #666;
            font-size: 12px;
        }
        hr { margin: 20px 0; }
        @media (max-width: 600px) {
            .content { padding: 20px; }
            .example-btn { font-size: 11px; padding: 6px 12px; }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🌾 Diné Cultural Learning Bot</h1>
            <p>Ask questions about Navajo traditions, language, and values</p>
        </div>
        <div class="content">
            <div class="protocol-box">
                🌄 <strong>Cultural Note:</strong> Some Diné traditions contain sacred knowledge not shared publicly. 
                This chatbot provides general cultural information from published educational sources.
            </div>
            <div class="ask-section">
                <div class="ask-label">✍️ Ask Your Own Question</div>
                <form method="POST" id="questionForm">
                    <textarea name="question" placeholder="Example: What is k'é? Who are the Hero Twins? What does hózhó mean?" id="questionInput" rows="4">{{ question }}</textarea>
                    <div>
                        <button type="submit" class="submit-btn" id="submitBtn">🔍 Ask Question</button>
                        <div id="loadingIndicator" style="display: none;" class="loading-container">
                            <span class="loading-spinner"></span>
                            <span class="searching-message">Searching Diné sources...</span>
                        </div>
                    </div>
                </form>
            </div>
            <div class="divider"><span>OR TRY ONE OF THESE</span></div>
            <div class="suggestions-section">
                <div class="suggestions-title">💡 POPULAR QUESTIONS TO EXPLORE</div>
                <div class="example-buttons">
                    <button class="example-btn" data-question="What is k'é?">🤝 What is k'é?</button>
                    <button class="example-btn" data-question="Tell me about Navajo clans">👨‍👩‍👧‍👦 Tell me about Navajo clans</button>
                    <button class="example-btn" data-question="What does hózhó mean?">☯️ What does hózhó mean?</button>
                    <button class="example-btn" data-question="Who are the Hero Twins?">🏹 Who are the Hero Twins?</button>
                    <button class="example-btn" data-question="Who is Black God?">⭐ Who is Black God?</button>
                    <button class="example-btn" data-question="What is the Long Walk?">👣 What is the Long Walk?</button>
                </div>
            </div>
            {% if answer %}
            <div class="answer-section" id="answerSection">
                <div class="answer-header">Your Answer</div>
                <div class="answer" id="answerContent">{{ answer | safe }}</div>
            </div>
            {% endif %}
            <div class="fact-box">
                💡 <strong>Did You Know?</strong><br>
                {{ random_fact }}
            </div>
        </div>
        <div class="footer">
            🌄 Learning about Diné culture | Sources: Local documents and trusted educational resources
        </div>
    </div>
    <script>
        document.querySelectorAll('.example-btn').forEach(btn => {
            btn.addEventListener('click', function() {
                document.getElementById('questionInput').value = this.dataset.question;
                document.getElementById('submitBtn').disabled = true;
                document.getElementById('submitBtn').textContent = 'Searching...';
                document.getElementById('loadingIndicator').style.display = 'inline-block';
                document.getElementById('questionForm').submit();
            });
        });
        document.getElementById('questionForm').addEventListener('submit', function() {
            if (!document.getElementById('questionInput').value.trim()) {
                alert('Please enter a question');
                event.preventDefault();
                return false;
            }
            document.getElementById('submitBtn').disabled = true;
            document.getElementById('submitBtn').textContent = 'Searching...';
            document.getElementById('loadingIndicator').style.display = 'inline-block';
        });
        window.addEventListener('load', function() {
            const submitBtn = document.getElementById('submitBtn');
            const loadingIndicator = document.getElementById('loadingIndicator');
            const answerSection = document.getElementById('answerSection');
            if (submitBtn && loadingIndicator) {
                submitBtn.disabled = false;
                submitBtn.textContent = '🔍 Ask Question';
                loadingIndicator.style.display = 'none';
            }
            if (answerSection) {
                answerSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
            }
        });
    </script>
</body>
</html>
"""

@app.errorhandler(Exception)
def handle_exception(e):
    print(f"Error: {e}")
    return f"An error occurred: {str(e)}. Please try again.", 500

@app.route('/', methods=['GET', 'POST'])
def home():
    question = ""
    answer = ""
    random_fact = random.choice(DID_YOU_KNOW_FACTS)
    
    if request.method == 'POST':
        question = request.form.get('question', '').strip()
        
        if question:
            try:
                if SEASONAL_MODE and is_hibernation_season() and mentions_animals(question):
                    answer = '<div style="line-height: 1.6;"><p><strong>🍂 Seasonal Teaching Protocol</strong></p><p>During winter months (November-March), traditional Diné teachings advise against discussing certain animals.</p></div>'
                else:
                    print(f"\n{'='*50}")
                    print(f"Processing question: {question}")
                    print(f"{'='*50}")
                    
                    sources_result = []
                    def gather():
                        sources_result.append(gather_sources(question))
                    
                    thread = threading.Thread(target=gather)
                    thread.start()
                    thread.join(timeout=25)
                    
                    if thread.is_alive():
                        answer = "Search is taking longer than expected. Please try a more specific question."
                    else:
                        sources = sources_result[0] if sources_result else []
                        print(f"\nTotal sources found: {len(sources)}")
                        answer = generate_answer(question, sources)
                        
            except Exception as e:
                print(f"Error: {e}")
                answer = f"I encountered an issue: {str(e)}. Please try again."
    
    return render_template_string(HTML_TEMPLATE, question=question, answer=answer, random_fact=random_fact)

if __name__ == "__main__":
    print(f"\n{'='*50}")
    print("Diné Cultural Learning Bot Starting...")
    print(f"Documents folder: {DOCUMENTS_FOLDER}")
    print(f"{'='*50}\n")
    app.run(host='0.0.0.0', port=5000, debug=True)
