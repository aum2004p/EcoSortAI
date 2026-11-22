"""
EcoSort AI - Configuration
===========================
Central configuration for the Flask application, AI models, and database.
"""

import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
DATABASE_DIR = os.path.join(BASE_DIR, 'data')
DATABASE_PATH = os.path.join(DATABASE_DIR, 'ecosort.db')
SQLALCHEMY_DATABASE_URI = f'sqlite:///{DATABASE_PATH}'
SQLALCHEMY_TRACK_MODIFICATIONS = False

# ---------------------------------------------------------------------------
# Upload Settings
# ---------------------------------------------------------------------------
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}
MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB

# ---------------------------------------------------------------------------
# Model Weights
# ---------------------------------------------------------------------------
WEIGHTS_DIR = os.path.join(BASE_DIR, 'models', 'weights')
# YOLO: if a custom-trained model exists it is used; otherwise the
# pre-trained YOLOv8n (auto-downloaded by ultralytics) serves as fallback.
YOLO_MODEL_PATH = os.path.join(WEIGHTS_DIR, 'yolo_waste.pt')
YOLO_FALLBACK = 'yolov8n.pt'

# CNN quality classifier: trained weights are optional. When absent, a
# heuristic based on image analysis is used as a demo fallback.
CNN_MODEL_PATH = os.path.join(WEIGHTS_DIR, 'cnn_quality.pth')

# ---------------------------------------------------------------------------
# Waste Category Definitions
# ---------------------------------------------------------------------------
WASTE_CATEGORIES = {
    'plastic': {
        'name_th': 'พลาสติก',
        'name_en': 'Plastic',
        'color': '#3498db',
        'recyclable': True,
        'bin': 'ถังพลาสติก/ขวด',
    },
    'paper': {
        'name_th': 'กระดาษ',
        'name_en': 'Paper',
        'color': '#f1c40f',
        'recyclable': True,
        'bin': 'ถังกระดาษ',
    },
    'cardboard': {
        'name_th': 'กระดาษลัง',
        'name_en': 'Cardboard',
        'color': '#e67e22',
        'recyclable': True,
        'bin': 'ถังกระดาษลัง',
    },
    'glass': {
        'name_th': 'แก้ว',
        'name_en': 'Glass',
        'color': '#1abc9c',
        'recyclable': True,
        'bin': 'ถังแก้ว',
    },
    'metal': {
        'name_th': 'โลหะ',
        'name_en': 'Metal',
        'color': '#95a5a6',
        'recyclable': True,
        'bin': 'ถังโลหะ/กระป๋อง',
    },
    'trash': {
        'name_th': 'ขยะทั่วไป',
        'name_en': 'General Waste',
        'color': '#e74c3c',
        'recyclable': False,
        'bin': 'ถังขยะทั่วไป',
    },
}

# Mapping from COCO class names (YOLOv8 pre-trained) to waste categories.
# Used only when a custom waste-trained YOLO is not available.
COCO_TO_WASTE = {
    # Containers / bottles
    'bottle': 'plastic',
    'wine glass': 'glass',
    'cup': 'plastic',
    'bowl': 'plastic',
    'vase': 'glass',

    # Utensils / metal
    'fork': 'metal',
    'knife': 'metal',
    'spoon': 'metal',
    'scissors': 'metal',
    'clock': 'metal',

    # Paper / cardboard
    'book': 'paper',
    'newspaper': 'paper',
    'magazine': 'paper',
    'envelope': 'paper',
    'backpack': 'trash',
    'handbag': 'trash',
    'suitcase': 'trash',

    # Electronics / trash
    'cell phone': 'trash',
    'laptop': 'trash',
    'remote': 'trash',
    'keyboard': 'trash',
    'mouse': 'trash',
    'hair drier': 'trash',
    'toothbrush': 'plastic',
    'teddy bear': 'trash',
    'tv': 'trash',
    'microwave': 'trash',
    'oven': 'trash',
    'toaster': 'trash',
    'refrigerator': 'trash',
    'sink': 'trash',

    # Sports / plastic
    'sports ball': 'plastic',
    'frisbee': 'plastic',
    'skis': 'trash',
    'snowboard': 'trash',
    'kite': 'plastic',

    # Cans / metal
    'can': 'metal',
    'tin': 'metal',

    # Food packaging (commonly plastic/cardboard)
    'banana': 'trash',
    'apple': 'trash',
    'sandwich': 'trash',
    'orange': 'trash',
    'carrot': 'trash',
    'pizza': 'cardboard',
    'donut': 'trash',
    'cake': 'trash',
    'hot dog': 'trash',
    'broccoli': 'trash',
}

# ---------------------------------------------------------------------------
# Flask Secret Key
# ---------------------------------------------------------------------------
SECRET_KEY = os.environ.get('ECOSORT_SECRET_KEY', 'ecosort-ai-dev-key-change-in-production')

# ---------------------------------------------------------------------------
# Carbon Footprint Factors
# Estimated CO2 savings (kg CO2) per recycled item by waste type.
# Based on approximate recycling industry values (per item, not per kg).
# ---------------------------------------------------------------------------
CARBON_FOOTPRINT = {
    'plastic':   0.06,   # ~60g CO2 saved per plastic item recycled
    'paper':     0.03,   # ~30g CO2 saved per paper item recycled
    'cardboard': 0.05,   # ~50g CO2 saved per cardboard item recycled
    'glass':     0.02,   # ~20g CO2 saved per glass item recycled
    'metal':     0.12,   # ~120g CO2 saved per metal/can item recycled
    'trash':     0.0,    # no savings for general waste
}

# ---------------------------------------------------------------------------
# Gamification: Badge definitions
# Badges are awarded based on total points earned by a user.
# ---------------------------------------------------------------------------
BADGES = [
    {'name': 'เริ่มต้นรีไซเคิล', 'name_en': 'Recycling Beginner',
     'icon': '🌱', 'points_required': 0,
     'description': 'เริ่มต้นเข้าร่วมระบบรีไซเคิล'},
    {'name': 'ผู้คัดแยกมือใหม่', 'name_en': 'Novice Sorter',
     'icon': '♻️', 'points_required': 50,
     'description': 'สะสมคะแนน 50 คะแนน'},
    {'name': 'ผู้คัดแยกตัวจริง', 'name_en': 'Active Sorter',
     'icon': '🏆', 'points_required': 200,
     'description': 'สะสมคะแนน 200 คะแนน'},
    {'name': 'วีรบุรุษสิ่งแวดล้อม', 'name_en': 'Eco Warrior',
     'icon': '🛡️', 'points_required': 500,
     'description': 'สะสมคะแนน 500 คะแนน'},
    {'name': 'ราชาแห่งรีไซเคิล', 'name_en': 'Recycling King',
     'icon': '👑', 'points_required': 1000,
     'description': 'สะสมคะแนน 1000 คะแนน'},
]

# Points awarded per scan
POINTS_PER_CLEAN_RECYCLABLE = 10   # clean + recyclable item
POINTS_PER_DIRTY_RECYCLABLE = 5    # contaminated but recyclable
POINTS_PER_GENERAL = 2             # general waste (still sorted correctly)
BONUS_FULL_CLEAN_SCAN = 5          # bonus if all items are clean
