import re
import os
import glob
import random
import threading
from datetime import datetime, date
from flask import Flask, request, render_template_string

app = Flask(__name__)

# Did You Know facts
DID_YOU_KNOW_FACTS = [
    "The Navajo language was used as a code during WWII by the famous Code Talkers - it was never broken!",
    "K'é (kinship) extends beyond blood relations to include all of creation.",
    "Hózhó is often translated as 'beauty' but encompasses harmony, balance, and wellness.",
]

# ----------------------------
# DOCUMENTS FOLDER - Try multiple possible locations
# ----------------------------
def find_documents_folder():
    """Try to find the documents folder in several possible locations"""
    possible_paths = [
        # Render possible paths
        "/opt/render/project/src/dine_documents",
        "/app/dine_documents",
        "/tmp/dine_documents",
        # Local development paths
        os.path.join(os.path.dirname(__file__), "dine_documents"),
        os.path.join(os.getcwd(), "dine_documents"),
        # Your local path (won't work on Render but works locally)
        "/home/tony-cullen/dine_documents",
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            print(f"✅ Found documents at: {path}")
            return path
    
    # If no folder exists, create one in the current directory
    fallback_path = os.path.join(os.getcwd(), "dine_documents")
    os.makedirs(fallback_path, exist_ok=True)
    print(f"📁 Created documents folder at: {fallback_path}")
    print(f"   Please upload your .txt files here")
    return fallback_path

DOCUMENTS_FOLDER = find_documents_folder()

def load_all_documents():
    """Load ALL text files from the documents folder"""
    documents = []
    
    if not os.path.exists(DOCUMENTS_FOLDER):
        print(f"❌ Folder not found: {DOCUMENTS_FOLDER}")
        return documents
    
    txt_files = glob.glob(os.path.join(DOCUMENTS_FOLDER, "*.txt"))
    print(f"📂 Found {len(txt_files)} text files in {DOCUMENTS_FOLDER}")
    
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
            print(f"   ❌ Error loading {file_path}: {e}")
    
    return documents

def find_answer_in_documents(question, documents):
    """Search through documents for answers"""
    question_lower = question.lower()
    print(f"\n🔍 Searching for: '{question_lower}'")
    
    # Define keywords for different topics
    topic_keywords = {
        "hero_twins": ["hero twin", "hero twins", "monster slayer", "born for water", "naayéé", "neizghání", "yé'iitsoh"],
        "black_god": ["black god", "haashch", "fire god", "haashch'ééshzhiní", "nightway"],
        "k'e": ["k'é", "k'e", "kinship", "clan", "family", "relative"],
        "weaving": ["weav", "weaver", "weaving", "blanket", "rug", "loom", "spider woman"],
    }
    
    # Determine which topic this question is about
    detected_topic = None
    for topic, keywords in topic_keywords.items():
        for keyword in keywords:
            if keyword in question_lower:
                detected_topic = topic
                print(f"   🎯 Detected topic: {topic} (matched keyword: '{keyword}')")
                break
        if detected_topic:
            break
    
    # Score each document
    scored_docs = []
    for doc in documents:
        content_lower = doc['content'].lower()
        filename_lower = doc['filename'].lower()
        score = 0
        
        # Special case for exact filename matches
        if detected_topic == "hero_twins" and "hero_twins" in filename_lower:
            score = 10000
            print(f"   ⭐⭐⭐ FOUND HERO TWINS FILE! +10000 points")
        elif detected_topic == "black_god" and "black_god" in filename_lower:
            score = 10000
            print(f"   ⭐⭐⭐ FOUND BLACK GOD FILE! +10000 points")
        
        # If we have a detected topic, use its keywords
        if detected_topic:
            for keyword in topic_keywords[detected_topic]:
                count = content_lower.count(keyword)
                if count > 0:
                    score += count * 100
                    print(f"   📖 Found '{keyword}' {count} times in {doc['filename']}")
        
        if score > 0:
            scored_docs.append((score, doc))
    
    scored_docs.sort(reverse=True, key=lambda x: x[0])
    
    results = []
    for score, doc in scored_docs[:3]:
        results.append(doc)
        print(f"   ✅ MATCH: {doc['filename']} (score: {score})")
    
    return results

def extract_relevant_text(doc, question):
    """Extract the most relevant paragraphs from a document"""
    content = doc['content']
    question_lower = question.lower()
    
    # Split into paragraphs
    paragraphs = content.split('\n\n')
    if len(paragraphs) < 2:
        paragraphs = content.split('\n')
    
    # Score each paragraph
    scored_paragraphs = []
    for para in paragraphs:
        para = para.strip()
        if len(para) < 50:
            continue
        
        para_lower = para.lower()
        score = 0
        
        # Special keywords boost
        special_keywords = ["hero twin", "monster slayer", "black god", "haashch", "k'é", "kinship"]
        for kw in special_keywords:
            if kw in para_lower:
                score += 100
        
        if score > 0 or len(scored_paragraphs) < 2:
            scored_paragraphs.append((score, para))
    
    scored_paragraphs.sort(reverse=True, key=lambda x: x[0])
    
    # Return top paragraphs
    result = []
    for score, para in scored_paragraphs[:4]:
        para = re.sub(r'\s+', ' ', para)
        if len(para) > 800:
            para = para[:800] + "..."
        result.append(para)
    
    return result

# HTML Template
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
            background: #f0f0f0;
            padding: 12px;
            border-left: 3px solid #2c5f2d;
            margin: 10px 0;
            font-style: italic;
        }
        .source-badge {
            background: #2c5f2d;
            color: white;
            padding: 2px 8px;
            border-radius: 12px;
            font-size: 11px;
            display: inline-block;
            margin-left: 8px;
        }
        .fact-box {
            background: #fff3e0;
            padding: 15px;
            border-radius: 10px;
            margin-top: 20px;
            font-size: 14px;
        }
        .footer {
            background: #f5f5f5;
            padding: 20px;
            text-align: center;
            color: #666;
            font-size: 12px;
        }
        hr { margin: 15px 0; }
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
            </div>
            
            <form method="POST" id="questionForm">
                <textarea name="question" placeholder="Example: Who are the Hero Twins? What is k'é? Who is Black God?" rows="4">{{ question }}</textarea>
                <div>
                    <button type="submit" class="submit-btn" id="submitBtn">🔍 Ask Question</button>
                    <div id="loadingIndicator" style="display: none; margin-left: 15px;">
                        <span class="loading-spinner"></span> Searching your local documents...
                    </div>
                </div>
            </form>
            
            <div class="example-buttons">
                <button class="example-btn" data-question="Who are the Hero Twins?">🏹 Hero Twins</button>
                <button class="example-btn" data-question="Who is Black God?">⭐ Black God</button>
                <button class="example-btn" data-question="What is k'é?">🤝 What is k'é?</button>
                <button class="example-btn" data-question="Tell me about Navajo weaving">🪶 Navajo Weaving</button>
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
            🌄 Answers from your local Diné documents | 📁 {{ doc_count }} documents loaded
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

