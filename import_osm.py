"""
Import real recycling points from OpenStreetMap (Overpass API) into the DB.
Run once on a machine with internet:   python import_osm.py
Removes the sample rows first, then inserts OSM nodes (amenity=recycling)
inside the Pathum Thani bounding box.  Data coverage in Thailand is partial.
"""
import json
import urllib.parse
import urllib.request

from app import app
from models.database import db, RecyclingPoint

BBOX = "13.85,100.40,14.25,100.95"   # south,west,north,east (Pathum Thani)
QUERY = f'[out:json][timeout:60];(node["amenity"="recycling"]({BBOX});' \
        f'way["amenity"="recycling"]({BBOX}););out center tags;'


def guess(tags):
    mats = [k.split(':', 1)[1] for k, v in tags.items()
            if k.startswith('recycling:') and v == 'yes']
    if any(m in ('electrical_items', 'small_electrical_appliances', 'batteries') for m in mats):
        return 'ewaste', ','.join(mats)
    if tags.get('recycling_type') == 'centre' or tags.get('shop') == 'scrap_yard':
        return 'junk_shop', ','.join(mats) or 'plastic,paper,glass,metal'
    if 'plastic_bottles' in mats or 'plastic' in mats:
        return 'bottle', 'plastic'
    return 'waste_bank', ','.join(mats)


def main():
    req = urllib.request.Request(
        'https://overpass-api.de/api/interpreter',
        data=urllib.parse.urlencode({'data': QUERY}).encode(),
        headers={'User-Agent': 'EcoSortAI-student-project'})
    with urllib.request.urlopen(req, timeout=90) as r:
        elements = json.load(r)['elements']

    with app.app_context():
        RecyclingPoint.query.filter_by(source='sample').delete()
        n = 0
        for e in elements:
            lat = e.get('lat') or e.get('center', {}).get('lat')
            lng = e.get('lon') or e.get('center', {}).get('lon')
            if lat is None or lng is None:
                continue
            tags = e.get('tags', {})
            ptype, accepts = guess(tags)
            db.session.add(RecyclingPoint(
                name=tags.get('name:th') or tags.get('name') or 'จุดรีไซเคิล',
                point_type=ptype, accepts=accepts, lat=lat, lng=lng,
                address=tags.get('addr:full', ''),
                opening_hours=tags.get('opening_hours', ''),
                phone=tags.get('phone', ''), source='osm'))
            n += 1
        db.session.commit()
        print(f'Imported {n} points from OpenStreetMap')


if __name__ == '__main__':
    main()
