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
from datetime import datetime
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

# Comprehensive knowledge base with better matching
KNOWLEDGE_BASE = {
    "k'e": {
        "keywords": ["k'é", "k'e", "kinship", "family", "relative", "relationship", "relatives", "clan", "family ties", "family bond", "how are people related"],
        "answer": """
            <div style="line-height: 1.6;">
                <p><strong>🌿 What is K'é?</strong></p>
                <p><strong>K'é</strong> is one of the most important concepts in Diné (Navajo) culture. It refers to the system of relationships, kinship, and responsibilities that connect all people, family, community, and even the natural world.</p>
                
                <p><strong>The Four Principles of K'é:</strong></p>
                <ul>
                    <li><strong>K'éí dóó áháyá (Kinship and Respect)</strong> - Honoring family and clan relationships</li>
                    <li><strong>Áłah nílʼįįh (Cooperation)</strong> - Working together for the good of all</li>
                    <li><strong>Hodzil (Strength through Unity)</strong> - Finding strength in community bonds</li>
                    <li><strong>Áłah ałchʼįʼ nahwiildééh (Helping One Another)</strong> - Mutual support and care</li>
                </ul>
                
                <p><strong>How K'é Works:</strong></p>
                <ul>
                    <li>When Diné people meet, they introduce themselves by sharing their clans</li>
                    <li>This practice immediately establishes kinship connections</li>
                    <li>K'é teaches that we are all related and have responsibilities to care for one another</li>
                    <li>It extends beyond blood to include adopted family and community members</li>
                </ul>
                
                <p><strong>Traditional Introduction Pattern:</strong></p>
                <ul>
                    <li>"My mother's clan is..." (your primary identity)</li>
                    <li>"My father's clan is..." (your father's lineage)</li>
                    <li>"My maternal grandfather's clan is..."</li>
                    <li>"My paternal grandfather's clan is..."</li>
                </ul>
                
                <p>K'é teaches respect, generosity, kindness, and responsibility in all relationships.</p>
            </div>
        """
    },
    
    "clan": {
        "keywords": ["clan", "clans", "dóoneʼé", "doonee", "clan system", "matrilineal", "how clans work", "clan structure", "original clans"],
        "answer": """
            <div style="line-height: 1.6;">
                <p><strong>🏠 Navajo Clans (Dóoneʼé)</strong></p>
                <p>The Navajo clan system is <strong>matrilineal</strong>, meaning clan membership passes through the mother. This system has existed for centuries and there are over 100 recognized Navajo clans today.</p>
                
                <p><strong>The Four Original Clans:</strong></p>
                <ul>
                    <li><strong>Kinyaa'áanii</strong> (Towering House Clan) - The first clan, created from the Towering House people</li>
                    <li><strong>Honágháahnii</strong> (One-walks-around Clan) - Those who walk around the sacred mountains</li>
                    <li><strong>Tódich'ii'nii</strong> (Bitter Water Clan) - People of the bitter water, associated with water sources</li>
                    <li><strong>Hashtł'ishnii</strong> (Mud Clan) - People of the mud or earth</li>
                </ul>
                
                <p><strong>Why Clans Matter:</strong></p>
                <ul>
                    <li><strong>Marriage Rules:</strong> You cannot marry within your own clan or your father's clan</li>
                    <li><strong>Identity:</strong> Your clan establishes your identity and place in the community</li>
                    <li><strong>Connection:</strong> Clans create kinship bonds across the entire Navajo Nation</li>
                    <li><strong>Ancestry:</strong> Clans connect you to ancestors and future generations</li>
                    <li><strong>Support Network:</strong> Your clan provides a network of family support wherever you go</li>
                </ul>
                
                <p><strong>Clan Introduction:</strong><br>
                When Diné people introduce themselves, they share four generations of clans:<br>
                "Áshįįhí nishłį́" (I am Salt Clan)<br>
                "Tódichʼiiʼnii bashishchiin" (Bitter Water Clan is born for me)<br>
                "Kinyaaʼáanii dashicheii" (Towering House is my maternal grandfather)<br>
                "Tábąąhá dashinalí" (Water's Edge is my paternal grandfather)</p>
                
                <p>This introduction immediately establishes family connections with others you meet.</p>
            </div>
        """
    },
    
    "hózhó": {
        "keywords": ["hózhó", "hozho", "harmony", "balance", "beauty", "wellness", "peace", "hozhooji", "walk in beauty", "beautiful"],
        "answer": """
            <div style="line-height: 1.6;">
                <p><strong>✨ Hózhó: Beauty, Harmony, and Balance</strong></p>
                <p><strong>Hózhó</strong> is a foundational Diné concept that is central to Navajo philosophy and way of life. Often translated as "beauty," it encompasses so much more - harmony, balance, peace, wellness, order, and living in a state of spiritual beauty.</p>
                
                <p><strong>The Four Elements of Hózhó:</strong></p>
                <ul>
                    <li><strong>Nitsáhákees</strong> (Thinking) - Clear, positive thoughts and reflection</li>
                    <li><strong>Nahat'á</strong> (Planning) - Living with purpose and intention</li>
                    <li><strong>Iiná</strong> (Living) - Active, healthy, meaningful life</li>
                    <li><strong>Sihasin</strong> (Assurance) - Peace, security, and confidence in the future</li>
                </ul>
                
                <p><strong>Living in Hózhó means:</strong></p>
                <ul>
                    <li>Maintaining balance between mind, body, and spirit</li>
                    <li>Living in harmony with nature, community, and oneself</li>
                    <li>Walking in beauty on the path of life (Hózhóogo naashá)</li>
                    <li>Finding wellness through relationships and purpose</li>
                    <li>Making choices that create beauty in the world</li>
                </ul>
                
                <p><strong>The Hózhóójí Ceremony:</strong><br>
                The Hózhóójí ceremony is one of the most important Diné healing ceremonies. It is performed to restore balance and beauty when it has been disrupted by illness, misfortune, or disharmony. Through prayers, songs, and sand paintings, the ceremony guides a person back to a state of hózhó.</p>
                
                <p><strong>Everyday Hózhó:</strong><br>
                Hózhó isn't just for ceremonies - it's a daily practice of making good choices, maintaining positive relationships, respecting nature, and striving for balance in all aspects of life.</p>
            </div>
        """
    },
    
    "weaving": {
        "keywords": ["weav", "weaving", "weaver", "blanket", "rug", "loom", "spider woman", "spider rock", "spider grandm", "weaving tradition", "navajo rug", "navajo blanket"],
        "answer": """
            <div style="line-height: 1.6;">
                <p><strong>🪶 Navajo Weaving (Diyin Dineʼé Binaaltsoos)</strong></p>
                <p>Navajo weaving is a sacred tradition passed down through generations. According to Diné teachings, the first loom was given to the Navajo people by <strong>Spider Woman</strong> (Na'ashjé'ii Asdzáá), a holy being who taught the Diné how to weave beauty into the world.</p>
                
                <p><strong>The Story of Spider Woman:</strong><br>
                Spider Woman taught the Navajo people to weave, saying that the first loom should be made of sky and earth, with weaving tools of sunlight, lightning, and rain. She taught that weaving is a prayer and a way to create beauty.</p>
                
                <p><strong>Traditional Weaving Elements:</strong></p>
                <ul>
                    <li><strong>Spirit Line (Chʼihóníʼįį)</strong> - A small thread from the center to the edge that lets the weaver's spirit escape from the weaving</li>
                    <li><strong>Storm Pattern</strong> - Represents the four sacred mountains and directions, with zigzag lines representing lightning</li>
                    <li><strong>Eye Dazzler</strong> - Bright, geometric patterns with contrasting colors</li>
                    <li><strong>Chief's Blanket</strong> - Traditional striped patterns with cultural significance</li>
                    <li><strong>Two Grey Hills</strong> - Natural, undyed wool in shades of brown, white, and gray</li>
                    <li><strong>Ganado</strong> - Red background with geometric designs</li>
                </ul>
                
                <p><strong>Colors and Meanings:</strong></p>
                <ul>
                    <li><strong>White (East)</strong> - Dawn, new beginnings, white shell</li>
                    <li><strong>Blue (South)</strong> - Day, water, turquoise</li>
                    <li><strong>Yellow (West)</strong> - Evening, harvest, abalone shell</li>
                    <li><strong>Black (North)</strong> - Night, protection, jet</li>
                </ul>
                
                <p>Traditional Navajo rugs and blankets are not just art - they tell stories, mark ceremonies, and connect weavers to their ancestors.</p>
            </div>
        """
    },
    
    "code talker": {
        "keywords": ["code talker", "code talkers", "wwii", "world war", "world war 2", "world war ii", "navajo code", "unbreakable code", "marine", "code", "encryption"],
        "answer": """
            <div style="line-height: 1.6;">
                <p><strong>📡 The Navajo Code Talkers</strong></p>
                <p>The Navajo Code Talkers were Navajo Marines who developed and used an unbreakable code based on the Navajo language during World War II (1942-1945). Their code was never broken by the enemy and played a crucial role in Allied victory in the Pacific.</p>
                
                <p><strong>Why the Code Was Unbreakable:</strong></p>
                <ul>
                    <li><strong>Unwritten Language:</strong> Navajo was an unwritten language with no published grammar or dictionaries</li>
                    <li><strong>Complex Grammar:</strong> The language's complex syntax and tonal qualities made it impossible for non-speakers to understand</li>
                    <li><strong>Code Within a Code:</strong> Code Talkers created a two-layer code using Navajo words for military terms</li>
                    <li><strong>Memorization:</strong> Code Talkers memorized everything - nothing was ever written down</li>
                    <li><strong>Speed:</strong> They could encode, transmit, and decode a message in seconds</li>
                </ul>
                
                <p><strong>How the Code Worked:</strong></p>
                <ul>
                    <li>Military terms were given Navajo names (e.g., "turtle" meant tank)</li>
                    <li>Letters were represented by Navajo words (A = "wol-la-chee" meaning ant)</li>
                    <li>The code used over 600 terms by war's end</li>
                </ul>
                
                <p><strong>Legacy:</strong></p>
                <ul>
                    <li>Over 400 Navajo served as Code Talkers</li>
                    <li>Their work was classified until 1968</li>
                    <li>Received Congressional Gold Medals in 2001</li>
                    <li>August 14 is National Navajo Code Talkers Day</li>
                </ul>
            </div>
        """
    },
    
    "sacred mountains": {
        "keywords": ["sacred mountain", "sacred mountains", "mountains", "four mountains", "sisnaajiní", "tsoodził", "dookʼoʼoosłííd", "dibé nitsaa", "blanca peak", "mount taylor", "san francisco peaks", "hesperus"],
        "answer": """
            <div style="line-height: 1.6;">
                <p><strong>⛰️ The Four Sacred Mountains of the Diné</strong></p>
                <p>The four sacred mountains were placed by the Holy People to mark the boundaries of Dinétah (traditional Navajo homeland).</p>
                
                <p><strong>The Four Mountains:</strong></p>
                <ul>
                    <li><strong>East - Sisnaajiní (Blanca Peak, Colorado)</strong> - White shell, dawn, new beginnings</li>
                    <li><strong>South - Tsoodził (Mount Taylor, New Mexico)</strong> - Turquoise, day, water</li>
                    <li><strong>West - Dookʼoʼoosłííd (San Francisco Peaks, Arizona)</strong> - Abalone shell, evening, harvest</li>
                    <li><strong>North - Dibé Nitsaa (Hesperus Peak, Colorado)</strong> - Black jet, night, protection</li>
                </ul>
                
                <p><strong>Significance:</strong></p>
                <ul>
                    <li>Each mountain is associated with a sacred stone, color, and direction</li>
                    <li>The mountains were created as boundaries for Diné territory</li>
                    <li>They hold spiritual significance in ceremonies and prayers</li>
                    <li>The mountains are considered living beings that protect the Diné</li>
                </ul>
            </div>
        """
    },
    
    "long walk": {
        "keywords": ["long walk", "bosque redondo", "fort sumner", "1864", "1868", "treaty of 1868", "navajo removal", "forced march", "hweeldi"],
        "answer": """
            <div style="line-height: 1.6;">
                <p><strong>👣 The Long Walk (Hwéeldi)</strong></p>
                <p>The Long Walk (1864-1868) was a tragic period when the U.S. Army forced the Diné people to walk over 300 miles to Bosque Redondo (Hwéeldi) in New Mexico.</p>
                
                <p><strong>What Happened:</strong></p>
                <ul>
                    <li>In 1864, approximately 8,000-10,000 Diné were forced to walk over 300 miles</li>
                    <li>Hundreds died during the journey from harsh conditions</li>
                    <li>At Bosque Redondo, they faced starvation, disease for four years</li>
                    <li>Approximately 2,000 Diné died during this period</li>
                </ul>
                
                <p><strong>The Treaty of 1868:</strong></p>
                <ul>
                    <li>In 1868, a treaty was signed establishing the Navajo Reservation</li>
                    <li>The Diné were allowed to return to their homeland</li>
                    <li>This treaty established the Navajo Nation as a sovereign nation</li>
                </ul>
                
                <p>The Long Walk represents resilience, survival, and the strength of the Diné people.</p>
            </div>
        """
    }
}

