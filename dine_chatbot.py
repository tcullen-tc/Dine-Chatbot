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

# Did You Know facts
DID_YOU_KNOW_FACTS = [
    "The Navajo language was used as a code during WWII by the famous Code Talkers - it was never broken!",
    "K'é (kinship) extends beyond blood relations to include all of creation.",
    "Hózhó is often translated as 'beauty' but encompasses harmony, balance, and wellness.",
    "Coyote (Ma'ii) is an important trickster figure in Diné stories.",
]

# ----------------------------
# APPROVED DINÉ DOMAINS - ORIGINAL MULTI-LINE FORMAT
# ----------------------------
APPROVED_DOMAINS = [
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

    # --- University Presses ---
    "unmpress.com",
    "upcolorado.com",
    "uapress.arizona.edu",
    
    # --- Academic & Cultural Resources ---
    "jstor.org",
    "ehillerman.unm.edu",
    
    # --- Additional Cultural Sites ---
    "navajoculture.org",
    "traditionalnavajoteachings.org",
]

USER_AGENT = "Mozilla/5.0 (iPhone; CPU iPhone OS like Mac OS X) AppleWebKit/605.1.15"

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
            })
            print(f"   ✅ Loaded: {filename}")
        except Exception as e:
            print(f"   ❌ Error: {e}")
    return documents

LOCAL_DOCUMENTS = load_local_documents()

# ----------------------------
# Dynamic Keyword Extraction
# ----------------------------
def extract_keywords(question):
    """Extract meaningful keywords from the question"""
    stop_words = {'what', 'who', 'how', 'why', 'when', 'where', 'is', 'are', 'was', 'were',
                  'the', 'a', 'an', 'and', 'or', 'but', 'for', 'nor', 'so', 'yet', 'of',
                  'to', 'in', 'for', 'on', 'by', 'with', 'without', 'about', 'tell', 'me',
                  'can', 'you', 'please', 'would', 'could', 'should', 'does', 'do', 'did',
                  'has', 'have', 'had', 'been', 'being', 'called', 'known', 'also', 'very'}
    
    words = question.lower().split()
    keywords = [w for w in words if w not in stop_words and len(w) > 2]
    
    # Keep important phrases (2-3 words)
    phrases = []
    for i in range(len(words) - 1):
        phrase = f"{words[i]} {words[i+1]}"
        if len(phrase) > 5 and words[i] not in stop_words:
            phrases.append(phrase)
    
    for i in range(len(words) - 2):
        phrase = f"{words[i]} {words[i+1]} {words[i+2]}"
        if len(phrase) > 8 and words[i] not in stop_words:
            phrases.append(phrase)
    
    all_keywords = list(set(keywords + phrases))
    print(f"🔍 Extracted keywords: {all_keywords[:10]}")
    return all_keywords

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

def is_approved_domain(url):
    domain = domain_of(url)
    return any(domain.endswith(d) for d in APPROVED_DOMAINS)

def ddg_search_approved(query, max_results=4):
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
            if link.startswith('http') and is_approved_domain(link):
                results.append(link)
            if len(results) >= max_results:
                break
        return results
    except Exception as e:
        print(f"Search error: {e}")
        return []

# ----------------------------
# Extract relevant content from a document
# ----------------------------
def extract_relevant_content(content, keywords, filename=""):
    """Extract the most relevant sentences from content"""
    # Split into sentences
    sentences = re.split(r'(?<=[.!?])\s+', content)
    
    # Score each sentence
    scored_sentences = []
    for sent in sentences:
        if len(sent) < 40:
            continue
        sent_lower = sent.lower()
        
        # Skip Gutenberg headers
        if 'gutenberg' in sent_lower or 'project gutenberg' in sent_lower:
            continue
        
        score = 0
        for kw in keywords:
            score += sent_lower.count(kw) * 10
        
        # Bonus for exact phrase matches
        if "black god" in sent_lower:
            score += 500
        if "haashch" in sent_lower:
            score += 500
        if "hero twin" in sent_lower:
            score += 500
        if "monster slayer" in sent_lower:
            score += 500
        if "coyote" in sent_lower:
            score += 300
        
        if score > 0:
            scored_sentences.append((score, sent.strip()))
    
    scored_sentences.sort(reverse=True, key=lambda x: x[0])
    
    # Return top 3-5 sentences
    result_sentences = []
    for score, sent in scored_sentences[:5]:
        # Clean up
        sent = re.sub(r'\s+', ' ', sent)
        result_sentences.append(sent)
    
    return result_sentences

