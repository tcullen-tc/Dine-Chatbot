import re
import sys
import time
import json
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from datetime import datetime, date
import threading
import random
import os
import glob
from flask import Flask, request, render_template_string

app = Flask(__name__)

# Did You Know facts
DID_YOU_KNOW_FACTS = [
    "The Navajo language was used as a code during WWII by the famous Code Talkers - it was never broken!",
    "K'é (kinship) extends beyond blood relations to include all of creation.",
    "Hózhó is often translated as 'beauty' but encompasses harmony, balance, and wellness.",
    "Coyote (Ma'ii) is an important trickster figure in Diné stories.",
    "The four sacred mountains mark the boundaries of traditional Dinétah.",
    "Weaving was taught to the Navajo by Spider Woman, a holy being.",
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
    return fallback_path

DOCUMENTS_FOLDER = find_documents_folder()

def load_local_documents():
    documents = []
    if not os.path.exists(DOCUMENTS_FOLDER):
        return documents
    
    txt_files = glob.glob(os.path.join(DOCUMENTS_FOLDER, "*.txt"))
    print(f"📂 Found {len(txt_files)} local text files")
    
    for file_path in txt_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            filename = os.path.basename(file_path)
            documents.append({
                "name": filename.replace('.txt', ''),
                "filename": filename,
                "content": content,
                "size": len(content)
            })
            print(f"   ✅ Loaded: {filename} ({len(content)} chars)")
        except Exception as e:
            print(f"   ❌ Error: {e}")
    return documents

# ----------------------------
# COMPLETE ALLOWED DOMAINS - ALL 39 DINÉ SOURCES
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

USER_AGENT = "Mozilla/5.0 (iPhone; CPU iPhone OS like Mac OS X) AppleWebKit/605.1.15"

# ----------------------------
# HTML to Text Extractor
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
        if tag in ('p', 'br', 'div'):
            self.text.append('\n')

    def handle_data(self, data):
        if not self.skip and data.strip():
            self.text.append(data.strip())

    def get_text(self):
        return ' '.join(self.text)

def fetch_url(url, timeout=15):
    try:
        req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return response.read().decode('utf-8', errors='ignore')
    except Exception as e:
        print(f"Error: {e}")
        return ""

def domain_of(url):
    try:
        return urllib.parse.urlparse(url).netloc.lower().replace('www.', '')
    except:
        return ""

def is_allowed(url):
    domain = domain_of(url)
    return any(domain.endswith(d) for d in ALLOWED_DOMAINS)

def ddg_search(query, max_results=6):
    try:
        q = urllib.parse.quote_plus(query)
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
            if link.startswith('http') and is_allowed(link):
                results.append(link)
            if len(results) >= max_results:
                break
        return results
    except Exception as e:
        print(f"Search error: {e}")
        return []

# ----------------------------
# Extract clean text from documents (skip Gutenberg headers)
# ----------------------------
def extract_clean_text(content, question=""):
    lines = content.split('\n')
    clean_lines = []
    start_collecting = False
    
    start_markers = ['coyote', 'story', 'legend', 'tale', 'myth', 'tradition', 
                     'once upon', 'long ago', 'there lived', 'according to']
    
    is_coyote = "coyote" in question.lower()
    
    for line in lines:
        line_lower = line.lower()
        
        if not start_collecting:
            if any(marker in line_lower for marker in start_markers):
                start_collecting = True
        
        if start_collecting:
            if 'gutenberg' in line_lower or 'copyright' in line_lower or 'end of the project' in line_lower:
                break
            if len(line.strip()) > 40:
                if is_coyote and 'coyote' in line_lower:
                    clean_lines.insert(0, line.strip())
                else:
                    clean_lines.append(line.strip())
    
    if not clean_lines:
        for line in lines:
            if len(line.strip()) > 80:
                clean_lines.append(line.strip())
                if len(clean_lines) >= 10:
                    break
    
    return '\n'.join(clean_lines[:15])

# ----------------------------
# Search local documents
# ----------------------------
def search_local_documents(question, documents):
    results = []
    question_lower = question.lower()
    is_coyote = "coyote" in question_lower
    is_hero = "hero" in question_lower or "twin" in question_lower
    is_blackgod = "black god" in question_lower
    
    for doc in documents:
        content_lower = doc['content'].lower()
        filename = doc['filename'].lower()
        score = 0
        
        if is_coyote and ("american_indian" in filename or "folklore" in filename):
            score += 5000
        elif is_hero and "hero_twins" in filename:
            score += 5000
        elif is_blackgod and "black_god" in filename:
            score += 5000
        
        words = [w for w in question_lower.split() if len(w) > 3]
        for word in words:
            score += content_lower.count(word) * 10
        
        if is_coyote:
            score += content_lower.count("coyote") * 100
        
        if score > 20:
            clean_text = extract_clean_text(doc['content'], question)
            results.append({
                "title": doc['name'],
                "filename": doc['filename'],
                "score": score,
                "text": clean_text,
                "type": "local"
            })
    
    results.sort(key=lambda x: x['score'], reverse=True)
    return results[:3]

# ----------------------------
# Search web sources (Diné-approved domains only)
# ----------------------------
def search_web_sources(question):
    results = []
    search_query = f"{question} Navajo Diné"
    urls = ddg_search(search_query, max_results=5)
    
    for url in urls:
        try:
            html = fetch_url(url, timeout=15)
            if html:
                parser = TextExtractor()
                parser.feed(html)
                text = parser.get_text()
                if text and len(text) > 200:
                    results.append({
                        "title": domain_of(url),
                        "url": url,
                        "text": text[:2000],
                        "type": "web"
                    })
        except Exception as e:
            print(f"Error: {e}")
            continue
    
    return results[:3]

# ----------------------------
# Generate answer
# ----------------------------
def generate_answer(question, local_results, web_results):
    output = []
    output.append(f'<p><strong>📖 Question:</strong> {question}</p>')
    output.append('<hr>')
    
    if local_results:
        output.append('<p><strong>📚 From your local documents:</strong></p>')
        for r in local_results:
            output.append(f'<p><strong>📄 {r["title"]}</strong></p>')
            if r['text']:
                preview = r['text'][:600]
                if len(r['text']) > 600:
                    preview += '...'
                output.append(f'<blockquote style="background:#f9f9f9;padding:12px;border-left:3px solid #2c5f2d;margin:10px 0;">{preview}</blockquote>')
        output.append('<hr>')
    
    if web_results:
        output.append('<p><strong>🌐 From trusted Diné web sources:</strong></p>')
        for r in web_results:
            output.append(f'<p><strong>{r["title"]}</strong><br><a href="{r["url"]}" target="_blank">{r["url"]}</a></p>')
            preview = r['text'][:500] + '...' if len(r['text']) > 500 else r['text']
            output.append(f'<blockquote style="background:#f0f0f0;padding:12px;border-left:3px solid #2c5f2d;margin:10px 0;">{preview}</blockquote>')
    
    if not local_results and not web_results:
        output.append('<p><strong>📖 No Diné cultural sources found.</strong></p>')
        output.append('<p>I can only answer questions about Diné (Navajo) culture from approved sources. Try asking about:</p>')
        output.append('<ul>')
        output.append('<li>Who are the Hero Twins?</li>')
        output.append('<li>Who is Black God?</li>')
        output.append('<li>Who is Coyote?</li>')
        output.append('<li>What is k\'é?</li>')
        output.append('<li>Tell me about Navajo weaving</li>')
        output.append('<li>What is the Long Walk?</li>')
        output.append('</ul>')
    
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
        .header p { opacity: 0.9; }
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
            transition: all 0.3s;
        }
        .example-btn:hover { background: #2c5f2d; color: white; transform: translateY(-2px); }
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
            
            <form method="POST" id="questionForm">
                <textarea name="question" placeholder="Example: Who are the Hero Twins? Who is Coyote? What is k'é?" rows="4">{{ question }}</textarea>
                <div>
                    <button type="submit" class="submit-btn" id="submitBtn">🔍 Ask Question</button>
                    <div id="loadingIndicator" style="display: none; margin-left: 15px;">
                        <span class="loading-spinner"></span> Searching approved Diné sources...
                    </div>
                </div>
            </form>
            
            <div class="example-buttons">
                <button class="example-btn" data-question="Who are the Hero Twins?">🏹 Hero Twins</button>
                <button class="example-btn" data-question="Who is Black God?">⭐ Black God</button>
                <button class="example-btn" data-question="Who is Coyote?">🦊 Coyote</button>
                <button class="example-btn" data-question="What is k'é?">🤝 What is k'é?</button>
                <button class="example-btn" data-question="Tell me about Navajo weaving">🪶 Weaving</button>
                <button class="example-btn" data-question="What is the Long Walk?">👣 Long Walk</button>
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
            🌍 Searching: {{ doc_count }} local documents + {{ domain_count }} approved Diné web domains
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
            document.getElementById('loadingIndicator').style.display = 'inline-block';
        });
        window.addEventListener('load', function() {
            document.getElementById('submitBtn').disabled = false;
            document.getElementById('loadingIndicator').style.display = 'none';
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
    return f"An error occurred: {str(e)}", 500

@app.route('/', methods=['GET', 'POST'])
def home():
    question = ""
    answer = ""
    random_fact = random.choice(DID_YOU_KNOW_FACTS)
    
    local_docs = load_local_documents()
    
    if request.method == 'POST':
        question = request.form.get('question', '').strip()
        
        if question:
            print(f"\n🔍 Searching for: {question}")
            
            local_results = search_local_documents(question, local_docs)
            web_results = search_web_sources(question)
            
            print(f"📚 Local: {len(local_results)} results")
            print(f"🌐 Web: {len(web_results)} results")
            
            answer = generate_answer(question, local_results, web_results)
    
    return render_template_string(HTML_TEMPLATE, 
                                   question=question, 
                                   answer=answer, 
                                   random_fact=random_fact,
                                   doc_count=len(local_docs),
                                   domain_count=len(ALLOWED_DOMAINS))

if __name__ == "__main__":
    print(f"\n{'='*60}")
    print("🌾 Diné Cultural Learning Bot")
    print(f"📁 Documents folder: {DOCUMENTS_FOLDER}")
    print(f"📚 Local documents: {len(load_local_documents())}")
    print(f"🌐 Approved web domains: {len(ALLOWED_DOMAINS)}")
    print(f"{'='*60}\n")
    app.run(host='0.0.0.0', port=5000, debug=True)
