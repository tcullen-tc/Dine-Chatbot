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

# Did You Know facts (just for UI)
DID_YOU_KNOW_FACTS = [
    "The Navajo language was used as a code during WWII by the famous Code Talkers - it was never broken!",
    "K'é (kinship) extends beyond blood relations to include all of creation.",
    "Hózhó is often translated as 'beauty' but encompasses harmony, balance, and wellness.",
]

# ----------------------------
# 1) Configure your allowlist - YOUR ORIGINAL
# ----------------------------
ALLOWED_DOMAINS = [
    "navajo-nsn.gov", "courts.navajo-nsn.gov", "navajocourts.org",
    "navajochapters.org", "nnwo.org", "navajopeople.org", "dinecollege.edu",
    "navajolanguageacademy.org", "roughrock.k12.az.us", "navajotimes.com",
    "navajocodetalkers.org", "discovernavajo.com", "ictnews.org",
    "indiancountrytoday.com", "nativeamericannews.net", "americanindian.si.edu",
    "loc.gov", "pbs.org", "smithsonianmag.com",
]

TRUSTED_MEDIA = [
    {"title": "Diné Teaching Video", "url": "https://youtu.be/waCH87_-Adk", "source": "YouTube"},
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
    return any(k in text.lower() for k in ANIMAL_KEYWORDS)

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

USER_AGENT = "Mozilla/5.0 (iPhone; CPU iPhone OS like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile Safari/604.1"

# ----------------------------
# 2) HTML -> Text extractor
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
        "museum": "Museum / Institution",
        "archive": "Archive",
        "public_media": "Public Media",
    }
    return tier_labels.get(tier, domain)

# ----------------------------
# 3) DuckDuckGo HTML search
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
# 4) Gather Diné-only sources (YOUR ORIGINAL FUNCTION)
# ----------------------------
def gather_sources(question: str, max_pages: int = 6):
    clean_q = question.replace("“", '"').replace("”", '"').replace("’", "'").replace("‘", "'").strip()
    topic = clean_q.strip()
    if len(topic) < 12:
        topic = f"{topic} Diné Navajo"
    search_query = f"{topic} meaning Diné Navajo culture kinship hózhó"
    
    urls = ddg_search(search_query, max_results=12)
    allowed_urls = [u for u in urls if is_allowed(u)]
    
    if not allowed_urls:
        urls = []
        for d in sorted(ALLOWED_DOMAINS):
            q = f"site:{d} {clean_q}"
            urls.extend(ddg_search(q, max_results=8))
        allowed_urls = [u for u in urls if is_allowed(u)]
    
    allowed_urls = allowed_urls[:max_pages]
    trusted_urls = list(ALLOWED_EXACT_URLS)
    
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
    
    sources.sort(key=lambda s: s.get("trust", 0), reverse=True)
    return sources

# ----------------------------
# 5) Detect principles (YOUR ORIGINAL)
# ----------------------------
def detect_principles(sources):
    def norm(s):
        return (s or "").lower().replace("’", "'")
    
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
                for k in kws:
                    k2 = norm(k)
                    idx = text.find(k2)
                    if idx != -1:
                        start = max(0, idx - 120)
                        end = min(len(text), idx + 240)
                        snippet = text[start:end].strip()
                        if snippet and snippet not in found[pname]["evidence"]:
                            found[pname]["evidence"].append(snippet)
                        break
    return found

# ----------------------------
# 6) Generate answer from sources (YOUR ORIGINAL LOGIC - converted to return string)
# ----------------------------
def generate_answer(question: str, sources):
    """Generate answer from sources - YOUR ORIGINAL print_fallback_answer converted"""
    if not sources:
        return """
        <div style="line-height: 1.6;">
            <p><strong>📖 No sources found.</strong></p>
            <p>I couldn't retrieve any sources from the allowed domains.</p>
            <p>Try asking about:</p>
            <ul>
                <li>What is k'é?</li>
                <li>Who are the Hero Twins?</li>
                <li>What does hózhó mean?</li>
            </ul>
        </div>
        """
    
    principles = detect_principles(sources)
    
    output = []
    output.append('<div style="line-height: 1.6;">')
    output.append(f'<p><strong>📖 Question:</strong> {question}</p>')
    output.append('<hr>')
    
    # Show sources
    output.append('<p><strong>📚 Sources found:</strong></p>')
    output.append('<ul>')
    for i, s in enumerate(sources[:5], 1):
        url = s.get('url', 'Unknown')
        output.append(f'<li><a href="{url}" target="_blank">{url}</a></li>')
    output.append('</ul>')
    output.append('<hr>')
    
    # Show content from the best source
    best_source = sources[0]
    text = best_source.get('text', '')
    if text:
        # Extract relevant paragraphs
        paragraphs = [p for p in text.split('\n\n') if len(p) > 100]
        if paragraphs:
            output.append('<p><strong>📖 Information from sources:</strong></p>')
            for p in paragraphs[:3]:
                clean_p = re.sub(r'\s+', ' ', p)
                if len(clean_p) > 600:
                    clean_p = clean_p[:600] + "..."
                output.append(f'<blockquote style="background: #f9f9f9; padding: 12px; border-left: 3px solid #2c5f2d; margin: 10px 0;">{clean_p}</blockquote>')
    
    # Show principles if detected
    if principles:
        output.append('<hr>')
        output.append('<p><strong>🏔️ Cultural Principles Detected:</strong></p>')
        output.append('<ul>')
        for p, data in principles.items():
            output.append(f'<li><strong>{p}</strong> - {data["hits"]} occurrences</li>')
        output.append('</ul>')
    
    output.append('</div>')
    return '\n'.join(output)

