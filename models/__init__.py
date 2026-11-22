"""EcoSort AI model package."""

from .database import (db, User, ScanRecord, DetectedItem,
                       WasteActionPlan, PlanTask)
from .waste_detection import WasteDetector
from .quality_classifier import QualityClassifier
from .recommendation import RecommendationEngine
from .gamification import GamificationEngine
from .carbon_footprint import CarbonFootprintCalculator
from .prediction import WastePredictor

__all__ = [
    'db',
    'User',
    'ScanRecord',
    'DetectedItem',
    'WasteActionPlan',
    'PlanTask',
    'WasteDetector',
    'QualityClassifier',
    'RecommendationEngine',
    'GamificationEngine',
    'CarbonFootprintCalculator',
    'WastePredictor',
]
