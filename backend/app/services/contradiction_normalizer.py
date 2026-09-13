"""
Feature 28: Multi-Source Contradiction Engine — Deterministic Normalizer

DESIGN CONTRACT:
- All normalization is deterministic (no AI, no Gemini, no speculative expansion).
- Normalization maps surface variants to a canonical form for COMPARISON ONLY.
- The canonical form is NOT a clinical judgment — it is a lookup key.
- No medical synonym expansion beyond verified string variants listed here.

IMPORTANT: These utilities never determine clinical correctness.
"""
import hashlib
import re
import unicodedata
from typing import Optional, Tuple


# ─────────────────────────────────────────────────────────────────────────────
# Text basics
# ─────────────────────────────────────────────────────────────────────────────

def normalize_text(s: Optional[str]) -> str:
    """Lowercase, strip leading/trailing whitespace, collapse internal whitespace."""
    if not s:
        return ""
    s = unicodedata.normalize("NFKC", s)
    return re.sub(r"\s+", " ", s.strip().lower())


# ─────────────────────────────────────────────────────────────────────────────
# Medication name
# ─────────────────────────────────────────────────────────────────────────────

# Verified brand→generic mappings (conservative; only well-known pairs)
_BRAND_TO_GENERIC: dict[str, str] = {
    "glucophage": "metformin",
    "glucomet": "metformin",
    "glycomet": "metformin",
    "amaryl": "glimepiride",
    "januvia": "sitagliptin",
    "janumet": "sitagliptin metformin",
    "disprin": "aspirin",
    "ecosprin": "aspirin",
    "crocin": "paracetamol",
    "dolo": "paracetamol",
    "combiflam": "ibuprofen paracetamol",
    "brufen": "ibuprofen",
    "augmentin": "amoxicillin clavulanic acid",
    "calpol": "paracetamol",
    "pantop": "pantoprazole",
    "pan": "pantoprazole",
    "atorva": "atorvastatin",
    "lipitor": "atorvastatin",
    "rosuvast": "rosuvastatin",
    "crestor": "rosuvastatin",
    "telmikind": "telmisartan",
    "telma": "telmisartan",
    "stugeron": "cinnarizine",
    "vertin": "betahistine",
}

# Common suffix patterns to strip from medication names for canonical form
_MED_SUFFIX_RE = re.compile(
    r"\s*(hcl|hydrochloride|sodium|potassium|sulfate|sulphate|phosphate|monohydrate|dihydrate|trihydrate|mesylate|maleate|tartrate|citrate|acetate|succinate|fumarate|besylate|stearate)\s*$",
    re.IGNORECASE,
)

def normalize_medication_name(s: Optional[str]) -> str:
    """
    Return a canonical medication name for comparison.
    Does NOT determine the correct/preferred name — only enables string matching.
    """
    if not s:
        return ""
    n = normalize_text(s)
    # Strip leading form prefix: "tab.", "tab ", "tablet ", "cap ", "capsule ", "inj ", "syrup "
    n = re.sub(r"^(tab\.|tab|tablet|cap\.|cap|capsule|inj\.|inj|injection|syrup)\s+", "", n).strip()
    # Strip trailing dosage number + unit: e.g. " 500mg", " 500 mg", " 1g", " 500"
    n = re.sub(r"\s+\d+(\.\d+)?\s*(mg|mcg|g|gm|ml|iu|%)?\s*$", "", n).strip()
    # Strip common salt/form suffixes
    n = _MED_SUFFIX_RE.sub("", n).strip()
    # Brand → generic lookup
    n = _BRAND_TO_GENERIC.get(n, n)
    # Remove trailing dosage forms again if any
    n = re.sub(r"\s+(tablet|cap|capsule|syrup|injection|inj|tab|tabs|caps)s?\s*$", "", n).strip()
    return n


# ─────────────────────────────────────────────────────────────────────────────
# Frequency
# ─────────────────────────────────────────────────────────────────────────────

_FREQ_PATTERNS: list[Tuple[re.Pattern, str]] = [
    (re.compile(r"\b(once\s*a?\s*day|once\s*daily|od|1\s*/\s*d|1\s*x\s*day|qd|q\.?d\.?|one\s*time\s*daily)\b", re.I), "once_daily"),
    (re.compile(r"\b(twice\s*a?\s*day|twice\s*daily|bd|bid|2\s*/\s*d|2\s*x\s*day|b\.?i\.?d\.?|two\s*times\s*daily)\b", re.I), "twice_daily"),
    (re.compile(r"\b(three\s*times\s*a?\s*day|thrice\s*daily|tds|tid|3\s*/\s*d|t\.?i\.?d\.?)\b", re.I), "thrice_daily"),
    (re.compile(r"\b(four\s*times\s*a?\s*day|qid|q\.?i\.?d\.?|4\s*/\s*d)\b", re.I), "four_times_daily"),
    (re.compile(r"\b(every\s*4\s*hours?|q4h|q\.?4\.?h\.?)\b", re.I), "every_4_hours"),
    (re.compile(r"\b(every\s*6\s*hours?|q6h|q\.?6\.?h\.?)\b", re.I), "every_6_hours"),
    (re.compile(r"\b(every\s*8\s*hours?|q8h|q\.?8\.?h\.?)\b", re.I), "every_8_hours"),
    (re.compile(r"\b(every\s*12\s*hours?|q12h|q\.?12\.?h\.?)\b", re.I), "every_12_hours"),
    (re.compile(r"\b(once\s*a?\s*week|weekly|ow)\b", re.I), "once_weekly"),
    (re.compile(r"\b(twice\s*a?\s*week|biweekly|bw)\b", re.I), "twice_weekly"),
    (re.compile(r"\b(at\s*bed\s*time|hs|bedtime|nocte)\b", re.I), "at_bedtime"),
    (re.compile(r"\b(morning|am)\b", re.I), "morning"),
    (re.compile(r"\b(evening|pm)\b", re.I), "evening"),
    (re.compile(r"\b(sos|as\s*needed|prn|p\.?r\.?n\.?|when\s*required)\b", re.I), "as_needed"),
]

