"""
EasyOCR Recognition Engine for License Plates
Problem Statement ID: SIH26127
"""
from typing import List, Dict, Any, Optional
import os
import logging
import numpy as np

from ai.anpr.base import BasePlateOCR

logger = logging.getLogger("cityvision.anpr.easy_ocr")


class EasyPlateOCR(BasePlateOCR):
    """
    License plate OCR engine powered by EasyOCR.
    Uses English character whitelist for alphanumeric license plate text.
    Preserves exact raw text output and confidence scores without modification.
    """

    def __init__(
        self,
        gpu: bool = False,
        languages: Optional[List[str]] = None,
        allowlist: str = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 -",
        reader: Optional[Any] = None,
    ):
        self.gpu = gpu
        self.languages = languages or ["en"]
        self.allowlist = allowlist
        self._reader = reader

    def _get_reader(self):
        """Lazy-load the EasyOCR reader instance."""
        if self._reader is None:
            # Ensure UTF-8 console compatibility for Windows environments
            os.environ.setdefault("PYTHONIOENCODING", "utf-8")
            import easyocr
            self._reader = easyocr.Reader(
                self.languages,
                gpu=self.gpu,
                verbose=False,
            )
        return self._reader

    def recognize_text(self, plate_crop: np.ndarray) -> List[Dict[str, Any]]:
        """
        Run OCR on plate image.
        Returns a list of candidate text segments:
        [
            {
                "raw_text": str,
                "confidence": float,
                "bbox": List[List[int]],
            }
        ]
        """
        if plate_crop is None or plate_crop.size == 0:
            return []

        h, w = plate_crop.shape[:2]
        if h < 8 or w < 15:
            return []

        reader = self._get_reader()

        try:
            results = reader.readtext(
                plate_crop,
                allowlist=self.allowlist,
                paragraph=False,
                detail=1,
            )
        except Exception as e:
            logger.warning(f"EasyOCR reader execution error on crop: {e}")
            return []

        extracted = []
        for bbox, text, conf in results:
            clean_str = str(text).strip()
            if clean_str:
                extracted.append(
                    {
                        "raw_text": clean_str,
                        "confidence": float(conf),
                        "bbox": [[int(pt[0]), int(pt[1])] for pt in bbox] if isinstance(bbox, (list, np.ndarray)) else None,
                    }
                )

        return extracted
