"""
EcoSort AI - Flask Application
================================
Main entry point for the EcoSort AI web application.

Routes:
  Pages:
    GET  /                 Home page
    GET  /scanner          AI scanner page (Module 1 & 2 & 3)
    GET  /dashboard        Analytics dashboard (Module 4)
    GET  /about            About / project info
    GET  /waste-planner    Smart Waste Action Planner (login)
    GET  /waste-recovery   Waste Recovery Center (login)

  APIs:
    POST /api/scan         Upload image, run YOLO + CNN, return results
    POST /api/save          Save scan results to database
    GET  /api/scans         List recent scans
    GET  /api/scans/<id>    Get a specific scan with items
    GET  /api/stats         Dashboard summary statistics
    GET  /api/trends        Time-series trend data
    GET  /api/export        Export data as CSV
    GET  /api/model-status  Check which AI models are loaded
"""

import os
import csv
import io
import uuid
import time
import logging
from datetime import datetime, timedelta

from flask import (
    Flask, render_template, request, jsonify, send_file,
    redirect, url_for, flash,
)
from werkzeug.utils import secure_filename  # noqa: F401
from sqlalchemy import func

from config import (
    SQLALCHEMY_DATABASE_URI, SQLALCHEMY_TRACK_MODIFICATIONS,
    UPLOAD_FOLDER, ALLOWED_EXTENSIONS, MAX_CONTENT_LENGTH,
    WASTE_CATEGORIES, SECRET_KEY, BASE_DIR,
)
from models.database import (
    db, User, ScanRecord, DetectedItem, WasteActionPlan, PlanTask,
    RecyclingPoint,
)
from models.recycling_points import (
    seed_recycling_points, nearest_points, POINT_TYPES, types_for_category,
)
from models.action_planner import ActionPlanner
from models.waste_detection import WasteDetector
from models.quality_classifier import QualityClassifier
from models.recommendation import RecommendationEngine
from models.gamification import GamificationEngine
from models.carbon_footprint import CarbonFootprintCalculator
from models.prediction import WastePredictor
from flask import session as flask_session

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
)
logger = logging.getLogger('EcoSortAI')

# ---------------------------------------------------------------------------
# Flask app factory
# ---------------------------------------------------------------------------
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = SQLALCHEMY_DATABASE_URI
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = SQLALCHEMY_TRACK_MODIFICATIONS
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH
app.config['SECRET_KEY'] = SECRET_KEY
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

db.init_app(app)

# Ensure directories exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(os.path.dirname(app.config['SQLALCHEMY_DATABASE_URI']
                            .replace('sqlite:///', '')), exist_ok=True)

# ---------------------------------------------------------------------------
# Initialize AI models (lazy-loaded on first request)
# ---------------------------------------------------------------------------
_detector = None
_classifier = None
_recommender = RecommendationEngine()
_gamification = GamificationEngine()
_carbon = CarbonFootprintCalculator()
_predictor = WastePredictor()
_planner = ActionPlanner()


def get_detector():
    global _detector
    if _detector is None:
        _detector = WasteDetector()
    return _detector


def get_classifier():
    global _classifier
    if _classifier is None:
        _classifier = QualityClassifier()
    return _classifier


# ---------------------------------------------------------------------------
# Session / Auth helpers
# ---------------------------------------------------------------------------
def current_user():
    """Return the logged-in User object or None."""
    uid = flask_session.get('user_id')
    if uid is None:
        return None
    return User.query.get(uid)


def login_required(fn):
    """Decorator: redirect to login page if not logged in (for pages)."""
    from functools import wraps
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if current_user() is None:
            return redirect(url_for('login_page'))
        return fn(*args, **kwargs)
    return wrapper


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def model_status():
    """Return current AI model status for display."""
    det = get_detector()
    clf = get_classifier()
    return {
        'detector': {
            'mode': det.mode,
            'ready': det.is_ready,
        },
        'classifier': {
            'mode': clf.mode,
            'ready': clf.is_ready,
        },
    }


# ---------------------------------------------------------------------------
# Page Routes
# ---------------------------------------------------------------------------
@app.route('/')
def index():
    """Home page with project overview."""
    status = model_status()
    # Quick stats for home page
    total_scans = ScanRecord.query.count()
    total_items = db.session.query(
        func.coalesce(func.sum(ScanRecord.total_items), 0)
    ).scalar()
    return render_template(
        'index.html',
        status=status,
        total_scans=total_scans,
        total_items=total_items,
        categories=WASTE_CATEGORIES,
        user=current_user(),
    )


@app.route('/scanner')
def scanner():
    """AI Scanner page - Modules 1, 2, 3."""
    status = model_status()
    return render_template('scanner.html', status=status,
                           categories=WASTE_CATEGORIES, user=current_user())


@app.route('/dashboard')
def dashboard():
    """Analytics Dashboard page - Module 4."""
    return render_template('dashboard.html', categories=WASTE_CATEGORIES, user=current_user())


@app.route('/about')
def about():
    """About page with project information."""
    status = model_status()
    return render_template('about.html', status=status,
                           categories=WASTE_CATEGORIES, user=current_user())


# ---------------------------------------------------------------------------
# New Page Routes (Advanced Features)
# ---------------------------------------------------------------------------
@app.route('/live-scan')
def live_scan():
    """Real-time camera scanner page."""
    status = model_status()
    user = current_user()
    return render_template('live_scan.html', status=status,
                           categories=WASTE_CATEGORIES, user=user)


@app.route('/leaderboard')
def leaderboard():
    """Community leaderboard page."""
    user = current_user()
    return render_template('leaderboard.html', user=user)


@app.route('/profile')
@login_required
def profile():
    """User profile page (requires login)."""
    user = current_user()
    badges = _gamification.get_badges(user.points)
    current_badge = _gamification.get_current_badge(user.points)
    next_badge = _gamification.get_next_badge(user.points)
    progress = _gamification.get_progress_to_next(user.points)
    # Get user's recent scans
    recent = ScanRecord.query.filter_by(user_id=user.id).order_by(
        ScanRecord.created_at.desc()).limit(10).all()
    return render_template('profile.html', user=user, badges=badges,
                           current_badge=current_badge,
                           next_badge=next_badge, progress=progress,
                           recent_scans=recent)


