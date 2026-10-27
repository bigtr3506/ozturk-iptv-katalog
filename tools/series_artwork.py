"""Reviewed promotional artwork survives all episode and catalog refreshes."""
import json
from pathlib import Path
FILE=Path(__file__).resolve().parents[1]/'schedules/series-artwork.json'
def apply_artwork(row,local=False):
    if row.get('afis_yonetim'):return row
    if not FILE.exists():return row
    registry=json.loads(FILE.read_text(encoding='utf-8'));art=registry.get('items',{}).get(row.get('id'))
    if not art:return row
    prefix='' if local else registry['publicBase']
    poster=art['poster'] if art['poster'].startswith('https://') else prefix+art['poster']
    backdrop=art['backdrop'] if art['backdrop'].startswith('https://') else prefix+art['backdrop']
    row.update(afis=poster,arka_plan=backdrop,afis_kaynak_url=art['source'],afis_saglayici=art['provider'])
    return row
