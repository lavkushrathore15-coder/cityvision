"""
License Plate Region Localization Module
Problem Statement ID: SIH26127

Detects candidate license plate regions within vehicle bounding box crops
using morphological edge profiling and aspect ratio filtering.
"""
from typing import List, Optional
import cv2
import numpy as np

from ai.detectors.base import BoundingBox
from ai.anpr.base import BasePlateDetector, PlateDetectionResult


class MorphologicalPlateDetector(BasePlateDetector):
    """
    Morphology- and gradient-based license plate detector.
    Operates on vehicle crop frames.
    Follows ANPR standard:
    - Focuses on vehicle lower region (bottom 60%)
    - Detects horizontal character edge patterns via Sobel horizontal gradients
    - Filters candidate contours by aspect ratio (2.0 - 5.5) and relative area
    - Rejects invalid candidates (strictly returns empty list when no plate is present)
    """

    def __init__(
        self,
        min_aspect_ratio: float = 1.8,
        max_aspect_ratio: float = 5.8,
        min_area_ratio: float = 0.003,
        max_area_ratio: float = 0.20,
        search_region_top_ratio: float = 0.35,  # start search from 35% down the vehicle
    ):
        self.min_aspect_ratio = min_aspect_ratio
        self.max_aspect_ratio = max_aspect_ratio
        self.min_area_ratio = min_area_ratio
        self.max_area_ratio = max_area_ratio
        self.search_region_top_ratio = search_region_top_ratio

    def detect_plates(self, vehicle_crop: np.ndarray) -> List[PlateDetectionResult]:
        """
        Detect license plate candidate regions in vehicle crop.
        Returns empty list if no valid plate region is detected.
        """
        if vehicle_crop is None or vehicle_crop.size == 0:
            return []

        vh, vw = vehicle_crop.shape[:2]
        if vh < 40 or vw < 40:
            return []

        total_vehicle_area = float(vh * vw)

        # Restrict search to lower section of the vehicle (front/rear bumper / grille)
        y_offset = int(vh * self.search_region_top_ratio)
        roi = vehicle_crop[y_offset:, :]
        roi_h, roi_w = roi.shape[:2]
        if roi_h < 15 or roi_w < 30:
            return []

        # Convert ROI to grayscale
        if len(roi.shape) == 3:
            gray_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        else:
            gray_roi = roi.copy()

        # Step 1: Horizontal gradient (vertical edges of characters)
        grad_x = cv2.Sobel(gray_roi, ddepth=cv2.CV_32F, dx=1, dy=0, ksize=-1)
        grad_x = np.absolute(grad_x)
        grad_x = cv2.normalize(grad_x, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)

        # Step 2: Smoothing and thresholding
        blurred = cv2.GaussianBlur(grad_x, (5, 5), 0)
        _, thresh = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        # Step 3: Morphological closing to fuse characters into a continuous rectangular plate region
        kernel_size = max(int(roi_w * 0.04), 9)
        morph_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (kernel_size, 3))
        closed = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, morph_kernel)

        # Step 4: Remove small noisy vertical artifacts
        vertical_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 3))
        cleaned = cv2.morphologyEx(closed, cv2.MORPH_OPEN, vertical_kernel)

        # Step 5: Contour extraction
        contours, _ = cv2.findContours(cleaned, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        candidates: List[PlateDetectionResult] = []

        for cnt in contours:
            x, y, w, h = cv2.boundingRect(cnt)
            if h <= 0 or w <= 0:
                continue

            aspect = w / float(h)
            area = float(w * h)
            area_ratio = area / total_vehicle_area

            # Aspect ratio check (standard plates are wide horizontal rectangles)
            if not (self.min_aspect_ratio <= aspect <= self.max_aspect_ratio):
                continue

            # Area check relative to vehicle crop
            if not (self.min_area_ratio <= area_ratio <= self.max_area_ratio):
                continue

            # Minimum absolute dimensions
            if w < 24 or h < 8:
                continue

            # Convert coordinates back to vehicle_crop space
            actual_y = y + y_offset
            # Add small 4% padding around plate candidate for character margins
            pad_w = int(w * 0.05)
            pad_h = int(h * 0.10)

            x1 = max(0, x - pad_w)
            y1 = max(0, actual_y - pad_h)
            x2 = min(vw, x + w + pad_w)
            y2 = min(vh, actual_y + h + pad_h)

            plate_crop = vehicle_crop[y1:y2, x1:x2]
            if plate_crop.size == 0:
                continue

            # Heuristic score based on aspect ratio proximity to ideal (3.2) and contrast
            ideal_aspect = 3.2
            aspect_score = max(0.0, 1.0 - abs(aspect - ideal_aspect) / 3.0)
            candidate_conf = float(np.clip(0.5 + 0.5 * aspect_score, 0.4, 0.95))

            bbox = BoundingBox(
                x1=float(x1),
                y1=float(y1),
                x2=float(x2),
                y2=float(y2),
            )

            candidates.append(
                PlateDetectionResult(
                    bbox=bbox,
                    confidence=candidate_conf,
                    plate_crop=plate_crop,
                    aspect_ratio=aspect,
                    area_ratio=area_ratio,
                )
            )

        # Sort candidates by confidence descending
        candidates.sort(key=lambda c: c.confidence, reverse=True)
        return candidates
