/* Full transcript speech and sentence-range loops. Uses the existing voice permission. */
let scriptRows=[],scriptKey='',scriptVersion=0,scriptSession=null,scriptPage=0,scriptTimer=null,scriptStartTimer=null;
let scriptMaterial=null;
function scriptSourceKey(){return scriptMaterial?'material:'+scriptMaterial.id:(ytVideo?.id||'')+'\n'+$('ytTranscript').value;}
function scriptRowSource(row){if(!row)return '';return `PDF ${row.page}쪽 · ${row.speaker}${row.context_ko?' · '+row.context_ko:''}`;}
const SCRIPT_PAGE_SIZE=40;
function scriptMessage(message,error=false){$('ytScriptStatus').textContent=message;$('ytScriptStatus').className='statusline '+(error?'error':'ok');}
function scriptActive(s=scriptSession){return !!s&&['starting','playing','gap','paused','waiting_voice','translating','translation_error'].includes(s.phase);}
function scriptValid(s){return scriptSession===s&&s.version===scriptVersion&&s.key===scriptKey&&scriptActive(s)&&!recording()&&!busy;}
function clearScriptTimers(){clearTimeout(scriptTimer);clearTimeout(scriptStartTimer);scriptTimer=null;scriptStartTimer=null;}
function interruptTranscriptPlayback(){
 clearScriptTimers();cancelScriptKorean();
 if(scriptActive()){scriptSession.segment++;scriptSession.phase='stopped';scriptSession.utterance=null;scriptMessage('대본 재생을 멈췄습니다. 전체 재생 또는 선택 구간 반복으로 다시 시작하세요.');}
 renderScriptTransport();
}
function resetTranscriptPlayer(){
 stopAudio();scriptKoErrors.clear();scriptRows=[];scriptKey='';scriptVersion++;scriptPage=0;scriptSession=null;renderTranscriptPlayer();
}
function syncTranscriptPlayer(){
 const key=scriptSourceKey();
 if(key===scriptKey)return;
 stopAudio();scriptKoErrors.clear();scriptVersion++;scriptKey=key;scriptPage=0;scriptSession=null;
 // Use all parsed cues. The learning-card filter, deduplication and 20-card limit do not apply.
 scriptRows=scriptMaterial?scriptMaterial.rows.map(c=>({...c,start:null,end:null})):ytCues.filter(c=>c.text.trim()&&!/^(?:\[(?:music|applause|laughter|silence)\]|[♪♫\s])+$/i.test(c.text)).map(c=>({...c}));
 renderTranscriptPlayer();
}
function scriptCardIds(row){
 if(scriptMaterial&&row.card_id)return [row.card_id];
 const norm=s=>s.replace(/\s+/g,' ').trim().toLowerCase(),text=norm(row.text);
 return state.customCards.filter(c=>c.media.video_id===ytVideo?.id&&text.includes(norm(c.expression))).map(c=>c.id);
}
function scriptKorean(row){if(scriptMaterial){const prepared=scriptMaterial.rows.find(r=>r.card_id===row.card_id&&r.text===row.text);if(prepared)return prepared.korean_text;}const c=state.customCards.find(c=>c.media.video_id===ytVideo?.id&&c.expression===row.text);return (c?K.ko(c,state.translations[c.id]):'')||K.transcriptMeaning(state.transcriptTranslations,row.text);}
// The transcript has its own exact-sentence cache, independent of the card quota.
let scriptKoEngine=null;
const scriptKoErrors=new Map();
function scriptKoCurrent(e){return !!window.document&&scriptKoEngine===e&&!e.controller.signal.aborted&&e.version===scriptVersion&&e.key===scriptKey&&e.key===scriptSourceKey()&&!busy&&!recording();}
function cancelScriptKorean(){
 const e=scriptKoEngine;if(!e)return;scriptKoEngine=null;e.controller.abort();e.translator?.destroy?.();
 for(const request of e.requests.values())request.reject(new DOMException('번역 중단','AbortError'));
 e.requests.clear();e.queue=[];
}
function scriptKoBound(promise,e,ms=120000){
 let timer,listener;
 const stopped=new Promise((_,reject)=>{listener=()=>reject(new DOMException('번역 중단','AbortError'));e.controller.signal.addEventListener('abort',listener,{once:true});timer=setTimeout(()=>{e.timeout=true;e.controller.abort();},ms);if(e.controller.signal.aborted)listener();});
 return Promise.race([promise,stopped]).finally(()=>{clearTimeout(timer);e.controller.signal.removeEventListener('abort',listener);});
}
function scriptKoCreate(){
 if(scriptKoEngine&&scriptKoCurrent(scriptKoEngine))return scriptKoEngine;
 cancelScriptKorean();
 const e={version:scriptVersion,key:scriptKey,controller:new AbortController(),requests:new Map(),queue:[],running:false,translator:null,browser:null,local:null,unavailable:'',timeout:false};scriptKoEngine=e;
 // Called under the playback/retry click when a language pack first needs activation.
 if(window.Translator?.create){
  try{e.browser=Promise.resolve(window.Translator.create({sourceLanguage:'en',targetLanguage:'ko',signal:e.controller.signal}));}catch(error){e.browser=Promise.reject(error);}
  e.browser.then(t=>{if(!scriptKoCurrent(e))t.destroy?.();},()=>{});
 }
 return e;
}
function requestScriptKorean(row,priority=true){
 const ko=scriptKorean(row);if(ko)return Promise.resolve(ko);
 if(scriptKoErrors.has(row.text))return Promise.reject(Error(scriptKoErrors.get(row.text)));
 const e=scriptKoCreate();let request=e.requests.get(row.text);
 if(!request){let resolve,reject;const promise=new Promise((yes,no)=>{resolve=yes;reject=no;});request={text:row.text,resolve,reject,promise};e.requests.set(row.text,request);if(priority)e.queue.unshift(request);else e.queue.push(request);}
 else if(priority){const index=e.queue.indexOf(request);if(index>=0){e.queue.splice(index,1);e.queue.unshift(request);}}
 runScriptKorean(e);return request.promise;
}
async function translateScriptText(e,text){
 if(config.deepl?.configured&&config.youtube_token){
  try{
   const response=await scriptKoBound(fetch('/deepl/translate',{method:'POST',headers:{'Content-Type':'application/json','X-Local-Token':config.youtube_token},body:JSON.stringify({texts:[text]}),signal:e.controller.signal}),e);
   const result=await scriptKoBound(response.json(),e);const t={source_en:text,korean_text:result.translations?.[0]?.korean_text,engine:'deepl'};
   if(response.ok&&result.engine==='deepl'&&result.translations?.[0]?.source_en===text&&K.validTranslation(t,text)&&t.korean_text.length<=2000)return t;
  }catch(error){if(e.controller.signal.aborted)throw error;}
 }
 if(e.unavailable)throw Error(e.unavailable);
 if(e.browser&&!e.translator){try{e.translator=await scriptKoBound(e.browser,e,390000);}catch(error){if(e.controller.signal.aborted)throw error;}e.browser=null;}
 if(!scriptKoCurrent(e))throw new DOMException('번역 중단','AbortError');
 if(e.translator){
  try{const korean_text=await scriptKoBound(e.translator.translate(text,{signal:e.controller.signal}),e);const t={source_en:text,korean_text,engine:'browser'};
   if(!K.validTranslation(t,text)||korean_text.length>2000)throw Error('문장 전체의 한국어 뜻을 확인하지 못했습니다.');return t;
  }catch(error){if(e.controller.signal.aborted)throw error;}
 }
 if(!e.local)e.local=scriptKoBound(refreshLocalAI(e.controller.signal),e);
 const local=await e.local;if(!scriptKoCurrent(e))throw new DOMException('번역 중단','AbortError');
 if(!local.ready){const message=e.translator?'이 문장의 한국어 뜻을 확인하지 못했습니다. 「한국어 다시 준비」를 눌러 주세요.':'한국어 번역을 연결하지 못했습니다. Chrome의 번역 기능 또는 아래 무료 AI를 준비한 뒤 「한국어 다시 준비」를 눌러 주세요.';if(!e.translator)e.unavailable=message;throw Error(message);}
 const id='script_sentence';
 const response=await scriptKoBound(fetch('/local-ai/translate',{method:'POST',headers:{'Content-Type':'application/json','X-Local-Token':config.youtube_token||''},body:JSON.stringify({cards:[{id,sentence_en:text}]}),signal:e.controller.signal}),e);
 const result=await scriptKoBound(response.json(),e);if(!response.ok)throw Error(result.detail||'한국어 번역을 완료하지 못했습니다.');
 const t=result.translations?.[0];
 if(result.engine!=='local_ai'||!Array.isArray(result.translations)||result.translations.length!==1||t.card_id!==id||!K.validTranslation(t,text)||t.korean_text.length>2000)throw Error('현재 문장과 일치하는 한국어 뜻을 확인하지 못했습니다.');
 return t;
}
async function runScriptKorean(e){
 if(e.running)return;e.running=true;
 try{
  while(e.queue.length&&scriptKoCurrent(e)){
   const request=e.queue.shift();
   try{
    let ko=scriptKorean({text:request.text});
    if(!ko){const t=await translateScriptText(e,request.text);if(!scriptKoCurrent(e))throw new DOMException('번역 중단','AbortError');
     state.transcriptTranslations=K.cacheTranscriptMeaning(state.transcriptTranslations,t);
     // Share the exact source translation with any matching learning cards.
     for(const c of state.customCards)if(c.media.video_id===ytVideo?.id&&K.target(c)===request.text&&!K.ko(c,state.translations[c.id]))state.translations[c.id]={source_en:t.source_en,korean_text:t.korean_text,engine:t.engine};
     saveState();ko=t.korean_text;refreshKoreanMeanings();
    }
    scriptKoErrors.delete(request.text);renderScriptMeaning();request.resolve(ko);
   }catch(error){
    const message=e.timeout?'한국어 번역 대기가 길어 중단했습니다. 「한국어 다시 준비」를 눌러 주세요.':error.message;
    if(scriptKoEngine===e&&e.version===scriptVersion&&(error.name!=='AbortError'||e.timeout))scriptKoErrors.set(request.text,message);
    request.reject(Error(message));
   }finally{e.requests.delete(request.text);}
  }
 }finally{
  e.running=false;
  if(e.controller.signal.aborted){for(const request of e.requests.values())request.reject(Error(e.timeout?'한국어 번역 시간이 초과됐습니다. 다시 준비해 주세요.':'번역을 중단했습니다.'));e.requests.clear();e.queue=[];}
 }
}
function prefetchScriptKorean(s){
 if(!scriptValid(s))return;
 for(let i=s.index+1;i<=Math.min(s.to,s.index+5);i++)requestScriptKorean(scriptRows[i],false).catch(()=>{});
}
function renderScriptMeaning(){
 if(!window.document)return;
 const s=scriptSession,row=s&&scriptRows[s.index],el=$('ytScriptNowKorean');if(!el)return;
 const ko=row?scriptKorean(row):'',error=row?scriptKoErrors.get(row.text):'';
 const stopped=!!s&&['stopped','waiting_voice','error'].includes(s.phase);
 el.classList.remove('hidden');el.textContent=ko||(!row?'':error?'한국어 뜻을 준비하지 못했습니다. 「한국어 다시 준비」를 눌러 주세요.':stopped?'재생을 시작하면 이 문장의 한국어 뜻도 준비합니다.':'한국어 뜻을 준비하고 있습니다…');
 el.dataset.translation=ko?'ready':error?'error':stopped?'paused':'waiting';el.setAttribute('aria-busy',String(!!row&&!ko&&!error&&!stopped));
 $('ytScriptKoRetry').classList.toggle('hidden',!row||!!ko||!error);$('ytScriptKoRetry').disabled=busy||recording();
}
function retryScriptKorean(){
 const s=scriptSession,row=s&&scriptRows[s.index];if(!row||busy||recording())return;
 const resume=scriptActive(s)&&s.phase!=='paused';s.segment++;cancelScriptKorean();scriptKoErrors.clear();
 if(resume)speakScriptSentence(s);
 else{if(s.phase==='paused')s.resumePhase='restart';renderScriptMeaning();requestScriptKorean(row).then(renderScriptMeaning,()=>{renderScriptMeaning();});}
}