def get_answer_from_knowledge(question):
    """Match question to knowledge base with improved keyword matching"""
    q_lower = question.lower()
    
    # Check each topic
    for topic, data in KNOWLEDGE_BASE.items():
        for keyword in data["keywords"]:
            if keyword in q_lower:
                logger.info(f"Matched question to topic: {topic} (keyword: {keyword})")
                return data["answer"]
    
    # If no match found, return None
    return None

def generate_answer(question):
    """Generate answer from knowledge base"""
    # First check knowledge base
    answer = get_answer_from_knowledge(question)
    if answer:
        return answer
    
    # If no match, provide helpful response with suggestions
    return f"""
    <div style="line-height: 1.6;">
        <p><strong>📖 Learning About Diné Culture</strong></p>
        <p>I'm still learning about that specific topic. Here are some topics I can help you with:</p>
        <ul>
            <li><strong>K'é</strong> - kinship, family, and relationships</li>
            <li><strong>Clans (Dóoneʼé)</strong> - the Navajo clan system and matrilineal structure</li>
            <li><strong>Hózhó</strong> - harmony, balance, and beauty</li>
            <li><strong>Navajo Weaving</strong> - traditions, Spider Woman, and rug patterns</li>
            <li><strong>Code Talkers</strong> - the Navajo Marines who created an unbreakable code</li>
            <li><strong>Four Sacred Mountains</strong> - the mountains that mark Diné territory</li>
            <li><strong>The Long Walk</strong> - the forced relocation of 1864-1868</li>
        </ul>
        
        <p><strong>Try asking:</strong></p>
        <ul>
            <li>"What is k'é?"</li>
            <li>"Tell me about Navajo clans"</li>
            <li>"What does hózhó mean?"</li>
            <li>"Tell me about Navajo weaving"</li>
            <li>"Who were the Code Talkers?"</li>
            <li>"What are the four sacred mountains?"</li>
            <li>"What happened during the Long Walk?"</li>
        </ul>
        
        <hr>
        <p><em>💡 Tip: Try using the example buttons above or ask about one of the specific topics listed!</em></p>
    </div>
    """

