"""Discover public full content from reviewed publishers; never obtain media URLs.

Unknown owners, incomplete first catalogs and uncertain seasons are quarantined.
Uses only public metadata without cookies, account logins or playback bypasses.
"""
import concurrent.futures as cf
import datetime as dt
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import subprocess
import sys
import unicodedata
import urllib.parse
import urllib.request

ROOT=Path(__file__).resolve().parents[1]
UA='OzturkIPTV/3.0 public-catalog-discovery'

def key(text):
    return re.sub(r'[^a-z0-9]+','-',unicodedata.normalize('NFKD',str(text).lower().replace('ı','i')).encode('ascii','ignore').decode()).strip('-')

def read(path,default):
    try:return json.loads(path.read_text(encoding='utf-8'))
    except (OSError,ValueError):return default

def write(path,data):
    path.parent.mkdir(parents=True,exist_ok=True);temp=path.with_suffix('.tmp')
    temp.write_text(json.dumps(data,ensure_ascii=False,separators=(',',':'))+'\n',encoding='utf-8');temp.replace(path)

def fetch(url):
    parsed=urllib.parse.urlsplit(url)
    if parsed.scheme!='https' or parsed.username or parsed.password:raise ValueError('Public HTTPS required')
    request=urllib.request.Request(url,headers={'User-Agent':UA})
    with urllib.request.urlopen(request,timeout=12) as response:
        body=response.read(4_000_001)
        if len(body)>4_000_000:raise ValueError('Metadata too large')
        return body.decode('utf-8',errors='replace')

def listing(url,limit=600):
    result=subprocess.run([sys.executable,'-m','yt_dlp','--flat-playlist','--skip-download','--no-warnings','--socket-timeout','15','--playlist-end',str(limit),'--dump-single-json',url],capture_output=True,text=True,encoding='utf-8',timeout=90)
    if result.returncode:raise ValueError('Publisher metadata unavailable')
    return json.loads(result.stdout)

class Page(HTMLParser):
    def __init__(self,text):
        super().__init__();self.links=[];self.meta={};self.heading=[];self.in_heading=False;self.feed(text)
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=='a' and a.get('href'):self.links.append(a['href'])
        if tag=='meta':self.meta[a.get('property',a.get('name',''))]=a.get('content','')
        if tag=='h1':self.in_heading=True
    def handle_endtag(self,tag):
        if tag=='h1':self.in_heading=False
    def handle_data(self,data):
        if self.in_heading:self.heading.append(data.strip())

def page_title(page):
    value=' '.join(page.heading).strip() or page.meta.get('og:title','')
    return re.split(r'\s*\|\s*|\s+(?:Dizisi|İzle|Izle)\b',value,flags=re.I)[0].strip()

def season_metadata(title,show,episodes):
    network=show.get('network') or show.get('webChannel') or {};country=(network.get('country') or {}).get('code')
    if key(show.get('name'))!=key(title) or country!='TR' or show.get('type')!='Scripted':raise ValueError('Series identity/country not verified')
    poster=(show.get('image') or {}).get('original')
    if not poster or urllib.parse.urlsplit(poster).hostname!='static.tvmaze.com':raise ValueError('Verified series poster unavailable')
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}',show.get('premiered') or ''):raise ValueError('Series premiere year not verified')
    seasons={}
    for ep in episodes:
        season,number=ep.get('season'),ep.get('number')
        if isinstance(season,int) and season>0 and isinstance(number,int) and number>0:seasons.setdefault(season,set()).add(number)
    if not seasons or sorted(seasons)!=list(range(1,max(seasons)+1)):raise ValueError('Season boundaries incomplete')
    ends=[];total=0
    for season,numbers in sorted(seasons.items()):
        if sorted(numbers)!=list(range(1,max(numbers)+1)):raise ValueError('Episode numbering incomplete')
        total+=len(numbers);ends.append(total)
    return ends[:-1],total,poster

