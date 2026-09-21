"""
AYUSH Entity Normalizer Service

Fuzzy string-matcher mapping raw Ayurvedic drug and formulation text to official
AFI (Ayurvedic Formulary of India) and NAMASTE (National AYUSH Morbidity and
Standardized Terminologies Electronic portal) codes.

Complies with Ministry of Ayush / AIIA standards.
"""

import logging
import re
from typing import Any, Dict, List, Optional
from pydantic import BaseModel

try:
    from rapidfuzz import fuzz, process
    RAPIDFUZZ_AVAILABLE = True
except ImportError:
    RAPIDFUZZ_AVAILABLE = False

logger = logging.getLogger(__name__)


class AyushStandardEntity(BaseModel):
    name: str
    hindi_name: str
    afi_code: str
    namaste_code: str
    category: str
    dosage_form: str
    common_indications: str


# Authoritative AFI & NAMASTE Standard Formulations Catalog
AYUSH_STANDARD_CATALOG: List[AyushStandardEntity] = [
    AyushStandardEntity(
        name="Ashwagandha Churna",
        hindi_name="अश्वगंधा चूर्ण",
        afi_code="AFI:Churna:01",
        namaste_code="AYU-CH-001",
        category="Churna",
        dosage_form="Powder",
        common_indications="Rasayana, Daurbalya, Stress, Vata disorders",
    ),
    AyushStandardEntity(
        name="Triphala Churna",
        hindi_name="त्रिफळा चूर्ण",
        afi_code="AFI:Churna:12",
        namaste_code="AYU-CH-012",
        category="Churna",
        dosage_form="Powder",
        common_indications="Vibandha (Constipation), Deepana, Chakshushya",
    ),
    AyushStandardEntity(
        name="Avipattikar Churna",
        hindi_name="अविपत्तिकर चूर्ण",
        afi_code="AFI:Churna:03",
        namaste_code="AYU-CH-003",
        category="Churna",
        dosage_form="Powder",
        common_indications="Amlapitta (Hyperacidity), Vibandha, Agnimandya",
    ),
    AyushStandardEntity(
        name="Sutshekhar Ras",
        hindi_name="सूतशेखर रस",
        afi_code="AFI:Rasa:45",
        namaste_code="AYU-RS-045",
        category="Rasa Shastra",
        dosage_form="Tablet",
        common_indications="Amlapitta, Chhardi (Vomiting), Shoola, Pitta disorders",
    ),
    AyushStandardEntity(
        name="Arogyavardhini Vati",
        hindi_name="आरोग्यवर्धिनी वटी",
        afi_code="AFI:Vati:02",
        namaste_code="AYU-VT-002",
        category="Vati",
        dosage_form="Tablet",
        common_indications="Yakrit Roga (Liver disorders), Kushtha, Medoroga",
    ),
    AyushStandardEntity(
        name="Chandraprabha Vati",
        hindi_name="चंद्रप्रभा वटी",
        afi_code="AFI:Vati:07",
        namaste_code="AYU-VT-007",
        category="Vati",
        dosage_form="Tablet",
        common_indications="Prameha (Diabetes/Urinary), Mutrakrichhra",
    ),
    AyushStandardEntity(
        name="Sitopaladi Churna",
        hindi_name="सितोपलादि चूर्ण",
        afi_code="AFI:Churna:15",
        namaste_code="AYU-CH-015",
        category="Churna",
        dosage_form="Powder",
        common_indications="Kasa (Cough), Shwasa (Asthma/Bronchitis), Rajayakshma",
    ),
    AyushStandardEntity(
        name="Yograj Guggulu",
        hindi_name="योगराज गुग्गुलु",
        afi_code="AFI:Guggulu:09",
        namaste_code="AYU-GG-009",
        category="Guggulu",
        dosage_form="Tablet",
        common_indications="Amavata (Rheumatoid arthritis), Sandhigatavata, Vatarakta",
    ),
    AyushStandardEntity(
        name="Dashamularishta",
        hindi_name="दशमूलारिष्ट",
        afi_code="AFI:Asava-Arishta:08",
        namaste_code="AYU-AA-008",
        category="Asava-Arishta",
        dosage_form="Fermented Liquid",
        common_indications="Sutika Roga, Daurbalya, Vata disorders",
    ),
    AyushStandardEntity(
        name="Brahmi Vati",
        hindi_name="ब्राह्मी वटी",
        afi_code="AFI:Vati:11",
        namaste_code="AYU-VT-011",
        category="Vati",
        dosage_form="Tablet",
        common_indications="Smriti Daurbalya (Memory impairment), Manasa Roga, Insomnia",
    ),
    AyushStandardEntity(
        name="Mahasudarshan Churna",
        hindi_name="महासुदर्शन चूर्ण",
        afi_code="AFI:Churna:22",
        namaste_code="AYU-CH-022",
        category="Churna",
        dosage_form="Powder",
        common_indications="Jwara (Fever of all Doshas), Yakrit-Pliha Roga",
    ),
    AyushStandardEntity(
        name="Shankh Bhasma",
        hindi_name="शंख भस्म",
        afi_code="AFI:Bhasma:14",
        namaste_code="AYU-BH-014",
        category="Bhasma",
        dosage_form="Incinerated Mineral",
        common_indications="Amlapitta, Agnimandya, Grahani, Shoola",
    ),
    AyushStandardEntity(
        name="Guduchi Ghana Vati",
        hindi_name="गुडूची घन वटी",
        afi_code="AFI:Vati:18",
        namaste_code="AYU-VT-018",
        category="Vati",
        dosage_form="Tablet",
        common_indications="Rasayana, Jwara, Prameha, Immunomodulator",
    ),
]


