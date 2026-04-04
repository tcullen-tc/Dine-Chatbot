import re
import os
import glob
import random
import urllib.parse
import urllib.request
from html.parser import HTMLParser
import threading
from datetime import datetime, timedelta
from flask import Flask, request, render_template_string, session, jsonify
import json

# Try to import OpenAI
try:
    import openai
    import os as _os
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    print("⚠️ OpenAI not installed. Run: pip install openai")

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dine-chatbot-secret-key-change-in-production')

DID_YOU_KNOW_FACTS = [
    "The Navajo language was used as a code during WWII by the famous Code Talkers - it was never broken!",
    "K'é (kinship) extends beyond blood relations to include all of creation.",
    "Hózhó is often translated as 'beauty' but encompasses harmony, balance, and wellness.",
    "The four sacred mountains mark the boundaries of traditional Dinétah.",
    "Weaving was taught to the Navajo by Spider Woman, a holy being.",
]

# ----------------------------
# DOCUMENT PRIORITY SCORES
# ----------------------------
DOCUMENT_PRIORITY = {
    "black_god_info": 100,
    "hero_twins_story": 100,
    "coyote_info": 100,
    "hair_bun_info": 100,
    "dine_philosophy_hozho": 95,
    "dine_ceremonies_healing": 95,
    "dine_history_heroes": 95,
    "dine_oral_traditions": 85,
    "dine_clan_etiquette": 90,
    "dine_education": 85,
    "dine_sacred_places": 90,
    "dine_songs_music": 85,
    "dine_daily_life": 85,
    "dine_family_life": 90,
    "dine_government": 85,
    "dine_economy": 85,
    "dine_health_medicine": 85,
    "dine_contemporary_issues": 85,
    "american_indian_fairy_tales": 30,
    "north_american_indian_folklore": 30,
}

# ----------------------------
# TOPIC KEYWORDS FOR SUGGESTIONS
# ----------------------------
TOPIC_SUGGESTIONS = {
    "black god": [
        "What is the Night Way ceremony?",
        "How were the stars created?",
        "Who is Coyote in Diné stories?",
        "What is the significance of the Pleiades?",
        "Who are the other Holy People?"
    ],
    "hero twins": [
        "What monsters did the Hero Twins defeat?",
        "Who is Changing Woman?",
        "What weapons did the Hero Twins receive?",
        "Where did the Hero Twins journey?",
        "What is the story of Monster Slayer?"
    ],
    "coyote": [
        "Why did Coyote scatter the stars?",
        "What are some Coyote stories?",
        "Why are Coyote stories told in winter?",
        "What does Coyote represent in Diné culture?",
        "Who is Ma'ii?"
    ],
    "k'é": [
        "How do I introduce myself in Navajo?",
        "What are the four original clans?",
        "How does the clan system work?",
        "What is the importance of family in Diné culture?",
        "How do you say grandmother in Navajo?"
    ],
    "hozho": [
        "What are the four elements of Hózhó?",
        "What does walking in beauty mean?",
        "What is the Blessing Way ceremony?",
        "How do Diné people practice Hózhó daily?",
        "What is the Hózhóójí prayer?"
    ],
    "long walk": [
        "What was the Treaty of 1868?",
        "Who was Barboncito?",
        "Who was Manuelito?",
        "What happened at Bosque Redondo?",
        "How did the Diné return home?"
    ],
    "weaving": [
        "Who taught the Navajo to weave?",
        "What is the spirit line in weaving?",
        "What are the different weaving patterns?",
        "What do the colors in Navajo rugs mean?",
        "Who was Spider Woman?"
    ],
    "code talkers": [
        "How did the Navajo code work?",
        "Who were the original 29 Code Talkers?",
        "Why was the code never broken?",
        "When were the Code Talkers recognized?",
        "What battles did Code Talkers serve in?"
    ],
    "hair bun": [
        "What is Tsiiyéél?",
        "How is the Navajo hair bun made?",
        "What does the hair bun symbolize?",
        "Do Navajo men wear hair buns?",
        "When is the hair bun worn?"
    ]
}

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
# RATE LIMITING
# ----------------------------
user_requests = {}

def check_rate_limit(user_id):
    """Prevent abuse - limit to 10 requests per minute"""
    now = datetime.now()
    if user_id in user_requests:
        requests = [t for t in user_requests[user_id] if now - t < timedelta(minutes=1)]
        user_requests[user_id] = requests
        if len(requests) >= 10:
            return False
    else:
        user_requests[user_id] = []
    user_requests[user_id].append(now)
    return True

