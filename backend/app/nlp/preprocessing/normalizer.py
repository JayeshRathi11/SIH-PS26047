"""
Stage 1 NLP Preprocessing and Normalization Module.

Responsible for deterministic normalization of raw patient or clinician text
before downstream clinical NLP processing (ASR post-processing, entity extraction,
ontology mapping, and validation).

Invariants:
- Preserves clinical meaning exactly.
- Preserves medical terms, medication names, dosages, units, numbers, symptoms,
  negations, and clinical punctuation.
- Does NOT perform clinical extraction, translation, or diagnosis.
- Purely deterministic; no external AI calls.
"""

import re
import unicodedata
from typing import Optional


# Non-printable control characters (excluding standard \t, \n, \r)
# along with zero-width space (\u200b) and byte-order mark (\ufeff).
# Note: \u200c (ZWNJ) and \u200d (ZWJ) are intentionally preserved because
# they are linguistically essential in Indic scripts (Hindi, Bengali, Malayalam, etc.).
_CONTROL_CHAR_REGEX = re.compile(
    r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f\ufeff\u200b]"
)

# Typographic replacements for harmless formatting noise
_TYPOGRAPHIC_MAP = {
    "“": '"',
    "”": '"',
    "„": '"',
    "‟": '"',
    "‘": "'",
    "’": "'",
    "‚": "'",
    "‛": "'",
    "–": "-",  # en-dash to hyphen
    "—": "-",  # em-dash to hyphen
    "―": "-",  # horizontal bar to hyphen
}


def normalize_text(text: Optional[str], *, preserve_newlines: bool = False) -> str:
    """
    Normalizes raw clinical text while strictly preserving clinical semantics.

    Actions performed:
    1. Unicode normalization (NFKC) to resolve composite forms and fullwidth characters.
    2. Removal of non-printable control characters, BOM, and zero-width spaces.
    3. Normalization of typographic quotes and dashes to standard ASCII equivalents.
    4. Whitespace cleanup:
       - If `preserve_newlines=False` (default): collapses all whitespace
         (spaces, tabs, newlines) into a single standard space and strips boundaries.
       - If `preserve_newlines=True`: normalizes horizontal whitespace on each line,
         collapses consecutive blank lines to at most one, and strips boundaries.

    Guarantees:
    - Empty or non-string inputs safely return "".
    - Numbers, units, dosages, medication names, symptoms, and negations are unchanged.
    - Multilingual and non-Latin scripts (Devanagari, Tamil, Telugu, etc.) remain intact.
    - Deterministic and free of side effects.
    """
    if not text or not isinstance(text, str):
        return ""

    # 1. Unicode normalization (NFKC decomposes compatibility characters safely)
    cleaned = unicodedata.normalize("NFKC", text)

    # 2. Strip non-printable control characters and invisible markers
    cleaned = _CONTROL_CHAR_REGEX.sub("", cleaned)

    # 3. Standardize typographic quotation marks and dashes
    for fancy, standard in _TYPOGRAPHIC_MAP.items():
        if fancy in cleaned:
            cleaned = cleaned.replace(fancy, standard)

    # 4. Whitespace normalization
    if preserve_newlines:
        lines = [re.sub(r"[^\S\r\n]+", " ", line).strip() for line in cleaned.splitlines()]
        result_lines = []
        for line in lines:
            if line:
                result_lines.append(line)
            elif result_lines and result_lines[-1] != "":
                result_lines.append("")
        return "\n".join(result_lines).strip()

    # Collapse all whitespace sequences into a single space
    return re.sub(r"\s+", " ", cleaned).strip()


# Alias for explicit stage naming
preprocess_text = normalize_text
