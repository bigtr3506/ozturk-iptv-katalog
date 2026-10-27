import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from tools.children_series import build
from tools import cloud_series_refresh
ROOT=Path(__file__).resolve().parents[1]

class ChildrenSeriesTests(unittest.TestCase):
 def config(self,**extra):
  return dict(id='test-child',title='Çocuk Serisi',channel='UC'+'a'*22,feed='children',publisher='trt',content_type='animasyon',minimum_seconds=300,maximum_seconds=1500,numbering='numbered',season_ends=[],season_titles=['Bölümler'],genres=['Çocuk','Animasyon'],official='https://www.trtcocuk.net.tr/test',url='https://www.youtube.com/channel/UC'+'a'*22+'/videos',**extra)
 def entry(self,vid,title,duration=700,**extra):return dict(id=vid,title=title,duration=duration,**extra)
 def test_complete_short_episodes_are_not_confused_with_trailers_compilations_or_wrong_owners(self):
  c=self.config();entries=[self.entry('abcdefghijk','Çocuk Serisi 1. Bölüm'),self.entry('12345678901','Çocuk Serisi 2. Bölüm Fragmanı',45),self.entry('22345678901','Çocuk Serisi 3. Bölüm Birden',1400),self.entry('32345678901','Çocuk Serisi 4. Bölüm',3600),self.entry('42345678901','Çocuk Serisi 5. Bölüm',channel_id='wrong')]
  row=build(c,dict(channel_id=c['channel'],entries=entries));self.assertEqual(row['son_tam_bolum'],1);self.assertEqual(row['icerik_turu'],'animasyon')
 def test_named_playlist_numbers_stay_stable_when_publisher_inserts_new_episode_at_top(self):
  c=self.config();c['numbering']='playlist'
  first=build(c,dict(channel_id=c['channel'],entries=[self.entry('abcdefghijk','Çocuk Serisi | Eski Öykü')]))
  new=build(c,dict(channel_id=c['channel'],entries=[self.entry('12345678901','Çocuk Serisi | Yeni Öykü'),self.entry('abcdefghijk','Çocuk Serisi | Eski Öykü')]),first)
  self.assertEqual([e['youtube_id'] for e in new['sezonlar'][0]['bolumler']],['abcdefghijk','12345678901'])
 def test_local_and_global_season_numbering_are_distinct(self):
  c=self.config();c.update(season_ends=[13,26],season_titles=['1. Sezon','2. Sezon','3. Sezon'])
  row=build(c,dict(channel_id=c['channel'],entries=[self.entry('abcdefghijk','Çocuk Serisi 27. Bölüm')]))
  self.assertEqual(row['sezonlar'][0]['no'],3);self.assertEqual(row['sezonlar'][0]['bolumler'][0]['sezon_icino'],1)
  c['season_numbers_local']=True
  row=build(c,dict(channel_id=c['channel'],entries=[self.entry('abcdefghijk','Çocuk Serisi 2. Sezon 1. Bölüm',_official_season=2)]))
  self.assertEqual(row['sezonlar'][0]['bolumler'][0]['no'],14)
 def test_cloud_keeps_short_child_feed_out_of_legacy_long_series_feed(self):
  with tempfile.TemporaryDirectory(dir=ROOT) as folder:
   root=Path(folder);(root/'public-updates').mkdir();(root/'public-updates/series-updates.json').write_text(json.dumps({'series':[]}))
   regs={'adult':{'title':'Dizi'},'child':{'title':'Çocuk','feed':'children'}}
   def scan(identity,c,previous):return dict(id=identity,son_tam_bolum=1,fragmanlar=[])
   with patch.dict(cloud_series_refresh.FOLLOWED,regs,clear=True),patch.object(cloud_series_refresh,'scan',side_effect=scan):result=cloud_series_refresh.refresh(root)
   self.assertEqual([r['id'] for r in result['series']],['adult']);self.assertNotIn('child',result['followed'])
   child=json.loads((root/'public-updates/children-updates.json').read_text());self.assertEqual([r['id'] for r in child['series']],['child'])
