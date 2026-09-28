/* One catalog for bundled lessons, source files and the user's saved videos. */
(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;else root.LabCatalog=api;})(typeof window!=='undefined'?window:globalThis,function(){
 'use strict';
 const groups=[{id:'gabriel',label:'가브리엘'},{id:'speech',label:'연설문'},{id:'kpop',label:'KPOP'},{id:'interview',label:'인터뷰 PDF'},{id:'youtube',label:'유튜브'}];
 const aliases={g01:'가브리엘 Gabriel',kpop:'케이팝 데몬 헌터스 대본',s01:'찰리 채플린 독재자',s02:'코난 하버드',s03:'스티브 잡스 스탠퍼드',s04:'버락 오바마',s05:'데이비드 포스터 월리스 이것은 물이다',s06:'바네사 브라이언트',s07:'제프 베이조스 프린스턴',s08:'브레네 브라운 취약성',s09:'말랄라 유엔',s10:'나탈리 포트먼',s11:'조앤 롤링',pdf_jennie:'제니 젠니',pdf_elon:'일론 머스크',pdf_harvard:'하버드 교수 아서 브룩스 Harvard Prof 행복 인생 후반전',video_hZWTGyXF0mI:'아서 브룩스 행복'};
 const norm=s=>String(s||'').normalize('NFKC').toLocaleLowerCase().replace(/\s+/g,' ').trim();
 const validVideo=id=>typeof id==='string'&&/^[A-Za-z0-9_-]{11}$/.test(id);
 function matchesCard(card,id,lessons=[]){
  if(id==='all')return true;
  if(id.startsWith('video_'))return card.media?.video_id===id.slice(6);
  return card.lesson_id===id||lessons.find(l=>l.id===card.lesson_id)?.family===id;
 }
 function build({lessons=[],cards=[],materials=[],videos=[],exercises=[],draft=null}={}){
  const result=[],byLesson=new Map(),byVideo=new Map();
  for(const c of cards){
   if(!byLesson.has(c.lesson_id))byLesson.set(c.lesson_id,[]);byLesson.get(c.lesson_id).push(c);
   if(validVideo(c.media?.video_id)){const id=c.media.video_id;if(!byVideo.has(id))byVideo.set(id,[]);byVideo.get(id).push(c);}
  }
  for(const l of lessons){
   if(l.family==='youtube'||l.id==='youtube')continue;
   const items=byLesson.get(l.id)||[],material=materials.find(m=>m.id===(l.material_id||l.id)),sources=[];
   const add=(url,label)=>{const href=String(url||'').split('#')[0];if(!/^sources\/[^/]+\.(?:png|jpe?g|webp|pdf|docx)$/i.test(href)||sources.some(s=>s.href===href))return;sources.push({href,label:label||(/\.docx$/i.test(href)?'원본 Word 자료':/\.pdf$/i.test(href)?'원본 PDF':'강의 캡처 '+(sources.length+1))});};
   for(const image of l.images||[])add(image);
   if(material)add('sources/'+material.source_file,'원본 PDF');
   for(const c of items)add(c.source_url);
   if(l.id==='kpop')add('sources/kpop_script.pdf','원본 대본 PDF');
   const itemIds=new Set(items.map(c=>c.id));
   const drills=exercises.filter(e=>e.card_ids?.length&&(e.lesson_id===l.id||e.card_ids.every(id=>itemIds.has(id))));
   const kind=material?'pdf':'lesson',group=groups.some(g=>g.id===l.family)?l.family:'other';
   result.push({id:l.id,title:l.title,group,kind,bundled:true,cards:items,exercises:drills,sources,material,
    search:norm([l.title,aliases[l.id],l.family==='gabriel'?'가브리엘 Gabriel':'',l.source,...items.map(c=>c.expression+' '+c.meaning_ko)].join(' '))});
  }
  const videoInfo=new Map(videos.filter(v=>validVideo(v.id)).map(v=>[v.id,v]));
  for(const id of byVideo.keys())if(!videoInfo.has(id))videoInfo.set(id,{id});
  if(validVideo(draft?.videoId)&&!videoInfo.has(draft.videoId))videoInfo.set(draft.videoId,{id:draft.videoId});
  for(const [id,video] of videoInfo){
   const items=byVideo.get(id)||[],currentDraft=draft?.videoId===id?draft:null;
   const savedTitle=items[0]?.source_locator?.replace(/\s+·\s+(?:\d{1,2}:.*|시간 정보 없음)$/,'');
   const title=video.study_title||currentDraft?.title||savedTitle||'내 유튜브 자료 · '+id;
   const entryId='video_'+id;
   result.push({id:entryId,title,group:'youtube',kind:'video',bundled:videos.some(v=>v.id===id),video:{...video,study_title:title,url:'https://www.youtube.com/watch?v='+id,lesson_id:entryId},cards:items,exercises:[],sources:[{href:'https://www.youtube.com/watch?v='+id,label:'원본 영상'}],hasDraft:!!currentDraft?.transcript?.trim(),
    search:norm([title,aliases[entryId],video.channel,id,...items.map(c=>c.expression+' '+c.meaning_ko)].join(' '))});
  }
  return result;
 }
 function filter(entries,{query='',group='all'}={}){const words=norm(query).split(' ').filter(Boolean);return entries.filter(e=>(group==='all'||e.group===group)&&words.every(word=>e.search.includes(word)));}
 return {groups,norm,build,filter,matchesCard};
});