# ----------------------------
# LOCAL DOCUMENTS FOLDER
# ----------------------------
DOCUMENTS_FOLDER = os.path.join(os.path.dirname(__file__), "dine_documents")

def chunk_document(content, chunk_size=2000):
    """Split large documents into smaller chunks for better retrieval"""
    chunks = []
    for i in range(0, len(content), chunk_size):
        chunks.append(content[i:i+chunk_size])
    return chunks

def load_all_documents():
    docs = []
    if not os.path.exists(DOCUMENTS_FOLDER):
        os.makedirs(DOCUMENTS_FOLDER)
        return docs
    
    for file_path in glob.glob(os.path.join(DOCUMENTS_FOLDER, "*.txt")):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            name = os.path.basename(file_path).replace('.txt', '')
            
            # Get priority score
            priority = DOCUMENT_PRIORITY.get(name, 50)
            
            # Split into chunks for large documents
            chunks = chunk_document(content)
            
            docs.append({
                "name": name,
                "content": content,
                "priority": priority,
                "chunks": chunks
            })
            print(f"✅ Loaded: {os.path.basename(file_path)} (priority: {priority})")
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
# FIND RELEVANT SOURCES
# ----------------------------
def find_relevant_sources(question, max_sources=5):
    question_lower = question.lower()
    
    stop_words = {'what', 'who', 'how', 'why', 'when', 'where', 'is', 'are', 'was', 'were',
                  'the', 'a', 'an', 'and', 'or', 'but', 'for', 'nor', 'so', 'yet', 'of',
                  'to', 'in', 'for', 'on', 'by', 'with', 'without', 'about', 'tell', 'me'}
    
    words = question_lower.split()
    keywords = [w for w in words if w not in stop_words and len(w) > 2]
    
    # Add 2-3 word phrases
    phrases = []
    for i in range(len(words) - 1):
        phrase = f"{words[i]} {words[i+1]}"
        if len(phrase) > 5:
            phrases.append(phrase)
    
    all_keywords = list(set(keywords + phrases))
    
    scored = []
    for doc in ALL_DOCS:
        content_lower = doc['content'].lower()
        score = 0
        
        # Keyword matching
        for kw in all_keywords:
            score += content_lower.count(kw) * 10
        
        # Priority boost
        score += doc.get('priority', 50)
        
        if score > 0:
            scored.append({
                "score": score,
                "title": doc['name'],
                "content": doc['content'],
                "type": "local",
                "priority": doc.get('priority', 50)
            })
    
    scored.sort(key=lambda x: x['score'], reverse=True)
    sources = scored[:max_sources]
    
    # Add web results if needed
    if len(sources) < 3:
        web_results = search_web(question)
        for r in web_results:
            sources.append({
                "score": 50,
                "title": r['title'],
                "content": r['content'],
                "type": "web",
                "url": r['url']
            })
    
    return sources[:max_sources]

# ----------------------------
# GET CONFIDENCE SCORE
# ----------------------------
def get_confidence(sources):
    if not sources:
        return "low", 0
    top_score = sources[0].get('score', 0)
    if top_score > 1000:
        return "high", min(100, int(top_score / 100))
    elif top_score > 200:
        return "medium", min(100, int(top_score / 20))
    return "low", min(100, int(top_score / 5))

# ----------------------------
# GET SUGGESTED QUESTIONS
# ----------------------------
def get_suggested_questions(question):
    question_lower = question.lower()
    for topic, suggestions in TOPIC_SUGGESTIONS.items():
        if topic in question_lower:
            return suggestions[:3]
    return [
        "Who are the Hero Twins?",
        "Who is Black God?",
        "What is k'é?",
        "What does hózhó mean?",
        "Tell me about Navajo weaving"
    ]

