"""
EcoSort AI - Database Models
=============================
SQLAlchemy models for storing scan records and detected waste items.
Uses SQLite by default (zero-config); can switch to MySQL by changing
SQLALCHEMY_DATABASE_URI in config.py.
"""

from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


class User(db.Model):
    """Registered user for gamification and leaderboard."""

    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(128), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    points = db.Column(db.Integer, default=0, nullable=False)
    total_scans = db.Column(db.Integer, default=0, nullable=False)
    total_items_sorted = db.Column(db.Integer, default=0, nullable=False)
    total_recyclable = db.Column(db.Integer, default=0, nullable=False)
    co2_saved = db.Column(db.Float, default=0.0, nullable=False)  # kg CO2
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Relationship: one user -> many scans
    scans = db.relationship('ScanRecord', backref='user', lazy=True)
    # Relationship: one user -> many action plans
    plans = db.relationship('WasteActionPlan', backref='user', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'points': self.points,
            'total_scans': self.total_scans,
            'total_items_sorted': self.total_items_sorted,
            'total_recyclable': self.total_recyclable,
            'co2_saved': round(self.co2_saved, 4),
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class ScanRecord(db.Model):
    """Represents one complete scan session (one uploaded image)."""

    __tablename__ = 'scan_records'

    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    image_filename = db.Column(db.String(256), nullable=False)
    total_items = db.Column(db.Integer, default=0, nullable=False)
    clean_count = db.Column(db.Integer, default=0, nullable=False)
    contaminated_count = db.Column(db.Integer, default=0, nullable=False)
    recyclable_count = db.Column(db.Integer, default=0, nullable=False)
    non_recyclable_count = db.Column(db.Integer, default=0, nullable=False)
    processing_time = db.Column(db.Float, default=0.0, nullable=False)  # seconds
    location = db.Column(db.String(128), default='', nullable=False)  # optional
    co2_saved = db.Column(db.Float, default=0.0, nullable=False)  # kg CO2 saved
    points_earned = db.Column(db.Integer, default=0, nullable=False)

    # Link to user (nullable for anonymous scans)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    # Relationship: one scan -> many detected items
    items = db.relationship(
        'DetectedItem', backref='scan', lazy=True,
        cascade='all, delete-orphan'
    )

    def to_dict(self):
        return {
            'id': self.id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'image_filename': self.image_filename,
            'total_items': self.total_items,
            'clean_count': self.clean_count,
            'contaminated_count': self.contaminated_count,
            'recyclable_count': self.recyclable_count,
            'non_recyclable_count': self.non_recyclable_count,
            'processing_time': self.processing_time,
            'location': self.location,
            'co2_saved': round(self.co2_saved, 4),
            'points_earned': self.points_earned,
            'user_id': self.user_id,
        }


class DetectedItem(db.Model):
    """Represents a single waste item detected within a scan."""

    __tablename__ = 'detected_items'

    id = db.Column(db.Integer, primary_key=True)
    scan_id = db.Column(db.Integer, db.ForeignKey('scan_records.id'), nullable=False)

    # Detection results from YOLO
    category = db.Column(db.String(32), nullable=False)       # plastic, paper, ...
    category_th = db.Column(db.String(64), nullable=False)
    confidence = db.Column(db.Float, nullable=False)          # 0.0 - 1.0

    # Bounding box coordinates (pixel-level relative to original image)
    bbox_x1 = db.Column(db.Integer, nullable=False)
    bbox_y1 = db.Column(db.Integer, nullable=False)
    bbox_x2 = db.Column(db.Integer, nullable=False)
    bbox_y2 = db.Column(db.Integer, nullable=False)

    # Quality classification from CNN
    quality = db.Column(db.String(16), nullable=False)       # 'clean' or 'contaminated'
    quality_confidence = db.Column(db.Float, default=0.0, nullable=False)

    # Recommendation
    recommendation = db.Column(db.Text, nullable=False)
    recyclable = db.Column(db.Boolean, default=False, nullable=False)
    suggested_bin = db.Column(db.String(64), nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'category': self.category,
            'category_th': self.category_th,
            'confidence': round(self.confidence, 4),
            'bbox': {
                'x1': self.bbox_x1,
                'y1': self.bbox_y1,
                'x2': self.bbox_x2,
                'y2': self.bbox_y2,
            },
            'quality': self.quality,
            'quality_confidence': round(self.quality_confidence, 4),
            'recommendation': self.recommendation,
            'recyclable': self.recyclable,
            'suggested_bin': self.suggested_bin,
        }


# ===========================================================================
# Smart Waste Action Planner + Recovery Tracking
# ===========================================================================
# Task status flow:
#   pending -> in_progress -> awaiting_review -> completed | unable
# "completed" means the user handled the item and confirmed the result.
# It does NOT prove the item was physically recycled.
TASK_STATUSES = ('pending', 'in_progress', 'awaiting_review',
                 'completed', 'unable')
OPEN_TASK_STATUSES = ('pending', 'in_progress', 'awaiting_review')


class WasteActionPlan(db.Model):
    """A saved plan generated from one or more scans of a user."""

    __tablename__ = 'waste_action_plans'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    title = db.Column(db.String(128), nullable=False)
    status = db.Column(db.String(16), default='active', nullable=False)  # active | done
    scan_ids = db.Column(db.String(256), default='', nullable=False)     # "1,2,3"
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow,
                           onupdate=datetime.utcnow, nullable=False)

    tasks = db.relationship('PlanTask', backref='plan', lazy=True,
                            cascade='all, delete-orphan',
                            order_by='PlanTask.id')

    def progress(self):
        total = len(self.tasks)
        closed = sum(1 for t in self.tasks if t.status in ('completed', 'unable'))
        return {
            'total': total,
            'closed': closed,
            'completed': sum(1 for t in self.tasks if t.status == 'completed'),
            'percent': round(closed / total * 100) if total else 0,
        }

    def to_dict(self, with_tasks=False):
        d = {
            'id': self.id,
            'title': self.title,
            'status': self.status,
            'scan_ids': [int(x) for x in self.scan_ids.split(',') if x],
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'progress': self.progress(),
        }
        if with_tasks:
            d['tasks'] = [t.to_dict() for t in self.tasks]
        return d


