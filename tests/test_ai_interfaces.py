"""
Tests verifying abstract contracts for AI components
"""
import pytest
from ai.detectors.base import BaseVehicleDetector, BoundingBox, DetectionResult
from ai.trackers.base import BaseTracker, TrackedVehicle
from ai.anpr.base import BasePlateDetector, BasePlateOCR, LicensePlateRead
from ai.reid.base import BaseVehicleReID
from ai.matching.base import BaseCrossCameraMatcher, VehicleObservation, MatchResult


def test_detector_cannot_be_instantiated_directly():
    with pytest.raises(TypeError):
        BaseVehicleDetector()


def test_tracker_cannot_be_instantiated_directly():
    with pytest.raises(TypeError):
        BaseTracker()


def test_anpr_cannot_be_instantiated_directly():
    with pytest.raises(TypeError):
        BasePlateDetector()
    with pytest.raises(TypeError):
        BasePlateOCR()


def test_reid_cannot_be_instantiated_directly():
    with pytest.raises(TypeError):
        BaseVehicleReID()


def test_matcher_cannot_be_instantiated_directly():
    with pytest.raises(TypeError):
        BaseCrossCameraMatcher()


def test_bounding_box_instantiation():
    box = BoundingBox(x1=10.0, y1=20.0, x2=100.0, y2=150.0)
    assert box.x1 == 10.0
    assert box.x2 == 100.0
