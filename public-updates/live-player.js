(function(){
 'use strict';
 var sources=['https://selcuksports-izle.online/hls/bein-1/360/index.m3u8','https://css.d6e3cae2e245k5.help//hls/bein1.m3u8'];
 var video=document.getElementById('video'),status=document.getElementById('status'),details=document.getElementById('details'),hls=null,timer=null,generation=0;
 function message(text,detail){status.textContent=text;if(detail)details.textContent=detail;}
 function stop(){generation++;clearTimeout(timer);if(hls){hls.destroy();hls=null;}video.pause();video.removeAttribute('src');video.load();}
 function fail(text,detail){stop();message(text,detail);}
 function play(){var result=video.play();if(result&&result.catch)result.catch(function(e){message('Oynatmak için videodaki oynat düğmesine bas.',e.name);});}
 document.getElementById('stop').onclick=function(){stop();message('Durduruldu.');};
 document.getElementById('play').onclick=function(){
  stop();var token=generation,url=sources[Number(document.getElementById('source').value)];details.textContent='';message('Yayın yükleniyor…');video.muted=false;video.volume=1;
  timer=setTimeout(function(){if(token===generation)fail('Yayın 30 saniye içinde başlayamadı.','Kaynak veya ağ erişimi kontrol edilmeli.');},30000);
  video.onplaying=function(){if(token!==generation)return;clearTimeout(timer);message('Yayın oynatılıyor.');};
  video.ontimeupdate=function(){if(token===generation&&video.readyState>=2&&video.currentTime>0)details.textContent='Görüntü: '+video.videoWidth+' × '+video.videoHeight+' | Süre: '+Math.floor(video.currentTime)+' sn';};
  video.onerror=function(){if(token===generation)fail('Cihaz oynatıcısı yayını açamadı.','Video hata kodu: '+(video.error&&video.error.code));};
  if(document.getElementById('engine').value==='mse'){
   if(!window.Hls||!Hls.isSupported()){fail('Bu cihaz HLS.js oynatımını desteklemiyor.','Cihaz oynatıcısı seçeneğini deneyebilirsin.');return;}
   hls=new Hls({enableWorker:false,maxBufferLength:20,backBufferLength:10});
   hls.on(Hls.Events.MEDIA_ATTACHED,function(){if(token===generation)hls.loadSource(url);});
   hls.on(Hls.Events.MANIFEST_PARSED,function(){if(token===generation)play();});
   hls.on(Hls.Events.ERROR,function(event,data){if(token!==generation||!data.fatal)return;var code=data.response&&data.response.code;fail(code===401||code===403?'Kaynak sunucu erişimi reddetti.':'Yayın alınamadı.',data.details+' | HTTP: '+(code||'tarayıcı yanıtı okunamadı'));});
   hls.attachMedia(video);
  }else{video.src=url;play();}
 };
 window.addEventListener('pagehide',stop);
})();
