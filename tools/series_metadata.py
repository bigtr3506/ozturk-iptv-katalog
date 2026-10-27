"""Pure episode/trailer selection; shared by local and cloud updater."""
import json
import re
import unicodedata
from pathlib import Path
from tools.youtube_metadata import make_series, now
from tools.series_artwork import apply_artwork

FOLLOWED=json.loads((Path(__file__).resolve().parents[1]/"schedules/followed-series.json").read_text(encoding="utf-8"))
_fallback_file=Path(__file__).resolve().parents[1]/'schedules/official-episode-fallbacks.json'
OFFICIAL_FALLBACKS=json.loads(_fallback_file.read_text(encoding='utf-8')) if _fallback_file.exists() else {}
_ratings_file=Path(__file__).resolve().parents[1]/'schedules/content-ratings.json'
RATINGS=json.loads(_ratings_file.read_text(encoding='utf-8')) if _ratings_file.exists() else {'items':{}}


def apply_rating(row):
    record=RATINGS['items'].get(row['id'])
    if not record:return row
    score=record['score'];url=record.get('source') or 'https://www.imdb.com/title/'+record['imdb']+'/'
    row.update(puan=score,populerlik=record.get('votes'),puan_kaynagi=record.get('provider','IMDb') if score is not None else None,
               puan_kontrol_tarihi=record.get('checkedAt',RATINGS['checkedAt']),puan_kaynak_url=url,
               puan_oy_sayisi=record.get('votes'),puan_oy_yaklasik=bool(record.get('approximate')),
               populerlik_kaynagi='IMDb oy sayısı' if record.get('votes') else None)
    return row


def select(metadata, title, channel, minimum=1800, aliases=None, trusted_channels=None, full_suffixes=None, title_prefixes=None):
    if metadata.get('channel_id')!=channel:raise ValueError('Unexpected source channel')
    full, trailers={},[]
    for e in metadata.get('entries',[]):
        e=e or {};name=unicodedata.normalize('NFC',e.get('title') or '');name=''.join(c for c in name if unicodedata.category(c)!='Cf');duration=e.get('duration')
        if not re.fullmatch(r'[\w-]{11}',e.get('id') or '') or e.get('availability') in {'private','needs_auth','premium_only','subscriber_only'}:continue
        if e.get('channel_id') not in [None,channel]+list(trusted_channels or []) or not isinstance(duration,(int,float)):continue
        for prefix in title_prefixes or []:
            if name.casefold().startswith(prefix.casefold()):name=name[len(prefix):].lstrip();break
        names='(?:'+'|'.join(re.escape(unicodedata.normalize('NFC',t)) for t in [title]+list(aliases or []))+')'
        name=re.sub(r'^('+names+r')\s*[|:–-]?\s*Episode\s+(\d+)',lambda m:m[1]+' '+m[2]+'. Bölüm',name,flags=re.I)
        match=re.match(r'^'+names+r'\s*[|:–-]?\s*(\d+)\s*\.?\s*(?:Bölüm|Episode)\b\s*(.*)$',name,re.I)
        if not match:continue
        number=int(match[1]);suffix=match[2].strip()
        if number<1 or number>1000:continue
        cleaned=re.sub(r'@[\w.]+','',suffix)
        # Publisher titles sometimes decorate genuine full episodes with emoji.
        # Remove only decorative symbols; scene/summary words remain rejected.
        cleaned=''.join(c for c in cleaned if unicodedata.category(c)!='So' and c not in '\ufe0e\ufe0f')
        cleaned=re.sub(r'\s+',' ',re.sub(r'[!|()–-]',' ',cleaned)).strip()
        if duration>=minimum and (cleaned in (full_suffixes or []) or re.fullmatch(r'(?:(?:Final|Sezon Finali|Yeni Sezon|\d+\.\s*Sezon|Full HD|Full Bölüm|HD|4K(?: Ultra HD)?|60\s*FPS|1080p)\s*)*',cleaned,re.I)):
            if number not in full:full[number]={**e,'title':name,'youtube_basligi':e.get('title')}
        elif 0<duration<minimum and re.match(r'^(?:\d+\.\s*)?(?:Tanıtım|Fragman|Trailer|TNT\s*\d)',suffix,re.I):
            part=re.search(r'^(?:(\d+)\.\s*(?:Fragman|Tanıtım)|(?:Fragman|Tanıtım|Trailer|TNT)\w*\s*(\d+))',suffix,re.I)
            trailers.append(dict(no=number,baslik=f'{title} {number}. Bölüm Fragmanı',youtube_basligi=e.get('title'),sure=int(duration),youtube_id=e['id'],fragman_sirasi=int((part[1] or part[2]) if part else 1),yayin_zamani=e.get('timestamp') or 0,
                                 kaynaklar=[dict(tip='youtube',url='https://www.youtube.com/watch?v='+e['id'],oncelik=0)]))
    return full,trailers