# ----------------------------
# GENERATE ANSWER WITH OPENAI
# ----------------------------
def generate_answer(question, sources, deep_dive=False):
    """Generate an answer using OpenAI that SYNTHESIZES information from sources"""
    
    if not sources:
        return "No relevant sources found. Please try a different question.", []
    
    # Build context from sources
    context = ""
    source_names = []
    source_urls = []
    
    max_content = 4000 if deep_dive else 2000
    
    for i, s in enumerate(sources[:4], 1):
        name = s.get('title', 'Unknown')
        source_names.append(f"[{i}] {name}")
        if s.get('type') == 'web' and s.get('url'):
            source_urls.append(s.get('url'))
        context += f"\n--- Source {i}: {name} ---\n"
        content = s.get('content', '')[:max_content]
        context += content + "\n"
    
    # TRY OPENAI FIRST - this is what makes the bot smart
    if OPENAI_AVAILABLE:
        try:
            openai.api_key = os.environ.get("OPENAI_API_KEY")
            
            # This prompt tells OpenAI to SYNTHESIZE, not just extract
            prompt = f"""You are a helpful assistant answering questions about Diné (Navajo) culture.

IMPORTANT: Your task is to SYNTHESIZE information from the sources below to answer the question. 
Do not just quote the sources. Instead, combine the information to create a helpful, practical answer.

For questions like "how to make friends" or "how to have a successful marriage":
- Look for information about k'é (kinship), respect, generosity, community responsibility
- Explain how these Diné values apply to the situation
- Give practical, actionable advice based on Diné teachings

Answer based ONLY on the source documents below. If the information is not in the sources, say "Based on the available sources, I don't have specific information about that."

SOURCES:
{context}

QUESTION: {question}

ANSWER:"""
            
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,  # Slightly higher for more natural answers
                max_tokens=800 if deep_dive else 600
            )
            answer = response.choices[0].message.content
            
            # Add confidence and sources
            confidence, confidence_score = get_confidence(sources)
            if confidence == "high":
                answer += f"\n\n---\n✅ Based on {len(sources)} sources from Diné cultural teachings."
            elif confidence == "medium":
                answer += f"\n\n---\n📚 Based on {len(sources)} sources."
            else:
                answer += f"\n\n---\n📚 Sources used: {', '.join(source_names)}"
            
            return answer, source_urls
            
        except Exception as e:
            print(f"OpenAI error: {e}")
            # Fall through to fallback
    
    # FALLBACK - simple text extraction (less helpful)
    best = sources[0]
    text = best.get('content', '')
    text = re.sub(r'\s+', ' ', text)
    if len(text) > 800:
        text = text[:800] + "..."
    
    answer = text
    answer += f"\n\n---\n⚠️ Note: Using simplified mode. For better answers, ensure OpenAI is configured."
    answer += f"\n📚 Source: {source_names[0] if source_names else 'Unknown'}"
    
    return answer, source_urls

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
        .button-group {
            display: flex;
            gap: 10px;
            margin-top: 15px;
            flex-wrap: wrap;
        }
        .submit-btn {
            background: #2c5f2d;
            color: white;
            border: none;
            padding: 12px 30px;
            border-radius: 25px;
            font-size: 16px;
            cursor: pointer;
        }
        .deep-dive-btn {
            background: #f39c12;
            color: white;
            border: none;
            padding: 12px 20px;
            border-radius: 25px;
            font-size: 14px;
            cursor: pointer;
        }
        .submit-btn:hover:not(:disabled) { background: #1e3a1e; }
        .deep-dive-btn:hover:not(:disabled) { background: #e67e22; }
        .submit-btn:disabled, .deep-dive-btn:disabled { background: #95a5a6; cursor: not-allowed; }
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
            white-space: pre-wrap;
        }
        .answer-actions {
            display: flex;
            gap: 10px;
            margin-top: 15px;
            flex-wrap: wrap;
        }
        .action-btn {
            background: none;
            border: 1px solid #2c5f2d;
            color: #2c5f2d;
            padding: 5px 12px;
            border-radius: 20px;
            cursor: pointer;
            font-size: 12px;
        }
        .action-btn:hover { background: #2c5f2d; color: white; }
        .feedback {
            margin-top: 15px;
            padding-top: 10px;
            border-top: 1px solid #e0e0e0;
            font-size: 12px;
            color: #666;
        }
        .feedback-btn {
            background: none;
            border: none;
            cursor: pointer;
            font-size: 16px;
            margin-left: 10px;
        }
        .related {
            margin-top: 15px;
            padding: 10px;
            background: #e8f5e9;
            border-radius: 8px;
        }
        .related-title {
            font-size: 13px;
            font-weight: bold;
            color: #2c5f2d;
            margin-bottom: 8px;
        }
        .related-question {
            background: white;
            border: none;
            padding: 5px 10px;
            margin: 3px;
            border-radius: 15px;
            cursor: pointer;
            font-size: 12px;
        }
        .related-question:hover { background: #2c5f2d; color: white; }
        .confidence {
            font-size: 12px;
            margin-top: 10px;
            padding: 5px;
            border-radius: 5px;
        }
        .confidence-high { background: #d5f5e3; color: #27ae60; }
        .confidence-medium { background: #fef9e7; color: #f39c12; }
        .confidence-low { background: #fdedec; color: #e74c3c; }
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
        .toast {
            position: fixed;
            bottom: 20px;
            right: 20px;
            background: #2c5f2d;
            color: white;
            padding: 10px 20px;
            border-radius: 8px;
            font-size: 14px;
            z-index: 1000;
            opacity: 0;
            transition: opacity 0.3s;
        }
        .toast.show { opacity: 1; }
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
                <textarea name="question" placeholder="Example: Who are the Hero Twins? Who is Black God? What is k'é?" rows="4" id="questionInput">{{ question }}</textarea>
                <div class="button-group">
                    <button type="submit" class="submit-btn" id="submitBtn">🔍 Ask Question</button>
                    <button type="button" class="deep-dive-btn" id="deepDiveBtn">🔬 Deep Dive</button>
                    <button type="button" class="action-btn" id="voiceBtn">🎤 Voice Input</button>
                    <button type="button" class="action-btn" id="randomBtn">🎲 Surprise Me</button>
                </div>
                <div id="loadingIndicator" style="display: none; margin-top: 10px;">
                    <span class="loading-spinner"></span> Searching sources and generating answer...
                </div>
            </form>
            
            <div class="example-buttons">
                <button class="example-btn" data-question="Who are the Hero Twins?">🏹 Hero Twins</button>
                <button class="example-btn" data-question="Who is Black God?">⭐ Black God</button>
                <button class="example-btn" data-question="Who is Coyote?">🦊 Coyote</button>
                <button class="example-btn" data-question="What is k'é?">🤝 What is k'é?</button>
                <button class="example-btn" data-question="What does hózhó mean?">☯️ Hózhó</button>
                <button class="example-btn" data-question="What is the Long Walk?">👣 Long Walk</button>
                <button class="example-btn" data-question="What is the hair bun called?">💇 Hair Bun</button>
            </div>
            
            {% if answer %}
            <div class="answer">
                <blockquote>{{ answer | safe }}</blockquote>
                <div class="answer-actions">
                    <button class="action-btn" onclick="copyAnswer()">📋 Copy Answer</button>
                    <button class="action-btn" onclick="speakAnswer()">🔊 Read Aloud</button>
                </div>
                <div class="feedback">
                    Was this helpful?
                    <button class="feedback-btn" onclick="feedback('yes')">👍 Yes</button>
                    <button class="feedback-btn" onclick="feedback('no')">👎 No</button>
                    <span id="feedbackMsg" style="margin-left: 10px;"></span>
                </div>
                {% if related %}
                <div class="related">
                    <div class="related-title">📌 Related Questions</div>
                    {% for q in related %}
                    <button class="related-question" data-question="{{ q }}">{{ q }}</button>
                    {% endfor %}
                </div>
                {% endif %}
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
    <div id="toast" class="toast"></div>
    
    <script>
        // Example buttons
        document.querySelectorAll('.example-btn, .related-question').forEach(btn => {
            btn.addEventListener('click', function() {
                if(this.dataset.question) {
                    document.getElementById('questionInput').value = this.dataset.question;
                    document.getElementById('submitBtn').click();
                }
            });
        });
        
        // Form submission
        document.getElementById('questionForm').addEventListener('submit', function() {
            if (!document.getElementById('questionInput').value.trim()) {
                alert('Please enter a question');
                event.preventDefault();
                return false;
            }
            document.getElementById('submitBtn').disabled = true;
            document.getElementById('deepDiveBtn').disabled = true;
            document.getElementById('loadingIndicator').style.display = 'block';
        });
        
        // Deep Dive mode
        document.getElementById('deepDiveBtn').addEventListener('click', function() {
            let question = document.getElementById('questionInput').value.trim();
            if (!question) {
                alert('Please enter a question first');
                return;
            }
            // Add deep dive parameter
            let form = document.getElementById('questionForm');
            let input = document.createElement('input');
            input.type = 'hidden';
            input.name = 'deep_dive';
            input.value = 'true';
            form.appendChild(input);
            form.submit();
        });
        
        // Voice input
        document.getElementById('voiceBtn').addEventListener('click', function() {
            if ('webkitSpeechRecognition' in window) {
                const recognition = new webkitSpeechRecognition();
                recognition.lang = 'en-US';
                recognition.onresult = (event) => {
                    document.getElementById('questionInput').value = event.results[0][0].transcript;
                };
                recognition.start();
            } else {
                alert('Voice input not supported in this browser');
            }
        });
        
        // Random question
        document.getElementById('randomBtn').addEventListener('click', function() {
            const questions = [
                "Who are the Hero Twins?",
                "Who is Black God?",
                "What is k'é?",
                "What does hózhó mean?",
                "Tell me about Navajo weaving",
                "What is the Long Walk?",
                "Who were the Code Talkers?",
                "What is the hair bun called?",
                "What are the four sacred mountains?"
            ];
            const random = questions[Math.floor(Math.random() * questions.length)];
            document.getElementById('questionInput').value = random;
            document.getElementById('submitBtn').click();
        });
        
        // Copy answer
        function copyAnswer() {
            const answerText = document.querySelector('.answer blockquote').innerText;
            navigator.clipboard.writeText(answerText);
            showToast('✅ Answer copied to clipboard!');
        }
        
        // Speak answer
        function speakAnswer() {
            const answerText = document.querySelector('.answer blockquote').innerText;
            const utterance = new SpeechSynthesisUtterance(answerText);
            speechSynthesis.speak(utterance);
        }
        
        // Feedback
        function feedback(type) {
            fetch('/feedback', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ feedback: type, question: document.getElementById('questionInput').value })
            });
            document.getElementById('feedbackMsg').innerText = 'Thank you for your feedback! 🙏';
            setTimeout(() => {
                document.getElementById('feedbackMsg').innerText = '';
            }, 3000);
        }
        
        function showToast(message) {
            const toast = document.getElementById('toast');
            toast.textContent = message;
            toast.classList.add('show');
            setTimeout(() => toast.classList.remove('show'), 2000);
        }
        
        window.addEventListener('load', function() {
            document.getElementById('submitBtn').disabled = false;
            document.getElementById('deepDiveBtn').disabled = false;
            document.getElementById('loadingIndicator').style.display = 'none';
        });
    </script>
</body>
</html>
"""

# ----------------------------
# FEEDBACK STORAGE (simple - in production use a database)
# ----------------------------
feedback_storage = []

@app.route('/feedback', methods=['POST'])
def handle_feedback():
    data = request.get_json()
    feedback_storage.append({
        "question": data.get('question'),
        "feedback": data.get('feedback'),
        "timestamp": datetime.now().isoformat()
    })
    return jsonify({"status": "ok"})

# ----------------------------
# FLASK ROUTES
# ----------------------------
@app.errorhandler(Exception)
def handle_exception(e):
    print(f"Error: {e}")
    return f"An error occurred: {str(e)}", 500

@app.route('/', methods=['GET', 'POST'])
def home():
    question = ""
    answer = None
    related = None
    random_fact = random.choice(DID_YOU_KNOW_FACTS)
    
    # Rate limiting
    client_ip = request.remote_addr
    if not check_rate_limit(client_ip):
        return "Rate limit exceeded. Please wait a moment before asking another question.", 429
    
    if request.method == 'POST':
        question = request.form.get('question', '').strip()
        deep_dive = request.form.get('deep_dive', 'false') == 'true'
        
        if question:
            print(f"\n{'='*50}")
            print(f"📖 QUESTION: {question}")
            print(f"🔬 Deep Dive: {deep_dive}")
            print(f"{'='*50}")
            
            max_sources = 8 if deep_dive else 5
            sources = find_relevant_sources(question, max_sources)
            print(f"Found {len(sources)} relevant sources")
            
            answer_text, source_urls = generate_answer(question, sources, deep_dive)
            answer = answer_text
            
            # Get related questions
            related = get_suggested_questions(question)
            
            # Store conversation in session
            if 'conversation' not in session:
                session['conversation'] = []
            session['conversation'].append({
                "question": question,
                "answer": answer[:500]  # Store preview
            })
            # Keep only last 10
            session['conversation'] = session['conversation'][-10:]
    
    return render_template_string(HTML_TEMPLATE, 
                                   question=question, 
                                   answer=answer,
                                   related=related,
                                   random_fact=random_fact,
                                   doc_count=len(ALL_DOCS),
                                   domain_count=len(APPROVED_DOMAINS))

# ----------------------------
# RANDOM QUESTION ENDPOINT
# ----------------------------
@app.route('/random-question')
def random_question():
    import random as rand
    questions = [
        "Who are the Hero Twins?",
        "Who is Black God?",
        "What is k'é?",
        "What does hózhó mean?",
        "Tell me about Navajo weaving",
        "What is the Long Walk?",
        "Who were the Code Talkers?",
        "What is the hair bun called?",
        "What are the four sacred mountains?"
    ]
    return jsonify({"question": rand.choice(questions)})

if __name__ == "__main__":
    print(f"\n{'='*60}")
    print(f"🌾 Diné Cultural Learning Bot - Enhanced Edition")
    print(f"📁 Documents folder: {DOCUMENTS_FOLDER}")
    print(f"📚 Local documents: {len(ALL_DOCS)}")
    print(f"🔒 Approved domains: {len(APPROVED_DOMAINS)}")
    print(f"🤖 OpenAI available: {OPENAI_AVAILABLE}")
