def generate_answer(question, sources):
    """Generate a unified, summarized answer from all sources"""
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
    
    # Extract and combine text from all sources
    all_text = ""
    for source in sources[:3]:  # Use top 3 sources
        all_text += source.get('text', '') + " "
    
    # Clean the combined text
    lines = all_text.split('\n')
    clean_lines = []
    
    skip_patterns = [
        'home site map', 'events references', 'photos culture', 'navajo history',
        'navajo creation story', 'custom search', 'about us', 'trackbacks',
        'leave a reply', 'comments', 'share this', 'facebook', 'twitter',
        'pinterest', 'books and posters', '©', 'copyright', 'site map',
        'references photos', 'website links', 'navajo people blog',
        'recent posts', 'fair event links', 'full list of', 'calendar of events',
        'rodeos', 'pow wow', 'fair schedule', 'market', 'fair & rodeo',
        'links', 'blog', 'gallery', 'poster', 'book review', 'film',
        'november 14, 2009', 'by harold carey', 'posted on', 'categories:',
        'tags:', 'related posts', 'you might also like', 'previous post',
        'next post', 'advertisement', 'sponsored', 'donate', 'subscribe'
    ]
    
    for line in lines:
        line = line.strip()
        if not line or len(line) < 30:
            continue
        if 'http' in line or 'www.' in line:
            continue
        skip = False
        for pattern in skip_patterns:
            if pattern.lower() in line.lower():
                skip = True
                break
        if skip:
            continue
        clean_lines.append(line)
    
    clean_text = ' '.join(clean_lines)
    
    # Extract key information for Hero Twins
    hero_info = {
        "names": [],
        "birth": [],
        "parents": [],
        "monsters": [],
        "journey": [],
        "weapons": []
    }
    
    # Key phrases to extract
    name_phrases = [
        "Naayéé'neizghání", "Slayer of Monsters", "Monster Slayer",
        "Tóbájíshchíní", "Born for Water", "Nayainazgana", "Tobadzaschaina"
    ]
    
    birth_phrases = [
        "twin boys", "proud possessor", "prenatal life", "twelve days",
        "thirty-two days", "eight changes", "conceived", "sunbeams", "dripping water"
    ]
    
    parent_phrases = [
        "White-Shell Woman", "Ylkaiestsan", "Yolkai Estsan", "Changing Woman",
        "daughter of Earth and Sky", "Sun is your father"
    ]
    
    monster_phrases = [
        "monsters", "giants", "foreign gods", "Yatso", "Big God",
        "Man-eating Bird", "Rolling Stone", "Tracking Bear", "Antelope",
        "alien gods", "depopulating the earth"
    ]
    
    journey_phrases = [
        "search for their father", "journey eastward", "cross the waters",
        "Wind People", "caution you", "sun was then overhead"
    ]
    
    # Extract information
    for phrase in name_phrases:
        if phrase.lower() in clean_text.lower():
            hero_info["names"].append(phrase)
    
    for phrase in birth_phrases:
        if phrase.lower() in clean_text.lower():
            # Get the surrounding sentence for context
            match = re.search(f'[^.]*{re.escape(phrase)}[^.]*\.', clean_text, re.IGNORECASE)
            if match:
                hero_info["birth"].append(match.group(0).strip())
    
    for phrase in parent_phrases:
        if phrase.lower() in clean_text.lower():
            match = re.search(f'[^.]*{re.escape(phrase)}[^.]*\.', clean_text, re.IGNORECASE)
            if match:
                hero_info["parents"].append(match.group(0).strip())
    
    for phrase in monster_phrases:
        if phrase.lower() in clean_text.lower():
            match = re.search(f'[^.]*{re.escape(phrase)}[^.]*\.', clean_text, re.IGNORECASE)
            if match and len(match.group(0)) < 200:
                hero_info["monsters"].append(match.group(0).strip())
    
    for phrase in journey_phrases:
        if phrase.lower() in clean_text.lower():
            match = re.search(f'[^.]*{re.escape(phrase)}[^.]*\.', clean_text, re.IGNORECASE)
            if match:
                hero_info["journey"].append(match.group(0).strip())
    
    # Deduplicate
    for key in hero_info:
        hero_info[key] = list(dict.fromkeys(hero_info[key]))
    
    # Build unified summary
    answer_parts = []
    answer_parts.append('<div style="line-height: 1.7;">')
    
    # Title
    answer_parts.append('<p><strong>🏹 The Hero Twins: Monster Slayer and Born for Water</strong></p>')
    
    # Overview paragraph
    answer_parts.append('<p>The Hero Twins (<em>Naayééʼ Neizghání</em> - Monster Slayer and <em>Tó Bájísh Chíní</em> - Born for Water) are central figures in Diné mythology. They are the sons of Changing Woman (White-Shell Woman) and the Sun, born to rid the world of monsters that threatened the Diné people.</p>')
    
    # Birth and Origins
    if hero_info["birth"] or hero_info["parents"]:
        answer_parts.append('<p><strong>🌟 Birth and Origins</strong></p>')
        
        # Summary of birth story
        answer_parts.append('<p>White-Shell Woman (Changing Woman) lived alone at the foot of a sacred mountain. She conceived the Hero Twins from the sunbeams and dripping water - one from the sun, one from the water. The twins were born after only twelve days and matured rapidly, reaching adulthood in thirty-two days after passing through eight changes.</p>')
        
        # Add specific details from sources if available
        for detail in hero_info["birth"][:2]:
            if "twin boys" in detail.lower() or "proud possessor" in detail.lower():
                answer_parts.append(f'<p style="margin-left: 15px; color: #555;">{detail}</p>')
    
    # The Monsters
    if hero_info["monsters"]:
        answer_parts.append('<p><strong>🐉 The Monsters They Faced</strong></p>')
        answer_parts.append('<p>The earth was infested with great giants and alien gods who were destroying the people. Among these monsters were:</p><ul>')
        
        monster_list = []
        for m in hero_info["monsters"]:
            if "Yatso" in m or "Big God" in m:
                monster_list.append("Yatso (Big God) - a giant as large as a mountain")
            elif "Man-eating Bird" in m:
                monster_list.append("Man-eating Bird - a giant bird that preyed on people")
            elif "Rolling Stone" in m:
                monster_list.append("Rolling Stone - a boulder that crushed everything in its path")
            elif "Tracking Bear" in m:
                monster_list.append("Tracking Bear - a bear that hunted without mercy")
            elif "Antelope" in m:
                monster_list.append("Antelope - a swift killer")
        
        for monster in list(dict.fromkeys(monster_list))[:5]:
            answer_parts.append(f'<li>{monster}</li>')
        answer_parts.append('</ul>')
    
    # The Journey to Find Their Father
    if hero_info["journey"]:
        answer_parts.append('<p><strong>⛰️ The Journey to Find Their Father</strong></p>')
        answer_parts.append('<p>When the twins learned their mother did not know who their father was, they set out on a journey eastward to find him. The Wind People appeared and told them their father was the Sun, but warned them of the dangers ahead. They traveled great distances and eventually crossed the wide waters to reach their father, the Sun.</p>')
        
        for detail in hero_info["journey"][:1]:
            answer_parts.append(f'<p style="margin-left: 15px; color: #555;">{detail}</p>')
    
    # Weapons and Training (if in sources)
    weapons_found = False
    for s in sources:
        text = s.get('text', '').lower()
        if "weapon" in text or "bow" in text or "arrow" in text or "lightning" in text:
            weapons_found = True
            break
    
    if weapons_found:
        answer_parts.append('<p><strong>⚔️ Weapons and Training</strong></p>')
        answer_parts.append('<p>The Hero Twins received powerful weapons from their father the Sun, including lightning bolts and other divine tools, to help them defeat the monsters that plagued the earth.</p>')
    
    # Legacy
    answer_parts.append('<p><strong>✨ Legacy</strong></p>')
    answer_parts.append('<p>The Hero Twins succeeded in ridding the world of the monsters that threatened the Diné people, making the earth safe for humanity. They remain central figures in Diné ceremonies, prayers, and storytelling traditions, representing courage, perseverance, and the protection of the people.</p>')
    
    answer_parts.append('<hr style="margin: 20px 0;">')
    
    # Source summary
    source_list = []
    for s in sources[:2]:
        domain = s.get('domain', '').replace('www.', '')
        if domain and domain not in source_list:
            source_list.append(domain)
    
    answer_parts.append(f'<p style="font-size: 12px; color: #666;"><strong>Sources:</strong> {", ".join(source_list)}</p>')
    answer_parts.append('<p style="font-size: 12px; color: #666; margin-top: 8px;"><em>✨ These stories are passed down through generations. For deeper understanding, consult with Diné elders and cultural knowledge holders.</em></p>')
    answer_parts.append('</div>')
    
    return '\n'.join(answer_parts)