# ----------------------------
# 7) HTML Template
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
        .example-btn:hover { background: #2c5f2d; color: white; transform: translateY(-2px); }
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
        .answer-header:before { content: "📖"; margin-right: 10px; }
        .answer {
            background: #f9f9f9;
            padding: 25px;
            border-radius: 0 0 12px 12px;
            border-left: 4px solid #2c5f2d;
            line-height: 1.6;
        }
        .answer p { margin-bottom: 12px; }
        .answer ul, .answer ol { margin-left: 25px; margin-bottom: 12px; }
        .answer li { margin-bottom: 6px; }
        .answer blockquote { margin: 10px 0; padding: 10px; background: #f0f0f0; border-left: 3px solid #2c5f2d; }
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
            <p>Ask any question about Navajo traditions, language, and values</p>
        </div>
        <div class="content">
            <div class="protocol-box">
                🌄 <strong>Cultural Note:</strong> Some Diné traditions contain sacred knowledge not shared publicly. 
                This chatbot provides general cultural information from published educational sources.
            </div>
            
            <div class="ask-section">
                <div class="ask-label">✍️ Ask Your Own Question</div>
                <form method="POST" id="questionForm">
                    <textarea name="question" placeholder="Example: Who are the Hero Twins? What is k'é? Tell me about Coyote..." rows="4">{{ question }}</textarea>
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
                    <button class="example-btn" data-question="Who are the Hero Twins?">🏹 Hero Twins</button>
                    <button class="example-btn" data-question="Who is Black God?">⭐ Black God</button>
                    <button class="example-btn" data-question="Tell me about Coyote">🦊 Coyote</button>
                    <button class="example-btn" data-question="What is k'é?">🤝 What is k'é?</button>
                    <button class="example-btn" data-question="What does hózhó mean?">☯️ Hózhó</button>
                    <button class="example-btn" data-question="What is the Long Walk?">👣 The Long Walk</button>
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
            🌄 Searching trusted Diné sources: Navajo Nation sites, Diné College, Navajo Times, ICT News, and more
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

# ----------------------------
# 8) Flask Routes
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
    
    if request.method == 'POST':
        question = request.form.get('question', '').strip()
        
        if question:
            try:
                if SEASONAL_MODE and is_hibernation_season() and mentions_animals(question):
                    answer = """
                        <div style="line-height: 1.6;">
                            <p><strong>🍂 Seasonal Teaching Protocol</strong></p>
                            <p>During winter months (November-March), traditional Diné teachings advise against discussing certain animals. Please ask about other aspects of Diné culture.</p>
                        </div>
                    """
                else:
                    print(f"\n{'='*60}")
                    print(f"Searching for: {question}")
                    print(f"{'='*60}")
                    
                    sources_result = []
                    def gather():
                        sources_result.append(gather_sources(question))
                    
                    thread = threading.Thread(target=gather)
                    thread.start()
                    thread.join(timeout=30)
                    
                    if thread.is_alive():
                        answer = "Search is taking longer than expected. Please try a more specific question."
                    else:
                        sources = sources_result[0] if sources_result else []
                        print(f"Found {len(sources)} sources")
                        answer = generate_answer(question, sources)
                        
            except Exception as e:
                print(f"Error: {e}")
                answer = f"I encountered an issue: {str(e)}. Please try again."
    
    return render_template_string(HTML_TEMPLATE, question=question, answer=answer, random_fact=random_fact)

if __name__ == "__main__":
    print(f"\n{'='*60}")
    print("Diné Cultural Learning Bot Starting...")
    print("Searching trusted Diné sources online")
    print(f"{'='*60}\n")
    app.run(host='0.0.0.0', port=5000, debug=True)