@app.route('/login')
def login_page():
    """Login page."""
    if current_user() is not None:
        return redirect(url_for('profile'))
    return render_template('login.html')


@app.route('/register')
def register_page():
    """Registration page."""
    if current_user() is not None:
        return redirect(url_for('profile'))
    return render_template('register.html')


# ---------------------------------------------------------------------------
# API: Scan image
# ---------------------------------------------------------------------------
@app.route('/api/scan', methods=['POST'])
def api_scan():
    """
    Upload an image and run the full AI pipeline:
      1. YOLO detection -> bounding boxes + categories
      2. CNN quality classification -> clean/contaminated per item
      3. Recommendation engine -> disposal instructions per item

    Returns JSON with detection results (not yet saved to DB).
    """
    if 'image' not in request.files:
        return jsonify({'error': 'ไม่พบไฟล์ภาพ กรุณาอัปโหลดภาพ'}), 400

    file = request.files['image']
    if file.filename == '':
        return jsonify({'error': 'กรุณาเลือกไฟล์ภาพ'}), 400

    if not allowed_file(file.filename):
        return jsonify({'error': 'รองรับเฉพาะไฟล์ PNG, JPG, JPEG, WEBP'}), 400

    # Save uploaded file
    ext = file.filename.rsplit('.', 1)[1].lower()
    filename = f"{uuid.uuid4().hex}.{ext}"
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)

    start_time = time.time()

    try:
        # Step 1: YOLO detection
        detector = get_detector()
        detections = detector.detect(filepath)

        if not detections:
            return jsonify({
                'error': 'ไม่พบวัตถุในภาพ กรุณาลองภาพอื่น',
                'image_url': f'/static/uploads/{filename}',
            }), 200

        # Step 2: CNN quality classification per item
        classifier = get_classifier()
        for det in detections:
            result = classifier.classify(filepath, bbox=det['bbox'])
            det['quality'] = result['quality']
            det['quality_confidence'] = result['confidence']

        # Step 3: Recommendations
        _recommender.recommend_batch(detections)

        # Step 3.5: Carbon footprint savings
        co2_result = _carbon.calculate_savings(detections)

        # Step 3.6: Gamification points
        points_result = _gamification.calculate_scan_points(detections)

        processing_time = round(time.time() - start_time, 3)

        # Count summary
        clean_count = sum(1 for d in detections if d['quality'] == 'clean')
        contaminated_count = len(detections) - clean_count
        recyclable_count = sum(1 for d in detections if d['recyclable'])
        non_recyclable_count = len(detections) - recyclable_count

        response = {
            'success': True,
            'image_url': f'/static/uploads/{filename}',
            'image_filename': filename,
            'total_items': len(detections),
            'clean_count': clean_count,
            'contaminated_count': contaminated_count,
            'recyclable_count': recyclable_count,
            'non_recyclable_count': non_recyclable_count,
            'processing_time': processing_time,
            'model_mode': {
                'detector': detector.mode,
                'classifier': classifier.mode,
            },
            'detections': detections,
            'carbon': co2_result,
            'carbon_impact_text': _carbon.format_impact_text(co2_result),
            'points': points_result,
        }

        logger.info("Scan complete: %d items in %.3fs (detector=%s, clf=%s)",
                     len(detections), processing_time,
                     detector.mode, classifier.mode)
        return jsonify(response)

    except Exception as e:
        logger.exception("Scan error")
        return jsonify({'error': f'เกิดข้อผิดพลาดในการประมวลผล: {str(e)}'}), 500


# ---------------------------------------------------------------------------
# API: Save scan results to database
# ---------------------------------------------------------------------------
@app.route('/api/save', methods=['POST'])
def api_save():
    """Persist a completed scan to the database."""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'ไม่พบข้อมูล'}), 400

    user = current_user()

    try:
        record = ScanRecord(
            image_filename=data.get('image_filename', ''),
            total_items=data.get('total_items', 0),
            clean_count=data.get('clean_count', 0),
            contaminated_count=data.get('contaminated_count', 0),
            recyclable_count=data.get('recyclable_count', 0),
            non_recyclable_count=data.get('non_recyclable_count', 0),
            processing_time=data.get('processing_time', 0.0),
            location=data.get('location', ''),
            co2_saved=data.get('carbon', {}).get('total_co2', 0.0),
            points_earned=data.get('points', {}).get('points', 0),
            user_id=user.id if user else None,
        )
        db.session.add(record)
        db.session.flush()  # get the record ID

        for det in data.get('detections', []):
            item = DetectedItem(
                scan_id=record.id,
                category=det['category'],
                category_th=det.get('category_th', ''),
                confidence=det.get('confidence', 0.0),
                bbox_x1=det['bbox']['x1'] if isinstance(det['bbox'], dict)
                         else det['bbox'][0],
                bbox_y1=det['bbox']['y1'] if isinstance(det['bbox'], dict)
                         else det['bbox'][1],
                bbox_x2=det['bbox']['x2'] if isinstance(det['bbox'], dict)
                         else det['bbox'][2],
                bbox_y2=det['bbox']['y2'] if isinstance(det['bbox'], dict)
                         else det['bbox'][3],
                quality=det.get('quality', 'clean'),
                quality_confidence=det.get('quality_confidence', 0.0),
                recommendation=det.get('recommendation', ''),
                recyclable=det.get('recyclable', False),
                suggested_bin=det.get('suggested_bin', ''),
            )
            db.session.add(item)

        db.session.commit()

        # Award points to user if logged in
        if user:
            user.points += record.points_earned
            user.total_scans += 1
            user.total_items_sorted += record.total_items
            user.total_recyclable += record.recyclable_count
            user.co2_saved += record.co2_saved
            db.session.commit()

        return jsonify({'success': True, 'scan_id': record.id,
                        'points_earned': record.points_earned,
                        'user_points': user.points if user else None})

    except Exception as e:
        db.session.rollback()
        logger.exception("Save error")
        return jsonify({'error': f'บันทึกไม่สำเร็จ: {str(e)}'}), 500


