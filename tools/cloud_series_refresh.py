"""Standalone cloud job. Reads/writes only the public followed-series update feed."""
import datetime as dt
import json
from pathlib import Path
import subprocess
import sys
from tools.series_metadata import FOLLOWED, build_followed


def refresh(folder=None):
    root=Path(folder) if folder else Path(__file__).resolve().parents[1]
    target=root/'public-updates/series-updates.json'
    payload=json.loads(target.read_text(encoding='utf-8'))
    rows={r['id']:r for r in payload['series']}
    failed=[]
    for identity,config in FOLLOWED.items():
        try:
            result=subprocess.run([sys.executable,'-m','yt_dlp','--flat-playlist','--extractor-args','youtube:lang=tr','--dump-single-json',
                                   '--skip-download','--no-warnings','--socket-timeout','20','--playlist-end','100',config['url']],
                                  capture_output=True,text=True,encoding='utf-8',timeout=150)
            if result.returncode:raise RuntimeError('Public channel listing unavailable')
            metadata=json.loads(result.stdout)
            if config.get('trailer_playlist'):
                trailer=subprocess.run([sys.executable,'-m','yt_dlp','--flat-playlist','--extractor-args','youtube:lang=tr','--dump-single-json','--skip-download',
                                        '--no-warnings','--socket-timeout','20','--playlist-end','50','https://www.youtube.com/playlist?list='+config['trailer_playlist']],
                                       capture_output=True,text=True,encoding='utf-8',timeout=90)
                if not trailer.returncode:
                    extra=json.loads(trailer.stdout)
                    if extra.get('channel_id')==config['channel']:metadata['entries']+=extra.get('entries',[])
            rows[identity]=build_followed(identity,metadata,rows.get(identity))
        except (ValueError,OSError,RuntimeError,subprocess.TimeoutExpired) as error:
            failed.append(identity);print(identity+': previous catalog retained: '+str(error),file=sys.stderr)
    if len(failed)==len(FOLLOWED):raise RuntimeError('All channel checks failed; feed left unchanged')
    payload=dict(schema=1,generatedAt=dt.datetime.now(dt.timezone.utc).isoformat(),followed=FOLLOWED,series=list(rows.values()))
    tmp=target.with_suffix('.tmp');tmp.write_text(json.dumps(payload,ensure_ascii=False,separators=(',',':')),encoding='utf-8');tmp.replace(target)
    print('Public episode/trailer feed refreshed; no video files downloaded.')


if __name__=='__main__':refresh()