def initial_series(title,official,publisher,metadata,show,episodes):
    from tools import series_metadata as series
    channel=metadata.get('channel_id')
    if not re.fullmatch(r'UC[\w-]{22}',channel or ''):raise ValueError('Source channel identity missing')
    ends,total,poster=season_metadata(title,show,episodes)
    network=key((show.get('network') or show.get('webChannel') or {}).get('name',''))
    expected={'show':['show-tv'],'trt':['trt-1','trt1'],'star':['star-tv'],'now':['now','fox','fox-turkiye','fox-turkey'],'kanald':['kanal-d'],'atv':['atv']}
    if network not in expected.get(publisher,[]):raise ValueError('Publisher/series network mismatch')
    if int(show['premiered'][:4])<dt.datetime.now(dt.timezone.utc).year-1:raise ValueError('Archive series requires a reviewed registration')
    full,_=series.select(metadata,title,channel,3600)
    if not full or sorted(full)!=list(range(1,max(full)+1)) or max(full)>total:raise ValueError('First full-episode catalog incomplete')
    identity=key(title)
    config=dict(title=title,channel=channel,url='https://www.youtube.com/channel/'+channel+'/videos',official=official,publisher=publisher,minimum_seconds=3600,season_ends=ends,season_titles=[],start_year=int((show.get('premiered') or '0000')[:4]),current_trailer_only=True,season_source=show['url']+'/episodes',discovery_source=official)
    series.FOLLOWED[identity]=config
    row=series.build_followed(identity,metadata)
    row.update(afis=poster,arka_plan=poster,afis_saglayici='TVmaze',afis_kaynak_url=show['url'],auto_discovered=True,kaynak_dogrulamasi='Official publisher link, owner, full duration, contiguous episodes and season metadata; device playback not asserted.')
    art=dict(poster=poster,backdrop=poster,source=show['url'],provider='TVmaze',publisher=publisher,year=config['start_year'])
    return identity,config,row,art

def inspect_series(provider,url):
    page=Page(fetch(url));title=page_title(page)
    if not title:raise ValueError('Series title missing')
    youtube=[]
    for href in page.links:
        u=urllib.parse.urlsplit(urllib.parse.urljoin(url,href))
        if u.hostname in ('youtube.com','www.youtube.com') and re.fullmatch(r'/(?:@[^/?#]+|channel/UC[\w-]{22})/?',u.path):youtube.append('https://www.youtube.com'+u.path.rstrip('/')+'/videos')
    if not youtube:raise ValueError('Official page has no verifiable YouTube channel link')
    show=json.loads(fetch('https://api.tvmaze.com/singlesearch/shows?q='+urllib.parse.quote(title)))
    episodes=json.loads(fetch('https://api.tvmaze.com/shows/'+str(show['id'])+'/episodes'))
    errors=[]
    for source in list(dict.fromkeys(youtube))[:2]:
        try:return initial_series(title,url,provider['publisher'],listing(source),show,episodes)
        except (ValueError,RuntimeError,subprocess.TimeoutExpired) as e:errors.append(str(e))
    raise ValueError('; '.join(errors))

def movie_row(entry,publisher):
    title=entry.get('title') or '';duration=entry.get('duration') or 0;vid=entry.get('id') or ''
    if not re.fullmatch(r'[\w-]{11}',vid) or not isinstance(duration,(int,float)) or not publisher['minimum_seconds']<=duration<=14400:return None
    if entry.get('live_status') in ('is_live','is_upcoming','post_live'):return None
    if entry.get('channel_id') not in (None,publisher['channel']) or entry.get('availability') in ('private','needs_auth','premium_only','subscriber_only'):return None
    if re.search(r'\b(?:bölüm|episode|fragman|trailer|sahne|sahneleri|özet|derleme|kolaj|canlı|belgesel|kamera arkası)\b',title,re.I):return None
    title=re.split(r'\s*\|\s*|\s+[–-]\s+',title)[0]
    title=re.sub(r'\s*\((?:19|20)\d{2}\)\s*',' ',title)
    title=re.sub(r'\s+(?:(?:Full(?:\s+(?:Film|HD))?|FullHD|HD(?:\s+Türk\s+Filmi)?|4K|Türk\s+Filmi|Yerli\s+Film|Tek\s+Parça)(?:\s+İzle)?\s*)+$','',title,flags=re.I).strip()
    if len(title)<2:return None
    return dict(id='auto-film-'+vid,baslik=title,kanal='diger',kategori='Film',turler=['Türk Filmi'],oyuncular=[],afis='https://i.ytimg.com/vi/'+vid+'/hqdefault.jpg',arka_plan='https://i.ytimg.com/vi/'+vid+'/hqdefault.jpg',durum='bilinmiyor',oynatilabilir=True,yonetim=True,sure=int(duration),yayinci=publisher['name'],kaynak_kanal_id=publisher['channel'],resmi_url='https://www.youtube.com/watch?v='+vid,kaynaklar=[dict(tip='youtube',url='https://www.youtube.com/watch?v='+vid,oncelik=0)],aciklama=publisher['name']+' resmî kanalındaki tam film. Cihaz oynatımı ve bölge erişimi ayrıca değişebilir.')

