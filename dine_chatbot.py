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

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Did You Know facts
DID_YOU_KNOW_FACTS = [
    "The Navajo language was used as a code during WWII by the famous Code Talkers - it was never broken!",
    "K'é (kinship) extends beyond blood relations to include all of creation.",
    "Hózhó is often translated as 'beauty' but encompasses harmony, balance, and wellness.",
    "Traditional Navajo hogans are built with the door facing east to greet the morning sun.",
    "The four sacred mountains mark the boundaries of traditional Dinétah (Navajo homeland).",
    "Weaving was taught to the Navajo by Spider Woman, a holy being.",
]

# PDF Support Check
try:
    import PyPDF2
    PDF_SUPPORT = True
except ImportError:
    PyPDF2 = None
    PDF_SUPPORT = False

# ----------------------------
# Configure allowlist
# ----------------------------
ALLOWED_DOMAINS = [
    "navajo-nsn.gov", "courts.navajo-nsn.gov", "navajocourts.org",
    "dinecollege.edu", "navajolanguageacademy.org", "nau.edu",
    "navajotimes.com", "ictnews.org", "indiancountrytoday.com",
    "americanindian.si.edu", "loc.gov", "pbs.org",
    "navajopeople.org", "navajoculture.org",
]

# Domain trust scores
DOMAIN_TRUST = {
    "navajo-nsn.gov": 1.00,
    "navajopeople.org": 0.95,
    "dinecollege.edu": 0.95,
    "navajotimes.com": 0.85,
    "ictnews.org": 0.82,
    "americanindian.si.edu": 0.80,
}

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
        if tag in ('p', 'br', 'div', 'h1', 'h2', 'h3'):
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

def ddg_search(query, max_results=8):
    """Search DuckDuckGo"""
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
        logger.error(f"Search error: {e}")
        return []

def gather_sources(question):
    """Gather information sources"""
    sources = []
    
    # Build search query based on question
    q_lower = question.lower()
    
    # Specific topic handling
    if "hero twin" in q_lower or "monster slayer" in q_lower or "born for water" in q_lower:
        search_terms = [
            f"Navajo Hero Twins Monster Slayer Born for Water legend",
            f"Changing Woman sons Navajo mythology"
        ]
    elif "black god" in q_lower or "haashch" in q_lower:
        search_terms = [
            f"Black God Haashchʼééshzhiní Navajo stars creation",
            f"Navajo Black God constellation fire god"
        ]
    elif "star" in q_lower:
        search_terms = [
            f"Navajo star creation Black God mythology",
            f"How Navajo stars were placed in sky legend"
        ]
    elif "long walk" in q_lower:
        search_terms = [
            f"Navajo Long Walk Hwéeldi 1864 Bosque Redondo",
            f"Treaty of 1868 Navajo history"
        ]
    else:
        search_terms = [f"{question} Navajo Diné culture legend"]
    
    for term in search_terms:
        urls = ddg_search(term, max_results=4)
        for url in urls:
            try:
                html = fetch_url(url)
                if html:
                    parser = TextExtractor()
                    parser.feed(html)
                    text = parser.get_text()
                    
                    if text and len(text) > 200:
                        domain = domain_of(url)
                        trust = DOMAIN_TRUST.get(domain, 0.50)
                        
                        sources.append({
                            'url': url,
                            'domain': domain,
                            'trust': trust,
                            'text': text
                        })
            except Exception as e:
                logger.error(f"Error processing {url}: {e}")
                continue
    
    # Remove duplicates by URL
    seen = set()
    unique_sources = []
    for s in sources:
        if s['url'] not in seen:
            seen.add(s['url'])
            unique_sources.append(s)
    
    unique_sources.sort(key=lambda x: x.get('trust', 0), reverse=True)
    return unique_sources[:5]

