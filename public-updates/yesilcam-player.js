(function(){
 'use strict';
 var program=document.body.getAttribute('data-program')==='arzu-film'?'arzu-film':'yesilcam';
 var schedule,player,index=0,total=0,ready=false,skips=0,timer,fade;
 var info=document.getElementById('info'),title=document.getElementById('title'),start=document.getElementById('start'),message=document.getElementById('message');
 function error(text){message.hidden=false;message.textContent=text;}
 function atTime(time){var seconds=((Math.floor(time/1000)%total)+total)%total;for(var i=0;i<schedule.movies.length;i++){if(seconds<schedule.movies[i].duration)return {index:i,offset:seconds};seconds-=schedule.movies[i].duration;}return {index:0,offset:0};}
 function show(){if(!schedule)return;title.textContent=schedule.movies[index].title;info.querySelector('small').textContent='ŞİMDİ · '+schedule.movies.length+' FİLMLİK ARŞİV';info.style.opacity='1';clearTimeout(fade);fade=setTimeout(function(){info.style.opacity='0';},6500);}
 function next(){if(!ready)return;for(var step=1;step<=schedule.movies.length;step++){var candidate=(index+step)%schedule.movies.length;if(schedule.movies[candidate].metadataAvailable!==false){index=candidate;break;}}show();player.loadVideoById({videoId:schedule.movies[index].id,startSeconds:0});}
 start.onclick=function(){if(player){player.unMute();player.playVideo();start.hidden=true;}};
 document.body.addEventListener('pointerdown',function(e){if(e.target!==start)show();});
 window.onYouTubeIframeAPIReady=function(){
  var current=atTime(Date.now());index=current.index;
  player=new YT.Player('player',{width:'100%',height:'100%',videoId:schedule.movies[index].id,playerVars:{autoplay:1,playsinline:1,controls:0,disablekb:1,fs:0,cc_load_policy:0,origin:location.origin,widget_referrer:location.href.split('#')[0],start:current.offset},events:{
   onReady:function(){ready=true;show();player.playVideo();},
   onStateChange:function(e){if(e.data===0){skips=0;next();}else if(e.data===1){skips=0;message.hidden=true;try{if(!player.isMuted())start.hidden=true;}catch(ignore){}}else if(e.data===2)player.playVideo();},
   onAutoplayBlocked:function(){player.mute();player.playVideo();start.hidden=false;},
   onError:function(e){if([2,100,101,150].indexOf(e.data)>=0&&skips<3){skips++;next();}else error('Bu yayın şu anda başlatılamadı. Sayfayı yeniden açıp deneyebilirsin.');}
  }});
 };
 fetch(program+'-schedule.json',{cache:'no-cache'}).then(function(r){if(!r.ok)throw new Error('schedule');return r.json();}).then(function(data){
  if(!data||data.schema!==1||data.id!==program||!Array.isArray(data.movies)||data.movies.length<(program==='yesilcam'?200:20)||data.movies.length>400||!data.movies.every(function(m){return m&&/^[\w-]{11}$/.test(m.id)&&typeof m.title==='string'&&typeof m.duration==='number'&&isFinite(m.duration)&&m.duration>=3600&&m.duration<=10800;}))throw new Error('schedule');
  schedule=data;total=data.movies.reduce(function(sum,m){return sum+m.duration;},0);show();var api=document.createElement('script');api.src='https://www.youtube.com/iframe_api';api.onerror=function(){error('YouTube oynatıcısına bağlanılamadı.');};document.head.appendChild(api);
 }).catch(function(){error('Film listesi alınamadı. İnternet bağlantını kontrol edip tekrar aç.');});
 window.addEventListener('pagehide',function(){clearTimeout(fade);clearInterval(timer);if(player)player.destroy();});
})();