def build_tuzlu(metadata, previous=None):
    return build_followed('tuzlu-kahve',metadata,previous)


def build_followed(identity,metadata,previous=None):
    config=FOLLOWED[identity];title=config['title'];channel=config['channel']
    if previous and not previous.get('yonetim'):previous=None
    entries,trailers=select(metadata,title,channel,config.get('minimum_seconds',3600),config.get('aliases'),config.get('trusted_channels'),config.get('full_suffixes'),config.get('title_prefixes'))
    # Completed Turkish archives may also contain a longer, renumbered export
    # edition. Keep only the publisher's verified original broadcast range.
    if config.get('last_episode'):
        entries={n:e for n,e in entries.items() if n<=config['last_episode']}
    old={e['no']:e for s in (previous or {}).get('sezonlar',[]) for e in s.get('bolumler',[])}
    if not entries and not old:raise ValueError('No verified full episodes; catalog kept intact')
    if entries:
        meta={**metadata,'id':channel,'entries':[e for _,e in sorted(entries.items())]}
        row,_=make_series(meta,identity,title,config.get('publisher','star'))
        old.update({e['no']:e for s in row['sezonlar'] for e in s['bolumler']})
    else:row=dict(previous)
    seasons={}
    for n,e in sorted(old.items()):
        fallback=OFFICIAL_FALLBACKS.get(identity,{}).get(str(n))
        if fallback:
            e['kaynaklar']=[s for s in e['kaynaklar'] if s.get('tip')!='embed']+[dict(tip='embed',url=fallback,oncelik=1)]
        season=1+sum(n>end for end in config['season_ends']);seasons.setdefault(season,[]).append(e)
    row['sezonlar']=[dict(no=n,baslik=config['season_titles'][n-1] if n<=len(config['season_titles']) else f'{n}. Sezon',bolumler=eps) for n,eps in sorted(seasons.items())]
    latest=max(old)
    # An empty/failed scan never deletes existing episodes. Trailer replacement
    # follows the newest published episode, including when its trailer is absent.
    upcoming={e['youtube_id']:e for e in (previous or {}).get('fragmanlar',[]) if e['no']==latest+1}
    upcoming.update({e['youtube_id']:e for e in trailers if e['no']==latest+1})
    row['fragmanlar']=list(upcoming.values())
    if config.get('current_trailer_only'):
        row['fragmanlar']=sorted(row['fragmanlar'],key=lambda e:(e.get('fragman_sirasi',1),e.get('yayin_zamani',0)),reverse=True)[:1]
    row.update(resmi_url=config['official'],kaynak_kanal_url=config['url'],
               aciklama=title+' — resmî kanalın tam bölümleri ve sıradaki bölümün tanıtımları.',
               yil_baslangic=config.get('start_year',2026),devam_ediyor=not bool(re.search(r'\bFinal\b',old[latest]['baslik'],re.I) and not re.search(r'Sezon Final',old[latest]['baslik'],re.I)),son_tam_bolum=latest,guncellendi=now(),
               kontrol_araligi_saniye=900,turler=config.get('genres',['Dram','Romantik']))
    if config.get('archive_complete'):
        row['devam_ediyor']=False
        row['fragmanlar']=[]
    if config.get('auto_discovered') or (previous or {}).get('auto_discovered'):
        row['auto_discovered']=True
    return apply_artwork(apply_rating(row))

