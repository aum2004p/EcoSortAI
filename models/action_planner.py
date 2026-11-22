"""
EcoSort AI - Smart Waste Action Planner
=========================================
Turns saved scan results (DetectedItem rows) into a plan made of tasks.

Rules are (category, quality) -> action. Steps come from the existing
RecommendationEngine knowledge base so advice stays consistent with the
scanner page.

Also owns the task state machine and the points rule for recovery.
"""

from datetime import datetime

from config import WASTE_CATEGORIES
from models.database import (
    db, WasteActionPlan, PlanTask, DetectedItem, ScanRecord, OPEN_TASK_STATUSES,
)
from models.recommendation import KNOWLEDGE_BASE

# Allowed status transitions: current -> set of next states
TRANSITIONS = {
    'pending': {'in_progress'},
    'in_progress': {'awaiting_review'},
    'awaiting_review': {'completed', 'unable'},
    'completed': set(),
    'unable': set(),
}

# Points granted when a task is verified as completed
POINTS_RECOVERED = 10     # contaminated item cleaned and confirmed
POINTS_COLLECTED = 3      # clean item collected / general waste handled

ACTION_LABELS = {
    'collect': 'รวบรวมและจัดเก็บ',
    'clean': 'ทำความสะอาดก่อนรีไซเคิล',
    'separate': 'แยกส่วนที่เปื้อนออก',
    'dispose_general': 'ทิ้งเป็นขยะทั่วไป',
}