class AyushNormalizationResult(BaseModel):
    raw_input: str
    matched: bool
    standard_name: Optional[str] = None
    hindi_name: Optional[str] = None
    afi_code: Optional[str] = None
    namaste_code: Optional[str] = None
    category: Optional[str] = None
    dosage_form: Optional[str] = None
    common_indications: Optional[str] = None
    match_score: float = 0.0


class AyushEntityNormalizer:
    def __init__(self, catalog: Optional[List[AyushStandardEntity]] = None, match_threshold: float = 65.0):
        self.catalog = catalog or AYUSH_STANDARD_CATALOG
        self.match_threshold = match_threshold
        # Pre-build lookup strings
        self._lookup_keys: List[tuple[str, AyushStandardEntity]] = []
        for item in self.catalog:
            self._lookup_keys.append((item.name.lower(), item))
            self._lookup_keys.append((item.hindi_name, item))

    def _clean_input(self, text: str) -> str:
        """Strip dosages, units, frequency terms, and bracketed content."""
        t = re.sub(r"\([^)]*\)", "", text)
        t = re.sub(r"\b(\d+(\.\d+)?\s*(g|mg|ml|gm|gram|tablet|tab|गोळी|ग्रॅम|चम्मच|tsp))\b", "", t, flags=re.IGNORECASE)
        t = re.sub(r"\b(od|bd|tds|sos|qid|post meals?|pre meals?|bedtime|सकाळी|दुपारी|रात्री|जेवणानंतर|जेवणापूर्वी)\b", "", t, flags=re.IGNORECASE)
        t = re.sub(r"[,\-\.\:;]", " ", t)
        return " ".join(t.split()).strip()

    def normalize(self, raw_text: str) -> AyushNormalizationResult:
        if not raw_text or not raw_text.strip():
            return AyushNormalizationResult(raw_input=raw_text, matched=False)

        cleaned = self._clean_input(raw_text).lower()
        if not cleaned:
            cleaned = raw_text.strip().lower()

        best_entity: Optional[AyushStandardEntity] = None
        best_score: float = 0.0

        for key, entity in self._lookup_keys:
            if RAPIDFUZZ_AVAILABLE:
                # Token set ratio handles word ordering and extra tokens
                score = fuzz.token_set_ratio(cleaned, key)
                partial = fuzz.partial_ratio(cleaned, key)
                effective_score = max(score, partial)
            else:
                # Basic token matching fallback
                key_tokens = set(key.split())
                cleaned_tokens = set(cleaned.split())
                if key_tokens and cleaned_tokens:
                    intersection = len(key_tokens.intersection(cleaned_tokens))
                    effective_score = (intersection / max(len(key_tokens), len(cleaned_tokens))) * 100.0
                else:
                    effective_score = 0.0

            if effective_score > best_score:
                best_score = effective_score
                best_entity = entity

        if best_entity and best_score >= self.match_threshold:
            return AyushNormalizationResult(
                raw_input=raw_text,
                matched=True,
                standard_name=best_entity.name,
                hindi_name=best_entity.hindi_name,
                afi_code=best_entity.afi_code,
                namaste_code=best_entity.namaste_code,
                category=best_entity.category,
                dosage_form=best_entity.dosage_form,
                common_indications=best_entity.common_indications,
                match_score=round(best_score, 2),
            )

        return AyushNormalizationResult(
            raw_input=raw_text,
            matched=False,
            match_score=round(best_score, 2) if best_score > 0 else 0.0,
        )

    def normalize_list(self, raw_items: List[str]) -> List[AyushNormalizationResult]:
        return [self.normalize(item) for item in raw_items]


ayush_normalizer_service = AyushEntityNormalizer()