def normalize_frequency(s: Optional[str]) -> str:
    """Return canonical frequency token or lowercased original if unrecognised."""
    if not s:
        return ""
    t = normalize_text(s)
    for pattern, canonical in _FREQ_PATTERNS:
        if pattern.search(t):
            return canonical
    return t


# ─────────────────────────────────────────────────────────────────────────────
# Dose unit
# ─────────────────────────────────────────────────────────────────────────────

_UNIT_MAP: dict[str, str] = {
    "milligram": "mg", "milligrams": "mg", "mg": "mg",
    "microgram": "mcg", "micrograms": "mcg", "mcg": "mcg",
    "µg": "mcg", "ug": "mcg",
    "gram": "g", "grams": "g", "gm": "g", "g": "g",
    "milliliter": "ml", "milliliters": "ml", "millilitre": "ml", "ml": "ml",
    "liter": "l", "litre": "l", "l": "l",
    "unit": "unit", "units": "unit", "iu": "iu", "international unit": "iu",
    "meq": "meq", "mmol": "mmol",
    "%": "%", "percent": "%", "percentage": "%",
}

def normalize_dose_unit(s: Optional[str]) -> str:
    if not s:
        return ""
    return _UNIT_MAP.get(normalize_text(s), normalize_text(s))


def normalize_dose_value_unit(
    amount: Optional[float], unit: Optional[str]
) -> Tuple[Optional[float], Optional[str]]:
    """Convert dose value & unit to standard unit (g -> mg) for deterministic comparison."""
    if amount is None:
        return None, normalize_dose_unit(unit)
    norm_unit = normalize_dose_unit(unit)
    if norm_unit == "g":
        return amount * 1000.0, "mg"
    if norm_unit == "mcg":
        return amount / 1000.0, "mg"
    return amount, norm_unit


# ─────────────────────────────────────────────────────────────────────────────
# Route of administration
# ─────────────────────────────────────────────────────────────────────────────

_ROUTE_MAP: dict[str, str] = {
    "oral": "oral", "orally": "oral", "by mouth": "oral", "po": "oral",
    "intravenous": "iv", "iv": "iv", "intra-venous": "iv",
    "intramuscular": "im", "im": "im", "intra-muscular": "im",
    "subcutaneous": "sc", "sc": "sc", "subcut": "sc", "sq": "sc",
    "topical": "topical", "locally": "topical",
    "inhaled": "inhaled", "inhalation": "inhaled", "nebulised": "inhaled",
    "sublingual": "sublingual", "sl": "sublingual",
    "rectal": "rectal", "pr": "rectal",
    "nasal": "nasal", "intranasal": "nasal",
    "ocular": "ocular", "ophthalmic": "ocular", "eye": "ocular",
    "otic": "otic", "ear": "otic",
    "transdermal": "transdermal", "patch": "transdermal",
}

def normalize_route(s: Optional[str]) -> str:
    if not s:
        return ""
    return _ROUTE_MAP.get(normalize_text(s), normalize_text(s))


# ─────────────────────────────────────────────────────────────────────────────
# Allergy / diagnosis value
# ─────────────────────────────────────────────────────────────────────────────

_NO_ALLERGY_PATTERNS = re.compile(
    r"\b(no\s+known|nkda|none|nil|no\s+allerg|not\s+known|denies)\b", re.I
)

def is_no_known_allergy(s: Optional[str]) -> bool:
    """Returns True if the text explicitly states no known allergies."""
    if not s:
        return False
    return bool(_NO_ALLERGY_PATTERNS.search(s))

def normalize_allergy_entry(s: Optional[str]) -> str:
    """Normalize an allergy name entry for comparison."""
    if not s:
        return ""
    # Strip common allergy descriptors
    n = normalize_text(s)
    n = re.sub(r"\b(allergy|allergic|reaction|sensitivity|intolerance|to)\b", "", n).strip()
    return normalize_medication_name(n) or n


def normalize_diagnosis(s: Optional[str]) -> str:
    """Normalize a diagnosis string for comparison."""
    if not s:
        return ""
    n = normalize_text(s)
    # Strip common suffix noise
    n = re.sub(r"\b(history\s+of|known\s+case\s+of|diagnosed\s+with|case\s+of)\b", "", n).strip()
    return n


# ─────────────────────────────────────────────────────────────────────────────
# Deduplication key generation
# ─────────────────────────────────────────────────────────────────────────────

def compute_dedup_key(
    patient_id: int,
    category: str,
    canonical_key: str,
    contradiction_type: str,
    source_a_type: str,
    source_a_id: str,
    source_b_type: str,
    source_b_id: str,
    source_a_field: str = "",
    source_b_field: str = "",
) -> str:
    """
    Compute a deterministic, order-invariant 64-char hex key for deduplication.

    Source ordering is normalised so that (A↔B) == (B↔A).
    The key includes enough specificity to distinguish different conflict types
    for the same medication/entity.
    """
    side_a = f"{source_a_type}|{source_a_id or ''}|{source_a_field or ''}"
    side_b = f"{source_b_type}|{source_b_id or ''}|{source_b_field or ''}"
    # Canonical (sorted) ordering
    ordered = sorted([side_a, side_b])
    raw = (
        f"{patient_id}::{category}::{canonical_key}::"
        f"{contradiction_type}::{ordered[0]}::{ordered[1]}"
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
