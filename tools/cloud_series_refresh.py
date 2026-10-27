"""Standalone cloud job. Reads/writes only the public followed-series update feed."""
import datetime as dt
import json
from pathlib import Path
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from tools.series_metadata import FOLLOWED, build_followed


def listing(url, limit):
    result=subprocess.run([sys.executable,'-m','yt_dlp','--flat-playlist','--extractor-args','youtube:lang=tr','--dump-single-json',
                           '--skip-download','--no-warnings','--socket-timeout','20','--playlist-end',str(limit),url],
                          capture_output=True,text=True,encoding='utf-8',timeout=120)
    if result.returncode:raise RuntimeError('Public channel listing unavailable')
    return json.loads(result.stdout)


def scan(identity, config, previous):
    if config.get('children_playlists'):
        metadata=dict(channel_id=config['channel'],entries=[])
        for section in config['children_playlists']:
            part=listing('https://www.youtube.com/playlist?list='+section['playlist'],600)
            if part.get('channel_id')!=config['channel']:raise ValueError('Unexpected children playlist owner')
            metadata['entries'] += [{**entry,'_official_season':section['season']} for entry in part['entries'] if entry]
        if config.get('supplement_channel_limit'):
            extra=listing(config['url'],config['supplement_channel_limit'])
            if extra.get('channel_id')!=config['channel']:raise ValueError('Unexpected additional child publisher')
            metadata['entries'] += [{**entry,'_official_season':1} for entry in extra['entries'] if entry]
    else:metadata=listing(config['url'],200)
    if config.get('trailer_playlist'):
        try:
            extra=listing('https://www.youtube.com/playlist?list='+config['trailer_playlist'],50)
            if extra.get('channel_id')==config['channel']:metadata['entries']+=extra.get('entries',[])
        except (ValueError,OSError,RuntimeError,subprocess.TimeoutExpired):
            # Main channel metadata still contains public trailers and episodes.
            pass
    return build_followed(identity,metadata,previous)


def refresh(folder=None):
    root=Path(folder) if folder else Path(__file__).resolve().parents[1]
    target=root/'public-updates/series-updates.json'
    payload=json.loads(target.read_text(encoding='utf-8'))
    rows={r['id']:r for r in payload['series']}
    children_file=root/'public-updates/children-updates.json'
    if children_file.exists():rows.update({r['id']:r for r in json.loads(children_file.read_text(encoding='utf-8'))['series']})
    failed=[];changes=[]
    with ThreadPoolExecutor(max_workers=4) as pool:
        tasks={pool.submit(scan,identity,config,rows.get(identity)):identity for identity,config in FOLLOWED.items()}
        for task in as_completed(tasks):
            identity=tasks[task]
            try:
                row=task.result();row['kontrol_araligi_saniye']=900;previous=rows.get(identity,{});before=previous.get('son_tam_bolum',0)
                if row.get('son_tam_bolum',0)<before:raise ValueError('Episode history cannot shrink')
                rows[identity]=row
                changes.append(dict(id=identity,before=before,after=row.get('son_tam_bolum'),trailers=[t['no'] for t in row.get('fragmanlar',[])]))
                print(identity+': '+str(before)+' -> '+str(row.get('son_tam_bolum'))+'; upcoming trailers '+str(len(row.get('fragmanlar',[]))),flush=True)
            except (ValueError,OSError,RuntimeError,subprocess.TimeoutExpired) as error:
                failed.append(identity);print(identity+': previous catalog retained: '+str(error),file=sys.stderr,flush=True)
    if len(failed)==len(FOLLOWED):raise RuntimeError('All channel checks failed; feed left unchanged')
    stamp=dt.datetime.now(dt.timezone.utc).isoformat()
    child_registry={i:c for i,c in FOLLOWED.items() if c.get('feed')=='children'}
    children=dict(schema=1,generatedAt=stamp,refreshIntervalSeconds=900,capability='short-child-episodes-v1',followed=child_registry,series=[r for i,r in rows.items() if i in child_registry],refreshStatus=dict(failedSeries=[i for i in failed if i in child_registry]))
    if children['series']:
        child_tmp=children_file.with_suffix('.tmp');child_tmp.write_text(json.dumps(children,ensure_ascii=False,separators=(',',':')),encoding='utf-8');child_tmp.replace(children_file)
    payload=dict(schema=1,generatedAt=stamp,refreshIntervalSeconds=900,
                 refreshStatus=dict(checked=len(FOLLOWED),succeeded=len(FOLLOWED)-len(failed),failedSeries=sorted(failed)),followed={i:c for i,c in FOLLOWED.items() if i not in child_registry},series=[r for i,r in rows.items() if i not in child_registry])
    tmp=target.with_suffix('.tmp');tmp.write_text(json.dumps(payload,ensure_ascii=False,separators=(',',':')),encoding='utf-8');tmp.replace(target)
    print('Public episode/trailer feed refreshed; no video files downloaded.')
    summary=__import__('os').environ.get('GITHUB_STEP_SUMMARY')
    if summary:
        with open(summary,'a',encoding='utf-8') as report:
            report.write('## Official catalog scan\n\nChecked '+str(len(FOLLOWED))+' series; succeeded '+str(len(FOLLOWED)-len(failed))+'.\n\n| Series | Previous episode | Latest episode | Upcoming trailers |\n|---|---:|---:|---|\n')
            for item in sorted(changes,key=lambda x:x['id']):report.write('| '+item['id']+' | '+str(item['before'])+' | '+str(item['after'])+' | '+', '.join(map(str,item['trailers']))+' |\n')
            if failed:report.write('\nRetained last verified catalog for: '+', '.join(sorted(failed))+'.\n')
    return payload


if __name__=='__main__':refresh()
