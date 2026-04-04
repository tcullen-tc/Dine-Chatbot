import re
import os
import glob
import random
import urllib.parse
import urllib.request
from html.parser import HTMLParser
import threading
from flask import Flask, request, render_template_string

app = Flask(__name__)

DID_YOU_KNOW_FACTS = [
    "The Navajo language was used as a code during WWII by the famous Code Talkers - it was never broken!",
    "K'é (kinship) extends beyond blood relations to include all of creation.",
    "Hózhó is often translated as 'beauty' but encompasses harmony, balance, and wellness.",
]

# ----------------------------
# APPROVED DINÉ DOMAINS
# ----------------------------
APPROVED_DOMAINS = [
    "navajo-nsn.gov", "courts.navajo-nsn.gov", "navajocourts.org",
    "navajochapters.org", "nnwo.org", "navajopeople.org", "navajo.org",
    "dinecollege.edu", "navajolanguageacademy.org", "roughrock.k12.az.us",
    "nau.edu", "navajotech.edu", "unm.edu", "navajotimes.com",
    "navajocodetalkers.org", "discovernavajo.com", "navajohopiobserver.com",
    "dineta.com", "ictnews.org", "indiancountrytoday.com", "nativeamericannews.net",
    "ncai.org", "americanindian.si.edu", "loc.gov", "pbs.org", "smithsonianmag.com",
    "unmpress.com", "upcolorado.com", "uapress.arizona.edu", "jstor.org",
    "ehillerman.unm.edu", "navajoculture.org", "traditionalnavajoteachings.org",
]

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

# ----------------------------
# LOCAL DOCUMENTS FOLDER
# ----------------------------
DOCUMENTS_FOLDER = os.path.join(os.path.dirname(__file__), "dine_documents")

def load_all_documents():
    docs = []
    if not os.path.exists(DOCUMENTS_FOLDER):
        os.makedirs(DOCUMENTS_FOLDER)
        return docs
    
    for file_path in glob.glob(os.path.join(DOCUMENTS_FOLDER, "*.txt")):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            docs.append({
                "name": os.path.basename(file_path).replace('.txt', ''),
                "content": content
            })
            print(f"✅ Loaded: {os.path.basename(file_path)}")
        except Exception as e:
            print(f"❌ Error: {e}")
    return docs

ALL_DOCS = load_all_documents()

# ----------------------------
# HTML PARSER FOR WEB CONTENT
# ----------------------------
class TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.text = []
        self.skip = False

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style'):
            self.skip = True

    def handle_endtag(self, tag):
        if tag in ('script', 'style'):
            self.skip = False
        if tag in ('p', 'br', 'div', 'h1', 'h2', 'h3'):
            self.text.append('\n')

    def handle_data(self, data):
        if not self.skip and data.strip():
            self.text.append(data.strip())

    def get_text(self):
        return ' '.join(self.text)

def fetch_url(url):
    try:
        req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
        with urllib.request.urlopen(req, timeout=15) as response:
            return response.read().decode('utf-8', errors='ignore')
    except:
        return ""

def domain_of(url):
    try:
        return urllib.parse.urlparse(url).netloc.lower().replace('www.', '')
    except:
        return ""

def is_approved_domain(url):
    domain = domain_of(url)
    return any(domain.endswith(d) for d in APPROVED_DOMAINS)

def search_web(question):
    try:
        q = urllib.parse.quote_plus(question)
        url = f"https://html.duckduckgo.com/html/?q={q}"
        html = fetch_url(url)
        if not html:
            return []
        
        links = re.findall(r'<a[^>]+href="([^"]+)"[^>]*>', html)
        results = []
        for link in links:
            if 'uddg=' in link:
                match = re.search(r'uddg=([^&]+)', link)
                if match:
                    link = urllib.parse.unquote(match.group(1))
            if link.startswith('http') and is_approved_domain(link):
                content = fetch_url(link)
                if content:
                    parser = TextExtractor()
                    parser.feed(content)
                    text = parser.get_text()
                    if text and len(text) > 200:
                        results.append({
                            "title": domain_of(link),
                            "url": link,
                            "content": text
                        })
            if len(results) >= 3:
                break
        return results
    except:
        return []

