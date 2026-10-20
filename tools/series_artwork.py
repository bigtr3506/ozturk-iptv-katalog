"""Reviewed promotional artwork survives all episode and catalog refreshes."""
import json
from pathlib import Path
FILE=Path(__file__).resolve().parents[1]/'schedules/series-artwork.json'
def apply_artwork(row,local=False):
    if not FILE.exists():return row
    registry=json.loads(FILE.read_text(encoding='utf-8'));art=registry.get('items',{}).get(row.get('id'))
    if not art:return row
    prefix='' if local else registry['publicBase']
    row.update(afis=prefix+art['poster'],arka_plan=prefix+art['backdrop'],afis_kaynak_url=art['source'],afis_saglayici=art['provider'])
    return row
