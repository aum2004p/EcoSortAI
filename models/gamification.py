"""
EcoSort AI - Gamification Module
==================================
Manages user points, badges, and leaderboard rankings.

Points system:
  - Clean recyclable item: 10 points
  - Contaminated recyclable item: 5 points
  - General waste (sorted): 2 points
  - All-clean scan bonus: +5 points

Badges are tiered by total accumulated points.
"""

from config import (
    BADGES,
    POINTS_PER_CLEAN_RECYCLABLE,
    POINTS_PER_DIRTY_RECYCLABLE,
    POINTS_PER_GENERAL,
    BONUS_FULL_CLEAN_SCAN,
    WASTE_CATEGORIES,
)


class GamificationEngine:
    """Calculate points and manage badges for waste sorting."""

    def calculate_scan_points(self, detections):
        """
        Calculate points earned for a single scan.

        Args:
            detections: list of detection dicts with 'recyclable', 'quality'.

        Returns:
            dict with points, co2_saved, breakdown.
        """
        points = 0
        clean_count = 0
        total_count = len(detections)

        for det in detections:
            if det.get('recyclable', False):
                if det.get('quality') == 'clean':
                    points += POINTS_PER_CLEAN_RECYCLABLE
                    clean_count += 1
                else:
                    points += POINTS_PER_DIRTY_RECYCLABLE
            else:
                points += POINTS_PER_GENERAL

        # Bonus: all items clean
        if total_count > 0 and clean_count == total_count:
            points += BONUS_FULL_CLEAN_SCAN

        return {
            'points': points,
            'clean_items': clean_count,
            'total_items': total_count,
            'bonus_applied': clean_count == total_count and total_count > 0,
        }

    def get_badges(self, total_points):
        """
        Return all badges with earned status based on total points.

        Returns list of dicts:
            {name, name_en, icon, description, points_required, earned}
        """
        result = []
        for badge in BADGES:
            result.append({
                'name': badge['name'],
                'name_en': badge['name_en'],
                'icon': badge['icon'],
                'description': badge['description'],
                'points_required': badge['points_required'],
                'earned': total_points >= badge['points_required'],
            })
        return result

    def get_current_badge(self, total_points):
        """Return the highest badge the user has earned."""
        current = BADGES[0]
        for badge in BADGES:
            if total_points >= badge['points_required']:
                current = badge
        return current

    def get_next_badge(self, total_points):
        """Return the next badge to earn, or None if max reached."""
        for badge in BADGES:
            if total_points < badge['points_required']:
                return badge
        return None

    def get_progress_to_next(self, total_points):
        """Return progress percentage to next badge."""
        next_badge = self.get_next_badge(total_points)
        if next_badge is None:
            return 100.0

        current_badge = self.get_current_badge(total_points)
        current_req = current_badge['points_required']
        next_req = next_badge['points_required']

        if next_req == current_req:
            return 100.0

        progress = (total_points - current_req) / (next_req - current_req) * 100
        return round(progress, 1)
