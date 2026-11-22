"""
EcoSort AI - Recommendation Engine
====================================
Rule-based engine that combines waste category and quality status to
produce actionable disposal instructions.

For each detected item the engine returns:
  - suggested_bin:   which bin to use
  - recyclable:      whether the item can be recycled
  - preparation:     steps to prepare the item before disposal
  - recommendation:  full text recommendation (Thai)
"""

from config import WASTE_CATEGORIES


# Knowledge base: per-category rules for clean and contaminated states.
#
# Each entry contains:
#   preparation_clean:  steps when the item is clean
#   preparation_dirty:  steps when the item is contaminated
#   disposal_clean:     final disposal instruction when clean
#   disposal_dirty:      final disposal instruction when contaminated
#   not_recyclable_note: what to do if the item can't be recycled at all

KNOWLEDGE_BASE = {
    'plastic': {
        'preparation_clean': [
            'ตรวจสอบหมายเลขรีไซเคิล (1-7) ที่ก้นขวดหรือตัวภาชนะ',
            'กดให้แบนเพื่อประหยัดพื้นที่ในถัง',
            'นำฝาปิดออก (ฝามักเป็นพลาสติกประเภทอื่น)',
        ],
        'preparation_dirty': [
            'ล้างเศษอาหารและคราบออกด้วยน้ำสะอาด',
            'เช็ดให้แห้งก่อนนำไปรีไซเคิล',
            'กดให้แบนเพื่อประหยัดพื้นที่ในถัง',
            'แยกฝาปิดออก (ฝาอาจเป็นพลาสติกประเภทอื่น)',
        ],
        'disposal_clean': 'นำไปทิ้งในถังพลาสติก/ขวดเพื่อส่งรีไซเคิล',
        'disposal_dirty': 'หากล้างทำความสะอาดได้ ให้ล้างแล้วนำไปรีไซเคิล '
                          'หากล้างไม่ออก ให้ทิ้งเป็นขยะทั่วไป',
        'not_recyclable_note': 'พลาสติกประเภท 3, 4, 6, 7 บางชนิดไม่รับรีไซเคิล '
                                'ตรวจสอบกับศูนย์รับซื้อในพื้นที่',
    },
    'paper': {
        'preparation_clean': [
            'กากัดหรือฉีกกระดาษที่มีข้อมูลส่วนบุคคล',
            'รวมกระดาษเป็นมัดหรือใส่ถุง',
            'ดึกลวดเย็บกระดาษออก (ถ้ามี)',
        ],
        'preparation_dirty': [
            'ถ้าเปื้อนน้ำมันหรืออาหาร ไม่สามารถนำไปรีไซเคิลได้',
            'ถ้าเปื้อนเล็กน้อยให้ตัดส่วนที่เปื้อนออกและทิ้ง',
            'ส่วนที่สะอาดยังสามารถรีไซเคิลได้',
        ],
        'disposal_clean': 'นำไปทิ้งในถังกระดาษเพื่อส่งรีไซเคิล',
        'disposal_dirty': 'กระดาษเปื้อนน้ำมัน/อาหารต้องทิ้งเป็นขยะทั่วไป '
                          'ส่วนที่สะอาดแยกไปรีไซเคิล',
        'not_recyclable_note': 'กระดาษคราบมัน กระดาษเช็ดปาก และกระดาษเปียกน้ำ '
                                'ไม่สามารถรีไซเคิลได้',
    },
    'cardboard': {
        'preparation_clean': [
            'ทำให้กล่องแบนโดยพับเข้าด้านใน',
            'นำเทปและสติกเกอร์ออกให้มากที่สุด',
            'มัดรวมกันเป็นกลุ่ม',
        ],
        'preparation_dirty': [
            'ถ้าเปื้อนน้ำหรืออาหาร ให้ตัดส่วนที่เปื้อนออก',
            'ทำให้กล่องแบนและแยกส่วนที่สะอาด',
        ],
        'disposal_clean': 'นำไปทิ้งในถังกระดาษลังเพื่อส่งรีไซเคิล',
        'disposal_dirty': 'กระดาษลังเปียก/เปื้อนต้องทิ้งเป็นขยะทั่วไป',
        'not_recyclable_note': 'กระดาษลังเคลือบพลาสติกหรือขี้ผึ้ง '
                                'ไม่สามารถรีไซเคิลได้',
    },
    'glass': {
        'preparation_clean': [
            'ล้างให้สะอาดและเช็ดให้แห้ง',
            'นำฝาออก (ฝาอาจเป็นโลหะหรือพลาสติก)',
            'ระวังอย่าให้แตก',
        ],
        'preparation_dirty': [
            'ล้างเศษอาหารและของเหลวออกให้สะอาด',
            'เช็ดให้แห้งก่อนนำไปรีไซเคิล',
            'แยกฝาออกจากขวดแก้ว',
        ],
        'disposal_clean': 'นำไปทิ้งในถังแก้วเพื่อส่งรีไซเคิล',
        'disposal_dirty': 'ล้างให้สะอาดก่อนนำไปรีไซเคิล '
                          'ถ้าล้างไม่ออกให้ทิ้งเป็นขยะทั่วไป',
        'not_recyclable_note': 'กระจก เครื่องแก้วไฟฟ้า และหลอดไฟ '
                                'ไม่สามารถนำไปรีไซเคิลเป็นขวดแก้วได้',
    },
    'metal': {
        'preparation_clean': [
            'ล้างให้สะอาดและเช็ดให้แห้ง',
            'กดกระป๋องให้แบน (ถ้าเป็นกระป๋องอลูมิเนียม)',
            'นำฉลากกระดาษออก (ถ้ามี)',
        ],
        'preparation_dirty': [
            'ล้างเศษอาหารและคราบออกให้สะอาด',
            'เช็ดให้แห้งก่อนนำไปรีไซเคิล',
            'กดกระป๋องให้แบนเพื่อประหยัดพื้นที่',
        ],
        'disposal_clean': 'นำไปทิ้งในถังโลหะ/กระป๋องเพื่อส่งรีไซเคิล',
        'disposal_dirty': 'ล้างให้สะอาดก่อนนำไปรีไซเคิล '
                          'ถ้าล้างไม่ออกให้ทิ้งเป็นขยะทั่วไป',
        'not_recyclable_note': 'กระป๋องสเปรย์และโลหะที่ปนสารเคมี '
                                'ต้องกำจัดตามขยะอันตราย',
    },
    'trash': {
        'preparation_clean': [
            'จัดเรียงให้เรียบร้อย',
            'ลดขนาดให้เล็กลงถ้าเป็นไปได้',
        ],
        'preparation_dirty': [
            'ห่อขยะเปียก/เปื้อนด้วยกระดาษหรือถุงก่อนทิ้ง',
            'แยกขยะเปียกออกจากขยะแห้ง',
        ],
        'disposal_clean': 'นำไปทิ้งในถังขยะทั่วไป',
        'disposal_dirty': 'ห่อให้มิดชิดแล้วนำไปทิ้งในถังขยะทั่วไป',
        'not_recyclable_note': 'ขยะทั่วไปไม่สามารถรีไซเคิลได้ '
                                'ควรลดการใช้และเลือกวัสดุที่นำกลับมาใช้ได้',
    },
}