def generate_answer(question, sources):
    """Generate answer from sources by finding the most relevant paragraphs"""
    if not sources:
        return """
        <div style="line-height: 1.6;">
            <p><strong>📖 I couldn't find any relevant sources.</strong></p>
            <p>Please try one of these questions:</p>
            <ul>
                <li>Who are the Hero Twins?</li>
                <li>Who is Black God?</li>
                <li>How were the stars created?</li>
                <li>What is the Long Walk?</li>
            </ul>
        </div>
        """
    
    q_lower = question.lower()
    best_source = sources[0]
    text = best_source.get('text', '')
    
    # Split into paragraphs
    paragraphs = [p.strip() for p in text.split('\n') if len(p.strip()) > 100]
    
    # Define keywords for different topics
    topic_keywords = {
        "hero_twins": ["hero twin", "monster slayer", "born for water", "changing woman", "nayé nazgháné", "túbaadeschine", "twins", "slayer of monsters"],
        "black_god": ["black god", "haashch", "fire god", "stars", "constellation"],
        "stars": ["star", "stars", "constellation", "sky", "heavens", "black god"],
        "long_walk": ["long walk", "bosque redondo", "hweeldi", "1864", "fort sumner"],
        "k'e": ["k'é", "k'e", "kinship", "family", "clan"],
        "clan": ["clan", "clans", "matrilineal", "dóoneʼé"],
        "weaving": ["weav", "spider woman", "loom", "blanket", "rug"],
    }
    
    # Determine which topic
    current_topic = None
    for topic, keywords in topic_keywords.items():
        if any(k in q_lower for k in keywords):
            current_topic = topic
            break
    
    # Score paragraphs by relevance
    scored = []
    for para in paragraphs:
        para_lower = para.lower()
        score = 0
        
        if current_topic == "hero_twins":
            hero_keywords = ["hero twin", "monster slayer", "born for water", "changing woman", "twin", "slayer", "nayé", "túbaadeschine", "sons", "white shell woman"]
            for kw in hero_keywords:
                if kw in para_lower:
                    score += 15
        elif current_topic == "black_god":
            bg_keywords = ["black god", "haashch", "fire god", "star", "fire", "darkness"]
            for kw in bg_keywords:
                if kw in para_lower:
                    score += 15
        elif current_topic == "stars":
            star_keywords = ["star", "stars", "constellation", "black god", "sky", "heavens", "placed"]
            for kw in star_keywords:
                if kw in para_lower:
                    score += 15
        elif current_topic == "long_walk":
            lw_keywords = ["long walk", "bosque redondo", "hweeldi", "1864", "fort sumner", "forced", "march"]
            for kw in lw_keywords:
                if kw in para_lower:
                    score += 15
        
        # Also check for question words
        for word in q_lower.split()[:5]:
            if len(word) > 3 and word in para_lower:
                score += 2
        
        if score > 0:
            scored.append((score, para))
    
    scored.sort(reverse=True)
    
    # Build answer
    answer_parts = []
    answer_parts.append('<div style="line-height: 1.6;">')
    
    # Add introduction based on topic
    if "hero twin" in q_lower or "monster slayer" in q_lower:
        answer_parts.append('<p><strong>🏹 The Hero Twins: Monster Slayer and Born for Water</strong></p>')
        answer_parts.append('<p>The Hero Twins (Naayééʼ Neizghání - Monster Slayer and Tó Bájísh Chíní - Born for Water) are central figures in Diné mythology, born to Changing Woman:</p>')
        answer_parts.append('<hr>')
    elif "black god" in q_lower:
        answer_parts.append('<p><strong>⭐ Black God (Haashchʼééshzhiní)</strong></p>')
        answer_parts.append('<p>Black God is a powerful Holy Person in Diné cosmology who placed the stars in the sky:</p>')
        answer_parts.append('<hr>')
    elif "star" in q_lower:
        answer_parts.append('<p><strong>✨ The Creation of the Stars</strong></p>')
        answer_parts.append('<p>According to Diné tradition, the stars were placed in the sky by the Holy People:</p>')
        answer_parts.append('<hr>')
    else:
        answer_parts.append(f'<p><strong>📖 About: {question}</strong></p>')
        answer_parts.append('<hr>')
    
    # Add the best paragraphs
    if scored:
        for i in range(min(3, len(scored))):
            para = scored[i][1]
            # Clean up the paragraph
            para = re.sub(r'\s+', ' ', para)
            # Limit length
            if len(para) > 800:
                para = para[:800] + '...'
            answer_parts.append(f'<p>{para}</p>')
    else:
        # Fallback to first few paragraphs
        for p in paragraphs[:2]:
            if len(p) > 100:
                answer_parts.append(f'<p>{p[:600]}...</p>')
    
    answer_parts.append('<hr>')
    
    # Add source
    source_url = best_source.get('url', 'Unknown')
    trust = best_source.get('trust', 0.5)
    trust_badge = ''
    if trust >= 0.95:
        trust_badge = '<span style="background: #2ecc71; color: white; padding: 2px 8px; border-radius: 12px; font-size: 11px;">✓ Verified Source</span>'
    elif trust >= 0.80:
        trust_badge = '<span style="background: #3498db; color: white; padding: 2px 8px; border-radius: 12px; font-size: 11px;">📚 Trusted Source</span>'
    
    answer_parts.append(f'<p><strong>Source:</strong> <a href="{source_url}" target="_blank">{source_url}</a> {trust_badge}</p>')
    answer_parts.append('<p style="font-size: 12px; color: #666; margin-top: 10px;"><em>Note: Traditional Diné stories are passed down orally. This excerpt comes from published sources. Consult with Diné cultural knowledge holders for deeper understanding.</em></p>')
    answer_parts.append('</div>')
    
    return '\n'.join(answer_parts)

# HTML Template (complete, with all UI features)
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
                        placeholder="Example: Who are the Hero Twins? Who is Black God? How were the stars created? What is k'é?" 
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
                    <button class="example-btn" data-question="Who are the Hero Twins?">🏹 Who are the Hero Twins?</button>
                    <button class="example-btn" data-question="Who is Black God?">⭐ Who is Black God?</button>
                    <button class="example-btn" data-question="How were the stars created?">✨ How were the stars created?</button>
                    <button class="example-btn" data-question="What is k'é?">🤝 What is k'é?</button>
                    <button class="example-btn" data-question="Tell me about Navajo clans">👨‍👩‍👧‍👦 Tell me about Navajo clans</button>
                    <button class="example-btn" data-question="What does hózhó mean?">☯️ What does hózhó mean?</button>
                    <button class="example-btn" data-question="What happened during the Long Walk?">👣 The Long Walk</button>
                    <button class="example-btn" data-question="Who were the Navajo Code Talkers?">📡 Code Talkers</button>
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
            🌄 Learning about Diné culture | Sources: Educational resources, cultural organizations, and Diné teachings
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
                    answer = generate_answer(question, sources)
                    
            except Exception as e:
                logger.error(f"Error: {e}")
                answer = "I encountered an issue. Please try again."
    
    return render_template_string(HTML_TEMPLATE, question=question, answer=answer, random_fact=random_fact)

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)