# ---------------------------------------------------------------------------
# API: List recent scans
# ---------------------------------------------------------------------------
@app.route('/api/scans')
def api_scans():
    """Return recent scan records (paginated)."""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)

    pagination = ScanRecord.query.order_by(
        ScanRecord.created_at.desc()
    ).paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        'scans': [s.to_dict() for s in pagination.items],
        'total': pagination.total,
        'pages': pagination.pages,
        'current_page': page,
    })


# ---------------------------------------------------------------------------
# API: Get specific scan with all detected items
# ---------------------------------------------------------------------------
@app.route('/api/scans/<int:scan_id>')
def api_scan_detail(scan_id):
    """Get a single scan with all its detected items."""
    record = ScanRecord.query.get_or_404(scan_id)
    items = [item.to_dict() for item in record.items]
    result = record.to_dict()
    result['items'] = items
    return jsonify(result)


# ---------------------------------------------------------------------------
# API: Dashboard statistics
# ---------------------------------------------------------------------------
@app.route('/api/stats')
def api_stats():
    """Aggregate statistics for the dashboard."""
    # Total counts
    total_scans = ScanRecord.query.count()
    total_items = db.session.query(
        func.coalesce(func.sum(ScanRecord.total_items), 0)
    ).scalar()
    total_clean = db.session.query(
        func.coalesce(func.sum(ScanRecord.clean_count), 0)
    ).scalar()
    total_contaminated = db.session.query(
        func.coalesce(func.sum(ScanRecord.contaminated_count), 0)
    ).scalar()
    total_recyclable = db.session.query(
        func.coalesce(func.sum(ScanRecord.recyclable_count), 0)
    ).scalar()
    total_non_recyclable = db.session.query(
        func.coalesce(func.sum(ScanRecord.non_recyclable_count), 0)
    ).scalar()

    # Items by category
    category_counts = db.session.query(
        DetectedItem.category,
        func.count(DetectedItem.id).label('count'),
    ).join(ScanRecord).group_by(DetectedItem.category).all()

    categories_data = []
    for cat, count in category_counts:
        meta = WASTE_CATEGORIES.get(cat, {})
        categories_data.append({
            'category': cat,
            'name_th': meta.get('name_th', cat),
            'color': meta.get('color', '#999'),
            'count': count,
        })

    # Quality breakdown
    quality_counts = db.session.query(
        DetectedItem.quality,
        func.count(DetectedItem.id).label('count'),
    ).join(ScanRecord).group_by(DetectedItem.quality).all()
    quality_data = {q: c for q, c in quality_counts}

    return jsonify({
        'total_scans': total_scans,
        'total_items': total_items,
        'total_clean': total_clean,
        'total_contaminated': total_contaminated,
        'total_recyclable': total_recyclable,
        'total_non_recyclable': total_non_recyclable,
        'categories': categories_data,
        'quality': {
            'clean': quality_data.get('clean', 0),
            'contaminated': quality_data.get('contaminated', 0),
        },
    })


# ---------------------------------------------------------------------------
# API: Trends over time
# ---------------------------------------------------------------------------
@app.route('/api/trends')
def api_trends():
    """Time-series data for trend charts."""
    period = request.args.get('period', 'daily')  # daily, weekly, monthly

    now = datetime.utcnow()

    if period == 'weekly':
        start = now - timedelta(weeks=12)
        date_fmt = '%Y-%W'
        label_fmt = 'W%W'
    elif period == 'monthly':
        start = now - timedelta(days=365)
        date_fmt = '%Y-%m'
        label_fmt = '%b %Y'
    else:  # daily
        start = now - timedelta(days=30)
        date_fmt = '%Y-%m-%d'
        label_fmt = '%d %b'

    # Query scans grouped by date period
    records = ScanRecord.query.filter(
        ScanRecord.created_at >= start
    ).order_by(ScanRecord.created_at.asc()).all()

    # Aggregate
    buckets = {}
    for r in records:
        key = r.created_at.strftime(date_fmt)
        if key not in buckets:
            buckets[key] = {
                'label': r.created_at.strftime(label_fmt),
                'total_items': 0,
                'clean': 0,
                'contaminated': 0,
                'recyclable': 0,
                'non_recyclable': 0,
                'scans': 0,
            }
        b = buckets[key]
        b['total_items'] += r.total_items
        b['clean'] += r.clean_count
        b['contaminated'] += r.contaminated_count
        b['recyclable'] += r.recyclable_count
        b['non_recyclable'] += r.non_recyclable_count
        b['scans'] += 1

    sorted_keys = sorted(buckets.keys())
    trend_data = [buckets[k] for k in sorted_keys]

    return jsonify({
        'period': period,
        'data': trend_data,
    })


# ---------------------------------------------------------------------------
# API: Category breakdown by date (stacked bar / line)
# ---------------------------------------------------------------------------
@app.route('/api/category-trends')
def api_category_trends():
    """Category counts over time for the dashboard."""
    period = request.args.get('period', 'daily')
    now = datetime.utcnow()

    if period == 'weekly':
        start = now - timedelta(weeks=12)
        date_fmt = '%Y-%W'
    elif period == 'monthly':
        start = now - timedelta(days=365)
        date_fmt = '%Y-%m'
    else:
        start = now - timedelta(days=30)
        date_fmt = '%Y-%m-%d'

    items = db.session.query(
        DetectedItem.category,
        DetectedItem.quality,
        func.count(DetectedItem.id),
    ).join(ScanRecord).filter(
        ScanRecord.created_at >= start
    ).group_by(DetectedItem.category, DetectedItem.quality).all()

    result = {}
    for cat, quality, count in items:
        if cat not in result:
            meta = WASTE_CATEGORIES.get(cat, {})
            result[cat] = {
                'name_th': meta.get('name_th', cat),
                'color': meta.get('color', '#999'),
                'clean': 0,
                'contaminated': 0,
                'total': 0,
            }
        result[cat][quality] = count
        result[cat]['total'] += count

    return jsonify(result)