# ----------------------------
# Search local documents
# ----------------------------
def search_local(question, keywords):
    results = []
    question_lower = question.lower()
    
    for doc in LOCAL_DOCUMENTS:
        content_lower = doc['content'].lower()
        score = 0
        
        # Special priority for exact filename matches
        if "black_god_info" in doc['filename'].lower() and ("black god" in question_lower or "haashch" in question_lower):
            score = 100000
            print(f"   ⭐ Found Black God file: {doc['filename']}")
        elif "hero_twins" in doc['filename'].lower() and ("hero twin" in question_lower or "monster slayer" in question_lower):
            score = 100000
            print(f"   ⭐ Found Hero Twins file: {doc['filename']}")
        elif "american_indian" in doc['filename'].lower() and "coyote" in question_lower:
            score = 50000
            print(f"   🦊 Found Coyote story file: {doc['filename']}")
        else:
            # Normal scoring
            for kw in keywords:
                count = content_lower.count(kw)
                if count > 0:
                    score += count * 10
        
        if score > 0:
            # Extract relevant sentences
            relevant_sentences = extract_relevant_content(doc['content'], keywords, doc['filename'])
            if relevant_sentences:
                results.append({
                    "title": doc['name'],
                    "content": ' '.join(relevant_sentences),
                    "score": score,
                    "type": "local",
                    "filename": doc['filename']
                })
    
    results.sort(key=lambda x: x['score'], reverse=True)
    return results[:3]

# ----------------------------
# Search web domains
# ----------------------------
def search_web(question, keywords):
    results = []
    urls = ddg_search_approved(question, max_results=4)
    
    for url in urls:
        try:
            html = fetch_url(url, timeout=15)
            if html:
                parser = TextExtractor()
                parser.feed(html)
                text = parser.get_text()
                
                if text and len(text) > 200:
                    # Check relevance
                    text_lower = text.lower()
                    relevance = 0
                    for kw in keywords:
                        relevance += text_lower.count(kw) * 5
                    
                    if relevance > 0:
                        relevant_sentences = extract_relevant_content(text, keywords)
                        if relevant_sentences:
                            results.append({
                                "title": domain_of(url),
                                "url": url,
                                "content": ' '.join(relevant_sentences),
                                "relevance": relevance,
                                "type": "web"
                            })
        except Exception as e:
            print(f"Error: {e}")
            continue
    
    results.sort(key=lambda x: x['relevance'], reverse=True)
    return results[:3]

