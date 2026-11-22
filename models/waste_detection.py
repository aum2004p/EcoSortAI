"""
EcoSort AI - Waste Detection Module (YOLO)
===========================================
Wraps YOLOv8 (via ultralytics) for object detection on waste images.

Two modes of operation:
  1. Custom model  - If models/weights/yolo_waste.pt exists (trained on
     TrashNet/RealWaste), the model outputs waste classes directly.
  2. Pre-trained   - Falls back to YOLOv8n (COCO). Detected COCO classes
     are mapped to waste categories via COCO_TO_WASTE in config.py.
  3. Demo mode     - If ultralytics/torch are not installed, returns a
     single full-image bounding box labelled as 'trash' so the UI still
     works for development and testing.
"""

import os
import logging

from config import (
    YOLO_MODEL_PATH, YOLO_FALLBACK,
    WASTE_CATEGORIES, COCO_TO_WASTE,
)

logger = logging.getLogger(__name__)


class WasteDetector:
    """YOLO-based waste object detector."""

    def __init__(self):
        self._model = None
        self._mode = 'unknown'       # 'custom', 'pretrained', 'demo'
        self._class_names = None      # list of class names the model outputs

        self._load_model()

    # ------------------------------------------------------------------
    # Model loading
    # ------------------------------------------------------------------
    def _load_model(self):
        """Try to load the best available YOLO model."""

        # Attempt 1: custom-trained waste model
        if os.path.exists(YOLO_MODEL_PATH):
            try:
                from ultralytics import YOLO
                self._model = YOLO(YOLO_MODEL_PATH)
                self._mode = 'custom'
                self._class_names = self._model.names
                logger.info("Loaded custom YOLO model: %s", YOLO_MODEL_PATH)
                return
            except Exception as e:
                logger.warning("Failed to load custom YOLO model: %s", e)

        # Attempt 2: pre-trained YOLOv8n (auto-downloads weights)
        try:
            from ultralytics import YOLO
            self._model = YOLO(YOLO_FALLBACK)
            self._mode = 'pretrained'
            self._class_names = self._model.names
            logger.info("Loaded pre-trained YOLO (%s) with COCO mapping", YOLO_FALLBACK)
            return
        except Exception as e:
            logger.warning("Could not load ultralytics YOLO: %s", e)

        # Attempt 3: demo mode (no AI libraries available)
        self._mode = 'demo'
        logger.warning("Running in DEMO mode (no YOLO available). Install "
                       "ultralytics + torch for full functionality.")

    # ------------------------------------------------------------------
    # Detection
    # ------------------------------------------------------------------
    def detect(self, image_path):
        """
        Run object detection on the given image.

        Returns a list of dicts, one per detected object:
            {
                'category':     'plastic',          # waste category key
                'category_th':  'พลาสติก',
                'confidence':   0.92,
                'bbox':         (x1, y1, x2, y2),    # pixel coordinates
            }
        """
        if self._mode == 'demo':
            return self._demo_detect(image_path)

        results = self._model(image_path, verbose=False)
        detections = []

        for r in results:
            boxes = r.boxes
            for i in range(len(boxes)):
                # Bounding box
                x1, y1, x2, y2 = boxes.xyxy[i].cpu().numpy().astype(int)
                conf = float(boxes.conf[i].cpu().numpy())

                if self._mode == 'custom':
                    # Custom model: class index maps directly to waste categories
                    cls_idx = int(boxes.cls[i].cpu().numpy())
                    cls_name = self._class_names.get(cls_idx, str(cls_idx))
                    category = cls_name.lower().strip()
                else:
                    # Pre-trained COCO: map COCO class to waste category
                    cls_idx = int(boxes.cls[i].cpu().numpy())
                    cls_name = self._class_names.get(cls_idx, '')
                    category = COCO_TO_WASTE.get(cls_name, None)

                # Skip detections that don't map to a waste category
                if category is None or category not in WASTE_CATEGORIES:
                    continue

                # Skip very low-confidence detections
                if conf < 0.25:
                    continue

                meta = WASTE_CATEGORIES[category]
                detections.append({
                    'category': category,
                    'category_th': meta['name_th'],
                    'confidence': round(conf, 4),
                    'bbox': (int(x1), int(y1), int(x2), int(y2)),
                })

        # If nothing was mapped (common with pre-trained model on waste
        # images), label the entire image as general waste.
        if not detections and self._mode == 'pretrained':
            detections = self._fallback_detect(image_path)

        return detections

    # ------------------------------------------------------------------
    # Fallback / Demo
    # ------------------------------------------------------------------
    def _fallback_detect(self, image_path):
        """When the pre-trained model finds nothing mappable, label the
        entire image as one 'general waste' detection."""
        try:
            from PIL import Image
            img = Image.open(image_path)
            w, h = img.size
        except Exception:
            w, h = 640, 480

        meta = WASTE_CATEGORIES['trash']
        return [{
            'category': 'trash',
            'category_th': meta['name_th'],
            'confidence': 0.50,
            'bbox': (10, 10, w - 10, h - 10),
        }]

    def _demo_detect(self, image_path):
        """Demo mode: return a single full-image detection so the UI works."""
        try:
            from PIL import Image
            img = Image.open(image_path)
            w, h = img.size
        except Exception:
            w, h = 640, 480

        meta = WASTE_CATEGORIES['trash']
        return [{
            'category': 'trash',
            'category_th': meta['name_th'],
            'confidence': 0.50,
            'bbox': (20, 20, w - 20, h - 20),
        }]

    # ------------------------------------------------------------------
    @property
    def mode(self):
        return self._mode

    @property
    def is_ready(self):
        return self._model is not None
