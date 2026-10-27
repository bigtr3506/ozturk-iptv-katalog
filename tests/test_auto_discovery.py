import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from tools import auto_discovery as discovery,series_metadata

class AutoDiscoveryTests(unittest.TestCase):
 def setUp(self):
  self.channel='UC'+'a'*22
  self.show={'id':123,'url':'https://www.tvmaze.com/shows/123/new','name':'Yeni Dizi','type':'Scripted','premiered':'2026-09-01','network':{'name':'Show TV','country':{'code':'TR'}},'image':{'original':'https://static.tvmaze.com/uploads/poster.jpg'}}
  self.episodes=[{'season':1,'number':1},{'season':1,'number':2},{'season':2,'number':1}]
  self.metadata={'id':self.channel,'channel_id':self.channel,'channel':'Yeni Dizi','entries':[{'id':'a'*10+str(i),'title':f'Yeni Dizi {i}. Bölüm','duration':7200,'channel_id':self.channel} for i in range(1,4)]}
 def test_verified_new_series_has_complete_initial_catalog_and_season_boundaries(self):
  with patch.dict(series_metadata.FOLLOWED,{},clear=False):
   identity,config,row,art=discovery.initial_series('Yeni Dizi','https://www.showtv.com.tr/dizi/tanitim/yeni-dizi/1','show',self.metadata,self.show,self.episodes)
   self.assertEqual(config['season_ends'],[2]);self.assertEqual([len(s['bolumler']) for s in row['sezonlar']],[2,1]);self.assertEqual(row['afis'],art['poster']);self.assertTrue(row['auto_discovered'])
   self.assertTrue(series_metadata.build_followed(identity,self.metadata,row)['auto_discovered'])
 def test_missing_episode_unknown_season_wrong_owner_and_wrong_network_are_rejected(self):
  for mutate in ('missing','seasons','owner','network'):
   meta=json.loads(json.dumps(self.metadata));show=json.loads(json.dumps(self.show));eps=list(self.episodes)
   if mutate=='missing':meta['entries'].pop(0)
   if mutate=='seasons':eps=[{'season':1,'number':2}]
   if mutate=='owner':meta['channel_id']='invalid'
   if mutate=='network':show['network']['name']='Other TV'
   with self.assertRaises(ValueError):discovery.initial_series('Yeni Dizi','https://www.showtv.com.tr/new','show',meta,show,eps)
 def test_movie_filters_reject_short_clips_trailers_wrong_owners_and_live_video(self):
  publisher={'name':'Resmi Film','channel':self.channel,'minimum_seconds':3600};entry={'id':'abcdefghijk','title':'Yeni Film | Full Film HD','duration':5400,'channel_id':self.channel}
  self.assertEqual(discovery.movie_row(entry,publisher)['baslik'],'Yeni Film')
  for bad in ({'duration':300},{'title':'Yeni Film Fragman'},{'channel_id':'UC'+'b'*22},{'live_status':'is_live'},{'duration':'unknown'},{'title':'All Commander Moments Full Film'},{'title':'Comedy Festival #38 Full Film'},{'title':'Uzun video HD'},{'title':'Hemşo En İyi Sahneler Türk Filmi'}):self.assertIsNone(discovery.movie_row({**entry,**bad},publisher))
 def test_reviewed_final_episode_title_is_not_confused_with_a_scene_compilation(self):
  metadata={'channel_id':self.channel,'entries':[{'id':'abcdefghijk','title':'Yeni Dizi 79. FİNAL BÖLÜMÜ 4K','duration':6315},{'id':'12345678901','title':'Yeni Dizi 80. FİNAL BÖLÜMÜ Sahneleri','duration':6315}]}
  full,_=series_metadata.select(metadata,'Yeni Dizi',self.channel,3600)
  self.assertEqual(list(full),[79])
 def test_provider_outage_keeps_catalog_and_writes_an_honest_pending_report(self):
  with tempfile.TemporaryDirectory(dir=discovery.ROOT) as folder:
   root=Path(folder);(root/'schedules').mkdir();(root/'public-updates').mkdir()
   config={'series_providers':[{'url':'https://www.showtv.com.tr/diziler','publisher':'show','pattern':'/new'}],'movie_publishers':[],'known_series':[]}
   (root/'schedules/auto-discovery.json').write_text(json.dumps(config));(root/'schedules/followed-series.json').write_text('{}')
   before={'schema':1,'series':[{'id':'kept'}]};(root/'public-updates/series-updates.json').write_text(json.dumps(before));(root/'public-updates/movies.json').write_text('[{"id":"kept-film","baslik":"Existing movie"}]')
   with patch.object(discovery,'fetch',side_effect=OSError('offline')):report=discovery.refresh(root)
   self.assertEqual(discovery.read(root/'public-updates/series-updates.json',{})['series'],before['series']);self.assertFalse(report['providers'][0]['ok']);self.assertEqual(report['addedSeries'],[])

if __name__=='__main__':unittest.main()