# ---------------------------------------------------------------------------
# API: Export data as CSV
# ---------------------------------------------------------------------------
@app.route('/api/export')
def api_export():
    """Export scan data as a downloadable CSV file."""
    output = io.StringIO()
    writer = csv.writer(output)

    # Header row
    writer.writerow([
        'Scan ID', 'Date', 'Image', 'Item #', 'Category', 'Category (TH)',
        'Confidence', 'Quality', 'Quality Confidence',
        'Recyclable', 'Suggested Bin', 'Recommendation',
    ])

    records = ScanRecord.query.order_by(ScanRecord.created_at.desc()).all()
    for rec in records:
        for i, item in enumerate(rec.items, 1):
            writer.writerow([
                rec.id,
                rec.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                rec.image_filename,
                i,
                item.category,
                item.category_th,
                f"{item.confidence:.4f}",
                item.quality,
                f"{item.quality_confidence:.4f}",
                'Yes' if item.recyclable else 'No',
                item.suggested_bin,
                item.recommendation.replace('\n', ' | '),
            ])

    output.seek(0)
    buf = io.BytesIO()
    buf.write(output.getvalue().encode('utf-8-sig'))  # BOM for Excel
    buf.seek(0)

    filename = f"ecosort_export_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
    return send_file(
        buf,
        as_attachment=True,
        download_name=filename,
        mimetype='text/csv',
    )


# ---------------------------------------------------------------------------
# API: Model status
# ---------------------------------------------------------------------------
@app.route('/api/model-status')
def api_model_status():
    """Check which AI models are loaded and in what mode."""
    return jsonify(model_status())


# ===========================================================================
# New API Routes: Auth, Gamification, Prediction, Live Scan, Report
# ===========================================================================

# ---------------------------------------------------------------------------
# API: User Registration
# ---------------------------------------------------------------------------
@app.route('/api/register', methods=['POST'])
def api_register():
    """Register a new user account."""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'ไม่พบข้อมูล'}), 400

    username = data.get('username', '').strip()
    email = data.get('email', '').strip()
    password = data.get('password', '')

    if not username or not email or not password:
        return jsonify({'error': 'กรุณากรอกข้อมูลให้ครบ'}), 400
    if len(username) < 3:
        return jsonify({'error': 'ชื่อผู้ใช้ต้องมีอย่างน้อย 3 ตัวอักษร'}), 400
    if len(password) < 6:
        return jsonify({'error': 'รหัสผ่านต้องมีอย่างน้อย 6 ตัวอักษร'}), 400

    if User.query.filter_by(username=username).first():
        return jsonify({'error': 'ชื่อผู้ใช้นี้มีอยู่แล้ว'}), 400
    if User.query.filter_by(email=email).first():
        return jsonify({'error': 'อีเมลนี้ถูกใช้แล้ว'}), 400

    user = User(username=username, email=email)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()

    flask_session['user_id'] = user.id
    return jsonify({'success': True, 'user': user.to_dict()})


# ---------------------------------------------------------------------------
# API: User Login
# ---------------------------------------------------------------------------
@app.route('/api/login', methods=['POST'])
def api_login():
    """Log in an existing user."""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'ไม่พบข้อมูล'}), 400

    username = data.get('username', '').strip()
    password = data.get('password', '')

    user = User.query.filter_by(username=username).first()
    if user is None or not user.check_password(password):
        return jsonify({'error': 'ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง'}), 401

    flask_session['user_id'] = user.id
    return jsonify({'success': True, 'user': user.to_dict()})


# ---------------------------------------------------------------------------
# API: User Logout
# ---------------------------------------------------------------------------
@app.route('/api/logout', methods=['POST'])
def api_logout():
    """Log out the current user."""
    flask_session.pop('user_id', None)
    return jsonify({'success': True})


# ---------------------------------------------------------------------------
# API: Current user info
# ---------------------------------------------------------------------------
@app.route('/api/user')
def api_user():
    """Get current logged-in user info with badges."""
    user = current_user()
    if user is None:
        return jsonify({'logged_in': False})
    badges = _gamification.get_badges(user.points)
    current_badge = _gamification.get_current_badge(user.points)
    next_badge = _gamification.get_next_badge(user.points)
    return jsonify({
        'logged_in': True,
        'user': user.to_dict(),
        'badges': badges,
        'current_badge': current_badge,
        'next_badge': next_badge,
        'progress': _gamification.get_progress_to_next(user.points),
    })


# ---------------------------------------------------------------------------
# API: Leaderboard
# ---------------------------------------------------------------------------
@app.route('/api/leaderboard')
def api_leaderboard():
    """Get the community leaderboard (top users by points)."""
    limit = request.args.get('limit', 20, type=int)
    users = User.query.order_by(User.points.desc()).limit(limit).all()

    leaderboard_data = []
    for rank, u in enumerate(users, 1):
        badge = _gamification.get_current_badge(u.points)
        leaderboard_data.append({
            'rank': rank,
            'id': u.id,
            'username': u.username,
            'points': u.points,
            'total_scans': u.total_scans,
            'total_items_sorted': u.total_items_sorted,
            'total_recyclable': u.total_recyclable,
            'co2_saved': round(u.co2_saved, 4),
            'badge_icon': badge['icon'],
            'badge_name': badge['name'],
            'created_at': u.created_at.isoformat() if u.created_at else None,
        })

    return jsonify({
        'leaderboard': leaderboard_data,
        'total_users': User.query.count(),
    })


# ---------------------------------------------------------------------------
# API: Waste Prediction (Time Series)
# ---------------------------------------------------------------------------
@app.route('/api/prediction')
def api_prediction():
    """Predict future waste generation using time series analysis."""
    days = request.args.get('days', 7, type=int)
    days = min(days, 30)  # cap at 30 days

    # Get all historical scan records
    records = ScanRecord.query.order_by(ScanRecord.created_at.asc()).all()

    if len(records) < 2:
        return jsonify({
            'error': 'ยังไม่มีข้อมูลเพียงพอ ต้องมีอย่างน้อย 2 ครั้งการสแกน',
            'predictions': [],
            'historical': [],
        })

    result = _predictor.predict(records, days_ahead=days)

    # Also predict by category
    category_pred = _predictor.predict_by_category(records, days_ahead=days)

    return jsonify({
        'prediction': result,
        'category_prediction': category_pred,
    })