class PlanTask(db.Model):
    """One to-do for one detected item, including its recovery history."""

    __tablename__ = 'plan_tasks'

    id = db.Column(db.Integer, primary_key=True)
    plan_id = db.Column(db.Integer, db.ForeignKey('waste_action_plans.id'),
                        nullable=False)
    detected_item_id = db.Column(db.Integer, db.ForeignKey('detected_items.id'),
                                 nullable=False)

    action_type = db.Column(db.String(32), nullable=False)   # collect | clean | ...
    title = db.Column(db.String(128), nullable=False)
    instruction = db.Column(db.Text, nullable=False)          # steps, one per line
    status = db.Column(db.String(16), default='pending', nullable=False)

    # Snapshot of state BEFORE handling (never rewritten afterwards)
    category = db.Column(db.String(32), nullable=False)
    before_quality = db.Column(db.String(16), nullable=False)

    # Re-verification (optional image re-scan)
    after_image = db.Column(db.String(256), nullable=True)
    after_category = db.Column(db.String(32), nullable=True)
    after_quality = db.Column(db.String(16), nullable=True)
    after_quality_confidence = db.Column(db.Float, nullable=True)
    mismatch = db.Column(db.Boolean, default=False, nullable=False)

    user_confirmed = db.Column(db.Boolean, default=False, nullable=False)
    note = db.Column(db.Text, default='', nullable=False)
    points_awarded = db.Column(db.Integer, default=0, nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    started_at = db.Column(db.DateTime, nullable=True)
    done_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)

    item = db.relationship('DetectedItem', lazy=True)

    def to_dict(self):
        scan = self.item.scan if self.item else None
        return {
            'id': self.id,
            'plan_id': self.plan_id,
            'detected_item_id': self.detected_item_id,
            'scan_id': scan.id if scan else None,
            'image_url': f'/static/uploads/{scan.image_filename}' if scan else None,
            'bbox': self.item.to_dict()['bbox'] if self.item else None,
            'action_type': self.action_type,
            'title': self.title,
            'instruction': self.instruction,
            'steps': [x for x in self.instruction.split('\n') if x.strip()],
            'status': self.status,
            'category': self.category,
            'before_quality': self.before_quality,
            'after_image_url': (f'/static/uploads/{self.after_image}'
                                if self.after_image else None),
            'after_category': self.after_category,
            'after_quality': self.after_quality,
            'after_quality_confidence': self.after_quality_confidence,
            'mismatch': self.mismatch,
            'user_confirmed': self.user_confirmed,
            'note': self.note,
            'points_awarded': self.points_awarded,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'done_at': self.done_at.isoformat() if self.done_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
        }


class RecyclingPoint(db.Model):
    """A real place where recyclables can be sold or dropped off."""

    __tablename__ = 'recycling_points'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(160), nullable=False)
    point_type = db.Column(db.String(24), nullable=False, index=True)
    # point_type: junk_shop | ewaste
    lat = db.Column(db.Float, nullable=True)   # optional until filled in
    lng = db.Column(db.Float, nullable=True)
    address = db.Column(db.String(255), default='')
    opening_hours = db.Column(db.String(120), default='')
    phone = db.Column(db.String(40), default='')
    rating = db.Column(db.Float, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'point_type': self.point_type,
            'lat': self.lat,
            'lng': self.lng,
            'address': self.address or '',
            'opening_hours': self.opening_hours or '',
            'phone': self.phone or '',
            'rating': self.rating,
        }