import re
from typing import Any, Dict, List, Optional


class TranslationValidationError(Exception):
    """Raised when a translated case summary fails safety or integrity checks."""
    pass


DEVANAGARI_TO_ARABIC = str.maketrans("०१२३४५६७८९", "0123456789")


class TranslationValidator:
    @staticmethod
    def normalize_text_numerics(text: str) -> str:
        if not text:
            return ""
        return text.translate(DEVANAGARI_TO_ARABIC)

    @classmethod
    def extract_numeric_tokens(cls, text: str) -> List[str]:
        norm = cls.normalize_text_numerics(text)
        return re.findall(r"\b\d+(?:\.\d+)?\b", norm)

    @classmethod
    def validate(
        cls,
        source_summary: Dict[str, Any],
        translated_payload: Dict[str, Any],
        target_language_code: str,
    ) -> None:
        if not isinstance(translated_payload, dict):
            raise TranslationValidationError("Translated payload must be a dictionary.")

        sections = translated_payload.get("sections")
        if not isinstance(sections, dict):
            raise TranslationValidationError("Translated payload missing 'sections' dictionary.")

        # 1. Structure Check: Section Keys
        expected_sections = [
            k for k, v in source_summary.items()
            if isinstance(v, dict) and "items" in v
        ]

        for sec_key in expected_sections:
            if sec_key not in sections:
                raise TranslationValidationError(f"Missing required section '{sec_key}' in translation.")

        for sec_key in sections.keys():
            if sec_key not in expected_sections:
                raise TranslationValidationError(f"Unexpected extra section '{sec_key}' in translation.")

        # 2. Section and Item Details
        for sec_key in expected_sections:
            src_sec = source_summary[sec_key]
            trans_sec = sections[sec_key]

            if not isinstance(trans_sec, dict):
                raise TranslationValidationError(f"Section '{sec_key}' in translation is not an object.")

            if "display_label" not in trans_sec or not str(trans_sec["display_label"]).strip():
                raise TranslationValidationError(f"Section '{sec_key}' missing valid 'display_label'.")

            src_items = src_sec.get("items", [])
            trans_items = trans_sec.get("items", [])

            if len(src_items) != len(trans_items):
                raise TranslationValidationError(
                    f"Item count mismatch in section '{sec_key}': "
                    f"source has {len(src_items)} items, translation has {len(trans_items)}."
                )

            # 3. Validate Each Item 1:1
            for idx, (s_itm, t_itm) in enumerate(zip(src_items, trans_items)):
                if not isinstance(t_itm, dict):
                    raise TranslationValidationError(
                        f"Item #{idx} in section '{sec_key}' is not an object."
                    )

                s_text = s_itm.get("text", "")
                t_text = t_itm.get("text", "")

                if not t_text or not str(t_text).strip():
                    raise TranslationValidationError(
                        f"Item #{idx} in section '{sec_key}' has empty translated text."
                    )

                # Source references preservation
                s_sources = s_itm.get("sources", [])
                t_sources = t_itm.get("sources", [])
                if s_sources != t_sources:
                    raise TranslationValidationError(
                        f"Source reference mismatch in item #{idx} of '{sec_key}': "
                        f"expected {s_sources}, got {t_sources}."
                    )

                # Status preservation
                s_stat = s_itm.get("status")
                t_stat = t_itm.get("status")
                if s_stat != t_stat:
                    raise TranslationValidationError(
                        f"Status mismatch in item #{idx} of '{sec_key}': "
                        f"expected '{s_stat}', got '{t_stat}'."
                    )

                # 'Not documented' semantic preservation
                if s_text.strip() == "Not documented":
                    norm_t = t_text.lower()
                    if "no history" in norm_t or "कोई इतिहास नहीं" in t_text or "कोणताही इतिहास नाही" in t_text:
                        raise TranslationValidationError(
                            f"Semantic safety violation: 'Not documented' was translated into "
                            f"a clinically false negative claim: '{t_text}'."
                        )

                # 4. Numeric Preservation Check
                s_nums = cls.extract_numeric_tokens(s_text)
                t_norm = cls.normalize_text_numerics(t_text)
                t_nums = cls.extract_numeric_tokens(t_norm)

                for num in s_nums:
                    if num not in t_nums:
                        raise TranslationValidationError(
                            f"Numeric safety violation in item #{idx} of '{sec_key}': "
                            f"source numeric token '{num}' missing from translation '{t_text}'."
                        )

                # 5. Laboratory Status Safety
                for stat in ("LOW", "HIGH", "NORMAL", "UNKNOWN"):
                    if f"({stat})" in s_text and f"({stat})" not in t_text and stat not in t_text:
                        # Ensure abnormal status wasn't corrupted or flipped
                        raise TranslationValidationError(
                            f"Lab status safety violation in item #{idx} of '{sec_key}': "
                            f"status flag '{stat}' corrupted in translation '{t_text}'."
                        )


translation_validator = TranslationValidator()
