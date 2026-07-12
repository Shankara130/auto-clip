import re
from collections import Counter

_STOPWORDS = {"the", "a", "an", "to", "of", "and", "is", "in", "this", "we", "our", "it", "that", "for", "on", "with", "how", "today"}

def _extract_entities(text: str) -> list[str]:
    """Stub NER: kata berhuruf kapital (nama dir). Naif"""
    matches = re.findall(r"\b[A-Z][a-zA-Z]+\b", text)
    return list(dict.fromkeys(matches))

def _extract_keywords(text: str, top_n: int = 5) -> list[str]:
    """Keyword = kata sering (tanpa stopword)"""
    words = re.findall(r"[a-z]+", text.lower())
    words = [w for w in words if w not in _STOPWORDS and len(w) > 2]
    return [w for w, _ in Counter(words).most_common(top_n)]

def analyze_text(text: str) -> dict:
    """Text -> {entities, keywords}. Stub (tanpa LLM)"""
    return {"entities": _extract_entities(text), "keywords": _extract_keywords(text)}