# ---------------------------------------------------------------------------
# API: Live Scan (single frame from camera)
# ---------------------------------------------------------------------------
@app.route('/api/scan-live', methods=['POST'])
def api_scan_live():
    """
    Process a single frame from the real-time camera.
    Same pipeline as /api/scan but optimized for speed (lower confidence
    threshold, no file save needed).
    """
    if 'image' not in request.files:
        return jsonify({'error': 'ไม่พบภาพ'}), 400

    file = request.files['image']
    ext = 'jpg'
    filename = f"live_{uuid.uuid4().hex[:8]}.{ext}"
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)
    start_live = time.time()

    try:
        detector = get_detector()
        detections = detector.detect(filepath)

        if not detections:
            # Clean up the temp file
            os.remove(filepath)
            return jsonify({'success': True, 'detections': [],
                            'total_items': 0, 'message': 'ไม่พบวัตถุ'})

        classifier = get_classifier()
        for det in detections:
            result = classifier.classify(filepath, bbox=det['bbox'])
            det['quality'] = result['quality']
            det['quality_confidence'] = result['confidence']

        _recommender.recommend_batch(detections)

        co2_result = _carbon.calculate_savings(detections)
        points_result = _gamification.calculate_scan_points(detections)

        # Keep the file so the user can choose to save this scan.
        # It will be cleaned up the next time the server starts, or
        # automatically by the OS temp-file rotation.
        # (We no longer delete it here.)

        return jsonify({
            'success': True,
            'detections': detections,
            'image_filename': filename,          # needed by /api/save
            'total_items': len(detections),
            'clean_count': sum(1 for d in detections if d['quality'] == 'clean'),
            'contaminated_count': sum(1 for d in detections if d['quality'] != 'clean'),
            'recyclable_count': sum(1 for d in detections if d.get('recyclable', False)),
            'non_recyclable_count': sum(1 for d in detections if not d.get('recyclable', False)),
            'co2_saved': co2_result['total_co2'],
            'carbon': co2_result,
            'points': points_result,
            'processing_time': round(time.time() - start_live, 3),
        })

    except Exception as e:
        if os.path.exists(filepath):
            os.remove(filepath)
        logger.exception("Live scan error")
        return jsonify({'error': str(e)}), 500


# ---------------------------------------------------------------------------
# API: Carbon Impact Summary
# ---------------------------------------------------------------------------
@app.route('/api/carbon-impact')
def api_carbon_impact():
    """Get overall carbon impact summary for the community."""
    total_co2 = db.session.query(
        func.coalesce(func.sum(ScanRecord.co2_saved), 0)
    ).scalar()

    # Per-category CO2
    items = db.session.query(
        DetectedItem.category,
        func.sum(ScanRecord.co2_saved),
    ).join(ScanRecord).group_by(DetectedItem.category).all()

    per_category = {}
    for cat, co2 in items:
        meta = WASTE_CATEGORIES.get(cat, {})
        per_category[cat] = {
            'name_th': meta.get('name_th', cat),
            'co2': round(float(co2 or 0), 4),
        }

    calc = CarbonFootprintCalculator()
    impact = {
        'total_co2': round(float(total_co2 or 0), 4),
        'trees_equivalent': round(float(total_co2 or 0) / 21.0, 4),
        'km_driven_equivalent': round(float(total_co2 or 0) / 0.4, 2),
        'per_category': per_category,
        'impact_text': calc.format_impact_text({
            'total_co2': float(total_co2 or 0),
            'trees_equivalent': float(total_co2 or 0) / 21.0,
            'km_driven_equivalent': float(total_co2 or 0) / 0.4,
            'phone_charges_equivalent': int(float(total_co2 or 0) / 0.005),
        }),
    }

    return jsonify(impact)