# HTML Template - COMPLETE
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
            display: flex;
            align-items: center;
            gap: 10px;
        }
        
        .answer-header:before {
            content: "📖";
            font-size: 20px;
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
        
        @keyframes highlight {
            0% { background: #fff3cd; border-left-color: #ffc107; }
            100% { background: #f9f9f9; border-left-color: #2c5f2d; }
        }
        
        .answer-highlight { animation: highlight 2s ease-out; }
        
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
            .answer-header { font-size: 16px; padding: 10px 15px; }
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
            
            <div class="ask-section">
                <div class="ask-label">✍️ Ask Your Own Question</div>
                <form method="POST" id="questionForm">
                    <textarea 
                        name="question" 
                        placeholder="Example: What is k'é? How do Navajo clans work? Tell me about the Code Talkers..." 
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
            
            <div class="suggestions-section">
                <div class="suggestions-title">💡 POPULAR QUESTIONS TO EXPLORE</div>
                <div class="example-buttons">
                    <button class="example-btn" data-question="What is k'é?">🤝 What is k'é?</button>
                    <button class="example-btn" data-question="Tell me about Navajo clans">👨‍👩‍👧‍👦 Tell me about Navajo clans</button>
                    <button class="example-btn" data-question="What does hózhó mean?">☯️ What does hózhó mean?</button>
                    <button class="example-btn" data-question="Tell me about Navajo weaving traditions">🪶 Tell me about Navajo weaving</button>
                    <button class="example-btn" data-question="Who were the Navajo Code Talkers?">📡 Who were the Navajo Code Talkers?</button>
                    <button class="example-btn" data-question="What are the four sacred mountains?">⛰️ What are the four sacred mountains?</button>
                    <button class="example-btn" data-question="What was the Long Walk?">👣 What was the Long Walk?</button>
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
            const answerContent = document.getElementById('answerContent');
            
            if (submitBtn && loadingIndicator) {
                submitBtn.disabled = false;
                submitBtn.textContent = '🔍 Ask Question';
                loadingIndicator.style.display = 'none';
            }
            
            if (answerSection && answerContent) {
                answerSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
                answerContent.classList.add('answer-highlight');
                setTimeout(() => answerContent.classList.remove('answer-highlight'), 2000);
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
                # Seasonal check for animal questions
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
                    answer = generate_answer(question)
                    
            except Exception as e:
                logger.error(f"Error: {e}")
                answer = "I encountered an issue. Please try asking your question in a different way."
    
    return render_template_string(HTML_TEMPLATE, question=question, answer=answer, random_fact=random_fact)

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)
