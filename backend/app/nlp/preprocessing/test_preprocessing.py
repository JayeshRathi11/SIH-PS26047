"""
Unit tests for Stage 1 NLP Text Preprocessing and Normalization.

Covers:
- normal text
- repeated whitespace
- multiline text (collapse and preserve modes)
- empty/whitespace-only input
- numbers, units, dosages, and medication names remaining unchanged
- negations remaining unchanged
- multilingual text remaining intact (Devanagari, Tamil, Telugu, Bengali)
- typographic normalization (quotes, dashes, control characters)
- determinism
"""

import unittest
from app.nlp.preprocessing import normalize_text, preprocess_text


class TestTextPreprocessing(unittest.TestCase):

    def test_alias_equivalence(self):
        """preprocess_text and normalize_text are identical functions."""
        sample = "Patient reports mild fever for 2 days."
        self.assertEqual(preprocess_text(sample), normalize_text(sample))

    def test_normal_text(self):
        """Normal text with standard punctuation remains clean and unchanged."""
        text = "Patient has a mild cough and headache for 3 days."
        self.assertEqual(normalize_text(text), text)

    def test_repeated_whitespace(self):
        """Multiple spaces, tabs, and mixed whitespace are collapsed to single spaces."""
        text = "Patient    has   fever   \t  and   \t\t  cough."
        expected = "Patient has fever and cough."
        self.assertEqual(normalize_text(text), expected)

        # Leading and trailing whitespace stripped
        padded = "   \t  severe abdominal pain   \t  "
        self.assertEqual(normalize_text(padded), "severe abdominal pain")

    def test_multiline_text_default(self):
        """Multiline text collapses to single-line space-separated text by default."""
        text = "Fever for 2 days.\n\nCough with phlegm.\n  No chest pain."
        expected = "Fever for 2 days. Cough with phlegm. No chest pain."
        self.assertEqual(normalize_text(text), expected)

        windows_crlf = "Symptoms:\r\nFever 101F\r\nHeadache"
        expected_crlf = "Symptoms: Fever 101F Headache"
        self.assertEqual(normalize_text(windows_crlf), expected_crlf)

    def test_multiline_text_preserve_newlines(self):
        """Multiline text preserves structured line breaks when preserve_newlines=True."""
        text = "Fever for 2 days.\n\n\nCough with phlegm.\n  No chest pain."
        expected = "Fever for 2 days.\n\nCough with phlegm.\nNo chest pain."
        self.assertEqual(normalize_text(text, preserve_newlines=True), expected)

    def test_empty_and_whitespace_only(self):
        """Empty, whitespace-only, None, and non-string inputs safely return empty string."""
        self.assertEqual(normalize_text(""), "")
        self.assertEqual(normalize_text("   "), "")
        self.assertEqual(normalize_text("\t\n  \r\n\t"), "")
        self.assertEqual(normalize_text(None), "")
        self.assertEqual(normalize_text(12345), "")  # type: ignore
        self.assertEqual(normalize_text([]), "")  # type: ignore

    def test_numbers_units_dosages_and_medications_unchanged(self):
        """
        Numbers, decimal values, units, dosages, and medication names must remain
        strictly unchanged.
        """
        cases = [
            "Metformin 500 mg twice daily",
            "Paracetamol 650mg 1-0-1 for 5 days",
            "Amoxicillin-Clavulanate 625 mg orally",
            "Insulin glargine 10 units subcutaneous at bedtime",
            "BP: 120/80 mmHg, Pulse: 72 bpm",
            "SpO2: 98%, Temp: 101.4°F (38.5 °C)",
            "HbA1c: 6.5%, Fasting blood glucose: 110 mg/dL",
            "Dosage range: 250-500 mcg/kg/min",
            "Dextrose 5% in 0.9% NaCl infusion 100 ml/hr",
            "WBC count: 11,500 /uL, Creatinine: 0.9 mg/dL",
        ]
        for case in cases:
            with self.subTest(case=case):
                self.assertEqual(normalize_text(case), case)

    def test_negations_remain_unchanged(self):
        """
        Clinical negations, denial assertions, and absence indicators must remain
        completely intact.
        """
        negation_texts = [
            "No chest pain or shortness of breath.",
            "Patient denies nausea, vomiting, or diarrhea.",
            "Not allergic to penicillin or sulfa drugs.",
            "Never had asthma or tuberculosis in the past.",
            "Without dizziness, headache, or visual disturbances.",
            "Nil per os (NPO) since midnight.",
            "No known drug allergies (NKDA).",
            "Negative for Covid-19 antigen test.",
        ]
        for neg in negation_texts:
            with self.subTest(neg=neg):
                self.assertEqual(normalize_text(neg), neg)

    def test_multilingual_text_intact(self):
        """
        Multilingual text in Indian languages (Devanagari, Tamil, Telugu, Bengali)
        must remain strictly intact without corruption of matras, conjuncts, or dandas.
        """
        multilingual_cases = [
            # Hindi
            (
                "मुझे  २ दिन से  बुखार और खांसी है।   पैरासिटामोल 650mg ले रहा हूँ।",
                "मुझे २ दिन से बुखार और खांसी है। पैरासिटामोल 650mg ले रहा हूँ।",
            ),
            # Marathi
            (
                "मला  ताप   आणि डोकेदुखी आहे.   रक्तदाब 120/80 mmHg.",
                "मला ताप आणि डोकेदुखी आहे. रक्तदाब 120/80 mmHg.",
            ),
            # Tamil
            (
                "எனக்கு   3 நாட்களாக   காய்ச்சல் உள்ளது.",
                "எனக்கு 3 நாட்களாக காய்ச்சல் உள்ளது.",
            ),
            # Telugu
            (
                "నాకు   రెండు రోజులుగా   జ్వరం ఉంది.",
                "నాకు రెండు రోజులుగా జ్వరం ఉంది.",
            ),
            # Bengali
            (
                "আমার  ২ দিন ধরে   জ্বর এবং কাশি আছে।",
                "আমার ২ দিন ধরে জ্বর এবং কাশি আছে।",
            ),
        ]
        for raw, expected in multilingual_cases:
            with self.subTest(lang=raw[:10]):
                self.assertEqual(normalize_text(raw), expected)

    def test_typographic_and_control_character_handling(self):
        """
        Removes non-printable control characters, BOM, and zero-width spaces,
        and standardizes typographic curly quotes and em/en-dashes.
        """
        # Non-breaking space (\u00a0) and control characters
        raw = "Fever\u00a0101°F\x00\x08 and\ufeff headache\u200b."
        expected = "Fever 101°F and headache."
        self.assertEqual(normalize_text(raw), expected)

        # Typographic quotes and dashes
        fancy = "“Fever” – patient’s condition is ‘stable’ — no chills."
        expected_fancy = '"Fever" - patient\'s condition is \'stable\' - no chills.'
        self.assertEqual(normalize_text(fancy), expected_fancy)

    def test_determinism(self):
        """Normalizing the same string repeatedly yields identical outputs."""
        sample = "  Patient with Type-2 Diabetes on Metformin 500mg BD   \n for 3 years. "
        first = normalize_text(sample)
        for _ in range(50):
            self.assertEqual(normalize_text(sample), first)


if __name__ == "__main__":
    unittest.main()
