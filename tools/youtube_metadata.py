"""Pure public playlist metadata conversion shared by PC and hosted refresh jobs."""
import re
import datetime as dt

def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def make_series(metadata, identity, title, publisher, season_map=None):
    if not re.fullmatch(r'[a-zA-Z0-9_-]{1,100}', identity):
        raise ValueError('Invalid series ID')
    playlist_id = metadata.get('id', '')
    if not re.fullmatch(r'[a-zA-Z0-9_-]{10,150}', playlist_id):
        raise ValueError('Invalid playlist ID')
    entries = metadata.get('entries', [])
    if not 1 <= len(entries) <= 1000:
        raise ValueError('Playlist must contain 1–1000 entries')
    seasons, seen, numbers, skipped = {}, set(), set(), []
    for position, entry in enumerate(entries, 1):
        entry = entry or {}
        video_id, name = entry.get('id', ''), entry.get('title', '')
        if (not re.fullmatch(r'[\w-]{11}', video_id)
                or entry.get('availability') in {'private', 'needs_auth', 'premium_only', 'subscriber_only'}
                or name in {'[Private video]', '[Deleted video]'}):
            skipped.append({'position': position, 'reason': 'unavailable', 'id': video_id})
            continue
        if video_id in seen:
            skipped.append({'position': position, 'reason': 'duplicate', 'id': video_id})
            continue
        match = re.search(r'(\d+)\s*\.\s*Bölüm', name, re.I)
        number = int(match[1]) if match else position
        season = (season_map or {}).get(number, 1)
        if (season, number) in numbers:
            raise ValueError('Duplicate episode number; check the playlist order')
        seen.add(video_id)
        numbers.add((season, number))
        url = 'https://www.youtube.com/watch?v=' + video_id
        duration = entry.get('duration')
        episode = dict(no=number, baslik=name or f'{number}. Bölüm',
                       sure=int(duration) if isinstance(duration, (int, float)) and duration > 0 else None,
                       kaynaklar=[dict(url=url, tip='youtube', oncelik=0)],
                       kaynak_tipi='youtube', url=url, durum='aktif',
                       gorsel=f'https://i.ytimg.com/vi/{video_id}/hqdefault.jpg',
                       youtube_id=video_id, playlist_sirasi=position)
        seasons.setdefault(season, []).append(episode)
    if not seen:
        raise ValueError('No public videos in playlist')
    row = dict(id=identity, baslik=title, kanal=publisher,
               afis=f'https://i.ytimg.com/vi/{next(iter(seasons.values()))[0]["youtube_id"]}/hqdefault.jpg',
               arka_plan=f'https://i.ytimg.com/vi/{next(iter(seasons.values()))[0]["youtube_id"]}/hqdefault.jpg',
               aciklama=f'{title} — {metadata.get("title", "YouTube bölümleri")}. Resmî YouTube oynatıcı ile izlenir.',
               turler=['Dram'], oyuncular=[], durum='aktif', oynatilabilir=True, yonetim=True,
               resmi_url='https://www.youtube.com/playlist?list='+playlist_id,
               kaynak_playlist=playlist_id, kaynak_kanal=metadata.get('channel'),
               kaynak_kanal_id=metadata.get('channel_id'), eklenme=now(), populerlik=0, puan=0,
               sezonlar=[dict(no=n, bolumler=sorted(eps, key=lambda e:e['no'])) for n, eps in sorted(seasons.items())])
    return row, skipped

