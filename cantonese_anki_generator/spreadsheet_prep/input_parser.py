"""
Input parsing utilities for spreadsheet preparation.

Handles mixed-language input containing English terms, Chinese characters,
and pinyin/jyutping romanization, separating them into their respective fields.
"""

import re
from dataclasses import dataclass
from typing import List


# Maximum letter count (before tone digit) for Jyutping/Pinyin syllables.
# Longest real Jyutping: "gwong" (5 letters). Longest Pinyin: "zhuang" (6 letters).
# We use 5 as the max — this correctly rejects "lesson1" (6 letters) and
# "unit3" (4 letters has vowels but we catch it differently).
# The rare 6-letter Pinyin "zhuang" is an acceptable false negative since
# it's uncommon and the user can use delimiters for such cases.
_MAX_ROMANIZATION_LETTERS = 5

# Vowels that must appear in a valid romanization syllable.
# This prevents matching English words like "mp3" or "nth5".
_ROMANIZATION_VOWELS = set('aeiouüAEIOUÜ')


@dataclass
class ParsedEntry:
    """A parsed vocabulary entry with separated language components."""
    english: str
    cantonese: str = ""
    jyutping: str = ""


def _is_cjk_char(char: str) -> bool:
    """Check if a character is a CJK (Chinese/Japanese/Korean) character."""
    if len(char) != 1:
        return False
    cp = ord(char)
    # CJK Unified Ideographs
    if 0x4E00 <= cp <= 0x9FFF:
        return True
    # CJK Unified Ideographs Extension A
    if 0x3400 <= cp <= 0x4DBF:
        return True
    # CJK Unified Ideographs Extension B
    if 0x20000 <= cp <= 0x2A6DF:
        return True
    # CJK Compatibility Ideographs
    if 0xF900 <= cp <= 0xFAFF:
        return True
    # CJK Unified Ideographs Extension C-F
    if 0x2A700 <= cp <= 0x2CEAF:
        return True
    # CJK Radicals Supplement
    if 0x2E80 <= cp <= 0x2EFF:
        return True
    # Kangxi Radicals
    if 0x2F00 <= cp <= 0x2FDF:
        return True
    # CJK Symbols and Punctuation
    if 0x3000 <= cp <= 0x303F:
        return True
    # Fullwidth forms
    if 0xFF00 <= cp <= 0xFFEF:
        return True
    return False


def _contains_cjk(text: str) -> bool:
    """Check if text contains any CJK characters."""
    return any(_is_cjk_char(c) for c in text)


def _is_jyutping_token(token: str) -> bool:
    """
    Check if a token looks like Jyutping romanization.

    Jyutping format: 1-6 letters (containing a vowel) + tone number (1-6).
    Examples: nei5, hou2, m4, gam2, sik1, jat1

    Rejects words like "lesson1", "mp3" — they are too long or lack vowels.
    The special case "m4" (唔) and "ng5" (五) are valid single-consonant
    Jyutping syllables, so we allow them explicitly.
    """
    token = token.strip()
    if len(token) < 2:
        return False
    letters = token[:-1]
    digit = token[-1]
    if not digit.isdigit() or int(digit) < 1 or int(digit) > 6:
        return False
    if not letters.isalpha():
        return False
    if len(letters) > _MAX_ROMANIZATION_LETTERS:
        return False
    # Must contain a vowel, OR be a known consonant-only syllable (m, ng, n)
    if not (any(c in _ROMANIZATION_VOWELS for c in letters)
            or letters.lower() in ('m', 'ng', 'n', 'hm', 'hng')):
        return False
    return True


def _is_pinyin_token(token: str) -> bool:
    """
    Check if a token looks like pinyin romanization.

    Pinyin can have tone marks (ā, á, ǎ, à) or tone numbers (1-5).
    Examples: nǐ, hǎo, ma, ni3, hao3

    Rejects long words that happen to end in a digit, and words without vowels.
    """
    token = token.strip()
    if not token:
        return False

    # Check for tone marks (common in pinyin) — these are definitive
    tone_marks = set('āáǎàēéěèīíǐìōóǒòūúǔùǖǘǚǜ')
    if any(c in tone_marks for c in token):
        return True

    # Pinyin with tone numbers (1-5)
    if len(token) < 2:
        return False
    letters = token[:-1]
    digit = token[-1]
    if not digit.isdigit() or int(digit) < 1 or int(digit) > 5:
        return False
    if not letters.isalpha():
        return False
    if len(letters) > _MAX_ROMANIZATION_LETTERS:
        return False
    # Must contain a vowel
    if not any(c in _ROMANIZATION_VOWELS for c in letters):
        return False
    return True


