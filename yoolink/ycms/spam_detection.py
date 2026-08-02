# yoolink/ycms/spam_detection.py
import re
import unicodedata

# einfache Keyword-Liste, kannst du nach und nach erweitern
SPAM_KEYWORDS = [
    "free spins",
    "free spin",
    "bonus",
    "cash bonus",
    "claim it",
    "claim now",
    "unlock",
    "reseller price",
    "reseller pricing",
    "time’s running out",
    "times running out",
    "limited offer",
    "up to",          # i.V.m. Betrag
    "discount",
    "casino",
    "slots",
]

CURRENCY_PATTERN = re.compile(r"\b(?:€|eur|usd|gbp|dollar|euro|pound)s?\b", re.IGNORECASE)
URL_PATTERN = re.compile(r"https?://", re.IGNORECASE)


def _has_mixed_scripts(text: str) -> bool:
    """
    Erkennung von Texten, die Latin + z.B. Cyrillic mischen
    (typisch bei „Unlосk Frее Sріns“-Spam mit Fake-Buchstaben).
    """
    scripts = set()

    for ch in text:
        if not ch.isalpha():
            continue
        name = unicodedata.name(ch, "")
        if "LATIN" in name:
            scripts.add("LATIN")
        elif "CYRILLIC" in name:
            scripts.add("CYRILLIC")
        # ggf. weitere Scripts ergänzen

    return len(scripts) > 1


def score_text_for_spam(text: str) -> int:
    score = 0
    t = text.lower()

    # 1) Keywords
    for kw in SPAM_KEYWORDS:
        if kw in t:
            score += 3  # jeder Treffer relativ stark gewichten

    # 2) Links
    link_count = len(URL_PATTERN.findall(text))
    if link_count:
        score += link_count * 2

    # 3) Währungen / Preise
    if CURRENCY_PATTERN.search(text):
        score += 2

    # 4) Sehr viel Großbuchstaben (oft „SCHREI“-Marketing)
    letters = [c for c in text if c.isalpha()]
    if letters:
        upper = sum(1 for c in letters if c.isupper())
        ratio = upper / len(letters)
        if ratio > 0.6 and len(letters) > 10:
            score += 2

    # 5) Gemischte Alphabete (z.B. Latin + Cyrillic => Homograph-Spam)
    if _has_mixed_scripts(text):
        score += 4

    return score

RU_EMAIL_PATTERN = re.compile(r'@[^@\s]+\.ru$', re.IGNORECASE)

def is_spam_message(message_obj) -> bool:
    """
    message_obj = dein Message-Modell (mit .title und .message)
    """
    # 1) .ru-Mails direkt als Spam
    email = (getattr(message_obj, "email", "") or "").strip()
    if RU_EMAIL_PATTERN.search(email):
        return True

    # 2) Restliche Heuristik wie vorher
    parts = []
    if getattr(message_obj, "title", None):
        parts.append(message_obj.title)
    if getattr(message_obj, "message", None):
        parts.append(message_obj.message)

    full_text = "\n".join(parts)

    score = score_text_for_spam(full_text)

    # Threshold wie gehabt
    return score >= 4
