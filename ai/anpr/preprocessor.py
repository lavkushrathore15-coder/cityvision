"""
Image Preprocessing Pipeline for License Plate Recognition
Problem Statement ID: SIH26127
"""
from dataclasses import dataclass
from typing import Tuple, Optional
import cv2
import numpy as np


@dataclass
class PreprocessedPlate:
    """Container for preprocessed plate image and quality assessment."""
    processed_image: np.ndarray
    original_crop: np.ndarray
    is_blurry: bool
    blur_score: float  # Variance of the Laplacian
    contrast_score: float  # Standard deviation of gray levels
    is_usable: bool  # Whether quality passes minimum thresholds


class PlatePreprocessor:
    """
    Image preprocessing for license plate crops prior to OCR:
    - Blur detection via Laplacian variance
    - Grayscale conversion
    - Contrast Limited Adaptive Histogram Equalization (CLAHE)
    - Bilateral noise filtering (edge-preserving)
    - Normalized aspect-ratio scaling
    """

    def __init__(
        self,
        target_height: int = 90,
        blur_threshold: float = 60.0,
        min_contrast: float = 15.0,
    ):
        self.target_height = target_height
        self.blur_threshold = blur_threshold
        self.min_contrast = min_contrast
        self.clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))

    def detect_blur(self, gray_image: np.ndarray) -> Tuple[bool, float]:
        """
        Compute Laplacian variance to detect out-of-focus or motion-blurred crops.
        Lower variance indicates less edge definition (higher blur).
        """
        if gray_image is None or gray_image.size == 0:
            return True, 0.0
        score = float(cv2.Laplacian(gray_image, cv2.CV_64F).var())
        is_blurry = score < self.blur_threshold
        return is_blurry, score

    def evaluate_contrast(self, gray_image: np.ndarray) -> float:
        """Compute luminance standard deviation as a proxy for contrast."""
        if gray_image is None or gray_image.size == 0:
            return 0.0
        return float(np.std(gray_image))

    def preprocess(self, plate_crop: np.ndarray) -> PreprocessedPlate:
        """
        Run complete preprocessing pipeline on raw license plate crop.
        """
        if plate_crop is None or plate_crop.size == 0:
            empty = np.zeros((self.target_height, self.target_height, 3), dtype=np.uint8)
            return PreprocessedPlate(
                processed_image=empty,
                original_crop=empty,
                is_blurry=True,
                blur_score=0.0,
                contrast_score=0.0,
                is_usable=False,
            )

        h, w = plate_crop.shape[:2]
        if h < 8 or w < 20:
            # Degenerate crop size
            return PreprocessedPlate(
                processed_image=plate_crop,
                original_crop=plate_crop,
                is_blurry=True,
                blur_score=0.0,
                contrast_score=0.0,
                is_usable=False,
            )

        # 1. Scale to target height maintaining aspect ratio
        aspect = w / float(h)
        new_w = max(int(self.target_height * aspect), 40)
        resized = cv2.resize(
            plate_crop,
            (new_w, self.target_height),
            interpolation=cv2.INTER_CUBIC if new_w > w else cv2.INTER_AREA,
        )

        # 2. Grayscale
        if len(resized.shape) == 3:
            gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
        else:
            gray = resized.copy()

        # 3. Quality evaluation
        is_blurry, blur_score = self.detect_blur(gray)
        contrast_score = self.evaluate_contrast(gray)

        # 4. Bilateral filter for edge-preserving denoising
        denoised = cv2.bilateralFilter(gray, d=7, sigmaColor=50, sigmaSpace=50)

        # 5. CLAHE for contrast equalization across shadows/sunlight
        equalized = self.clahe.apply(denoised)

        # Usability check: plate must have sufficient contrast
        is_usable = (contrast_score >= self.min_contrast)

        return PreprocessedPlate(
            processed_image=equalized,
            original_crop=plate_crop,
            is_blurry=is_blurry,
            blur_score=blur_score,
            contrast_score=contrast_score,
            is_usable=is_usable,
        )
