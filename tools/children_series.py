"""Reviewed public children's playlists. Never substitutes compilations for episodes."""
import datetime as dt
import re
import unicodedata
from tools.series_artwork import apply_artwork

def normalized(value):
    return unicodedata.normalize('NFKD',str(value).lower().replace('ı','i')).encode('ascii','ignore').decode()

def build(config,metadata,previous=None):
    if metadata.get('channel_id')!=config['channel']:raise ValueError('Unexpected children publisher')
    if config.get('feed')!='children' or config.get('content_type') not in ('animasyon','cocuk_dizisi'):raise ValueError('Reviewed children registration required')
    owner=config['channel'];minimum=config['minimum_seconds'];maximum=config['maximum_seconds']
    old={e['no']:dict(e) for s in (previous or {}).get('sezonlar',[]) for e in s['bolumler']}
    old_ids={e['youtube_id']:n for n,e in old.items()};next_number=max(old,default=0)+1
    entries=[];seen=set()
    for e in metadata.get('entries',[]):
        if not e:continue
        title=unicodedata.normalize('NFC',e.get('title') or '');duration=e.get('duration');vid=e.get('id','');name=normalized(title)
        if not re.fullmatch(r'[\w-]{11}',vid) or vid in seen or e.get('channel_id') not in (None,owner) or e.get('availability') in ('private','needs_auth','premium_only','subscriber_only'):continue
        if not isinstance(duration,(int,float)) or not minimum<=duration<=maximum:continue
        if not config.get('allow_unprefixed_titles') and not any(normalized(alias) in name for alias in [config['title']]+config.get('aliases',[])):continue
        if re.search(r'\b(?:fragman\w*|tanitim\w*|teaser|sarki\w*|jenerik|sahne\w*|derleme|birden|maraton|ozet\w*|kesit\w*|canli)\b|bir arada',name):continue
        matches=list(re.finditer(r'(\d+)\s*\.?\s*bolum\b',name))
        if len(matches)>1:continue
        season=int(e.get('_official_season',1))
        if config['numbering']=='numbered':
            if len(matches)!=1:continue
            local=int(matches[0][1]);ends=config.get('season_ends',[])
            if config.get('season_numbers_local'):
                if season<1 or season>len(ends)+1:continue
                number=(ends[season-2] if season>1 else 0)+local
                if season<=len(ends) and number>ends[season-1]:continue
            else:
                number=local;season=1+sum(number>end for end in ends)
                local=number-(ends[season-2] if season>1 else 0)
            if local<1 or number>1000:continue
        else:
            number=old_ids.get(vid)
            if number is None:number=next_number;next_number+=1
            local=number
        seen.add(vid);url='https://www.youtube.com/watch?v='+vid
        entry=dict(no=number,sezon_icino=local,baslik=title,sure=int(duration),youtube_id=vid,kaynaklar=[dict(tip='youtube',url=url,oncelik=0)],url=url,kaynak_tipi='youtube',durum='aktif',gorsel='https://i.ytimg.com/vi/'+vid+'/hqdefault.jpg',_season=season)
        entries.append(entry)
    if not entries and not old:raise ValueError('No verified full child episodes; previous catalog retained')
    for e in entries:old[e['no']]=e
    seasons={}
    for number,e in sorted(old.items()):
        season=1+sum(number>end for end in config.get('season_ends',[]));e.pop('_season',None);seasons.setdefault(season,[]).append(e)
    if config.get('seasons_verified'):
        for season in range(1,len(config.get('season_ends',[]))+2):seasons.setdefault(season,[])
    latest=max(old);missing=[n for n in range(1,latest+1) if n not in old] if config['numbering']=='numbered' else []
    stamp=dt.datetime.now(dt.timezone.utc).isoformat();row=dict(previous or {})
    row.update(id=config['id'],baslik=config['title'],kanal='trt',yayinci='TRT Çocuk',icerik_turu=config['content_type'],turler=config['genres'],yil_baslangic=config.get('start_year'),resmi_url=config['official'],kaynak_kanal_id=owner,kaynak_kanal_url=config['url'],kaynak_kanal='TRT Çocuk',yonetim=True,oynatilabilir=True,durum='aktif',populerlik=row.get('populerlik',0),puan=row.get('puan',0),oyuncular=[],fragmanlar=[],devam_ediyor=config.get('ongoing'),son_tam_bolum=latest,guncellenme=stamp,guncellendi=stamp,eklenme=row.get('eklenme',stamp),eksik_bolumler=missing,arsiv_kontrolu='resmi_liste' if config['numbering']=='playlist' else 'eksik' if missing else 'numaralar_tam',bolum_no_kaynagi='Yayıncının bölüm numaraları' if config['numbering']=='numbered' else 'Resmî oynatma listesi sırası',aciklama=config['title']+' — TRT Çocuk ve doğrulanmış resmî yapımcı listelerindeki tam bölümler. '+('Yayıncı sezon ayırmadığı için resmî bölüm listesi gösterilir.' if not config.get('seasons_verified') else 'Yayıncının sezon ve bölüm ayrımı korunur.'))
    row['sezonlar']=[dict(no=n,baslik=(config.get('season_titles') or ['Bölümler'])[n-1] if n<=len(config.get('season_titles') or ['Bölümler']) else str(n)+'. Sezon',bolumler=eps) for n,eps in sorted(seasons.items())]
    return apply_artwork(row)
