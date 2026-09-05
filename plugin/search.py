import re
from typing import List, Dict, Any, Tuple

def _clean_string(text: str) -> str:
    return re.sub(r"[^\w\s]", " ", text.lower()).strip()

def _fuzzy_score(query: str, target: str) -> float:
    q = _clean_string(query)
    t = _clean_string(target)
    if not q or not t:
        return 0.0
    
    if q == t:
        return 100.0
    if t.startswith(q):
        return 95.0
    if f" {q}" in t:
        return 90.0
    if q in t:
        return 85.0
    
    q_words = q.split()
    t_words = t.split()
    matched_words = 0
    for qw in q_words:
        if any(tw.startswith(qw) for tw in t_words):
            matched_words += 1
        elif any(qw in tw for tw in t_words):
            matched_words += 0.8
            
    word_score = (matched_words / len(q_words)) * 80.0
    
    seq_idx = 0
    matches = 0
    for char in q:
        idx = t.find(char, seq_idx)
        if idx != -1:
            matches += 1
            seq_idx = idx + 1
        else:
            break
            
    seq_score = (matches / len(q)) * 60.0 if matches == len(q) else 0.0
    return max(word_score, seq_score)

def search_items(items: List[Dict[str, Any]], query: str, threshold: float = 55.0) -> List[Dict[str, Any]]:
    clean_q = query.strip().lower()
    if not clean_q:
        return items
    
    scored: List[Tuple[float, Dict[str, Any]]] = []
    for item in items:
        name_score = _fuzzy_score(clean_q, item.get("name", ""))
        year_bonus = 5.0 if clean_q in item.get("year", "") else 0.0
        final_score = name_score + year_bonus
        if final_score >= threshold:
            scored.append((final_score, item))
            
    scored.sort(key=lambda x: x[0], reverse=True)
    return [item for _, item in scored]
