import re
import sys
import io
import os
import random
import threading
import logging
import urllib.parse
import urllib.request
import json
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

# Knowledge base for common questions
KNOWLEDGE_BASE = {
    "k'é": """
        <div style="line-height: 1.6;">
            <p><strong>🌿 What is K'é?</strong></p>
            <p><strong>K'é</strong> is one of the most important concepts in Diné culture. It refers to the system of relationships, kinship, and responsibilities that connect all people, family, and community.</p>
            
            <p><strong>Key Principles of K'é:</strong></p>
            <ul>
                <li><strong>K'éí dóó áháyá (Kinship and Respect)</strong> - Honoring family and clan relationships</li>
                <li><strong>Áłah nílʼįįh (Cooperation)</strong> - Working together for the good of all</li>
                <li><strong>Hodzil (Strength through Unity)</strong> - Finding strength in community bonds</li>
            </ul>
            
            <p>When Diné people meet, they introduce themselves by sharing their clans. This practice immediately establishes kinship connections. A traditional introduction follows this pattern:</p>
            <ul>
                <li>"My mother's clan is..." (your primary identity)</li>
                <li>"My father's clan is..." (your father's lineage)</li>
                <li>"My maternal grandfather's clan is..."</li>
                <li>"My paternal grandfather's clan is..."</li>
            </ul>
            
            <p>K'é teaches that we are all related and have responsibilities to care for one another, showing respect, generosity, and kindness in all relationships.</p>
        </div>
    """,
    
    "clan": """
        <div style="line-height: 1.6;">
            <p><strong>🏠 Navajo Clans (Dóoneʼé)</strong></p>
            <p>The Navajo clan system is matrilineal, meaning clan membership passes through the mother. There are over 100 recognized Navajo clans today.</p>
            
            <p><strong>The Four Original Clans:</strong></p>
            <ul>
                <li><strong>Kinyaa'áanii</strong> (Towering House Clan)</li>
                <li><strong>Honágháahnii</strong> (One-walks-around Clan)</li>
                <li><strong>Tódich'ii'nii</strong> (Bitter Water Clan)</li>
                <li><strong>Hashtł'ishnii</strong> (Mud Clan)</li>
            </ul>
            
            <p><strong>Why Clans Matter:</strong></p>
            <ul>
                <li>Clans determine who you can marry (you cannot marry within your own clan)</li>
                <li>Clans establish kinship bonds across the Navajo Nation</li>
                <li>Clans connect you to ancestors and future generations</li>
                <li>Clans create an extended family network of support</li>
            </ul>
            
            <p>When introducing yourself, you share four generations of clans, creating an immediate family connection with others you meet.</p>
        </div>
    """,
    
    "hózhó": """
        <div style="line-height: 1.6;">
            <p><strong>✨ Hózhó: Beauty, Harmony, and Balance</strong></p>
            <p><strong>Hózhó</strong> is a foundational Diné concept often translated as "beauty," but it encompasses so much more. Hózhó represents living in a state of harmony, balance, peace, wellness, and spiritual beauty.</p>
            
            <p><strong>The Elements of Hózhó:</strong></p>
            <ul>
                <li><strong>Nitsáhákees</strong> (Thinking) - Clear, positive thoughts</li>
                <li><strong>Nahat'á</strong> (Planning) - Living with purpose</li>
                <li><strong>Iiná</strong> (Living) - Active, healthy life</li>
                <li><strong>Sihasin</strong> (Assurance) - Peace and security</li>
            </ul>
            
            <p><strong>Living in Hózhó means:</strong></p>
            <ul>
                <li>Maintaining balance in mind, body, and spirit</li>
                <li>Living in harmony with nature and community</li>
                <li>Walking in beauty on the path of life</li>
                <li>Finding wellness through relationships and purpose</li>
            </ul>
            
            <p>The Hózhóójí ceremony is one of the most important Diné healing ceremonies, restoring balance and beauty when it has been disrupted.</p>
        </div>
    """,
    
    "weaving": """
        <div style="line-height: 1.6;">
            <p><strong>🪶 Navajo Weaving (Diyin Dineʼé Binaaltsoos)</strong></p>
            <p>Navajo weaving is a sacred tradition taught to the Diné by Spider Woman, a holy being. The first loom was said to be made of sky and earth, with weaving tools of sunlight and lightning.</p>
            
            <p><strong>Traditional Weaving Elements:</strong></p>
            <ul>
                <li><strong>Spirit Line (Chʼihóníʼįį)</strong> - A small thread from the center to the edge that lets the weaver's spirit escape from the weaving</li>
                <li><strong>Storm Pattern</strong> - Represents the four sacred mountains and directions</li>
                <li><strong>Eye Dazzler</strong> - Bright, geometric patterns that catch the light</li>
                <li><strong>Chief's Blanket</strong> - Traditional striped patterns with cultural significance</li>
            </ul>
            
            <p><strong>Colors and Meanings:</strong></p>
            <ul>
                <li>White (East) - Dawn, new beginnings</li>
                <li>Blue (South) - Day, water</li>
                <li>Yellow (West) - Evening, harvest</li>
                <li>Black (North) - Night, protection</li>
            </ul>
            
            <p>Traditional Navajo rugs and blankets are not just art - they tell stories, mark ceremonies, and connect weavers to their ancestors.</p>
        </div>
    """,
    
    "code talker": """
        <div style="line-height: 1.6;">
            <p><strong>📡 Navajo Code Talkers</strong></p>
            <p>The Navajo Code Talkers were Navajo Marines who developed an unbreakable code based on the Navajo language during World War II. The Japanese were never able to break this code.</p>
            
            <p><strong>Why the Code Was Unbreakable:</strong></p>
            <ul>
                <li>Navajo was an unwritten language with no published grammar or dictionaries</li>
                <li>The code used Navajo words for military terms (e.g., "turtle" meant tank)</li>
                <li>Code Talkers memorized everything - nothing was written down</li>
                <li>The code was never broken by enemy forces</li>
            </ul>
            
            <p><strong>Legacy:</strong></p>
            <ul>
                <li>Over 400 Navajo served as Code Talkers</li>
                <li>Their work was classified until 1968</li>
                <li>They received Congressional Gold Medals in 2001</li>
                <li>Their service helped win WWII and preserved the Navajo language</li>
            </ul>
            
            <p>The Code Talkers are heroes who used their sacred language to protect their country and their people.</p>
        </div>
    """,
    
    "sacred mountains": """
        <div style="line-height: 1.6;">
            <p><strong>⛰️ The Four Sacred Mountains of the Diné</strong></p>
            <p>The four sacred mountains mark the boundaries of traditional Dinétah (Navajo homeland). They were placed by the Holy People to protect and guide the Diné.</p>
            
            <p><strong>The Four Mountains:</strong></p>
            <ul>
                <li><strong>East - Sisnaajiní</strong> (Blanca Peak, Colorado) - White shell, dawn, new beginnings</li>
                <li><strong>South - Tsoodził</strong> (Mount Taylor, New Mexico) - Turquoise, day, water</li>
                <li><strong>West - Dookʼoʼoosłííd</strong> (San Francisco Peaks, Arizona) - Abalone shell, evening, harvest</li>
                <li><strong>North - Dibé Nitsaa</strong> (Hesperus Peak, Colorado) - Black jet, night, protection</li>
            </ul>
            
            <p><strong>Significance:</strong></p>
            <ul>
                <li>Each mountain is associated with a color, direction, and sacred stone</li>
                <li>The mountains were created as boundaries for Diné territory</li>
                <li>They hold spiritual significance in ceremonies and prayers</li>
                <li>The mountains connect the Diné to their ancestral lands</li>
            </ul>
            
            <p>Even today, the four sacred mountains remain central to Diné identity, spirituality, and connection to the land.</p>
        </div>
    """,
}

