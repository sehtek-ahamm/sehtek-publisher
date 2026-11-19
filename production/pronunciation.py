"""Pronunciation fixes applied to the voice-over before it goes to ElevenLabs.

The page speaks to a woman in Levantine Arabic. Without vowel marks the voice
often reads «حليبك» as masculine (حليبَك) or «أكل» as formal (أَكْل). These marks
only change the voice; subtitles are drawn without vowel marks.

Add new words here whenever the voice gets one wrong.
"""

import re

# Second-person feminine: word + كِ ending read as ...ِك (e.g. حليبِك).
FEMININE_NOUNS = [
    "طفل", "طفلت", "حليب", "جسم", "صحت", "وزن", "حمل", "رضاعت", "نفاس", "دكتور",
    "طبيب", "طبيبت", "يوم", "سرير", "شنطت", "مطبخ", "بيت", "نوم", "أكل", "بطن",
    "ضغط", "سكر", "دم", "ولادت", "عيلت", "زوج", "إيد", "صحن", "فطور", "غدا",
    "عشا", "مزاج", "تعب", "قلب", "عمر", "شغل", "وقت",
    "عند", "مع", "وجبات", "عضلات", "طول", "معدت", "شعر", "بشرت", "ضهر", "رجل",
]

# Whole-word replacements (Levantine pronunciation).
WORDS = {
    "الأكل": "الأَكِل",
    "أكل": "أَكِل",
    "بالأكل": "بالأَكِل",
    "للأكل": "للأَكِل",
    "وأكل": "وأَكِل",
    "بتعوضك": "بتعوّضِك",
}

PREFIXES = "(?:و|ف|ب|ل|لل|بال|وب|ول|وال)?"
# Arabic letters only (not punctuation such as «،» or «؟»)
L = "[\u0621-\u063A\u0641-\u064A\u0671-\u06D3]"


def _feminine(text: str) -> str:
    for noun in FEMININE_NOUNS:
        # e.g. «طفلك», «لطفلك», «وطفلك» -> «طفلِك» (kasra on the letter before ك)
        pattern = rf"(?<!{L})({PREFIXES}{noun[:-1]})({noun[-1]})ك(?!{L})"
        text = re.sub(pattern, lambda m: f"{m.group(1)}{m.group(2)}ِك", text)
    return text


def _words(text: str) -> str:
    for plain, marked in WORDS.items():
        text = re.sub(rf"(?<!{L}){plain}(?!{L})", marked, text)
    return text


def prepare(text: str) -> str:
    """Return the voice-over text with pronunciation marks added."""
    return _feminine(_words(text))