# ----------------------------
# Generate ONE synthesized answer from ALL sources
# ----------------------------
def generate_synthesized_answer(question, local_results, web_results, keywords):
    """Combine all sources into ONE coherent answer"""
    
    # Collect all content
    all_sentences = []
    all_sources = []
    
    for r in local_results:
        if r['content']:
            # Split into sentences
            sentences = re.split(r'(?<=[.!?])\s+', r['content'])
            for sent in sentences:
                if len(sent) > 30:
                    all_sentences.append({
                        "text": sent,
                        "source": r['title'],
                        "type": "local",
                        "score": r['score']
                    })
            all_sources.append({"title": r['title'], "type": "local"})
    
    for r in web_results:
        if r['content']:
            sentences = re.split(r'(?<=[.!?])\s+', r['content'])
            for sent in sentences:
                if len(sent) > 30:
                    all_sentences.append({
                        "text": sent,
                        "source": r['title'],
                        "type": "web",
                        "score": r['relevance']
                    })
            all_sources.append({"title": r['title'], "type": "web", "url": r.get('url', '')})
    
    if not all_sentences:
        return None
    
    # Score sentences by relevance to question
    question_lower = question.lower()
    for sent in all_sentences:
        sent_lower = sent['text'].lower()
        relevance = 0
        
        # Check for exact phrase matches
        if "black god" in question_lower and "black god" in sent_lower:
            relevance += 1000
        if "haashch" in question_lower and "haashch" in sent_lower:
            relevance += 1000
        if "hero twin" in question_lower and "hero twin" in sent_lower:
            relevance += 1000
        if "coyote" in question_lower and "coyote" in sent_lower:
            relevance += 800
        
        # Check for keywords
        for kw in keywords[:5]:
            if kw in sent_lower:
                relevance += 50
        
        sent['relevance'] = relevance
    
    # Sort by relevance
    all_sentences.sort(key=lambda x: x['relevance'], reverse=True)
    
    # Take top unique sentences (avoid duplicates)
    seen_text = set()
    unique_sentences = []
    for sent in all_sentences:
        # Use first 50 chars as key for deduplication
        key = sent['text'][:50]
        if key not in seen_text:
            seen_text.add(key)
            unique_sentences.append(sent)
    
    # Build the answer (first 3-6 sentences)
    answer_sentences = unique_sentences[:6]
    answer_text = ' '.join([s['text'] for s in answer_sentences])
    
    # Clean up
    answer_text = re.sub(r'\s+', ' ', answer_text)
    if len(answer_text) > 1200:
        answer_text = answer_text[:1200] + "..."
    
    # Build the output
    output = []
    output.append(f'<p><strong>📖 Question:</strong> {question}</p>')
    output.append('<hr>')
    output.append('<p><strong>📖 Answer:</strong></p>')
    output.append(f'<blockquote style="background:#f9f9f9;padding:20px;border-left:4px solid #2c5f2d;margin:10px 0;font-size:16px;line-height:1.6;">{answer_text}</blockquote>')
    
    # List sources
    output.append('<hr>')
    output.append('<p><strong>📚 Sources used to create this answer:</strong></p>')
    output.append('<ul>')
    for s in all_sources[:5]:
        if s['type'] == 'local':
            output.append(f'<li><strong>📄 {s["title"]}</strong> (Local Document)</li>')
        else:
            output.append(f'<li><strong>🌐 {s["title"]}</strong>: <a href="{s["url"]}" target="_blank">{s["url"]}</a></li>')
    output.append('</ul>')
    
    output.append(f'<p style="font-size:12px; color:#666; margin-top:15px;">🔒 Search restricted to {len(APPROVED_DOMAINS)} approved Diné cultural domains + {len(LOCAL_DOCUMENTS)} local documents.</p>')
    
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
            <p>Ask any question about Navajo traditions, language, and values</p>
        </div>
        <div class="content">
            <div class="protocol-box">
                🌄 <strong>Cultural Note:</strong> Answers are from approved Diné cultural sources only.
                <span class="badge">{{ domain_count }} approved domains</span>
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
    
    if request.method == 'POST':
        question = request.form.get('question', '').strip()
        
        if question:
            print(f"\n{'='*50}")
            print(f"📖 QUESTION: {question}")
            print(f"{'='*50}")
            
            keywords = extract_keywords(question)
            local_results = search_local(question, keywords)
            web_results = search_web(question, keywords)
            
            print(f"📚 Local results: {len(local_results)}")
            for r in local_results:
                print(f"   - {r['title']} (score: {r['score']})")
            
            answer = generate_synthesized_answer(question, local_results, web_results, keywords)
            
            if not answer:
                answer = """
                <p><strong>📖 No information found in approved Diné sources.</strong></p>
                <p>Try asking about:</p>
                <ul>
                    <li>Who are the Hero Twins?</li>
                    <li>Who is Black God?</li>
                    <li>Who is Coyote?</li>
                    <li>What is k'é?</li>
                    <li>Tell me about Navajo weaving</li>
                </ul>
                """
    
    return render_template_string(HTML_TEMPLATE, 
                                   question=question, 
                                   answer=answer, 
                                   random_fact=random_fact,
                                   doc_count=len(LOCAL_DOCUMENTS),
                                   domain_count=len(APPROVED_DOMAINS))

if __name__ == "__main__":
    print(f"\n{'='*60}")
    print(f"🌾 Diné Cultural Learning Bot")
    print(f"📁 Documents folder: {DOCUMENTS_FOLDER}")
    print(f"📚 Local documents: {len(LOCAL_DOCUMENTS)}")
    print(f"🔒 Approved web domains: {len(APPROVED_DOMAINS)}")
    print(f"{'='*60}\n")
    app.run(host='0.0.0.0', port=5000, debug=True)
    