# ---------------------------------------------------------------------------
# API: PDF Report Generator
# ---------------------------------------------------------------------------
@app.route('/api/report')
def api_report():
    """Generate a downloadable PDF report with full Thai text support."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    # --- Register Thai fonts ---
    fonts_dir = os.path.join(BASE_DIR, 'static', 'fonts')
    font_regular = os.path.join(fonts_dir, 'Sarabun-Regular.ttf')
    font_bold    = os.path.join(fonts_dir, 'Sarabun-Bold.ttf')

    if os.path.exists(font_regular) and os.path.exists(font_bold):
        pdfmetrics.registerFont(TTFont('Sarabun',     font_regular))
        pdfmetrics.registerFont(TTFont('Sarabun-Bold', font_bold))
        THAI_FONT   = 'Sarabun'
        THAI_BOLD   = 'Sarabun-Bold'
    else:
        # Fallback: no Thai glyphs but won't crash
        THAI_FONT = THAI_BOLD = 'Helvetica'

    # --- Colour palette ---
    GREEN     = colors.HexColor('#16a34a')
    GREEN_LT  = colors.HexColor('#dcfce7')
    BLUE      = colors.HexColor('#1d4ed8')
    BLUE_LT   = colors.HexColor('#dbeafe')
    DARK      = colors.HexColor('#1e293b')
    DARK_ALT  = colors.HexColor('#f8fafc')
    GREY      = colors.HexColor('#64748b')

    # --- Styles ---
    def make_style(name, font=THAI_FONT, size=10, bold=False,
                   align=TA_LEFT, color=colors.black):
        fn = THAI_BOLD if bold else font
        return ParagraphStyle(name, fontName=fn, fontSize=size,
                              alignment=align, textColor=color,
                              leading=size * 1.5, encoding='utf-8')

    style_title    = make_style('T', font=THAI_BOLD, size=22, bold=True,
                                align=TA_CENTER, color=GREEN)
    style_subtitle = make_style('Sub', size=10, align=TA_CENTER, color=GREY)
    style_h2       = make_style('H2', font=THAI_BOLD, size=13, bold=True, color=DARK)
    style_body     = make_style('B', size=9, color=DARK)
    style_footer   = make_style('F', size=8, align=TA_CENTER, color=GREY)
    style_cell     = make_style('C', size=9)
    style_cell_hdr = make_style('CH', font=THAI_BOLD, size=9, bold=True,
                                color=colors.white)

    # helper: wrap text in a Paragraph so Thai renders correctly in tables
    def P(text, style=None):
        return Paragraph(str(text), style or style_cell)
    def PH(text):
        return Paragraph(str(text), style_cell_hdr)

    # Table style helpers
    def base_table_style(header_color):
        return TableStyle([
            # Header row
            ('BACKGROUND',   (0, 0), (-1, 0),  header_color),
            ('TEXTCOLOR',    (0, 0), (-1, 0),  colors.white),
            ('FONTNAME',     (0, 0), (-1, 0),  THAI_BOLD),
            ('FONTSIZE',     (0, 0), (-1, 0),  9),
            ('BOTTOMPADDING',(0, 0), (-1, 0),  7),
            ('TOPPADDING',   (0, 0), (-1, 0),  7),
            # Body rows
            ('FONTNAME',     (0, 1), (-1, -1), THAI_FONT),
            ('FONTSIZE',     (0, 1), (-1, -1), 9),
            ('ROWBACKGROUNDS',(0, 1),(-1, -1), [colors.white, DARK_ALT]),
            ('GRID',         (0, 0), (-1, -1), 0.4, colors.HexColor('#cbd5e1')),
            ('VALIGN',       (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING',  (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING',   (0, 1), (-1, -1), 5),
            ('BOTTOMPADDING',(0, 1), (-1, -1), 5),
        ])

    # --- Gather data ---
    total_scans       = ScanRecord.query.count()
    total_items       = int(db.session.query(func.coalesce(func.sum(ScanRecord.total_items), 0)).scalar() or 0)
    total_clean       = int(db.session.query(func.coalesce(func.sum(ScanRecord.clean_count), 0)).scalar() or 0)
    total_contaminated= int(db.session.query(func.coalesce(func.sum(ScanRecord.contaminated_count), 0)).scalar() or 0)
    total_recyclable  = int(db.session.query(func.coalesce(func.sum(ScanRecord.recyclable_count), 0)).scalar() or 0)
    total_co2         = float(db.session.query(func.coalesce(func.sum(ScanRecord.co2_saved), 0)).scalar() or 0)
    total_users       = User.query.count()
    total_points      = int(db.session.query(func.coalesce(func.sum(ScanRecord.points_earned), 0)).scalar() or 0)

    cat_data = db.session.query(
        DetectedItem.category, func.count(DetectedItem.id)
    ).join(ScanRecord).group_by(DetectedItem.category)\
     .order_by(func.count(DetectedItem.id).desc()).all()

    recent = ScanRecord.query.order_by(ScanRecord.created_at.desc()).limit(15).all()

    # --- Build PDF ---
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            topMargin=18*mm, bottomMargin=18*mm,
                            leftMargin=20*mm, rightMargin=20*mm)
    story = []

    # ── Title block ──
    story.append(Paragraph("EcoSort AI", style_title))
    story.append(Paragraph("รายงานการจัดการขยะชุมชน", style_title))
    story.append(Spacer(1, 3*mm))
    story.append(Paragraph(
        f"วันที่สร้างรายงาน: {datetime.now().strftime('%d/%m/%Y เวลา %H:%M น.')}",
        style_subtitle))
    story.append(Spacer(1, 8*mm))

    # ── Section 1: สรุปสถิติ ──
    story.append(Paragraph("1. สรุปสถิติทั่วไป", style_h2))
    story.append(Spacer(1, 3*mm))

    summary_rows = [
        [PH("ตัวชี้วัด"), PH("ค่า")],
        [P("จำนวนครั้งการสแกนทั้งหมด"),        P(f"{total_scans:,} ครั้ง")],
        [P("จำนวนชิ้นขยะที่ตรวจพบ"),           P(f"{total_items:,} ชิ้น")],
        [P("ขยะสะอาด"),                          P(f"{total_clean:,} ชิ้น")],
        [P("ขยะมีสิ่งปนเปื้อน"),                P(f"{total_contaminated:,} ชิ้น")],
        [P("ขยะที่รีไซเคิลได้"),                 P(f"{total_recyclable:,} ชิ้น")],
        [P("CO2 ที่ลดได้"),                       P(f"{total_co2:.4f} kg")],
        [P("เทียบเท่าต้นไม้ดูดซับ CO2"),          P(f"{total_co2/21.0:.4f} ต้น/ปี")],
        [P("เทียบเท่าการขับรถที่ลดลง"),           P(f"{total_co2/0.4:.2f} km")],
        [P("จำนวนสมาชิกในระบบ"),                 P(f"{total_users:,} คน")],
        [P("คะแนนรีไซเคิลรวม"),                  P(f"{total_points:,} คะแนน")],
    ]
    t1 = Table(summary_rows, colWidths=[110*mm, 55*mm])
    t1.setStyle(base_table_style(GREEN))
    story.append(t1)
    story.append(Spacer(1, 7*mm))

    # ── Section 2: ประเภทขยะ ──
    if cat_data:
        story.append(Paragraph("2. สถิติขยะตามประเภท", style_h2))
        story.append(Spacer(1, 3*mm))
        cat_rows = [[PH("ประเภทขยะ"), PH("ชื่อไทย"), PH("จำนวน (ชิ้น)")]]
        for cat, count in cat_data:
            meta = WASTE_CATEGORIES.get(cat, {})
            cat_rows.append([
                P(cat),
                P(meta.get('name_th', cat)),
                P(f"{count:,}"),
            ])
        t2 = Table(cat_rows, colWidths=[40*mm, 85*mm, 40*mm])
        t2.setStyle(base_table_style(BLUE))
        story.append(t2)
        story.append(Spacer(1, 7*mm))

    # ── Section 3: ประวัติการสแกน ──
    if recent:
        story.append(Paragraph("3. ประวัติการสแกนล่าสุด", style_h2))
        story.append(Spacer(1, 3*mm))
        scan_rows = [[
            PH("ID"), PH("วันที่"), PH("ชิ้น"),
            PH("สะอาด"), PH("ปนเปื้อน"), PH("CO2 (kg)"), PH("คะแนน")
        ]]
        for s in recent:
            dt_str = s.created_at.strftime('%d/%m/%y %H:%M') if s.created_at else '-'
            scan_rows.append([
                P(str(s.id)),
                P(dt_str),
                P(str(s.total_items)),
                P(str(s.clean_count)),
                P(str(s.contaminated_count)),
                P(f"{s.co2_saved:.3f}"),
                P(str(s.points_earned)),
            ])
        t3 = Table(scan_rows, colWidths=[13*mm, 35*mm, 15*mm, 18*mm, 20*mm, 24*mm, 20*mm])
        t3.setStyle(base_table_style(DARK))
        story.append(t3)

    story.append(Spacer(1, 10*mm))
    story.append(Paragraph(
        "รายงานนี้สร้างโดย EcoSort AI  —  CS461 Final Project  —  ข้อมูลจาก EcoSort Database",
        style_footer))

    doc.build(story)
    buf.seek(0)

    filename = f"ecosort_report_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.pdf"
    return send_file(buf, as_attachment=True,
                     download_name=filename, mimetype='application/pdf')


# ---------------------------------------------------------------------------
# Smart Waste Action Planner + Recovery
# ---------------------------------------------------------------------------
def api_login_required(fn):
    """Decorator: return JSON 401 if not logged in (for API routes)."""
    from functools import wraps
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if current_user() is None:
            return jsonify({'error': 'กรุณาเข้าสู่ระบบก่อนใช้งานส่วนนี้',
                            'login_required': True}), 401
        return fn(*args, **kwargs)
    return wrapper


def _own_plan_or_404(plan_id):
    user = current_user()
    plan = WasteActionPlan.query.filter_by(id=plan_id, user_id=user.id).first()
    return plan


def _own_task_or_404(task_id):
    user = current_user()
    return (PlanTask.query.join(WasteActionPlan)
            .filter(PlanTask.id == task_id, WasteActionPlan.user_id == user.id)
            .first())


@app.route('/waste-planner')
@login_required
def waste_planner():
    """Smart Waste Action Planner page."""
    return render_template('waste_planner.html', user=current_user(),
                           categories=WASTE_CATEGORIES)


@app.route('/waste-recovery')
@login_required
def waste_recovery():
    """Waste Recovery Center page."""
    return render_template('waste_recovery.html', user=current_user(),
                           categories=WASTE_CATEGORIES)


@app.route('/api/my-scans')
@api_login_required
def api_my_scans():
    """The user's saved scans, with how many items are still plannable."""
    user = current_user()
    scans = (ScanRecord.query.filter_by(user_id=user.id)
             .order_by(ScanRecord.created_at.desc()).limit(50).all())
    scan_ids = [s.id for s in scans]
    open_items = set()
    if scan_ids:
        open_items = {
            r[0] for r in db.session.query(PlanTask.detected_item_id)
            .join(DetectedItem, DetectedItem.id == PlanTask.detected_item_id)
            .filter(DetectedItem.scan_id.in_(scan_ids),
                    PlanTask.status.in_(('pending', 'in_progress',
                                         'awaiting_review')))
            .all()
        }
    out = []
    for s in scans:
        d = s.to_dict()
        d['image_url'] = f'/static/uploads/{s.image_filename}'
        d['plannable_items'] = sum(1 for i in s.items if i.id not in open_items)
        out.append(d)
    return jsonify({'scans': out})