def refresh(root=ROOT):
    from tools import series_metadata as series
    config=read(root/'schedules/auto-discovery.json',{});stamp=dt.datetime.now(dt.timezone.utc).isoformat();report=dict(schema=1,checkedAt=stamp,addedSeries=[],addedMovies=[],pending=[],providers=[])
    followed=read(root/'schedules/followed-series.json',{});series.FOLLOWED.update(followed)
    feed=read(root/'public-updates/series-updates.json',dict(schema=1,series=[]));existing={r['id']:r for r in feed['series']}
    known={key(r['title']) for r in config.get('known_series',[])}|set(followed)
    candidates=[]
    for provider in config.get('series_providers',[]):
        try:
            page=Page(fetch(provider['url']));base=urllib.parse.urlsplit(provider['url'])
            urls=sorted({urllib.parse.urljoin(provider['url'],href).split('?')[0] for href in page.links if urllib.parse.urlsplit(urllib.parse.urljoin(provider['url'],href)).hostname==base.hostname and re.fullmatch(provider['pattern'],urllib.parse.urlsplit(urllib.parse.urljoin(provider['url'],href)).path)})
            for url in urls:
                slug=url.rstrip('/').split('/')[-2 if provider['publisher']=='show' else -1]
                if key(slug) not in known and not re.search(r'(?:haber|canli|diziler|program|iletisim|kunye|gizlilik|filmler|basvuru|yayin|frekans|kvkk|reklam)',slug):candidates.append((provider,url))
            report['providers'].append(dict(source=provider['url'],ok=True,candidates=len(urls)))
        except Exception:report['providers'].append(dict(source=provider['url'],ok=False,reason='Official listing unavailable; previous catalog retained'))
    artwork=read(root/'schedules/series-artwork.json',{'items':{}})
    previous=read(root/'public-updates/discovery-report.json',{})
    cursor=int(previous.get('nextCandidateIndex',0))%max(1,len(candidates))
    rotated=candidates[cursor:]+candidates[:cursor]
    selected=rotated[:config.get('maximum_new_series_per_scan',8)]
    report['nextCandidateIndex']=(cursor+len(selected))%max(1,len(candidates))
    with cf.ThreadPoolExecutor(max_workers=3) as pool:
        tasks={pool.submit(inspect_series,p,url):url for p,url in selected}
        for future in cf.as_completed(tasks):
            url=tasks[future]
            try:
                identity,registry,row,art=future.result()
                if identity in followed:continue
                row['guncellenme']=stamp;followed[identity]=registry;existing[identity]=row;artwork['items'][identity]=art;report['addedSeries'].append(dict(id=identity,title=row['baslik'],episodes=row['son_tam_bolum']))
            except Exception as e:report['pending'].append(dict(source=url,reason=str(e)[:180]))
    movies=read(root/'public-updates/movies.json',[]);movie_ids={s['url'] for row in movies for s in row.get('kaynaklar',[])};movie_titles={key(r['baslik']) for r in movies}
    additions=[]
    def scan_movies(publisher):
        metadata=listing(publisher['url'],120)
        if metadata.get('channel_id')!=publisher['channel']:raise ValueError('Publisher owner mismatch')
        rows=[]
        for entry in metadata.get('entries',[]):
            row=movie_row(entry or {},publisher)
            if not row or row['resmi_url'] in movie_ids or key(row['baslik']) in movie_titles:continue
            try:
                embed=json.loads(fetch('https://www.youtube.com/oembed?format=json&url='+urllib.parse.quote(row['resmi_url'],safe='')))
                if key(embed.get('author_name'))!=key(metadata.get('channel')):continue
                row.update(eklenme=stamp,guncellenme=stamp,auto_discovered=True,kaynak_dogrulamasi='Publisher owner, minimum duration and public oEmbed verified; device playback not asserted.');rows.append(row)
            except Exception:pass
            if len(rows)>=20:break
        return rows
    with cf.ThreadPoolExecutor(max_workers=3) as pool:
        tasks={pool.submit(scan_movies,p):p for p in config.get('movie_publishers',[])}
        for future in cf.as_completed(tasks):
            try:additions.extend(future.result())
            except Exception:report['pending'].append(dict(source=tasks[future]['url'],reason='Public film listing unavailable; previous catalog retained'))
    for row in additions:
        if row['resmi_url'] in movie_ids or key(row['baslik']) in movie_titles:continue
        movies.append(row);movie_ids.add(row['resmi_url']);movie_titles.add(key(row['baslik']));report['addedMovies'].append(dict(id=row['id'],title=row['baslik']))
    feed['series']=list(existing.values());feed['followed']=followed
    write(root/'schedules/followed-series.json',followed);write(root/'schedules/series-artwork.json',artwork);write(root/'public-updates/series-updates.json',feed);write(root/'public-updates/movies.json',movies)
    write(root/'public-updates/discovery-report.json',report)
    print('Discovery: '+str(len(report['addedSeries']))+' series, '+str(len(report['addedMovies']))+' films, '+str(len(report['pending']))+' awaiting verification.',flush=True)
    return report

if __name__=='__main__':refresh()