def get_answer_from_knowledge(question):
    """Check if the question matches any known topics"""
    q_lower = question.lower()
    
    # Check for keywords
    if any(word in q_lower for word in ["k'é", "k'e", "kinship", "family"]):
        return KNOWLEDGE_BASE["k'é"]
    elif any(word in q_lower for word in ["clan", "clans", "dóoneʼé"]):
        return KNOWLEDGE_BASE["clan"]
    elif any(word in q_lower for word in ["hózhó", "hozho", "harmony", "balance", "beauty"]):
        return KNOWLEDGE_BASE["hózhó"]
    elif any(word in q_lower for word in ["weav", "weaving", "blanket", "rug", "spider woman"]):
        return KNOWLEDGE_BASE["weaving"]
    elif any(word in q_lower for word in ["code talker", "code talkers", "wwii", "world war"]):
        return KNOWLEDGE_BASE["code talker"]
    elif any(word in q_lower for word in ["sacred mountain", "mountains", "sisnaajiní", "tsoodził"]):
        return KNOWLEDGE_BASE["sacred mountains"]
    
    return None

# Enhanced search function with fallback
def search_online(question):
    """Try to search online for answers"""
    try:
        # Use a simple search approach
        search_url = f"https://en.wikipedia.org/wiki/{urllib.parse.quote_plus(question.replace(' ', '_'))}"
        
        # For demo purposes, return None to use knowledge base
        # In production, you'd implement proper search
        return None
    except:
        return None

