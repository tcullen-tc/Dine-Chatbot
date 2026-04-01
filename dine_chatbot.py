import re
import sys
import io
import os
import random
import threading
import logging
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from datetime import datetime, date
from typing import List, Dict, Any, Optional
from flask import Flask, request, render_template_string

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
    "The Navajo Nation is the largest Native American reservation in the United States.",
    "In Diné tradition, the number four is sacred - representing the four directions.",
    "The Navajo creation story tells of the Diné emerging through four worlds.",
    "Traditional Navajo names are often given in ceremonies and hold deep spiritual significance.",
]

# Pronunciation guide
PRONUNCIATION_GUIDE = {
    "k'é": "k'-eh (glottal stop)",
    "hózhó": "hoh-zhoh",
    "diné": "di-nay (the people)",
}

def add_pronunciation_tooltips(text):
    """Add pronunciation tooltips to Diné words"""
    if not text:
        return text
    
    for word, pron in PRONUNCIATION_GUIDE.items():
        pattern = r'\b' + re.escape(word) + r'\b'
        replacement = f'<span title="Pronunciation: {pron}" style="border-bottom: 1px dotted #2c5f2d; cursor: help;">{word}</span>'
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    return text

def get_trust_badge(trust_score: float) -> str:
    """Generate trust badge HTML"""
    if trust_score >= 0.95:
        return '<span style="background: #2ecc71; color: white; padding: 2px 8px; border-radius: 12px; font-size: 11px; margin-left: 8px;">✓ Verified</span>'
    elif trust_score >= 0.80:
        return '<span style="background: #3498db; color: white; padding: 2px 8px; border-radius: 12px; font-size: 11px; margin-left: 8px;">📚 Trusted</span>'
    else:
        return '<span style="background: #95a5a6; color: white; padding: 2px 8px; border-radius: 12px; font-size: 11px; margin-left: 8px;">📖 Reference</span>'

# Allowed domains
ALLOWED_DOMAINS = [
    "navajo-nsn.gov",
    "navajocourts.org",
    "dinecollege.edu",
    "navajolanguageacademy.org",
    "navajotimes.com",
    "ictnews.org",
    "indiancountrytoday.com",
    "americanindian.si.edu",
    "loc.gov",
    "pbs.org",
    "navajoculture.org",
]

# Domain trust scores
DOMAIN_TRUST = {
    "navajo-nsn.gov": 1.00,
    "dinecollege.edu": 0.95,
    "navajotimes.com": 0.85,
    "ictnews.org": 0.82,
    "americanindian.si.edu": 0.80,
}

# Seasonal teaching mode
SEASONAL_MODE = True
HIBERNATION_MONTHS = {11, 12, 1, 2, 3}
ANIMAL_KEYWORDS = ["bear", "coyote", "wolf", "snake", "owl", "eagle"]

def is_hibernation_season():
    return datetime.now().month in HIBERNATION_MONTHS

def mentions_animals(text):
    return any(k in text.lower() for k in ANIMAL_KEYWORDS)

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

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

def fetch_url(url, timeout=10):
    """Fetch URL content"""
    try:
        req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
        with urllib.request.urlopen(req, timeout=timeout) as response:
            content = response.read().decode('utf-8', errors='ignore')
            return content
    except Exception as e:
        logger.error(f"Error fetching {url}: {e}")
        return ""

def domain_of(url):
    try:
        return urllib.parse.urlparse(url).netloc.lower().replace('www.', '')
    except:
        return ""

def is_allowed(url):
    domain = domain_of(url)
    return any(domain.endswith(d) for d in ALLOWED_DOMAINS)

def ddg_search(query, max_results=5):
    """Search DuckDuckGo"""
    try:
        q = urllib.parse.quote_plus(query)
        url = f"https://html.duckduckgo.com/html/?q={q}"
        html = fetch_url(url)
        
        if not html:
            return []
        
        # Extract links
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
        logger.error(f"Search error: {e}")
        return []

def gather_sources(question):
    """Gather information sources"""
    sources = []
    
    # Search online
    search_terms = [
        f"{question} Navajo Diné culture",
        f"{question} Navajo tradition"
    ]
    
    for term in search_terms:
        urls = ddg_search(term, max_results=3)
        for url in urls:
            try:
                html = fetch_url(url)
                if html:
                    parser = TextExtractor()
                    parser.feed(html)
                    text = parser.get_text()
                    
                    if text and len(text) > 100:
                        # Calculate trust score
                        domain = domain_of(url)
                        trust = DOMAIN_TRUST.get(domain, 0.50)
                        
                        sources.append({
                            'url': url,
                            'domain': domain,
                            'trust': trust,
                            'text': text[:3000]
                        })
            except Exception as e:
                logger.error(f"Error processing {url}: {e}")
                continue
    
    # Sort by trust score
    sources.sort(key=lambda x: x.get('trust', 0), reverse=True)
    return sources[:5]

def generate_answer(question, sources):
    """Generate answer from sources"""
    if not sources:
        return "I couldn't find any relevant sources. Please try rephrasing your question."
    
    # Get the best source
    best_source = sources[0]
    text = best_source.get('text', '')
    
    # Find relevant paragraphs
    paragraphs = text.split('\n')
    relevant = []
    question_words = set(question.lower().split())
    
    for para in paragraphs:
        if len(para) > 100:
            score = sum(1 for word in question_words if word in para.lower())
            if score > 0:
                relevant.append((score, para))
    
    relevant.sort(reverse=True)
    
    # Build answer
    answer_parts = []
    answer_parts.append(f'<div style="line-height: 1.6;">')
    
    if relevant:
        # Add summary
        answer_parts.append('<p><strong>📖 Information:</strong></p>')
        for i in range(min(2, len(relevant))):
            answer_parts.append(f'<p>{relevant[i][1][:500]}...</p>')
    
    # Add sources
    answer_parts.append('<hr>')
    answer_parts.append('<p><strong>📚 Sources:</strong></p>')
    answer_parts.append('<ul>')
    for i, source in enumerate(sources[:3], 1):
        url = source.get('url', 'Unknown')
        trust_badge = get_trust_badge(source.get('trust', 0.5))
        answer_parts.append(f'<li style="margin-bottom: 8px;">[{i}] {url} {trust_badge}</li>')
    answer_parts.append('</ul>')
    answer_parts.append('</div>')
    
    return '\n'.join(answer_parts)