function scriptBounds(){
 const from=Number($('ytScriptFrom').value),to=Number($('ytScriptTo').value);
 if(!Number.isInteger(from)||!Number.isInteger(to)||from<0||to<from||to>=scriptRows.length)throw Error('반복할 시작·끝 문장을 확인하세요.');
 return {from,to};
}
function renderScriptTransport(){
 const s=scriptSession,active=scriptActive(s),paused=s?.phase==='paused',playable=active&&s.phase!=='waiting_voice',blocked=recording()||busy;
 $('ytScriptPause').disabled=blocked||!playable||s.phase==='translation_error';$('ytScriptPause').textContent=paused?'▶ 이어 듣기':'Ⅱ 일시정지';
 $('ytScriptStop').disabled=!active;$('ytScriptPrev').disabled=blocked||!playable||s.index<=s.from;$('ytScriptNext').disabled=blocked||!playable||s.index>=s.to;
 for(const id of ['ytScriptPlayAll','ytScriptPlayRange'])$(id).disabled=blocked||!scriptRows.length;
 for(const id of ['ytScriptFrom','ytScriptTo','ytScriptRepeat','ytScriptGap'])$(id).disabled=blocked||!scriptRows.length;
 document.querySelectorAll('.script-play,.script-loop,.script-from,.script-to').forEach(el=>el.disabled=blocked);
 $('ytScriptLocate').disabled=!s;
 $('ytScriptProgress').max=Math.max(1,scriptRows.length);$('ytScriptProgress').value=s?s.index+1:0;
 $('ytScriptPosition').textContent=s?`${s.index+1} / ${scriptRows.length}문장${s.mode==='range'?' · '+s.cycle+' / '+(s.repeat===0?'∞':s.repeat)+'회':''}`:'재생 대기';
 $('ytScriptNow').textContent=s?scriptRows[s.index]?.text||'':'';
 $('ytScriptNowSource').textContent=s&&scriptMaterial?scriptRowSource(scriptRows[s.index]):'';
 renderScriptMeaning();
 $('ytScriptNowBox').classList.toggle('hidden',!s);
 document.querySelectorAll('.script-row').forEach(row=>{const current=!!s&&Number(row.dataset.index)===s.index;row.classList.toggle('is-current',current);if(current)row.setAttribute('aria-current','true');else row.removeAttribute('aria-current');});
}
function renderScriptRange(){
 if(!scriptRows.length){$('ytScriptRangeNote').textContent='대본을 불러오면 원하는 문장을 선택할 수 있습니다.';return;}
 try{const {from,to}=scriptBounds();$('ytScriptRangeNote').textContent=from===to?`${from+1}번 문장 하나를 반복합니다.`:`${from+1}번부터 ${to+1}번까지 ${to-from+1}개 문장을 순서대로 반복합니다.`;
 document.querySelectorAll('.script-row').forEach(row=>row.classList.toggle('in-range',Number(row.dataset.index)>=from&&Number(row.dataset.index)<=to));
 }catch(e){$('ytScriptRangeNote').textContent=e.message;}
}
function renderScriptList(){
 const box=$('ytScriptList');box.replaceChildren();const end=Math.min(scriptRows.length,scriptPage+SCRIPT_PAGE_SIZE);
 for(let index=scriptPage;index<end;index++){
  const row=scriptRows[index],li=document.createElement('div');li.className='script-row';li.dataset.index=index;
  li.innerHTML=`<div class="script-row-heading"><b>${index+1}</b><span class="tiny">${row.start===null?'시간 없음':Y.stamp(row.start)}</span></div><p class="script-text" lang="en">${esc(row.text)}</p><div class="task-actions"><button class="btn small script-play" data-index="${index}">▷ 이 문장 듣기</button><button class="btn small script-loop" data-index="${index}">↻ 이 문장 반복</button><button class="btn small script-from" data-index="${index}">구간 시작</button><button class="btn small script-to" data-index="${index}">구간 끝</button></div>`;
  li.querySelector('.script-play').onclick=()=>startTranscriptPlayback({mode:'single',from:index,to:index});
  if(scriptMaterial){li.querySelector('.script-row-heading .tiny').textContent=scriptRowSource(row);const ko=document.createElement('p');ko.className='material-meaning';ko.lang='ko';ko.textContent=row.korean_text;li.querySelector('.script-text').after(ko);}
  li.querySelector('.script-loop').onclick=()=>{selectScriptRange(index,index);startTranscriptPlayback({mode:'range',from:index,to:index});};
  li.querySelector('.script-from').onclick=()=>selectScriptRange(index,Math.max(index,Number($('ytScriptTo').value)));
  li.querySelector('.script-to').onclick=()=>selectScriptRange(Math.min(index,Number($('ytScriptFrom').value)),index);
  box.append(li);
 }
 $('ytScriptPageLabel').textContent=scriptRows.length?`${scriptPage+1}–${end} / ${scriptRows.length}문장`:'대본 없음';
 $('ytScriptPagePrev').disabled=scriptPage===0;$('ytScriptPageNext').disabled=end>=scriptRows.length;
 renderScriptRange();renderScriptTransport();
 if($('ytScriptDetails').open){const ids=new Set();scriptRows.slice(scriptPage,end).forEach(row=>scriptCardIds(row).forEach(id=>ids.add(id)));if(ids.size)expose([...ids]);}
}
function renderTranscriptPlayer(){
 $('ytScriptSummary').textContent=scriptRows.length?`${scriptMaterial?scriptMaterial.short_title+' PDF 전체':'불러온 대본 전체'} · ${scriptRows.length}문장`:'자막을 불러오면 전체 재생과 구간 반복을 사용할 수 있습니다.';
 for(const id of ['ytScriptFrom','ytScriptTo']){$(id).innerHTML=scriptRows.map((row,i)=>`<option value="${i}">${i+1}. ${esc(row.text.slice(0,75))}</option>`).join('');$(id).disabled=!scriptRows.length;}
 if(scriptRows.length){$('ytScriptFrom').value='0';$('ytScriptTo').value='0';}
 $('ytScriptDetails').classList.toggle('hidden',!scriptRows.length);
 renderScriptList();scriptMessage(scriptRows.length?'대본 전체 재생 또는 원하는 문장의 구간 반복을 누르세요.':'먼저 영어 자막을 불러오세요.');
}
function selectScriptRange(from,to){
 if(recording()||busy||!Number.isInteger(from)||!Number.isInteger(to)||from<0||to<from||to>=scriptRows.length)return;
 stopAudio();$('ytScriptFrom').value=String(from);$('ytScriptTo').value=String(to);renderScriptRange();
 scriptMessage('반복 구간을 선택했습니다. 「선택 구간 반복」을 누르세요.');
}
function scriptSettings(mode,from,to){
 if(!scriptRows.length)throw Error('먼저 대본을 불러오세요.');
 if(!['all','range','single'].includes(mode)||!Number.isInteger(from)||!Number.isInteger(to)||from<0||to<from||to>=scriptRows.length)throw Error('시작·끝 문장을 확인하세요.');
 const repeat=mode==='range'?Number($('ytScriptRepeat').value):1,gap=mode==='range'?Number($('ytScriptGap').value)*1000:0;
 if(![0,1,2,3,5,10].includes(repeat)||![0,1000,2000,3000,5000].includes(gap))throw Error('반복 횟수와 간격을 확인하세요.');
 return {mode,from,to,repeat,gap};
}
function startTranscriptPlayback({mode='all',from=0,to=scriptRows.length-1,settings=null}={}){
 if(recording()||busy){scriptMessage('현재 작업이나 녹음을 마친 뒤 재생하세요.',true);return;}
 let selected;try{selected=settings||scriptSettings(mode,from,to);}catch(e){scriptMessage(e.message,true);return;}
 stopAudio();
 const s={...selected,version:scriptVersion,key:scriptKey,index:selected.from,cycle:1,phase:'starting',segment:0,utterance:null,started:false};scriptSession=s;
 const {chosen:voice,needsOnlinePermission}=refreshVoices();
 if(!voice){s.phase=needsOnlinePermission?'waiting_voice':'error';
  if(needsOnlinePermission)pendingSpeech={resume:()=>{if(s.version===scriptVersion&&s.key===scriptKey)startTranscriptPlayback({settings:selected});}};
  scriptMessage(needsOnlinePermission?'대본 재생 대기 · 위에서 「온라인 영어 음성 사용」을 허용해 주세요.':'대본을 읽을 영어 음성을 찾지 못했습니다. 위의 음성 설정을 확인하세요.',true);renderScriptTransport();$('ytAudioControls').scrollIntoView({block:'center',behavior:'smooth'});if(needsOnlinePermission)$('ytAllowOnlineVoice').focus({preventScroll:true});return;
 }
 s.voice=voice;s.rate=Number($('ytSpeechRate').value)||.9;
 if(scriptRows.slice(s.from,s.to+1).some(row=>!scriptKorean(row)))scriptKoCreate();
 speakScriptSentence(s);
}
function scriptFailure(s,message){
 if(scriptSession!==s)return;
 clearScriptTimers();s.segment++;s.phase='error';s.utterance=null;cancelScriptKorean();window.speechSynthesis?.cancel();scriptMessage(message,true);renderScriptTransport();
}
function armScriptStart(s,segment){
 clearTimeout(scriptStartTimer);scriptStartTimer=setTimeout(()=>{if(scriptValid(s)&&s.segment===segment&&s.phase==='starting')scriptFailure(s,'대본 음성이 시작되지 않았습니다. 위의 목소리 새로 읽기와 음성 테스트를 확인한 뒤 다시 재생하세요.');},8000);
}
function speakScriptSentence(s){
 if(!scriptValid(s))return;
 clearScriptTimers();const segment=++s.segment,row=scriptRows[s.index];s.started=false;s.endedWhilePaused=false;s.phase='starting';
 if(!row){scriptFailure(s,'대본이 바뀌었습니다. 다시 재생하세요.');return;}
 if(!scriptKorean(row)){
  s.phase='translating';scriptMessage(`${s.index+1}번 문장의 한국어 뜻을 준비한 뒤 읽습니다…`);renderScriptTransport();
  requestScriptKorean(row).then(()=>{
   if(!scriptValid(s)||s.segment!==segment)return;
   if(s.phase==='paused'){s.resumePhase='restart';renderScriptMeaning();return;}speakScriptSentence(s);
  },error=>{
   if(!scriptValid(s)||s.segment!==segment)return;
   scriptKoErrors.set(row.text,error.message);if(s.phase!=='paused')s.phase='translation_error';else s.resumePhase='restart';scriptMessage(error.message,true);renderScriptTransport();
  });return;
 }
 const u=new SpeechSynthesisUtterance(row.text);s.utterance=u;u.voice=s.voice;u.lang=s.voice.lang;u.rate=s.rate;let ended=false;
 const current=()=>scriptValid(s)&&s.segment===segment&&!ended;
 u.onstart=()=>{if(!current())return;clearTimeout(scriptStartTimer);s.started=true;if(s.phase!=='paused')s.phase='playing';const ids=scriptCardIds(row);if(ids.length)expose(ids);scriptMessage(s.phase==='paused'?'대본 재생을 일시정지했습니다.':`${s.index+1}번 문장을 읽고 있습니다.`);renderScriptTransport();};
 u.onend=()=>{if(!current()||ended)return;ended=true;clearTimeout(scriptStartTimer);s.utterance=null;if(s.phase==='paused'){s.endedWhilePaused=true;return;}advanceScript(s);};
 u.onerror=e=>{if(!current())return;scriptFailure(s,e.error==='network'?'온라인 음성 연결이 끊겼습니다. 인터넷이나 기기 음성을 확인한 뒤 다시 재생하세요.':`대본 재생 오류 (${e.error||'알 수 없음'}). 위의 음성 테스트를 확인한 뒤 다시 시작하세요.`);};
 if($('ytScriptFollow').checked){const page=Math.floor(s.index/SCRIPT_PAGE_SIZE)*SCRIPT_PAGE_SIZE;if(page!==scriptPage){scriptPage=page;renderScriptList();}}
 renderScriptTransport();
 if($('ytScriptFollow').checked&&$('ytScriptDetails').open){const active=$('ytScriptList').querySelector('.is-current');if(active)$('ytScriptList').scrollTop=active.offsetTop-$('ytScriptList').offsetTop;}
 scriptMessage(`${s.index+1}번 문장 재생 준비 중…`);armScriptStart(s,segment);
 try{speechSynthesis.resume?.();speechSynthesis.speak(u);prefetchScriptKorean(s);}catch(e){scriptFailure(s,'음성을 시작하지 못했습니다. 다른 영어 음성을 선택한 뒤 다시 재생하세요.');}
}
function scheduleScriptNext(s,delay){
 s.phase='gap';s.gapUntil=performance.now()+delay;s.remainingGap=delay;
 scriptMessage(delay?`반복 사이 ${Math.round(delay/1000)}초 쉬는 중 · 다음 ${s.next.cycle}회차`:'다음 문장으로 이동합니다.');renderScriptTransport();
 scriptTimer=setTimeout(()=>{if(!scriptValid(s)||s.phase!=='gap')return;s.index=s.next.index;s.cycle=s.next.cycle;s.next=null;speakScriptSentence(s);},delay);
}
function advanceScript(s){
 if(!scriptValid(s))return;
 if(s.index<s.to){s.next={index:s.index+1,cycle:s.cycle};scheduleScriptNext(s,0);}
 else if(s.repeat===0||s.cycle<s.repeat){s.next={index:s.from,cycle:s.cycle+1};scheduleScriptNext(s,s.gap);}
 else{s.phase='done';s.utterance=null;clearScriptTimers();scriptMessage(s.mode==='range'?`선택 구간을 ${s.repeat}회 반복했습니다.`:s.mode==='single'?'선택한 문장 재생을 마쳤습니다.':'대본 전체 재생을 마쳤습니다.');renderScriptTransport();}
}
function pauseScriptPlayback(){
 const s=scriptSession;if(!scriptValid(s)||s.phase==='waiting_voice')return;
 if(s.phase==='paused'){
  if(s.endedWhilePaused){s.phase='playing';advanceScript(s);return;}
  if(s.resumePhase==='gap'){scheduleScriptNext(s,s.remainingGap);return;}
  if(s.resumePhase==='restart'){speakScriptSentence(s);return;}
  s.phase=s.started?'playing':'starting';if(!s.started)armScriptStart(s,s.segment);
  try{speechSynthesis.resume();scriptMessage('대본을 이어서 읽습니다.');renderScriptTransport();}catch(e){scriptFailure(s,'이어 듣기를 시작하지 못했습니다. 재생 버튼으로 다시 시작하세요.');}return;
 }
 const phase=s.phase;clearScriptTimers();s.phase='paused';s.resumePhase=phase==='gap'?'gap':'speech';
 if(phase==='gap')s.remainingGap=Math.max(0,s.gapUntil-performance.now());
 else if(phase==='translating')s.resumePhase='restart';
 else try{if(!speechSynthesis.pause)throw Error();speechSynthesis.pause();}catch(e){s.segment++;speechSynthesis.cancel();s.utterance=null;s.resumePhase='restart';}
 scriptMessage(s.resumePhase==='restart'?'일시정지했습니다. 이어 들으면 현재 문장부터 다시 읽습니다.':'일시정지했습니다. 「이어 듣기」를 누르면 계속합니다.');renderScriptTransport();
}
function stepScript(delta){
 const s=scriptSession;if(!scriptValid(s)||s.phase==='waiting_voice')return;const index=s.index+delta;if(index<s.from||index>s.to)return;
 const paused=s.phase==='paused';clearScriptTimers();s.segment++;speechSynthesis.cancel();s.utterance=null;s.next=null;s.index=index;s.endedWhilePaused=false;
 if(paused){s.resumePhase='restart';scriptMessage(`${index+1}번 문장에서 일시정지 중입니다.`);renderScriptTransport();requestScriptKorean(scriptRows[index]).then(renderScriptMeaning,renderScriptMeaning);}else speakScriptSentence(s);
}
function repeatStudyCard(id){
 if(recording()||busy)return;const c=cards.get(id);if(!c)return;
 const index=c.media?.video_id===ytVideo?.id?scriptRows.findIndex(row=>row.text===c.expression&&(c.source_cue_id?row.id===c.source_cue_id:c.media.start===null||row.start===c.media.start)):-1;
 if(index<0){scriptMessage('이 문장이 들어 있는 대본을 먼저 불러오세요.',true);$('ytTranscriptPlayer').scrollIntoView({block:'center'});return;}
 selectScriptRange(index,index);startTranscriptPlayback({mode:'range',from:index,to:index});$('ytTranscriptPlayer').scrollIntoView({block:'center',behavior:'smooth'});
}
$('ytScriptKoRetry').onclick=retryScriptKorean;
$('ytScriptPlayAll').onclick=()=>startTranscriptPlayback();
$('ytScriptPlayRange').onclick=()=>{try{startTranscriptPlayback({mode:'range',...scriptBounds()});}catch(e){scriptMessage(e.message,true);}};
$('ytScriptPause').onclick=pauseScriptPlayback;$('ytScriptStop').onclick=stopAudio;
$('ytScriptPrev').onclick=()=>stepScript(-1);$('ytScriptNext').onclick=()=>stepScript(1);
$('ytScriptFrom').onchange=()=>selectScriptRange(Number($('ytScriptFrom').value),Math.max(Number($('ytScriptFrom').value),Number($('ytScriptTo').value)));
$('ytScriptTo').onchange=()=>selectScriptRange(Math.min(Number($('ytScriptFrom').value),Number($('ytScriptTo').value)),Number($('ytScriptTo').value));
for(const id of ['ytScriptRepeat','ytScriptGap'])$(id).onchange=()=>{stopAudio();scriptMessage('반복 설정을 바꿨습니다. 「선택 구간 반복」을 누르세요.');};
$('ytScriptPagePrev').onclick=()=>{if(scriptPage>0){$('ytScriptFollow').checked=false;scriptPage=Math.max(0,scriptPage-SCRIPT_PAGE_SIZE);renderScriptList();}};
$('ytScriptPageNext').onclick=()=>{if(scriptPage+SCRIPT_PAGE_SIZE<scriptRows.length){$('ytScriptFollow').checked=false;scriptPage+=SCRIPT_PAGE_SIZE;renderScriptList();}};
$('ytScriptLocate').onclick=()=>{if(scriptSession){scriptPage=Math.floor(scriptSession.index/SCRIPT_PAGE_SIZE)*SCRIPT_PAGE_SIZE;renderScriptList();}};
$('ytScriptDetails').ontoggle=()=>{if($('ytScriptDetails').open)renderScriptList();};
for(const id of ['ytScriptFrom','ytScriptTo'])$(id).addEventListener('focus',()=>{const ids=new Set();scriptRows.forEach(row=>scriptCardIds(row).forEach(id=>ids.add(id)));if(ids.size)expose([...ids]);});
for(const id of ['ytSpeechRate','speechRate'])$(id).addEventListener('change',()=>{if(scriptActive()){stopAudio();scriptMessage('재생 속도를 바꿨습니다. 전체 재생 또는 구간 반복을 다시 누르세요.');}});
window.addEventListener('beforeunload',stopAudio);
window.addEventListener('pagehide',stopAudio);
syncTranscriptPlayer();