def _is_romanization_sequence(text: str) -> bool:
    """
    Check if a text segment is a sequence of Jyutping or Pinyin tokens.

    Requires that *all* non-empty tokens match romanization patterns,
    AND that there are at least 2 matching tokens. A single token like
    "unit3" is too ambiguous to classify as romanization on its own.

    Examples:
        "nei5 hou2"  -> True  (Jyutping, 2 tokens)
        "nǐ hǎo"    -> True  (Pinyin with tone marks)
        "ni3 hao3"   -> True  (Pinyin with tone numbers)
        "hello world" -> False (English)
        "unit3"       -> False (single token, ambiguous)
    """
    tokens = text.strip().split()
    if not tokens:
        return False

    match_count = 0
    for token in tokens:
        clean = token.strip('.,;:!?()[]{}')
        if not clean:
            continue
        if not (_is_jyutping_token(clean) or _is_pinyin_token(clean)):
            return False
        match_count += 1

    # Require at least 2 matching tokens to reduce false positives
    return match_count >= 2


def _extract_cjk_segment(text: str) -> str:
    """
    Extract CJK characters and any characters embedded between them
    (digits, CJK punctuation) from text.

    Preserves digits that appear between CJK characters (e.g., "第1課" -> "第1課").
    """
    cjk_punctuation = set('，。、！？：；「」『』（）')
    result = []
    for char in text:
        if _is_cjk_char(char) or char in cjk_punctuation:
            result.append(char)
        elif result and (char.isdigit() or char == ' '):
            # Keep digits and spaces that appear after CJK content
            # (they may be embedded, e.g., "第1課" or "你 好")
            result.append(char)
        elif result and not char.isascii():
            # Keep other non-ASCII chars that might be related
            result.append(char)

    # Trim trailing non-CJK characters (spaces/digits at the end)
    text_out = ''.join(result)
    # Strip trailing spaces and digits that aren't followed by CJK
    text_out = re.sub(r'[\s\d]+$', '', text_out)
    return text_out.strip()


def _extract_english_segment(text: str) -> str:
    """Extract English words (and adjacent digits like 'Lesson 1') from text."""
    # Match sequences of ASCII words, allowing digits
    english_words = re.findall(
        r"[A-Za-z0-9][A-Za-z0-9'\-]*(?:\s+[A-Za-z0-9][A-Za-z0-9'\-]*)*", text
    )
    result_words = []
    for phrase in english_words:
        tokens = phrase.split()
        non_roman_tokens = []
        for t in tokens:
            clean = t.strip('.,;:!?()[]{}')
            if not clean:
                continue
            # Skip tokens that match romanization patterns
            if _is_jyutping_token(clean) or _is_pinyin_token(clean):
                continue
            non_roman_tokens.append(t)
        if non_roman_tokens:
            result_words.append(' '.join(non_roman_tokens))
    return ' '.join(result_words).strip()


def _extract_romanization_segment(text: str) -> str:
    """Extract Jyutping/Pinyin romanization tokens from text."""
    tokens = text.split()
    roman_tokens = []
    for token in tokens:
        clean = token.strip('.,;:!?()[]{}')
        if clean and (_is_jyutping_token(clean) or _is_pinyin_token(clean)):
            roman_tokens.append(clean)
    return ' '.join(roman_tokens).strip()


def _split_by_delimiter(line: str) -> List[str]:
    """
    Try to split a line by tab or pipe delimiter.

    Only tab and pipe are used — semicolons and commas are too common in
    natural English text and cause false splits.

    Returns list of parts if a delimiter is found, empty list otherwise.
    """
    # Tab first (most common in copy-paste from spreadsheets)
    if '\t' in line:
        return [p.strip() for p in line.split('\t') if p.strip()]

    # Pipe delimiter
    if '|' in line:
        return [p.strip() for p in line.split('|') if p.strip()]

    return []