@app.route('/api/plans', methods=['GET'])
@api_login_required
def api_plans_list():
    user = current_user()
    plans = (WasteActionPlan.query.filter_by(user_id=user.id)
             .order_by(WasteActionPlan.created_at.desc()).all())
    return jsonify({'plans': [p.to_dict() for p in plans]})


@app.route('/api/plans', methods=['POST'])
@api_login_required
def api_plans_create():
    """Create a plan from one or more saved scans."""
    data = request.get_json(silent=True) or {}
    scan_ids = data.get('scan_ids') or []
    if not isinstance(scan_ids, list):
        return jsonify({'error': 'รูปแบบข้อมูลไม่ถูกต้อง'}), 400
    try:
        scan_ids = [int(x) for x in scan_ids]
    except (TypeError, ValueError):
        return jsonify({'error': 'รหัสการสแกนไม่ถูกต้อง'}), 400
    title = (data.get('title') or '').strip()[:128] or None
    try:
        plan, info = _planner.create_plan(current_user(), scan_ids, title)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception:
        db.session.rollback()
        logger.exception('Create plan error')
        return jsonify({'error': 'สร้างแผนไม่สำเร็จ'}), 500
    if plan is None:
        return jsonify({
            'error': 'ขยะทุกชิ้นในการสแกนที่เลือกมีงานที่ยังดำเนินการอยู่แล้ว '
                     'จึงไม่สร้างแผนซ้ำ',
            'info': info}), 409
    return jsonify({'success': True, 'plan': plan.to_dict(with_tasks=True),
                    'info': info}), 201


@app.route('/api/plans/<int:plan_id>', methods=['GET'])
@api_login_required
def api_plan_detail(plan_id):
    plan = _own_plan_or_404(plan_id)
    if plan is None:
        return jsonify({'error': 'ไม่พบแผนนี้'}), 404
    return jsonify({'plan': plan.to_dict(with_tasks=True)})


@app.route('/api/plans/<int:plan_id>', methods=['PATCH'])
@api_login_required
def api_plan_update(plan_id):
    """Rename a plan. (Status is derived from its tasks.)"""
    plan = _own_plan_or_404(plan_id)
    if plan is None:
        return jsonify({'error': 'ไม่พบแผนนี้'}), 404
    data = request.get_json(silent=True) or {}
    title = (data.get('title') or '').strip()
    if not title:
        return jsonify({'error': 'กรุณาระบุชื่อแผน'}), 400
    plan.title = title[:128]
    db.session.commit()
    return jsonify({'success': True, 'plan': plan.to_dict()})


@app.route('/api/plans/<int:plan_id>', methods=['DELETE'])
@api_login_required
def api_plan_delete(plan_id):
    """Delete a plan that has no finished work in it."""
    plan = _own_plan_or_404(plan_id)
    if plan is None:
        return jsonify({'error': 'ไม่พบแผนนี้'}), 404
    if any(t.status != 'pending' for t in plan.tasks):
        return jsonify({'error': 'ลบไม่ได้ เพราะมีงานที่เริ่มดำเนินการแล้ว'}), 409
    db.session.delete(plan)
    db.session.commit()
    return jsonify({'success': True})


