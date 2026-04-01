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

# Did You Know facts (new addition)
DID_YOU_KNOW_FACTS = [
    "The Navajo language was used as a code during WWII by the famous Code Talkers - it was never broken!",
    "K'é (kinship) extends beyond blood relations to include all of creation.",
    "Hózhó is often translated as 'beauty' but encompasses harmony, balance, and wellness.",
    "Traditional Navajo hogans are built with the door facing east to greet the morning sun.",
    "The four sacred mountains mark the boundaries of traditional Dinétah (Navajo homeland).",
    "Weaving was taught to the Navajo by Spider Woman, a holy being.",
    "The Navajo Nation is the largest Native American reservation in the United States.",
    "In Diné tradition, the number four is sacred - representing the four directions.",
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
            logger.info("OpenAI initialized")
    except:
        pass

# PDF Support Check
try:
    import PyPDF2
    PDF_SUPPORT = True
except ImportError:
    PyPDF2 = None
    PDF_SUPPORT = False

# ----------------------------
# Configure allowlist - ORIGINAL WORKING DOMAINS
# ----------------------------
ALLOWED_DOMAINS = [
    # Official Navajo Nation / Diné Government
    "navajo-nsn.gov",
    "courts.navajo-nsn.gov",
    "navajocourts.org",
    "navajochapters.org",
    "nnwo.org",
    "navajopeople.org",
    "navajo.org",
    # Diné Education & Language
    "dinecollege.edu",
    "navajolanguageacademy.org",
    "roughrock.k12.az.us",
    "nau.edu",
    "navajotech.edu",
    "unm.edu",
    # Diné Media
    "navajotimes.com",
    "navajocodetalkers.org",
    "discovernavajo.com",
    "navajohopiobserver.com",
    "dineta.com",
    # Indigenous Journalism
    "ictnews.org",
    "indiancountrytoday.com",
    "nativeamericannews.net",
    "ncai.org",
    # Museums & Academic
    "americanindian.si.edu",
    "loc.gov",
    "pbs.org",
    "smithsonianmag.com",
    # Academic Presses
    "unmpress.com",
    "upcolorado.com",
    "uapress.arizona.edu",
    "jstor.org",
    # Cultural Sites
    "navajoculture.org",
    "traditionalnavajoteachings.org",
]

# Domain trust scores
DOMAIN_TRUST = {
    "navajo-nsn.gov": 1.00,
    "courts.navajo-nsn.gov": 1.00,
    "navajocourts.org": 1.00,
    "nnwo.org": 0.95,
    "dinecollege.edu": 0.95,
    "navajolanguageacademy.org": 0.92,
    "navajotimes.com": 0.85,
    "ictnews.org": 0.82,
    "indiancountrytoday.com": 0.82,
    "americanindian.si.edu": 0.80,
    "loc.gov": 0.80,
}

USER_AGENT = "Mozilla/5.0 (iPhone; CPU iPhone OS like Mac OS X) AppleWebKit/605.1.15"

# Document search configuration
DOCUMENTS_FOLDER = "/home/tony-cullen/dine_documents"

def load_documents_from_folder():
    """Load all text files from the documents folder."""
    documents = []
    if not os.path.exists(DOCUMENTS_FOLDER):
        os.makedirs(DOCUMENTS_FOLDER)
        return documents
    
    import glob
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
    """Search through local documents for relevant content."""
    if not documents:
        return []
    
    question_lower = question.lower()
    keywords = [k for k in question_lower.split() if len(k) > 3 and k not in {'the','a','an','is','at','which','on','and','or','to','in','for'}]
    
    results = []
    for doc in documents:
        text_lower = doc['text'].lower()
        score = sum(text_lower.count(k) for k in keywords)
        
        # Special boosts for specific topics
        if "black god" in question_lower and ("black god" in text_lower or "haashch" in text_lower):
            score += 50
        if "stars" in question_lower and ("star" in text_lower or "constellation" in text_lower):
            score += 30
            
        if score > 10:
            doc_copy = doc.copy()
            doc_copy['relevance'] = score
            results.append(doc_copy)
    
    results.sort(key=lambda x: x.get('relevance', 0), reverse=True)
    return results[:5]

class TextExtractor(HTMLParser):
    """Extract text content from HTML."""
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
    """Fetch URL content."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="ignore")
    except Exception as e:
        logger.error(f"Error fetching {url}: {e}")
        return ""

def domain_of(url: str) -> str:
    try:
        return urllib.parse.urlparse(url).netloc.lower().lstrip("www.")
    except:
        return ""

def is_allowed(url: str) -> bool:
    d = domain_of(url)
    return any(d == ad or d.endswith("." + ad) for ad in ALLOWED_DOMAINS)

def trust_for_url(url: str):
    host = domain_of(url)
    for d, score in DOMAIN_TRUST.items():
        if host == d or host.endswith("." + d):
            return score
    return 0.50

def ddg_search(query: str, max_results: int = 8) -> List[str]:
    """Search DuckDuckGo and return list of result URLs."""
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
    """Gather sources from local documents AND allowed domains."""
    sources = []
    
    # Search local documents
    documents = load_documents_from_folder()
    doc_sources = search_documents(question, documents)
    if doc_sources:
        sources.extend(doc_sources)
    
    # Search the web
    clean_q = question.replace("“", '"').replace("”", '"').replace("’", "'").replace("‘", "'").strip()
    topic = clean_q.lower()
    
    # Build search query based on question type
    kinship_terms = ["grandmother", "grandfather", "mother", "father", "aunt", "uncle", "sister", "brother", "clan", "family", "relative"]
    story_terms = ["coyote", "black god", "holy people", "ceremony", "creation", "monster slayer", "stars", "sky", "constellation"]
    
    if any(word in topic for word in kinship_terms):
        search_query = f"{clean_q} Diné Navajo kinship term family relationship"
    elif any(word in topic for word in story_terms):
        search_query = f"{clean_q} Diné Navajo teaching story holy people meaning"
    else:
        search_query = f"{clean_q} Navajo Diné culture"
    
    urls = ddg_search(search_query, max_results=12)
    allowed_urls = [u for u in urls if is_allowed(u)]
    allowed_urls = allowed_urls[:max_pages]
    
    for u in allowed_urls:
        trust = trust_for_url(u)
        try:
            html = fetch_url(u, timeout=15)
            if not html:
                continue
            
            parser = TextExtractor()
            parser.feed(html)
            full_text = parser.get_text()
            
            # Extract relevant paragraphs
            paragraphs = [p.strip() for p in full_text.split("\n") if p.strip()]
            priority_terms = ["navajo", "diné", "dine", "black god", "haashch", "star", "creation", "holy people"]
            
            relevant_parts = []
            for p in paragraphs:
                p_low = p.lower()
                if any(term in p_low for term in priority_terms):
                    relevant_parts.append(p)
            
            text = "\n\n".join(relevant_parts)[:12000] if relevant_parts else full_text[:12000]
            
            sources.append({
                "url": u,
                "domain": domain_of(u),
                "trust": trust,
                "text": text,
            })
        except Exception as e:
            logger.error(f"Error processing {u}: {e}")
            continue
    
    sources.sort(key=lambda s: s.get("trust", 0), reverse=True)
    return sources

def generate_fallback_answer(question: str, sources: List[Dict[str, Any]]) -> str:
    """Generate formatted answer from sources."""
    if not sources:
        return """
        <div style="line-height: 1.6;">
            <p><strong>📖 I couldn't find any relevant sources.</strong></p>
            <p>Please try rephrasing your question or ask about topics like:</p>
            <ul>
                <li>Who is Black God?</li>
                <li>How were the stars created?</li>
                <li>What is k'é?</li>
                <li>Tell me about Navajo clans</li>
                <li>What is the Long Walk?</li>
            </ul>
        </div>
        """
    
    # Get the best source
    primary = sources[0]
    text = primary.get('text', '')
    
    if not text or len(text) < 50:
        return "I found a source but couldn't extract enough text. Please try a different question."
    
    # Clean up the text
    text = re.sub(r'\s+', ' ', text)  # Normalize whitespace
    text = text.strip()
    
    # Split into sentences for better formatting
    sentences = re.split(r'(?<=[.!?])\s+', text)
    
    # Find relevant sentences based on question
    q_lower = question.lower()
    keywords = [w for w in q_lower.split() if len(w) > 3 and w not in {'the','what','how','why','does','tell','about'}]
    
    # Special keyword boosts
    if "star" in q_lower:
        keywords.extend(["star", "stars", "constellation", "sky", "heavens", "creation"])
    if "black god" in q_lower:
        keywords.extend(["black god", "haashch", "fire god", "darkness"])
    
    # Score each sentence
    scored_sentences = []
    for sentence in sentences:
        if len(sentence) < 30:
            continue
        s_lower = sentence.lower()
        score = sum(s_lower.count(k) for k in keywords)
        if score > 0:
            scored_sentences.append((score, sentence))
    
    scored_sentences.sort(reverse=True)
    
    # Build a clean answer
    answer_parts = []
    answer_parts.append('<div style="line-height: 1.6;">')
    
    # Add introduction based on question
    if "star" in q_lower:
        answer_parts.append('<p><strong>✨ The Diné Creation Story of the Stars:</strong></p>')
        answer_parts.append('<p>According to Diné (Navajo) tradition, the stars were placed in the sky by the Holy People during the creation of the Fifth World. Below is an excerpt from traditional teachings:</p>')
    elif "black god" in q_lower:
        answer_parts.append('<p><strong>⭐ Who is Black God (Haashchʼééshzhiní)?</strong></p>')
        answer_parts.append('<p>Black God is a powerful Holy Person in Diné cosmology who played a crucial role in placing the stars in the sky. According to tradition:</p>')
    else:
        answer_parts.append(f'<p><strong>📖 Answer about: {question}</strong></p>')
    
    answer_parts.append('<hr>')
    
    # Add the best relevant sentences with context
    if scored_sentences:
        # Take top 3-5 relevant sentences
        for i in range(min(5, len(scored_sentences))):
            sentence = scored_sentences[i][1].strip()
            # Clean up the sentence
            sentence = re.sub(r'\.\.\.+', '...', sentence)
            answer_parts.append(f'<p>{sentence}</p>')
    else:
        # Fallback to first few substantial sentences
        count = 0
        for sent in sentences:
            if len(sent) > 60 and count < 4:
                answer_parts.append(f'<p>{sent.strip()}</p>')
                count += 1
    
    answer_parts.append('<hr>')
    
    # Add source information
    source_url = primary.get('url', 'Unknown')
    trust_score = primary.get('trust', 0.5)
    trust_badge = ''
    if trust_score >= 0.95:
        trust_badge = '<span style="background: #2ecc71; color: white; padding: 2px 8px; border-radius: 12px; font-size: 11px;">✓ Verified Source</span>'
    elif trust_score >= 0.80:
        trust_badge = '<span style="background: #3498db; color: white; padding: 2px 8px; border-radius: 12px; font-size: 11px;">📚 Trusted Source</span>'
    
    answer_parts.append(f'<p><strong>Source:</strong> <a href="{source_url}" target="_blank">{source_url}</a> {trust_badge}</p>')
    
    # Add cultural note
    answer_parts.append('<p style="font-size: 12px; color: #666; margin-top: 15px;"><em>Note: Traditional Diné stories are passed down orally through generations. This excerpt comes from published educational sources. For deeper understanding, consult with Diné cultural knowledge holders.</em></p>')
    
    answer_parts.append('</div>')
    
    return '\n'.join(answer_parts)

# HTML Template with loading spinner and example buttons
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
                    <textarea 
                        name="question" 
                        placeholder="Example: Who is Black God? How were the stars created? What is k'é? Tell me about the Long Walk..." 
                        id="questionInput"
                        rows="4"
                    >{{ question }}</textarea>
                    <div>
                        <button type="submit" class="submit-btn" id="submitBtn">🔍 Ask Question</button>
                        <div id="loadingIndicator" style="display: none;" class="loading-container">
                            <span class="loading-spinner"></span>
                            <span class="searching-message">Searching Diné sources...</span>
                        </div>
                    </div>
                </form>
            </div>
            
            <div class="divider">
                <span>OR TRY ONE OF THESE</span>
            </div>
            
            <div class="suggestions-section">
                <div class="suggestions-title">💡 POPULAR QUESTIONS TO EXPLORE</div>
                <div class="example-buttons">
                    <button class="example-btn" data-question="Who is Black God?">⭐ Who is Black God?</button>
                    <button class="example-btn" data-question="How were the stars created?">✨ How were the stars created?</button>
                    <button class="example-btn" data-question="What is k'é?">🤝 What is k'é?</button>
                    <button class="example-btn" data-question="Tell me about Navajo clans">👨‍👩‍👧‍👦 Tell me about Navajo clans</button>
                    <button class="example-btn" data-question="What does hózhó mean?">☯️ What does hózhó mean?</button>
                    <button class="example-btn" data-question="Tell me about the Long Walk">👣 Tell me about the Long Walk</button>
                    <button class="example-btn" data-question="Who were the Navajo Code Talkers?">📡 Who were the Navajo Code Talkers?</button>
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
            🌄 Learning about Diné culture | Sources: Educational resources, cultural organizations, and Diné teachings<br>
            For deeper learning, consult with Diné elders and cultural knowledge holders.
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
    logger.error(f"Error: {e}")
    return "An error occurred. Please try again.", 500

@app.route('/', methods=['GET', 'POST'])
def home():
    question = ""
    answer = ""
    random_fact = random.choice(DID_YOU_KNOW_FACTS)
    
    if request.method == 'POST':
        question = request.form.get('question', '').strip()
        
        if question:
            try:
                # Seasonal check for animal questions (winter months)
                current_month = datetime.now().month
                animal_keywords = ["bear", "coyote", "wolf", "snake", "owl", "eagle"]
                
                if current_month in [11, 12, 1, 2, 3] and any(k in question.lower() for k in animal_keywords):
                    answer = """
                        <div style="line-height: 1.6;">
                            <p><strong>🍂 Seasonal Teaching Protocol</strong></p>
                            <p>During winter months (November-March), traditional Diné teachings advise against discussing certain animals. This is a time for reflection and other types of storytelling.</p>
                            <p>I'd be happy to tell you about other aspects of Diné culture! Try asking about k'é (kinship), the clan system, or hózhó (harmony).</p>
                        </div>
                    """
                else:
                    # Gather sources and generate answer
                    sources = []
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
                        answer = generate_fallback_answer(question, sources)
                        
            except Exception as e:
                logger.error(f"Error: {e}")
                answer = "I encountered an issue. Please try asking your question in a different way."
    
    return render_template_string(HTML_TEMPLATE, question=question, answer=answer, random_fact=random_fact)

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)