def _is_romanization_token(text: str) -> bool:
    """Check if a single token is a Jyutping or Pinyin romanization."""
    clean = text.strip().strip('.,;:!?()[]{}')
    return bool(clean) and (_is_jyutping_token(clean) or _is_pinyin_token(clean))


def _classify_segment(text: str) -> str:
    """
    Classify a text segment as 'english', 'chinese', or 'romanization'.
    """
    text = text.strip()
    if not text:
        return 'unknown'

    if _contains_cjk(text):
        return 'chinese'

    if _is_romanization_sequence(text):
        return 'romanization'

    # Check single-token romanization (e.g., "m4", "go2" in a delimited field)
    if _is_romanization_token(text):
        return 'romanization'

    # Default to english for ASCII text
    return 'english'


def parse_line(line: str) -> ParsedEntry:
    """
    Parse a single line of mixed-language input into separated components.

    Handles various input formats:
    - "hello"                       -> english only
    - "hello\\t你好\\tnei5 hou2"   -> tab-delimited
    - "hello | 你好 | nei5 hou2"   -> pipe-delimited
    - "hello 你好 nei5 hou2"       -> space-separated mixed content
    - "你好"                        -> chinese only
    - "nei5 hou2"                   -> romanization only

    Args:
        line: A single line of input text

    Returns:
        ParsedEntry with separated english, cantonese, and jyutping fields
    """
    line = line.strip()
    if not line:
        return ParsedEntry(english="")

    # First, try delimiter-based splitting
    parts = _split_by_delimiter(line)
    if len(parts) >= 2:
        entry = ParsedEntry(english="")
        for part in parts:
            classification = _classify_segment(part)
            if classification == 'english' and not entry.english:
                entry.english = part
            elif classification == 'chinese' and not entry.cantonese:
                entry.cantonese = part
            elif classification == 'romanization' and not entry.jyutping:
                entry.jyutping = part
            elif not entry.english:
                entry.english = part
            elif not entry.cantonese:
                entry.cantonese = part
            elif not entry.jyutping:
                entry.jyutping = part
        return entry

    # No delimiter found — try to separate by language detection
    if _contains_cjk(line):
        english = _extract_english_segment(line)
        cantonese = _extract_cjk_segment(line)
        jyutping = _extract_romanization_segment(line)

        return ParsedEntry(
            english=english,
            cantonese=cantonese,
            jyutping=jyutping
        )

    # Check if the entire line is romanization (require 2+ tokens for whole lines
    # to avoid misclassifying ambiguous single tokens like "unit3")
    if _is_romanization_sequence(line):
        return ParsedEntry(english="", jyutping=line.strip())

    # Default: treat as English term
    return ParsedEntry(english=line.strip())


def parse_input(input_text: str) -> List[str]:
    """
    Parse multi-line input text into a list of English terms.

    This is the legacy interface that returns only English terms.
    For full parsing with column separation, use parse_input_full().

    Splits input by newlines, filters out empty lines, and trims whitespace
    from each term.

    Args:
        input_text: Multi-line string containing English terms

    Returns:
        List of non-empty English terms with whitespace trimmed

    Examples:
        >>> parse_input("hello\\nworld")
        ['hello', 'world']

        >>> parse_input("  hello  \\n\\n  world  \\n")
        ['hello', 'world']

        >>> parse_input("\\n\\n")
        []
    """
    lines = input_text.split('\n')
    terms = [line.strip() for line in lines if line.strip()]
    return terms


def parse_input_full(input_text: str) -> List[ParsedEntry]:
    """
    Parse multi-line input text into structured vocabulary entries.

    Each line is analyzed to separate English terms, Chinese characters,
    and pinyin/jyutping romanization into their respective fields.

    Supports various input formats:
    - One English term per line (will need translation)
    - Tab or pipe-delimited columns (any column order)
    - Mixed content with English, Chinese, and romanization

    Args:
        input_text: Multi-line string containing vocabulary data

    Returns:
        List of ParsedEntry objects with separated language components
    """
    lines = input_text.split('\n')
    entries = []

    for line in lines:
        line = line.strip()
        if not line:
            continue

        entry = parse_line(line)
        if entry.english or entry.cantonese or entry.jyutping:
            entries.append(entry)

    return entries
