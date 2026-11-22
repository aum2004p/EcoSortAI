"""
EcoSort AI - Recycling Location helpers
=======================================
Point types, category mapping and distance sorting.
Real data lives in data/recycling_points.csv and is loaded with
`python import_csv.py`.
"""

import math

POINT_TYPES = {
    'junk_shop': {'name_th': 'ร้านรับซื้อของเก่า', 'icon': '🏪', 'color': '#f39c12'},
    'ewaste':    {'name_th': 'ร้านรับซื้ออิเล็กทรอนิกส์', 'icon': '🔌', 'color': '#9b59b6'},
}

# Which point types to show for each waste category from the scanner
CATEGORY_TO_TYPES = {
    'plastic':   ['junk_shop'],
    'paper':     ['junk_shop'],
    'cardboard': ['junk_shop'],
    'glass':     ['junk_shop'],
    'metal':     ['junk_shop'],
    # COCO fallback maps phones/laptops to "trash"
    'trash':     ['ewaste'],
}


def types_for_category(category):
    return CATEGORY_TO_TYPES.get(category, list(POINT_TYPES))


def haversine_km(lat1, lng1, lat2, lng2):
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def nearest_points(points, lat=None, lng=None, category=None, limit=100):
    """Dicts for the API. Sorted by distance if lat/lng given, else by rating."""
    out = []
    for p in points:
        d = p.to_dict()
        meta = POINT_TYPES.get(p.point_type, {})
        d['type_th'] = meta.get('name_th', p.point_type)
        d['icon'] = meta.get('icon', '📍')
        has_xy = p.lat is not None and p.lng is not None
        d['distance_km'] = (round(haversine_km(lat, lng, p.lat, p.lng), 2)
                            if has_xy and lat is not None and lng is not None
                            else None)
        out.append(d)
    if lat is not None and lng is not None:
        out.sort(key=lambda x: (x['distance_km'] is None, x['distance_km'] or 0))
    else:
        out.sort(key=lambda x: (-(x['rating'] or 0), x['name']))
    return out[:limit]


def seed_recycling_points(db, RecyclingPoint):
    """Kept as a no-op so app.py needs no change. Data comes from import_csv.py."""
    return