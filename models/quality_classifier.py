"""
EcoSort AI - Quality Classifier Module (CNN)
=============================================
Classifies cropped waste images as 'clean' or 'contaminated' using a
fine-tuned CNN (ResNet18 backbone with transfer learning).

Two modes of operation:
  1. Trained model  - If models/weights/cnn_quality.pth exists, the CNN
     is loaded and used for inference.
  2. Heuristic      - When no trained weights are available, a
     color/texture heuristic provides a demo estimate so the pipeline
     still works end-to-end.
  3. Demo mode      - If torch is not installed at all, returns a random
     but deterministic guess based on image properties.
"""

import os
import logging

# numpy is needed for the heuristic classifier but is a soft dependency:
# if it is not installed the app still starts in a degraded demo mode.
try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

from config import CNN_MODEL_PATH

logger = logging.getLogger(__name__)

# Image size expected by the CNN
IMG_SIZE = 224

# Class labels (index -> name)
CLASS_NAMES = ['clean', 'contaminated']


class QualityClassifier:
    """CNN-based clean/contaminated waste classifier."""

    def __init__(self):
        self._model = None
        self._device = None
        self._transform = None
        self._mode = 'unknown'   # 'trained', 'heuristic', 'demo'

        self._load_model()

    # ------------------------------------------------------------------
    # Model loading
    # ------------------------------------------------------------------
    def _load_model(self):
        """Attempt to load a trained CNN; fall back to heuristic."""

        if os.path.exists(CNN_MODEL_PATH):
            try:
                import torch
                import torchvision.transforms as transforms
                from torchvision.models import resnet18, ResNet18_Weights

                self._device = torch.device('cuda' if torch.cuda.is_available()
                                            else 'cpu')
                self._model = resnet18(weights=None)
                # ResNet18 has 512 features before the final FC layer;
                # we replace it with a 2-class output (clean / contaminated).
                self._model.fc = torch.nn.Linear(512, 2)
                self._model.load_state_dict(
                    torch.load(CNN_MODEL_PATH, map_location=self._device)
                )
                self._model.to(self._device)
                self._model.eval()

                self._transform = transforms.Compose([
                    transforms.Resize((IMG_SIZE, IMG_SIZE)),
                    transforms.ToTensor(),
                    transforms.Normalize(
                        mean=[0.485, 0.456, 0.406],
                        std=[0.229, 0.224, 0.225],
                    ),
                ])
                self._mode = 'trained'
                logger.info("Loaded trained CNN quality model: %s", CNN_MODEL_PATH)
                return
            except Exception as e:
                logger.warning("Failed to load CNN model: %s", e)

        # Heuristic fallback (needs numpy + PIL or cv2, no torch)
        if HAS_NUMPY:
            try:
                import cv2  # noqa: F401
                self._mode = 'heuristic'
                logger.info("Using heuristic quality classifier (OpenCV-based)")
                return
            except ImportError:
                pass

            try:
                from PIL import Image  # noqa: F401
                self._mode = 'heuristic'
                logger.info("Using heuristic quality classifier (PIL-based)")
                return
            except ImportError:
                pass

        self._mode = 'demo'
        logger.warning("Running in DEMO mode for quality classification.")

    # ------------------------------------------------------------------
    # Classification
    # ------------------------------------------------------------------
    def classify(self, image_path, bbox=None):
        """
        Classify the quality of a waste item.

        Args:
            image_path: path to the original image.
            bbox: optional (x1, y1, x2, y2) to crop the item first.

        Returns:
            dict with keys:
                'quality':           'clean' or 'contaminated'
                'confidence':        float 0.0-1.0
        """
        if self._mode == 'trained':
            return self._predict_cnn(image_path, bbox)
        else:
            return self._heuristic_classify(image_path, bbox)

    # ------------------------------------------------------------------
    # Trained CNN inference
    # ------------------------------------------------------------------
    def _predict_cnn(self, image_path, bbox=None):
        import torch
        from PIL import Image

        img = Image.open(image_path).convert('RGB')
        if bbox:
            x1, y1, x2, y2 = bbox
            img = img.crop((x1, y1, x2, y2))

        tensor = self._transform(img).unsqueeze(0).to(self._device)
        with torch.no_grad():
            output = self._model(tensor)
            probs = torch.softmax(output, dim=1)
            pred_idx = int(probs.argmax(dim=1).item())
            confidence = float(probs[0][pred_idx].item())

        return {
            'quality': CLASS_NAMES[pred_idx],
            'confidence': round(confidence, 4),
        }

    # ------------------------------------------------------------------
    # Heuristic fallback
    # ------------------------------------------------------------------
    def _heuristic_classify(self, image_path, bbox=None):
        """
        Estimate clean/contaminated from image statistics.

        Heuristic logic:
          - Convert to HSV, measure colour variation and saturation.
          - High colour variation in the brown/green/yellow range
            (typical of food stains) suggests contamination.
          - Low saturation with uniform colour suggests clean.
        """
        if not HAS_NUMPY:
            return {'quality': 'clean', 'confidence': 0.50}

        try:
            import cv2
            img = cv2.imread(image_path)
            if img is None:
                return {'quality': 'clean', 'confidence': 0.50}

            if bbox:
                x1, y1, x2, y2 = bbox
                img = img[y1:y2, x1:x2]

            if img.size == 0:
                return {'quality': 'clean', 'confidence': 0.50}

            hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

            # Saturation mean: high saturation often means stains/food residue
            sat_mean = float(np.mean(hsv[:, :, 1]))       # 0-255
            # Value (brightness) std: low brightness variation suggests clean
            val_std = float(np.std(hsv[:, :, 2]))

            # Brown/green/yellow hue ranges (food residue colours)
            # OpenCV hue range: 0-179 (half of 0-359)
            # Brown ~ 10-25, Green ~ 35-85, Yellow ~ 20-35
            lower_residue = np.array([8, 40, 40])
            upper_residue = np.array([35, 255, 200])
            residue_mask = cv2.inRange(hsv, lower_residue, upper_residue)
            residue_ratio = float(np.count_nonzero(residue_mask)) / \
                             float(residue_mask.size)

            # Combine signals into a contamination score
            # Higher sat_mean, higher residue_ratio -> more likely contaminated
            contam_score = (
                (sat_mean / 255.0) * 0.35 +
                residue_ratio * 0.45 +
                min(val_std / 80.0, 1.0) * 0.20
            )

            if contam_score > 0.35:
                quality = 'contaminated'
                confidence = min(contam_score + 0.15, 0.95)
            else:
                quality = 'clean'
                confidence = min(1.0 - contam_score, 0.95)

            return {
                'quality': quality,
                'confidence': round(confidence, 4),
            }

        except ImportError:
            # Fallback with PIL only
            try:
                from PIL import Image
                img = Image.open(image_path).convert('RGB')
                if bbox:
                    x1, y1, x2, y2 = bbox
                    img = img.crop((x1, y1, x2, y2))

                arr = np.array(img)
                if arr.size == 0:
                    return {'quality': 'clean', 'confidence': 0.50}

                # Simple std-based heuristic
                std = float(np.std(arr))
                mean_sat = float(np.mean(np.max(arr, axis=2) -
                                         np.min(arr, axis=2)))

                contam_score = (mean_sat / 128.0) * 0.6 + \
                               min(std / 80.0, 1.0) * 0.4

                if contam_score > 0.4:
                    return {'quality': 'contaminated',
                            'confidence': round(min(contam_score + 0.2, 0.9), 4)}
                return {'quality': 'clean',
                        'confidence': round(min(1.0 - contam_score, 0.9), 4)}

            except Exception:
                return {'quality': 'clean', 'confidence': 0.50}
        except Exception:
            return {'quality': 'clean', 'confidence': 0.50}

    # ------------------------------------------------------------------
    @property
    def mode(self):
        return self._mode

    @property
    def is_ready(self):
        return self._model is not None or self._mode == 'heuristic'
