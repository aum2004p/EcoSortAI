"""
EcoSort AI - Carbon Footprint Module
======================================
Calculates CO2 savings from recycling waste items.

Uses estimated CO2 savings factors per waste type (config.CARBON_FOOTPRINT).
Only recyclable and clean items contribute to CO2 savings.
Contaminated recyclable items still save CO2 if they can be cleaned.

Also provides tree-equivalent and other environmental impact metrics
to make the results more relatable for communities and schools.
"""

from config import CARBON_FOOTPRINT, WASTE_CATEGORIES

# Environmental reference values
# A mature tree absorbs ~21 kg CO2 per year (EPA estimate)
CO2_PER_TREE_PER_YEAR = 21.0  # kg

# Average car emits ~0.4 kg CO2 per km driven
CO2_PER_KM_DRIVEN = 0.4  # kg

# Average smartphone charge ~0.005 kg CO2
CO2_PER_PHONE_CHARGE = 0.005  # kg


class CarbonFootprintCalculator:
    """Calculate CO2 savings and environmental impact from recycling."""

    def calculate_savings(self, detections):
        """
        Calculate CO2 savings for a list of detected items.

        Args:
            detections: list of dicts with 'category', 'recyclable', 'quality'.

        Returns:
            dict with:
                total_co2: total kg CO2 saved
                per_category: breakdown by waste type
                trees_equivalent: equivalent trees absorbing for a year
                km_driven_equivalent: equivalent km of car emissions avoided
                phone_charges_equivalent: equivalent phone charges
        """
        total_co2 = 0.0
        per_category = {}

        for det in detections:
            category = det.get('category', 'trash')
            recyclable = det.get('recyclable', False)

            if not recyclable:
                continue

            factor = CARBON_FOOTPRINT.get(category, 0.0)
            # Contaminated items save less CO2 (assume 50% efficiency
            # because they may not actually get recycled if too dirty)
            if det.get('quality') == 'contaminated':
                factor *= 0.5

            total_co2 += factor

            if category not in per_category:
                per_category[category] = {
                    'name_th': WASTE_CATEGORIES.get(category, {}).get('name_th', category),
                    'co2': 0.0,
                    'count': 0,
                }
            per_category[category]['co2'] += factor
            per_category[category]['count'] += 1

        # Round values
        total_co2 = round(total_co2, 4)
        for cat in per_category:
            per_category[cat]['co2'] = round(per_category[cat]['co2'], 4)

        return {
            'total_co2': total_co2,
            'per_category': per_category,
            'trees_equivalent': round(total_co2 / CO2_PER_TREE_PER_YEAR, 4),
            'km_driven_equivalent': round(total_co2 / CO2_PER_KM_DRIVEN, 2),
            'phone_charges_equivalent': int(total_co2 / CO2_PER_PHONE_CHARGE) if total_co2 > 0 else 0,
        }

    def format_impact_text(self, savings):
        """Generate a human-readable impact summary in Thai."""
        total = savings['total_co2']
        if total <= 0:
            return "ไม่มีการลด CO2 ในครั้งนี้ (ไม่มีขยะที่รีไซเคิลได้)"

        lines = [
            f"ลด CO2 ได้ {total:.4f} กิโลกรัม",
            f"เทียบเท่าการปลูกต้นไม้ {savings['trees_equivalent']:.4f} ต้น (ดูดซับ CO2 1 ปี)",
            f"เทียบเท่าการขับรถลดลง {savings['km_driven_equivalent']:.1f} กิโลเมตร",
        ]

        if savings['phone_charges_equivalent'] > 0:
            lines.append(
                f"เทียบเท่าการชาร์จมือถือ {savings['phone_charges_equivalent']:,} ครั้ง"
            )

        return '\n'.join(lines)

    def get_category_factor(self, category):
        """Get the CO2 savings factor for a single waste type."""
        return CARBON_FOOTPRINT.get(category, 0.0)