# Load documents once at startup
print("\n" + "="*60)
print("LOADING DOCUMENTS...")
print("="*60)
ALL_DOCUMENTS = load_all_documents()
print(f"\n✅ Loaded {len(ALL_DOCUMENTS)} documents total")
print("="*60 + "\n")

@app.route('/', methods=['GET', 'POST'])
def home():
    question = ""
    answer = ""
    random_fact = random.choice(DID_YOU_KNOW_FACTS)
    
    if request.method == 'POST':
        question = request.form.get('question', '').strip()
        
        if question:
            try:
                print(f"\n{'='*60}")
                print(f"QUESTION: {question}")
                print(f"{'='*60}")
                
                matching_docs = find_answer_in_documents(question, ALL_DOCUMENTS)
                
                if matching_docs:
                    answer_parts = []
                    answer_parts.append(f'<p><strong>📖 Answer about: {question}</strong></p>')
                    answer_parts.append('<hr>')
                    
                    for doc in matching_docs:
                        source_name = doc['name']
                        answer_parts.append(f'<p><strong>📚 Source: {source_name}</strong> <span class="source-badge">Local Document</span></p>')
                        
                        relevant_text = extract_relevant_text(doc, question)
                        for text in relevant_text:
                            answer_parts.append(f'<blockquote>{text}</blockquote>')
                        answer_parts.append('<hr>')
                    
                    answer = '\n'.join(answer_parts)
                else:
                    answer = f"""
                        <p><strong>📖 No matching documents found.</strong></p>
                        <p>I couldn't find information about that topic in your local documents.</p>
                        <p><strong>Documents available ({len(ALL_DOCUMENTS)} files):</strong></p>
                        <ul>
                    """
                    for doc in ALL_DOCUMENTS[:15]:
                        answer += f"<li>{doc['name']}</li>"
                    answer += "</ul>"
                    
            except Exception as e:
                print(f"ERROR: {e}")
                answer = f"I encountered an issue: {str(e)}"
    
    return render_template_string(HTML_TEMPLATE, 
                                   question=question, 
                                   answer=answer, 
                                   random_fact=random_fact,
                                   doc_count=len(ALL_DOCUMENTS))

if __name__ == "__main__":
    print(f"\n{'='*60}")
    print(f"Starting Diné Cultural Learning Bot...")
    print(f"Documents folder: {DOCUMENTS_FOLDER}")
    print(f"Total documents loaded: {len(ALL_DOCUMENTS)}")
    print(f"{'='*60}\n")
    app.run(host='0.0.0.0', port=5000, debug=True)
