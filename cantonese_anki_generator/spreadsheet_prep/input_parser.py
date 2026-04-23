"""
Input parsing utilities for spreadsheet preparation.

Handles mixed-language input containing English terms, Chinese characters,
and pinyin/jyutping romanization, separating them into their respective fields.
"""

import re
import unicodedata
from dataclasses import dataclass
from typing import List, Optional


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
    
    Jyutping format: consonant(s) + vowel(s) + tone number (1-6)
    Examples: nei5, hou2, m4, gam2, sik1, jat1
    """
    # Jyutping pattern: letters followed by a tone number 1-6
    # Allow for compound jyutping separated by spaces
    jyutping_pattern = re.compile(
        r'^[a-z]+[1-6]$', re.IGNORECASE
    )
    return bool(jyutping_pattern.match(token.strip()))


def _is_pinyin_token(token: str) -> bool:
    """
    Check if a token looks like pinyin romanization.
    
    Pinyin can have tone marks (ā, á, ǎ, à) or tone numbers (1-4, 5 for neutral).
    Examples: nǐ, hǎo, ma, ni3, hao3
    """
    # Check for tone marks (common in pinyin)
    tone_marks = set('āáǎàēéěèīíǐìōóǒòūúǔùǖǘǚǜ')
    if any(c in tone_marks for c in token):
        return True
    # Pinyin with tone numbers (1-5)
    pinyin_pattern = re.compile(
        r'^[a-z]+[1-5]$', re.IGNORECASE
    )
    return bool(pinyin_pattern.match(token.strip()))


def _is_romanization_sequence(text: str) -> bool:
    """
    Check if a text segment is a sequence of Jyutping or Pinyin tokens.
    
    Examples:
        "nei5 hou2" -> True (Jyutping)
        "nǐ hǎo" -> True (Pinyin with tone marks)
        "ni3 hao3" -> True (Pinyin with tone numbers)
        "hello world" -> False (English)
    """
    tokens = text.strip().split()
    if not tokens:
        return False
    
    romanization_count = 0
    for token in tokens:
        # Strip common punctuation
        clean = token.strip('.,;:!?()[]{}')
        if not clean:
            continue
        if _is_jyutping_token(clean) or _is_pinyin_token(clean):
            romanization_count += 1
    
    # Consider it romanization if majority of tokens match
    return romanization_count > 0 and romanization_count >= len(tokens) * 0.5


def _extract_cjk_segment(text: str) -> str:
    """Extract contiguous CJK characters (and CJK punctuation) from text."""
    cjk_chars = []
    for char in text:
        if _is_cjk_char(char) or char in '，。、！？：；「」『』（）':
            cjk_chars.append(char)
        elif cjk_chars and char == ' ':
            # Allow single spaces between CJK segments
            continue
    return ''.join(cjk_chars).strip()


def _extract_english_segment(text: str) -> str:
    """Extract English words from text (ASCII letters, common punctuation)."""
    # Match sequences of ASCII words
    english_words = re.findall(r"[A-Za-z][A-Za-z'\-]*(?:\s+[A-Za-z][A-Za-z'\-]*)*", text)
    # Filter out tokens that look like romanization
    result_words = []
    for phrase in english_words:
        tokens = phrase.split()
        non_roman_tokens = []
        for t in tokens:
            clean = t.strip('.,;:!?()[]{}')
            if clean and not _is_jyutping_token(clean) and not _is_pinyin_token(clean):
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


def _split_by_delimiter(line: str) -> Optional[List[str]]:
    """
    Try to split a line by common delimiters (tab, |, comma).
    
    Returns list of parts if a delimiter is found, None otherwise.
    """
    # Try tab first (most common in copy-paste from spreadsheets)
    if '\t' in line:
        return [p.strip() for p in line.split('\t') if p.strip()]
    
    # Try pipe delimiter
    if '|' in line:
        return [p.strip() for p in line.split('|') if p.strip()]
    
    # Try semicolon
    if ';' in line:
        return [p.strip() for p in line.split(';') if p.strip()]
    
    return None


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
    
    # Default to english for ASCII text
    return 'english'


def parse_line(line: str) -> ParsedEntry:
    """
    Parse a single line of mixed-language input into separated components.
    
    Handles various input formats:
    - "hello" -> english only
    - "hello\t你好\tnei5 hou2" -> tab-delimited
    - "hello | 你好 | nei5 hou2" -> pipe-delimited
    - "hello 你好 nei5 hou2" -> space-separated mixed content
    - "你好" -> chinese only
    - "nei5 hou2" -> romanization only
    
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
    if parts and len(parts) >= 2:
        # Classify each part
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
                # If we can't classify, put it in english as fallback
                entry.english = part
            elif not entry.cantonese:
                entry.cantonese = part
            elif not entry.jyutping:
                entry.jyutping = part
        return entry
    
    # No delimiter found — try to separate by language detection
    # Check if the line contains CJK characters
    if _contains_cjk(line):
        english = _extract_english_segment(line)
        cantonese = _extract_cjk_segment(line)
        jyutping = _extract_romanization_segment(line)
        
        return ParsedEntry(
            english=english,
            cantonese=cantonese,
            jyutping=jyutping
        )
    
    # Check if the entire line is romanization
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
    # Split input by newlines
    lines = input_text.split('\n')
    
    # Filter out empty lines and trim whitespace
    terms = [line.strip() for line in lines if line.strip()]
    
    return terms


def parse_input_full(input_text: str) -> List[ParsedEntry]:
    """
    Parse multi-line input text into structured vocabulary entries.
    
    Each line is analyzed to separate English terms, Chinese characters,
    and pinyin/jyutping romanization into their respective fields.
    
    Supports various input formats:
    - One English term per line (will need translation)
    - Tab/pipe/semicolon-delimited columns
    - Mixed content with English, Chinese, and romanization
    
    Args:
        input_text: Multi-line string containing vocabulary data
        
    Returns:
        List of ParsedEntry objects with separated language components
        
    Examples:
        >>> entries = parse_input_full("hello\\tä½ å¥½\\tnei5 hou2")
        >>> entries[0].english
        'hello'
        >>> entries[0].cantonese
        'ä½ å¥½'
        >>> entries[0].jyutping
        'nei5 hou2'
    """
    lines = input_text.split('\n')
    entries = []
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        entry = parse_line(line)
        # Only include entries that have at least some content
        if entry.english or entry.cantonese or entry.jyutping:
            entries.append(entry)
    
    return entries
