"""
Plate Text Normalization and Quality Evaluation Module
Problem Statement ID: SIH26127
"""
import re
from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass
class NormalizedPlateResult:
    """Represents the normalized text alongside the raw OCR output."""
    raw_text: str
    normalized_text: str
    is_valid: bool
    is_partial: bool
    confidence: float
    confidence_passed: bool
    rejection_reason: Optional[str] = None


class PlateTextNormalizer:
    """
    Normalizes raw OCR text into standardized license plate syntax:
    - Retains original raw text without alteration
    - Converts to uppercase
    - Removes whitespace, hyphens, and non-alphanumeric noise
    - Evaluates length (distinguishing partial reads from full plates)
    - Applies configurable confidence thresholds
    """

    def __init__(
        self,
        min_confidence: float = 0.35,
        min_characters: int = 4,
        max_characters: int = 12,
        partial_min_characters: int = 3,
    ):
        self.min_confidence = min_confidence
        self.min_characters = min_characters
        self.max_characters = max_characters
        self.partial_min_characters = partial_min_characters

    def normalize(self, raw_text: str, confidence: float, is_blurry: bool = False) -> NormalizedPlateResult:
        """
        Normalize raw OCR output into standard alphanumeric format while preserving raw text.
        """
        if not raw_text or not raw_text.strip():
            return NormalizedPlateResult(
                raw_text="" if raw_text is None else raw_text,
                normalized_text="",
                is_valid=False,
                is_partial=False,
                confidence=confidence,
                confidence_passed=False,
                rejection_reason="EMPTY_TEXT",
            )

        raw_str = raw_text.strip()

        # Step 1: Strip non-alphanumeric characters and capitalize
        sanitized = re.sub(r"[^A-Za-z0-9]", "", raw_str).upper()

        # Step 2: Confidence check
        conf_passed = confidence >= self.min_confidence

        # Step 3: Partial and validity checks
        length = len(sanitized)

        if length == 0:
            return NormalizedPlateResult(
                raw_text=raw_str,
                normalized_text="",
                is_valid=False,
                is_partial=False,
                confidence=confidence,
                confidence_passed=conf_passed,
                rejection_reason="NO_ALPHANUMERIC",
            )

        if length < self.partial_min_characters:
            return NormalizedPlateResult(
                raw_text=raw_str,
                normalized_text=sanitized,
                is_valid=False,
                is_partial=True,
                confidence=confidence,
                confidence_passed=conf_passed,
                rejection_reason="TOO_SHORT",
            )

        is_partial = length < self.min_characters
        if length > self.max_characters:
            # Strip excessive noise if detected, or mark invalid
            return NormalizedPlateResult(
                raw_text=raw_str,
                normalized_text=sanitized[:self.max_characters],
                is_valid=False,
                is_partial=False,
                confidence=confidence,
                confidence_passed=conf_passed,
                rejection_reason="TOO_LONG",
            )

        if not conf_passed:
            return NormalizedPlateResult(
                raw_text=raw_str,
                normalized_text=sanitized,
                is_valid=False,
                is_partial=is_partial,
                confidence=confidence,
                confidence_passed=False,
                rejection_reason="LOW_CONFIDENCE",
            )

        if is_blurry and confidence < 0.60:
            return NormalizedPlateResult(
                raw_text=raw_str,
                normalized_text=sanitized,
                is_valid=False,
                is_partial=is_partial,
                confidence=confidence,
                confidence_passed=conf_passed,
                rejection_reason="BLURRY_LOW_CONFIDENCE",
            )

        return NormalizedPlateResult(
            raw_text=raw_str,
            normalized_text=sanitized,
            is_valid=not is_partial,
            is_partial=is_partial,
            confidence=confidence,
            confidence_passed=conf_passed,
            rejection_reason=None,
        )