class RecommendationEngine:
    """Generate disposal recommendations from category + quality."""

    def __init__(self):
        self.knowledge_base = KNOWLEDGE_BASE

    def recommend(self, category, quality):
        """
        Build a full recommendation for a single waste item.

        Args:
            category: waste category key (e.g. 'plastic')
            quality: 'clean' or 'contaminated'

        Returns:
            dict with: recyclable, suggested_bin, preparation (list),
            recommendation (str)
        """
        meta = WASTE_CATEGORIES.get(category, WASTE_CATEGORIES['trash'])
        rules = self.knowledge_base.get(category, self.knowledge_base['trash'])

        is_clean = (quality == 'clean')

        # Determine recyclability
        # Contaminated recyclable items may still be recyclable if they
        # can be cleaned; otherwise they go to general waste.
        if meta['recyclable']:
            recyclable = True
            if not is_clean:
                # Can potentially be cleaned and recycled
                recyclable = True  # still recyclable if cleaned
        else:
            recyclable = False

        # Preparation steps
        if is_clean:
            prep_steps = rules['preparation_clean']
        else:
            prep_steps = rules['preparation_dirty']

        # Build the full recommendation text
        lines = []

        # Header
        lines.append(f"ประเภท: {meta['name_th']}")
        lines.append(f"สภาพ: {'สะอาด' if is_clean else 'มีสิ่งปนเปื้อน'}")
        lines.append(f"ถังที่แนะนำ: {meta['bin']}")
        lines.append("")

        # Preparation steps
        lines.append("วิธีเตรียมก่อนกำจัด:")
        for step in prep_steps:
            lines.append(f"  • {step}")
        lines.append("")

        # Disposal instruction
        if is_clean:
            lines.append(f"การจัดการ: {rules['disposal_clean']}")
        else:
            lines.append(f"การจัดการ: {rules['disposal_dirty']}")
            lines.append(f"  คำแนะนำเพิ่มเติม: {rules['not_recyclable_note']}")

        recommendation_text = '\n'.join(lines)

        return {
            'recyclable': recyclable,
            'suggested_bin': meta['bin'],
            'preparation': prep_steps,
            'recommendation': recommendation_text,
        }

    def recommend_batch(self, items):
        """
        Apply recommendations to a list of detected items.

        Each item dict must have 'category' and 'quality' keys.
        The recommendation result is merged into each item dict.
        """
        for item in items:
            rec = self.recommend(item['category'], item['quality'])
            item['recyclable'] = rec['recyclable']
            item['suggested_bin'] = rec['suggested_bin']
            item['recommendation'] = rec['recommendation']
            item['preparation'] = rec['preparation']
        return items