# ----------------------------
# SIMPLE SEARCH - Find the most relevant document
# ----------------------------
def find_best_answer(question):
    """Simple search - returns the best matching document content"""
    question_lower = question.lower()
    
    # Extract keywords (remove common words)
    stop_words = {'what', 'who', 'how', 'why', 'when', 'where', 'is', 'are', 'was', 'were',
                  'the', 'a', 'an', 'and', 'or', 'but', 'for', 'nor', 'so', 'yet', 'of',
                  'to', 'in', 'for', 'on', 'by', 'with', 'without', 'about', 'tell', 'me'}
    
    words = question_lower.split()
    keywords = [w for w in words if w not in stop_words and len(w) > 2]
    
    # Also add 2-word phrases
    phrases = []
    for i in range(len(words) - 1):
        phrase = f"{words[i]} {words[i+1]}"
        if len(phrase) > 5:
            phrases.append(phrase)
    
    all_keywords = list(set(keywords + phrases))
    print(f"🔍 Keywords: {all_keywords[:8]}")
    
    # Score all local documents
    scored = []
    for doc in ALL_DOCS:
        content_lower = doc['content'].lower()
        score = 0
        for kw in all_keywords:
            score += content_lower.count(kw) * 10
        if score > 0:
            scored.append({
                "score": score,
                "title": doc['name'],
                "content": doc['content'],
                "type": "local"
            })
    
    # Search web if no local results
    if not scored:
        web_results = search_web(question)
        for r in web_results:
            scored.append({
                "score": 50,
                "title": r['title'],
                "content": r['content'],
                "type": "web",
                "url": r['url']
            })
    
    if not scored:
        return None
    
    # Sort by score
    scored.sort(key=lambda x: x['score'], reverse=True)
    best = scored[0]
    
    # Extract the first few paragraphs
    content = best['content']
    # Remove excessive whitespace
    content = re.sub(r'\s+', ' ', content)
    
    # Take first 1000 characters
    if len(content) > 1000:
        content = content[:1000] + "..."
    
    return {
        "text": content,
        "source": best['title'],
        "type": best['type'],
        "url": best.get('url')
    }

# ----------------------------
# HTML TEMPLATE
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
        .answer blockquote {
            margin: 10px 0;
            padding: 15px;
            background: #f0f0f0;
            border-left: 3px solid #2c5f2d;
            font-size: 16px;
            line-height: 1.6;
        }
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
        hr { margin: 15px 0; }
        .badge {
            display: inline-block;
            background: #2c5f2d;
            color: white;
            font-size: 10px;
            padding: 2px 8px;
            border-radius: 12px;
            margin-left: 8px;
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
                🌄 <strong>Cultural Note:</strong> Answers are from approved Diné cultural sources.
                <span class="badge">{{ domain_count }} approved domains</span>
                <span class="badge">{{ doc_count }} local documents</span>
            </div>
            
            <form method="POST" id="questionForm">
                <textarea name="question" placeholder="Example: Who are the Hero Twins? Who is Black God? What is k'é?" rows="4">{{ question }}</textarea>
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
                <button class="example-btn" data-question="What is the Long Walk?">👣 Long Walk</button>
            </div>
            
            {% if answer %}
            <div class="answer">
                <blockquote>{{ answer.text | safe }}</blockquote>
                <p><strong>📚 Source:</strong> 
                {% if answer.type == 'local' %}
                    📄 {{ answer.source }} (Local Document)
                {% else %}
                    🌐 <a href="{{ answer.url }}" target="_blank">{{ answer.source }}</a>
                {% endif %}
                </p>
            </div>
            {% endif %}
            
            <div class="fact-box">
                💡 <strong>Did You Know?</strong><br>
                {{ random_fact }}
            </div>
        </div>
        <div class="footer">
            🔒 Search restricted to {{ domain_count }} approved Diné cultural domains + {{ doc_count }} local documents
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

@app.route('/', methods=['GET', 'POST'])
def home():
    question = ""
    answer = None
    random_fact = random.choice(DID_YOU_KNOW_FACTS)
    
    if request.method == 'POST':
        question = request.form.get('question', '').strip()
        
        if question:
            print(f"\n{'='*50}")
            print(f"📖 QUESTION: {question}")
            print(f"{'='*50}")
            
            answer = find_best_answer(question)
            
            if not answer:
                answer = {
                    "text": f"No information found about '{question}' in approved Diné sources. Try asking about Hero Twins, Black God, Coyote, or k'é.",
                    "source": "None",
                    "type": "local"
                }
    
    return render_template_string(HTML_TEMPLATE, 
                                   question=question, 
                                   answer=answer, 
                                   random_fact=random_fact,
                                   doc_count=len(ALL_DOCS),
                                   domain_count=len(APPROVED_DOMAINS))

if __name__ == "__main__":
    print(f"\n{'='*60}")
    print(f"🌾 Diné Cultural Learning Bot")
    print(f"📁 Documents folder: {DOCUMENTS_FOLDER}")
    print(f"📚 Local documents: {len(ALL_DOCS)}")
    print(f"🔒 Approved domains: {len(APPROVED_DOMAINS)}")
    print(f"{'='*60}\n")
    app.run(host='0.0.0.0', port=5000, debug=True)