@app.route('/api/recovery/tasks')
@api_login_required
def api_recovery_tasks():
    user = current_user()
    q = (PlanTask.query.join(WasteActionPlan)
         .filter(WasteActionPlan.user_id == user.id))
    status = request.args.get('status')
    if status:
        q = q.filter(PlanTask.status == status)
    plan_id = request.args.get('plan_id', type=int)
    if plan_id:
        q = q.filter(PlanTask.plan_id == plan_id)
    tasks = q.order_by(PlanTask.created_at.desc(), PlanTask.id.desc()).all()
    return jsonify({
        'tasks': [dict(t.to_dict(), plan_title=t.plan.title) for t in tasks],
        'summary': _planner.summary(user.id),
    })


def _task_action(task_id, fn):
    """Run a state change on an owned task and return JSON."""
    task = _own_task_or_404(task_id)
    if task is None:
        return jsonify({'error': 'ไม่พบงานนี้'}), 404
    try:
        extra = fn(task) or {}
        _planner.refresh_plan_status(task.plan)
        db.session.commit()
    except ValueError as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 409
    except Exception:
        db.session.rollback()
        logger.exception('Task action error')
        return jsonify({'error': 'ดำเนินการไม่สำเร็จ'}), 500
    return jsonify(dict({'success': True, 'task': task.to_dict(),
                         'plan': task.plan.to_dict()}, **extra))


@app.route('/api/recovery/tasks/<int:task_id>/start', methods=['POST'])
@api_login_required
def api_task_start(task_id):
    return _task_action(task_id, _planner.start)


@app.route('/api/recovery/tasks/<int:task_id>/complete', methods=['POST'])
@api_login_required
def api_task_complete(task_id):
    """User says they have handled the item -> awaiting review."""
    note = ((request.get_json(silent=True) or {}).get('note') or '').strip()[:500]
    return _task_action(task_id, lambda t: _planner.mark_done(t, note))


@app.route('/api/recovery/tasks/<int:task_id>/rescan', methods=['POST'])
@api_login_required
def api_task_rescan(task_id):
    """Re-scan the item after handling it (stores evidence, does not close)."""
    task = _own_task_or_404(task_id)
    if task is None:
        return jsonify({'error': 'ไม่พบงานนี้'}), 404
    if task.status != 'awaiting_review':
        return jsonify({'error': 'สแกนซ้ำได้เฉพาะงานที่รอตรวจสอบ'}), 409
    file = request.files.get('image')
    if file is None or file.filename == '' or not allowed_file(file.filename):
        return jsonify({'error': 'กรุณาแนบภาพ PNG, JPG, JPEG หรือ WEBP'}), 400

    ext = file.filename.rsplit('.', 1)[1].lower()
    filename = f"{uuid.uuid4().hex}.{ext}"
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)
    try:
        detections = get_detector().detect(filepath)
        if not detections:
            return jsonify({'error': 'ไม่พบวัตถุในภาพ กรุณาถ่ายใหม่ให้เห็นชิ้นงานชัดเจน'}), 422
        # Prefer the same category; otherwise the most confident detection
        same = [d for d in detections if d['category'] == task.category]
        best = max(same or detections, key=lambda d: d.get('confidence', 0))
        res = get_classifier().classify(filepath, bbox=best['bbox'])
        _planner.apply_rescan(task, {
            'image': filename, 'category': best['category'],
            'quality': res['quality'], 'confidence': res['confidence'],
        })
        db.session.commit()
    except ValueError as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 409
    except Exception:
        db.session.rollback()
        logger.exception('Rescan error')
        return jsonify({'error': 'สแกนซ้ำไม่สำเร็จ'}), 500
    return jsonify({'success': True, 'task': task.to_dict(),
                    'category_changed': best['category'] != task.category})


@app.route('/api/recovery/tasks/<int:task_id>/verify', methods=['POST'])
@api_login_required
def api_task_verify(task_id):
    """User confirms the result: recovered=true -> completed, false -> unable."""
    data = request.get_json(silent=True) or {}
    if 'recovered' not in data:
        return jsonify({'error': 'กรุณาระบุผลการจัดการ (recovered)'}), 400
    recovered = bool(data['recovered'])
    note = (data.get('note') or '').strip()[:500]
    user = current_user()

    def run(task):
        pts = _planner.verify(task, recovered, note)
        if pts:
            user.points += pts
        return {'points_awarded': pts, 'user_points': user.points}

    return _task_action(task_id, run)


@app.route('/api/recovery/stats')
def api_recovery_stats():
    """Community-wide recovery statistics (for the dashboard)."""
    return jsonify(_planner.summary())



# ---------------------------------------------------------------------------
# Recycling Location Map
# ---------------------------------------------------------------------------
@app.route('/recycling-map')
def recycling_map():
    """Map of drop-off / buy-back points for recyclables."""
    return render_template('recycling_map.html', user=current_user(),
                           categories=WASTE_CATEGORIES,
                           point_types=POINT_TYPES)


@app.route('/api/recycling-points')
def api_recycling_points():
    """List recycling points, optionally sorted by distance from lat/lng.

    Query: lat, lng, type (bottle|junk_shop|waste_bank|ewaste),
           category (plastic|paper|...), limit
    """
    lat = request.args.get('lat', type=float)
    lng = request.args.get('lng', type=float)
    ptype = request.args.get('type')
    category = request.args.get('category')
    limit = min(request.args.get('limit', 100, type=int), 300)

    q = RecyclingPoint.query
    if ptype:
        q = q.filter(RecyclingPoint.point_type == ptype)
    elif category:
        q = q.filter(RecyclingPoint.point_type.in_(types_for_category(category)))
    points = q.all()
    return jsonify({'points': nearest_points(points, lat, lng, category, limit)})

# ---------------------------------------------------------------------------
# Create database tables
# ---------------------------------------------------------------------------
with app.app_context():
    db.create_all()
    seed_recycling_points(db, RecyclingPoint)
    logger.info("Database initialized at: %s",
                app.config['SQLALCHEMY_DATABASE_URI'])


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if __name__ == '__main__':
    logger.info("Starting EcoSort AI...")
    logger.info("Model status: %s", model_status())
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)