def generate_answer(question):
    """Generate answer from knowledge base or search"""
    # First check knowledge base
    answer = get_answer_from_knowledge(question)
    if answer:
        return answer
    
    # If not found, try to search online
    search_result = search_online(question)
    if search_result:
        return search_result
    
    # If still nothing, provide helpful response
    return f"""
    <div style="line-height: 1.6;">
        <p><strong>📖 Learning About Diné Culture</strong></p>
        <p>I'm still learning about that specific topic. Here are some related things you might want to explore:</p>
        <ul>
            <li>Ask about <strong>k'é</strong> (kinship and relationships)</li>
            <li>Learn about the <strong>clan system</strong> (how Diné people connect through family)</li>
            <li>Explore <strong>hózhó</strong> (harmony, balance, and beauty)</li>
            <li>Discover <strong>Navajo weaving</strong> traditions</li>
            <li>Learn about the <strong>Code Talkers</strong> and their heroism</li>
            <li>Understand the <strong>four sacred mountains</strong> and their significance</li>
        </ul>
        <p>You can also try asking your question in a different way, or ask about one of these topics above!</p>
        <hr>
        <p><em>💡 Tip: Try asking about specific topics like "What is k'é?" or "Tell me about Navajo clans"</em></p>
    </div>
    """

# HTML Template with improved UI
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
        
        .header h1 {
            font-size: 2em;
            margin-bottom: 10px;
        }
        
        .header p {
            opacity: 0.9;
            font-size: 1.1em;
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
        
        .ask-section {
            margin-bottom: 25px;
        }
        
        .ask-label {
            font-size: 16px;
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
            font-weight: 500;
        }
        
        .submit-btn:hover:not(:disabled) {
            background: #1e3a1e;
            transform: translateY(-2px);
        }
        
        .submit-btn:disabled {
            background: #95a5a6;
            cursor: not-allowed;
        }
        
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
        
        .answer {
            background: #f9f9f9;
            padding: 25px;
            border-radius: 12px;
            margin-top: 25px;
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
            margin: 20px 0;
        }
        
        ul {
            margin-left: 20px;
            margin-top: 10px;
            margin-bottom: 10px;
        }
        
        li {
            margin-bottom: 8px;
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
            <p>Ask your own questions about Navajo traditions, language, and values</p>
        </div>
        
        <div class="content">
            <div class="protocol-box">
                🌄 <strong>Cultural Note:</strong> Some Diné traditions contain sacred knowledge not shared publicly. 
                This chatbot provides general cultural information from published educational sources.
            </div>
            
            <!-- Ask Your Own Question Section -->
            <div class="ask-section">
                <div class="ask-label">✍️ Ask Your Own Question</div>
                <form method="POST" id="questionForm">
                    <textarea 
                        name="question" 
                        placeholder="Example: What is the significance of the number four in Diné culture? How do Navajo clans work? Tell me about traditional healing..." 
                        id="questionInput"
                        rows="4"
                    >{{ question }}</textarea>
                    <div>
                        <button type="submit" class="submit-btn" id="submitBtn">🔍 Ask Question</button>
                        <div id="loadingIndicator" style="display: none;" class="loading-container">
                            <span class="loading-spinner"></span>
                            <span class="searching-message">Searching for answer...</span>
                        </div>
                    </div>
                </form>
            </div>
            
            <div class="divider">
                <span>OR TRY ONE OF THESE</span>
            </div>
            
            <!-- Suggested Questions Section -->
            <div class="suggestions-section">
                <div class="suggestions-title">💡 POPULAR QUESTIONS TO EXPLORE</div>
                <div class="example-buttons">
                    <button class="example-btn" data-question="What is k'é?">🤝 What is k'é?</button>
                    <button class="example-btn" data-question="Tell me about Navajo clans">👨‍👩‍👧‍👦 Tell me about Navajo clans</button>
                    <button class="example-btn" data-question="What does hózhó mean?">☯️ What does hózhó mean?</button>
                    <button class="example-btn" data-question="Tell me about Navajo weaving traditions">🪶 Tell me about Navajo weaving</button>
                    <button class="example-btn" data-question="Who were the Navajo Code Talkers?">📡 Who were the Navajo Code Talkers?</button>
                    <button class="example-btn" data-question="What are the four sacred mountains?">⛰️ What are the four sacred mountains?</button>
                </div>
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
            🌄 Learning about Diné culture | Sources: Educational resources, cultural organizations, and Diné teachings<br>
            For deeper learning, consult with Diné elders and cultural knowledge holders.
        </div>
    </div>
    
    <script>
        // Example buttons - fill the textarea and submit
        document.querySelectorAll('.example-btn').forEach(btn => {
            btn.addEventListener('click', function() {
                const questionInput = document.getElementById('questionInput');
                const submitBtn = document.getElementById('submitBtn');
                const loadingIndicator = document.getElementById('loadingIndicator');
                
                // Fill the textarea
                questionInput.value = this.dataset.question;
                
                // Show loading state
                submitBtn.disabled = true;
                submitBtn.textContent = 'Searching...';
                loadingIndicator.style.display = 'inline-block';
                
                // Submit the form
                document.getElementById('questionForm').submit();
            });
        });
        
        // Handle regular form submission
        document.getElementById('questionForm').addEventListener('submit', function() {
            const questionInput = document.getElementById('questionInput');
            const submitBtn = document.getElementById('submitBtn');
            const loadingIndicator = document.getElementById('loadingIndicator');
            
            // Don't submit empty questions
            if (!questionInput.value.trim()) {
                alert('Please enter a question');
                event.preventDefault();
                return false;
            }
            
            // Show loading state
            submitBtn.disabled = true;
            submitBtn.textContent = 'Searching...';
            loadingIndicator.style.display = 'inline-block';
        });
        
        // Clear loading state if page loads with answer
        window.addEventListener('load', function() {
            const submitBtn = document.getElementById('submitBtn');
            const loadingIndicator = document.getElementById('loadingIndicator');
            if (submitBtn && loadingIndicator) {
                submitBtn.disabled = false;
                submitBtn.textContent = '🔍 Ask Question';
                loadingIndicator.style.display = 'none';
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
                # Check seasonal restrictions
                current_month = datetime.now().month
                animal_keywords = ["bear", "coyote", "wolf", "snake", "owl", "eagle"]
                
                if current_month in [11, 12, 1, 2, 3] and any(k in question.lower() for k in animal_keywords):
                    answer = """
                        <div style="line-height: 1.6;">
                            <p><strong>🍂 Seasonal Teaching Protocol</strong></p>
                            <p>During winter months (November-March), traditional Diné teachings advise against discussing certain animals and creation stories. This is a time for reflection, storytelling of other kinds, and preparation for spring.</p>
                            <p>I'd be happy to tell you about other aspects of Diné culture! You can ask about topics like k'é (kinship), the clan system, hózhó (harmony), or Navajo traditions that are appropriate to discuss year-round.</p>
                        </div>
                    """
                else:
                    # Generate answer from knowledge base
                    answer = generate_answer(question)
                    
            except Exception as e:
                logger.error(f"Error: {e}")
                answer = "I encountered an issue. Please try asking your question in a different way."
    
    return render_template_string(HTML_TEMPLATE, question=question, answer=answer, random_fact=random_fact)

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)