class ActionPlanner:
    """Create plans and drive task state changes."""

    # ------------------------------------------------------------------
    # Rule table
    # ------------------------------------------------------------------
    def build_task_spec(self, category, quality):
        """Return dict(action_type, title, steps[]) for a (category, quality)."""
        meta = WASTE_CATEGORIES.get(category, {})
        name = meta.get('name_th', category)
        kb = KNOWLEDGE_BASE.get(category, {})
        bin_name = meta.get('bin', 'ถังขยะทั่วไป')

        if not meta.get('recyclable', False):
            steps = ['นำไปทิ้งในถังขยะทั่วไป']
            note = kb.get('not_recyclable_note')
            if note:
                steps.append(note)
            return {'action_type': 'dispose_general',
                    'title': f'ทิ้ง{name}เป็นขยะทั่วไป', 'steps': steps}

        if quality == 'contaminated':
            if category in ('paper', 'cardboard'):
                action = 'separate'
                title = f'แยกส่วนที่เปื้อนของ{name}'
            else:
                action = 'clean'
                title = f'ทำความสะอาด{name}'
            steps = list(kb.get('preparation_dirty', []))
            if category == 'glass':
                steps.insert(0, 'ระวังเศษแก้วบาด สวมถุงมือก่อนจัดการ')
            steps.append('สแกนซ้ำเพื่อตรวจสอบผล แล้วกดยืนยัน')
            return {'action_type': action, 'title': title, 'steps': steps}

        steps = list(kb.get('preparation_clean', []))
        steps.append(f'นำไปทิ้งที่{bin_name}')
        return {'action_type': 'collect',
                'title': f'รวบรวม{name}สะอาด', 'steps': steps}

    # ------------------------------------------------------------------
    # Plan creation
    # ------------------------------------------------------------------
    def create_plan(self, user, scan_ids, title=None):
        """
        Create a plan for `user` from the given scans.

        Returns (plan, info) where info = {'created': n, 'skipped_open': n,
        'skipped_duplicates': n}. Returns (None, info) if nothing to do.
        Raises ValueError for invalid input.
        """
        # De-duplicate scan ids so the same scan is never counted twice
        unique_ids = []
        for sid in scan_ids:
            sid = int(sid)
            if sid not in unique_ids:
                unique_ids.append(sid)
        duplicates = len(scan_ids) - len(unique_ids)
        if not unique_ids:
            raise ValueError('กรุณาเลือกประวัติการสแกนอย่างน้อย 1 รายการ')

        scans = ScanRecord.query.filter(
            ScanRecord.id.in_(unique_ids),
            ScanRecord.user_id == user.id,
        ).all()
        if len(scans) != len(unique_ids):
            raise ValueError('พบประวัติการสแกนที่ไม่ใช่ของคุณหรือไม่มีอยู่จริง')

        items = DetectedItem.query.filter(
            DetectedItem.scan_id.in_(unique_ids)
        ).order_by(DetectedItem.id).all()
        if not items:
            raise ValueError('ประวัติการสแกนที่เลือกไม่มีวัตถุที่ตรวจพบ')

        # Items that already have an open task are skipped (no duplicate work)
        open_item_ids = {
            row[0] for row in db.session.query(PlanTask.detected_item_id)
            .filter(PlanTask.detected_item_id.in_([i.id for i in items]),
                    PlanTask.status.in_(OPEN_TASK_STATUSES))
            .all()
        }
        fresh = [i for i in items if i.id not in open_item_ids]
        info = {'created': len(fresh), 'skipped_open': len(open_item_ids),
                'skipped_duplicates': duplicates}
        if not fresh:
            return None, info

        plan = WasteActionPlan(
            user_id=user.id,
            title=title or f"แผนจัดการขยะ {datetime.now():%d/%m/%Y %H:%M}",
            scan_ids=','.join(str(i) for i in unique_ids),
        )
        db.session.add(plan)
        db.session.flush()

        for item in fresh:
            spec = self.build_task_spec(item.category, item.quality)
            db.session.add(PlanTask(
                plan_id=plan.id,
                detected_item_id=item.id,
                action_type=spec['action_type'],
                title=spec['title'],
                instruction='\n'.join(spec['steps']),
                category=item.category,
                before_quality=item.quality,
            ))
        db.session.commit()
        return plan, info

    # ------------------------------------------------------------------
    # State machine
    # ------------------------------------------------------------------
    def can_transition(self, task, new_status):
        return new_status in TRANSITIONS.get(task.status, set())

    def start(self, task):
        self._move(task, 'in_progress')
        task.started_at = datetime.utcnow()

    def mark_done(self, task, note=''):
        self._move(task, 'awaiting_review')
        task.done_at = datetime.utcnow()
        if note:
            task.note = note

    def apply_rescan(self, task, after):
        """Store re-scan evidence on a task (only while awaiting review)."""
        if task.status != 'awaiting_review':
            raise ValueError('สแกนซ้ำได้เฉพาะงานที่อยู่ในสถานะรอตรวจสอบ')
        task.after_image = after.get('image')
        task.after_category = after.get('category')
        task.after_quality = after.get('quality')
        task.after_quality_confidence = after.get('confidence')

    def verify(self, task, recovered, note=''):
        """
        Close a task after review.

        recovered: True -> completed, False -> unable.
        The original 'before' snapshot is never changed. If a re-scan exists
        and disagrees with what the user claims, `mismatch` is recorded
        (the user's confirmation still decides the final status).
        Returns the points awarded.
        """
        self._move(task, 'completed' if recovered else 'unable')
        task.user_confirmed = True
        task.completed_at = datetime.utcnow()
        if note:
            task.note = note

        if task.after_quality:
            if recovered and task.before_quality == 'contaminated':
                task.mismatch = task.after_quality != 'clean'
            if task.after_category and task.after_category != task.category:
                task.mismatch = True

        awarded = 0
        if recovered and task.points_awarded == 0:
            awarded = (POINTS_RECOVERED if task.before_quality == 'contaminated'
                       else POINTS_COLLECTED)
            task.points_awarded = awarded
        return awarded

    def _move(self, task, new_status):
        if not self.can_transition(task, new_status):
            raise ValueError(
                f'ไม่สามารถเปลี่ยนสถานะจาก {task.status} เป็น {new_status} ได้')
        task.status = new_status

    def refresh_plan_status(self, plan):
        """Plan is 'done' when every task is closed."""
        if plan.tasks and all(t.status in ('completed', 'unable')
                              for t in plan.tasks):
            plan.status = 'done'
        else:
            plan.status = 'active'

    # ------------------------------------------------------------------
    # Aggregates (for dashboard)
    # ------------------------------------------------------------------
    def summary(self, user_id=None):
        q = PlanTask.query
        if user_id is not None:
            q = q.join(WasteActionPlan).filter(WasteActionPlan.user_id == user_id)
        tasks = q.all()
        by_status = {s: 0 for s in
                     ('pending', 'in_progress', 'awaiting_review',
                      'completed', 'unable')}
        recovered = 0
        mismatches = 0
        problem_cat = {}
        for t in tasks:
            by_status[t.status] = by_status.get(t.status, 0) + 1
            if t.status == 'completed' and t.before_quality == 'contaminated':
                recovered += 1
            if t.mismatch:
                mismatches += 1
            if t.status == 'unable' or (t.before_quality == 'contaminated'
                                        and t.status != 'completed'):
                problem_cat[t.category] = problem_cat.get(t.category, 0) + 1
        total = len(tasks)
        closed = by_status['completed'] + by_status['unable']
        top = max(problem_cat.items(), key=lambda kv: kv[1], default=None)
        return {
            'total_tasks': total,
            'by_status': by_status,
            'open_tasks': total - closed,
            'completion_rate': round(by_status['completed'] / total * 100) if total else 0,
            'contaminated_recovered': recovered,
            'mismatches': mismatches,
            'top_problem_category': (
                {'category': top[0],
                 'name_th': WASTE_CATEGORIES.get(top[0], {}).get('name_th', top[0]),
                 'count': top[1]} if top else None),
        }