# HTML Template
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Diné Cultural Learning Bot</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        
        .container {
            max-width: 800px;
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
        
        .header h1 {
            font-size: 2em;
            margin-bottom: 10px;
        }
        
        .content {
            padding: 30px;
        }
        
        .protocol-box {
            background: #fef3c7;
            border-left: 4px solid #f59e0b;
            padding: 15px;
            border-radius: 10px;
            margin-bottom: 20px;
            font-size: 14px;
        }
        
        .welcome-box {
            background: #e8f5e9;
            padding: 20px;
            border-radius: 12px;
            margin-bottom: 20px;
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
        
        .submit-btn {
            background: #2c5f2d;
            color: white;
            border: none;
            padding: 12px 30px;
            border-radius: 25px;
            font-size: 16px;
            cursor: pointer;
            margin-top: 15px;
            transition: background 0.3s;
        }
        
        .submit-btn:hover:not(:disabled) {
            background: #1e3a1e;
        }
        
        .submit-btn:disabled {
            background: #95a5a6;
            cursor: not-allowed;
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
        
        .answer {
            background: #f9f9f9;
            padding: 20px;
            border-radius: 12px;
            margin-top: 20px;
            border-left: 4px solid #2c5f2d;
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
        
        hr {
            margin: 15px 0;
        }
        
        ul {
            margin-left: 20px;
            margin-top: 10px;
        }
        
        li {
            margin-bottom: 8px;
            word-break: break-all;
        }
        
        @media (max-width: 600px) {
            .content {
                padding: 20px;
            }
            
            .example-btn {
                font-size: 11px;
                padding: 6px 12px;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🌾 Diné Cultural Learning Bot</h1>
            <p>Learn about Navajo traditions, language, and values</p>
        </div>
        
        <div class="content">
            <div class="protocol-box">
                🌄 <strong>Cultural Note:</strong> Some Diné traditions contain sacred knowledge not shared publicly. 
                This chatbot provides general cultural information from published educational sources.
            </div>
            
            <div class="welcome-box">
                <strong>✨ Welcome! Ask me about Diné culture</strong>
                <div class="example-buttons">
                    <button class="example-btn" data-question="What is k'é?">🤝 What is k'é?</button>
                    <button class="example-btn" data-question="Tell me about Navajo clans">👨‍👩‍👧‍👦 Clans</button>
                    <button class="example-btn" data-question="What does hózhó mean?">☯️ Hózhó</button>
                    <button class="example-btn" data-question="Tell me about Navajo weaving">🪶 Weaving</button>
                    <button class="example-btn" data-question="Who were the Navajo Code Talkers?">📡 Code Talkers</button>
                    <button class="example-btn" data-question="What are the four sacred mountains?">⛰️ Sacred Mountains</button>
                </div>
            </div>
            
            <form method="POST" id="questionForm">
                <textarea 
                    name="question" 
                    placeholder="Example: What is k'é? How does the clan system work? Tell me about Navajo weaving..." 
                    id="questionInput"
                    rows="4"
                >{{ question }}</textarea>
                <div>
                    <button type="submit" class="submit-btn" id="submitBtn">Ask Question</button>
                    <div id="loadingIndicator" style="display: none;" class="loading-container">
                        <span class="loading-spinner"></span>
                        <span class="searching-message">Searching Diné sources...</span>
                    </div>
                </div>
            </form>
            
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
            Answers sourced from Diné educational resources and trusted cultural organizations.
            <br>For deeper learning, consult with Diné elders and cultural knowledge holders.
        </div>
    </div>
    
    <script>
        // Example buttons
        document.querySelectorAll('.example-btn').forEach(btn => {
            btn.addEventListener('click', function() {
                document.getElementById('questionInput').value = this.dataset.question;
                document.getElementById('questionForm').submit();
            });
        });
        
        // Loading indicator
        document.getElementById('questionForm').addEventListener('submit', function() {
            const submitBtn = document.getElementById('submitBtn');
            const loadingIndicator = document.getElementById('loadingIndicator');
            
            submitBtn.disabled = true;
            submitBtn.textContent = 'Searching...';
            loadingIndicator.style.display = 'inline-block';
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
        question = request.form.get('question', '')
        
        # Seasonal check
        if SEASONAL_MODE and is_hibernation_season() and mentions_animals(question):
            answer = "During winter months (November-March), we avoid discussing certain animals per Diné tradition. Please ask about other aspects of Diné culture."
        else:
            try:
                # Gather sources with timeout
                sources_result = []
                
                def gather():
                    sources_result.append(gather_sources(question))
                
                thread = threading.Thread(target=gather)
                thread.start()
                thread.join(timeout=20)
                
                if thread.is_alive():
                    answer = "Search is taking longer than expected. Please try a more specific question."
                else:
                    sources = sources_result[0] if sources_result else []
                    answer = generate_answer(question, sources)
                    answer = add_pronunciation_tooltips(answer)
                    
            except Exception as e:
                logger.error(f"Error: {e}")
                answer = "I encountered an issue. Please try again."
    
    return render_template_string(HTML_TEMPLATE, question=question, answer=answer, random_fact=random_fact)

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)
