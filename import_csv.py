"""
Load data/recycling_points.csv into the database.

    python import_csv.py

Replaces everything in the recycling_points table with the CSV contents.
lat / lng are optional: rows without them still appear in the list with a
"open in Google Maps" link; they just get no pin until you fill them in
(Google Maps: right-click the pin -> click the numbers at the top).
"""
import csv
import os

from app import app
from models.database import db, RecyclingPoint
from models.recycling_points import POINT_TYPES

CSV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        'data', 'recycling_points.csv')


def num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def main():
    with open(CSV_PATH, encoding='utf-8-sig', newline='') as f:
        rows = list(csv.DictReader(f))

    with app.app_context():
        # Recreate the table so older schemas (e.g. NOT NULL lat/lng) are replaced
        RecyclingPoint.__table__.drop(db.engine, checkfirst=True)
        RecyclingPoint.__table__.create(db.engine)

        added = with_xy = 0
        for r in rows:
            if r['point_type'] not in POINT_TYPES:
                print(f"! ข้าม '{r['name']}': point_type ต้องเป็น "
                      f"{', '.join(POINT_TYPES)}")
                continue
            lat, lng = num(r.get('lat')), num(r.get('lng'))
            if lat is None or lng is None:
                lat = lng = None
            else:
                with_xy += 1
            db.session.add(RecyclingPoint(
                name=r['name'].strip(), point_type=r['point_type'],
                lat=lat, lng=lng, address=r.get('address', ''),
                opening_hours=r.get('opening_hours', ''),
                phone=r.get('phone', ''), rating=num(r.get('rating'))))
            added += 1
        db.session.commit()
        print(f'นำเข้า {added} จุด (มีพิกัด {with_xy}, ยังไม่มีพิกัด {added - with_xy})')


if __name__ == '__main__':
    main()
