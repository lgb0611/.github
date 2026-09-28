/* Korean-first prompts. Translation is on-device or through the fixed loopback model. */
const K=window.LabKorean;
let koreanJob=null,koDisabled=[],paragraphPicked=new Set(),koreanWarmup=null;
const koreanMeaningStates=new Map();
const hasKorean=c=>!!K.ko(c,state.translations[c.id]);
function refreshKoreanMeanings(){
 for(const article of document.querySelectorAll('.auto-expression-card')){
  const c=cards.get(article.dataset.cardId),el=article.querySelector('.auto-meaning');if(!c||!el)continue;
  const meaning=K.ko(c,state.translations[c.id]),phase=meaning?'ready':koreanMeaningStates.get(c.id)||'waiting';
  el.textContent=meaning||({waiting:'한국어 뜻을 자동으로 준비합니다…',translating:'이 문장의 한국어 뜻을 번역하고 있습니다…',paused:'한국어 번역을 중단했습니다. 완료된 뜻은 유지됩니다.',error:'한국어 자동 번역을 완료하지 못했습니다. 위 번역 연결 안내를 확인하세요.'})[phase];
  el.dataset.translation=phase;el.setAttribute('aria-busy',String(['waiting','translating'].includes(phase)));el.lang='ko';
 }
 const missing=autoLessonCards.filter(c=>!hasKorean(c)),retry=missing.some(c=>['paused','error'].includes(koreanMeaningStates.get(c.id)));
 $('ytPrepareKorean').classList.toggle('hidden',!retry||!!koreanJob);
 $('ytPrepareKorean').textContent=missing.some(c=>koreanMeaningStates.get(c.id)==='error')?'한국어 번역 다시 시도':'남은 한국어 이어 번역';
 $('ytTranslationCount').textContent=autoLessonCards.length?'한국어 뜻 '+(autoLessonCards.length-missing.length)+' / '+autoLessonCards.length+'개 표시됨':'문장을 추출하면 한국어 뜻도 함께 준비합니다.';
 if(typeof renderScriptMeaning==='function')renderScriptMeaning();
}
function setKoreanPhase(selected,phase){for(const c of selected)if(!hasKorean(c))koreanMeaningStates.set(c.id,phase);refreshKoreanMeanings();}
function discardKoreanWarmup(){if(!koreanWarmup)return;const warm=koreanWarmup;koreanWarmup=null;clearTimeout(warm.timer);warm.controller.abort();warm.translator?.destroy?.();}
function primeKoreanTranslation(){
 if(!window.Translator?.create||koreanWarmup||koreanJob||recording()||busy)return;
 const warm={controller:new AbortController(),translator:null,timer:null,promise:null};koreanWarmup=warm;
 // Start under the link/import click, before caption retrieval can consume user activation.
 try{warm.promise=Promise.resolve(window.Translator.create({sourceLanguage:'en',targetLanguage:'ko',signal:warm.controller.signal}));}
 catch(e){warm.promise=Promise.reject(e);}
 warm.promise.then(t=>{warm.translator=t;if(warm.controller.signal.aborted)t.destroy?.();},()=>{});
 warm.timer=setTimeout(()=>{if(koreanWarmup===warm)discardKoreanWarmup();},390000);
}
function autoPrepareKoreanDeck(){
 refreshKoreanMeanings();
 if(!$('youtubeView').classList.contains('hidden')&&autoLessonCards.length&&!busy&&!recording()&&!koreanJob)return prepareKoreanCards(autoLessonCards.map(c=>c.id));
}
function koreanMessage(message,error=false,inParagraph=false){for(const id of ['koStatus','ytKoStatus']){$(id).textContent=message;$(id).className='statusline '+(error?'error':'ok');}if(koreanJob?.kind==='paragraph'||inParagraph){ $('ytParagraphStatus').textContent=message;$('ytParagraphStatus').className='statusline '+(error?'error':'ok');}}
function lockKorean(on){
 if(on){koDisabled=[...document.querySelectorAll('main button,main input,main select,main textarea,.nav')].map(e=>[e,e.disabled]);setBusy(true);koDisabled.forEach(([e])=>e.disabled=true);for(const id of ['koCancel','ytKoCancel','ytParagraphCancel']){$(id).disabled=false;$(id).classList.remove('hidden');}}
 else{setBusy(false);koDisabled.forEach(([e,d])=>e.disabled=d);koDisabled=[];for(const id of ['koCancel','ytKoCancel','ytParagraphCancel'])$(id).classList.add('hidden');youtubeCapability();renderAutoCapability();}
 renderParagraphSelection();
}
function currentKoreanJob(job){return koreanJob===job&&!job.controller.signal.aborted&&!storageBlocked&&job.sources.every(x=>cards.get(x.id)&&K.target(cards.get(x.id))===x.sentence_en)&&(!job.videoId||ytVideo?.id===job.videoId&&$('ytTranscript').value===job.raw);}
function assertKoreanJob(job){if(!currentKoreanJob(job))throw Error('문장이나 영상이 바뀌어 결과를 적용하지 않았습니다. 다시 준비하세요.');}
function cancelKorean(){if(!koreanJob)return;const job=koreanJob;koreanMessage('준비를 중단했습니다. 완료된 한국어와 기존 기록은 남습니다.');setKoreanPhase(job.sources.map(x=>cards.get(x.id)).filter(Boolean),'paused');koreanJob=null;job.controller.abort();job.translator?.destroy?.();lockKorean(false);refreshKoreanMeanings();}
async function boundedKorean(promise,job,ms=390000){
 let timer,listener;const aborted=new Promise((_,reject)=>{listener=()=>reject(new DOMException('중단','AbortError'));job.controller.signal.addEventListener('abort',listener,{once:true});timer=setTimeout(()=>{job.controller.abort();},ms);});
 try{return await Promise.race([promise,aborted]);}finally{clearTimeout(timer);job.controller.signal.removeEventListener('abort',listener);}
}
async function runKoreanJob(selected,operation,{kind='translation'}={}){
 if(recording()||busy||koreanJob||storageBlocked)return null;
 const job={kind,controller:new AbortController(),translator:null,sources:selected.map(c=>({id:c.id,sentence_en:K.target(c)})),videoId:!$('youtubeView').classList.contains('hidden')?ytVideo?.id:null,raw:$('ytTranscript').value};
 koreanJob=job;setKoreanPhase(selected,'waiting');lockKorean(true);
 try{const result=await operation(job);assertKoreanJob(job);return result;}
 catch(e){if(koreanJob===job){setKoreanPhase(selected,'error');koreanMessage((e.name==='AbortError'?'준비 시간이 길어 중단했습니다.':e.message)+' 완료된 한국어는 저장되어 있습니다.',true);}return null;}
 finally{job.translator?.destroy?.();if(koreanJob===job){koreanJob=null;lockKorean(false);refreshKoreanMeanings();renderKoreanPractice();}}
}
async function koreanLocalRequest(path,payload,job){
 const res=await boundedKorean(fetch(path,{method:'POST',headers:{'Content-Type':'application/json','X-Local-Token':config.youtube_token||''},body:JSON.stringify(payload),signal:job.controller.signal}),job);
 const data=await res.json();assertKoreanJob(job);if(!res.ok)throw Error(data.detail||'한국어 준비에 실패했습니다.');return data;
}
function saveKorean(c,text,engine){
 const t={source_en:K.target(c),korean_text:text,engine};if(!K.validTranslation(t,K.target(c))||text.length>2000)throw Error('문장 전체의 한국어 버전을 확인하지 못했습니다.');
 state.translations[c.id]=t;if(!saveState())throw Error('저장 공간이 부족합니다. 현재 기록을 내보낸 뒤 다시 시도하세요.');
 koreanMeaningStates.delete(c.id);refreshKoreanMeanings();
}
async function translateCards(selected,job){
 let missing=selected.filter(c=>!hasKorean(c));if(!missing.length)return;
 let browserError='';
 if(window.Translator?.create){
  try{
   koreanMessage('문장별 한국어를 준비합니다. 처음에는 브라우저가 번역용 언어 파일을 내려받을 수 있습니다.');
   // Call create while the initiating click can still supply user activation.
   const warm=koreanWarmup;koreanWarmup=null;if(warm){clearTimeout(warm.timer);job.controller.signal.addEventListener('abort',()=>warm.controller.abort(),{once:true});}
   const creation=warm?warm.promise:window.Translator.create({sourceLanguage:'en',targetLanguage:'ko',signal:job.controller.signal,monitor:m=>m.addEventListener('downloadprogress',e=>{if(currentKoreanJob(job))koreanMessage('한국어 기능 준비 중 · '+Math.round(e.loaded*100)+'%');})});
   creation.then(t=>{if(!currentKoreanJob(job))t.destroy?.();},()=>{});
   job.translator=await boundedKorean(creation,job);
   assertKoreanJob(job);
   for(let i=0;i<missing.length;i++){
    koreanMessage('한국어 문장 준비 중 · '+(i+1)+' / '+missing.length);
    const c=missing[i];setKoreanPhase([c],'translating');
    try{const text=await boundedKorean(job.translator.translate(K.target(c),{signal:job.controller.signal}),job,120000);assertKoreanJob(job);saveKorean(c,text,'browser');}
    catch(e){if(!currentKoreanJob(job))throw e;browserError='일부 문장의 브라우저 번역을 완료하지 못했습니다. ';setKoreanPhase([c],'error');}
   }
  }catch(e){if(!currentKoreanJob(job))throw e;browserError='브라우저 번역을 준비하지 못했습니다. ';}
 }
 missing=selected.filter(c=>!hasKorean(c));if(!missing.length)return;
 const ai=await refreshLocalAI(job.controller.signal);assertKoreanJob(job);
 if(!ai.ready){$('localAISetup').open=true;throw Error(browserError+'한국어 자동 번역을 연결하지 못했습니다. 지원되는 데스크톱 Chrome에서 실행하고 「한국어 번역 다시 시도」를 눌러 첫 언어 파일을 준비하거나, 아래 무료 AI를 설치·실행해 주세요. 이후에는 뜻을 자동으로 표시합니다.');}
 for(let i=0;i<missing.length;i+=4){
  const batch=missing.slice(i,i+4);setKoreanPhase(batch,'translating');koreanMessage('무료 AI로 한국어 준비 중 · '+i+' / '+missing.length);
  const result=await koreanLocalRequest('/local-ai/translate',{cards:batch.map(c=>({id:c.id,sentence_en:K.target(c)}))},job);
  if(result.engine!=='local_ai'||!Array.isArray(result.translations)||result.translations.length!==batch.length||new Set(result.translations.map(t=>t.card_id)).size!==batch.length)throw Error('일부 문장의 한국어가 빠졌습니다.');
  for(const t of result.translations){const c=batch.find(c=>c.id===t.card_id);if(!c||!K.validTranslation(t,K.target(c)))throw Error('다른 문장의 한국어 결과입니다.');}
  for(const t of result.translations)saveKorean(cards.get(t.card_id),t.korean_text,'local_ai');
 }
}
async function prepareKoreanCards(ids){
 const selected=[...new Set(ids)].map(id=>cards.get(id)).filter(Boolean);
 if(!selected.length)return false;
 if(selected.every(hasKorean)){refreshKoreanMeanings();koreanMessage(selected.length+'개 문장의 한국어 준비 완료 · 한글을 보고 영어로 말해 보세요.');return true;}
 const ok=await runKoreanJob(selected,async job=>{await translateCards(selected,job);return true;});
 if(ok)koreanMessage(selected.length+'개 문장의 한국어를 준비했습니다. 한글을 보고 영어로 말해 보세요.');
 return !!ok;
}
function renderKoreanPractice(){
 if(!exercise)return;
 const single=activeIds().length===1&&(mode==='single'||exercise.id.startsWith('single_'));
 const missing=single&&!hasKorean(cards.get(activeIds()[0]));
 $('prepareCurrentKorean').classList.toggle('hidden',!missing);
 $('koMissing').classList.toggle('hidden',!missing);
 if(single){$('taskText').textContent=missing?'이 문장의 한국어를 준비하면 여기에 문제를 보여 드립니다.':K.ko(cards.get(activeIds()[0]),state.translations[activeIds()[0]]);$('taskInstruction').textContent=missing?'한국어 준비를 누르면 자동 번역합니다. 문장을 직접 입력할 필요는 없습니다.':'위 한국어 문장의 내용을 영어 한 문장으로 말하세요. 영어 답안과 음성은 필요할 때만 확인하세요.';}
 $('taskText').classList.remove('hidden');
 $('nextParagraph').classList.toggle('hidden',!exercise.paragraph_mode);
}
async function koreanSingle(id){
 if(recording()||busy||!cards.has(id)||!mayLeave())return;
 if(!await prepareKoreanCards([id]))return;
 resetResponse();loadExercise('single_'+id,{newStage:'recall'});$('taskText').scrollIntoView({block:'center',behavior:'smooth'});
}
async function koreanSequence(ids){
 if(recording()||busy||!ids.length||!mayLeave())return;
 if(!await prepareKoreanCards(ids))return;
 resetResponse();state.session={ids:[...new Set(ids)],index:0,completed:[],skipped:[],at:Date.now()};saveState();sessionCard();renderSession();status('한국어 문장이 처음부터 보입니다. 영어로 말한 뒤 자가 점검하고 다음 문장으로 이어가세요.');
}
function paragraphPool(){
 if(!$('youtubeView').classList.contains('hidden')&&autoLessonCards.length)return autoLessonCards;
 const current=cards.get(activeIds()[0]);if(current?.media)return state.customCards.filter(c=>c.media.video_id===current.media.video_id&&c.chunk_kind);
 return library.cards.filter(c=>c.lesson_id===current?.lesson_id&&c.cue_ko);
}
function defaultParagraphCards(next=false){
 const pool=paragraphPool();if(!pool.length)return [];
 let start=0;if(next){const index=pool.findIndex(c=>c.id===activeIds().at(-1));start=(index+1)%pool.length;}
 const ordered=next?[...pool.slice(start),...pool.slice(0,start)]:[...pool.filter(c=>state.cards[c.id]),...pool.filter(c=>!state.cards[c.id])];
 return ordered.slice(0,3).map(c=>c.id);
}
function renderParagraphSelection(){
 const allowed=new Set(autoLessonCards.map(c=>c.id));paragraphPicked=new Set([...paragraphPicked].filter(id=>allowed.has(id)));
 const count=paragraphPicked.size,blocked=busy||recording(),preparing=koreanJob?.kind==='paragraph';
 $('ytParagraph').classList.toggle('hidden',autoLessonCards.length<2);
 $('ytParagraphSelection').classList.toggle('hidden',autoLessonCards.length<2);
 $('ytParagraphSelection').textContent=count?count+'개 선택됨 · 화면 하단의 문단 연습 버튼을 누르세요.':'카드의 「문단에 활용」을 체크하세요. 선택 없이 시작하면 학습한 문장부터 최대 3개를 고릅니다.';
 const action=count===1?'한 문장 더 선택하세요':count?'선택한 '+count+'문장으로 문단 연습':'여러 문장으로 한글 문단 연습';
 $('ytParagraph').textContent=preparing?'한글 문단 준비 중…':action;
 $('ytParagraph').disabled=blocked||count===1;
 $('ytParagraphDock').classList.toggle('hidden',count===0);
 $('youtubeView').classList.toggle('has-paragraph-selection',count>0);
 $('ytParagraphCount').textContent=count+'개 문장 선택됨';
 $('ytParagraphHint').textContent=count===1?'한 문장만 더 고르면 한글 문단으로 연습할 수 있습니다.':'선택을 마쳤으면 오른쪽 버튼을 누르세요. 이 문장들을 활용할 한글 문단을 제시합니다.';
 $('ytParagraphStart').textContent=preparing?'한글 문단 준비 중…':action;
 $('ytParagraphStart').disabled=blocked||count<2;
 $('ytParagraphClear').disabled=blocked;
 $('ytParagraphChips').replaceChildren();
 for(const id of paragraphPicked){const c=cards.get(id),number=autoLessonCards.findIndex(c=>c.id===id)+1,b=document.createElement('button');b.className='btn small paragraph-chip';b.textContent='문장 '+String(number).padStart(2,'0')+' ×';b.title=c.expression;b.setAttribute('aria-label','문장 '+number+' 선택 해제');b.disabled=blocked;b.onclick=()=>{if(recording()||busy)return;paragraphPicked.delete(id);$('ytParagraphStatus').textContent='';renderParagraphSelection();};$('ytParagraphChips').append(b);}
 document.querySelectorAll('.paragraph-pick').forEach(b=>{b.checked=paragraphPicked.has(b.dataset.id);const card=b.closest('.auto-expression-card');card.classList.toggle('is-selected',b.checked);card.querySelector('.paragraph-pick-text').textContent=b.checked?'문단에 선택됨':'문단에 활용';b.onchange=()=>{if(recording()||busy){b.checked=paragraphPicked.has(b.dataset.id);return;}if(b.checked){if(paragraphPicked.size>=5){b.checked=false;$('ytParagraphStatus').textContent='문단 하나에는 최대 5문장을 사용합니다. 선택한 문장을 해제한 뒤 다른 문장을 고르세요.';$('ytParagraphStatus').className='statusline error';return;}paragraphPicked.add(b.dataset.id);}else paragraphPicked.delete(b.dataset.id);$('ytParagraphStatus').textContent='';renderParagraphSelection();};});
}
async function createParagraphPractice(ids){
 if(recording()||busy||!mayLeave())return;
 const selected=[...new Set(ids)].map(id=>cards.get(id)).filter(Boolean);if(selected.length<2||selected.length>5){koreanMessage('문단에 활용할 문장을 2~5개 선택하세요.',true);return;}
 let fallback='';
 let result;
 if(selected.every(c=>c.material_id)){
  // Bundled translations can be joined synchronously even if browser storage is unavailable.
  const source=selected.map(c=>({id:c.id,sentence_en:K.target(c),korean_text:K.ko(c,state.translations[c.id])}));
  result={paragraph:K.sourceParagraph(source),engine:'source',source};
 }else result=await runKoreanJob(selected,async job=>{
  koreanMessage('선택한 '+selected.length+'개 문장으로 한글 문단을 준비합니다.');
  await translateCards(selected,job);assertKoreanJob(job);
  const source=selected.map(c=>({id:c.id,sentence_en:K.target(c),korean_text:K.ko(c,state.translations[c.id])}));
  const ai=await refreshLocalAI(job.controller.signal);assertKoreanJob(job);let paragraph,engine;
  if(ai.ready){
   try{koreanMessage('학습한 '+selected.length+'개 문장을 활용하는 한글 문단을 만들고 있습니다.');const data=await koreanLocalRequest('/local-ai/paragraph',{cards:source},job);if(data.engine!=='local_ai'||!K.validateParagraph(data.paragraph,source))throw Error('선택한 문장을 활용한 문단인지 확인하지 못했습니다.');paragraph=data.paragraph;engine='local_ai';}
   catch(e){if(!currentKoreanJob(job))throw e;fallback=e.message;}
  }
  if(!paragraph){paragraph=K.sourceParagraph(source);engine='source';}
  if(!K.validateParagraph(paragraph,source,{source:engine==='source'}))throw Error('문단의 한글·영어 대응을 확인하지 못했습니다.');
  return {paragraph,engine,source};
 },{kind:'paragraph'});
 if(!result)return;
 const {paragraph:p,engine,source}=result;
 const existing=state.customExercises.find(e=>e.paragraph_mode===engine&&e.card_ids.join('|')===selected.map(c=>c.id).join('|')&&e.task_ko===p.task_ko&&e.sample_en===p.sample_en);
 const e=existing||{...p,id:'paragraph_'+Date.now().toString(36)+'_'+Math.random().toString(36).slice(2,8),lesson_id:selected.every(c=>c.lesson_id===selected[0].lesson_id)?selected[0].lesson_id:'custom',card_ids:selected.map(c=>c.id),paragraph_mode:engine,origin:engine==='local_ai'?'학습 문장 활용 · 무료 AI 새 상황 문단':'학습 문장 이어 말하기 · 원문 내용 연결'};
 if(!C.validateExercise(e,cards)||state.customExercises.length>=2000&&!existing){koreanMessage('문단을 저장할 수 없습니다. 기존 기록을 내보내 주세요.',true,true);return;}
 if(!existing)state.customExercises.push(e);
 resetResponse();state.session=null;saveState();loadExercise(e.id,{newStage:'recall'});
 koreanMessage('한글 문단 준비 완료 · '+source.length+'개 학습 문장을 활용해 말해 보세요.',false,true);
 status(engine==='local_ai'?'한글 문단을 보고 학습한 '+source.length+'개 문장을 활용해 영어로 말하세요.':(fallback?'새 상황 생성을 완료하지 못해 ':'')+'학습 문장들의 한국어를 한 문단으로 연결했습니다. 같은 순서로 이어 말하세요. 무료 AI가 준비되면 새로운 상황의 문단도 만듭니다.');
 $('taskText').scrollIntoView({block:'center',behavior:'smooth'});
}
$('ytPrepareKorean').onclick=()=>prepareKoreanCards(autoLessonCards.map(c=>c.id));
$('prepareCurrentKorean').onclick=async()=>{if(recording()||busy)return;const id=activeIds()[0];if(await prepareKoreanCards([id])){exercise=resolveExercise(exercise.id);renderTask();saveDraft();}};
$('ytParagraph').onclick=()=>createParagraphPractice(paragraphPicked.size?[...paragraphPicked]:defaultParagraphCards());
$('ytParagraphStart').onclick=()=>createParagraphPractice([...paragraphPicked]);
$('ytParagraphClear').onclick=()=>{if(recording()||busy)return;paragraphPicked.clear();$('ytParagraphStatus').textContent='';renderParagraphSelection();};
$('combinedPractice').onclick=()=>createParagraphPractice(activeIds().length>1?activeIds():defaultParagraphCards());
$('nextParagraph').onclick=()=>createParagraphPractice(defaultParagraphCards(true));
$('koCancel').onclick=$('ytKoCancel').onclick=$('ytParagraphCancel').onclick=cancelKorean;
$('koOpenSetup').onclick=()=>{if(recording()||busy)return;showView('youtube');$('ytWorkspace').classList.remove('hidden');$('localAISetup').open=true;$('localAISetup').scrollIntoView({block:'center'});};
$('ytAutoPractice').onclick=()=>koreanSequence(autoLessonCards.map(c=>c.id));
$('practicePicked').onclick=()=>picked.size>1?createParagraphPractice([...picked]):picked.size?koreanSingle([...picked][0]):status('표현 서재에서 문장을 선택하세요.',true);
$('ytSpeechStop').onclick=()=>{stopAudio();$('ytSpeechStatus').textContent='음성 재생을 멈췄습니다.';};
$('ytVoiceSelect').onchange=()=>{state.voice.uri=$('ytVoiceSelect').value;$('voiceSelect').value=state.voice.uri;stopAudio();refreshVoices();saveState();};
$('ytSpeechRate').onchange=()=>{$('speechRate').value=$('ytSpeechRate').value;};
$('speechRate').onchange=()=>{$('ytSpeechRate').value=$('speechRate').value;};
$('ytVoiceRefresh').onclick=refreshVoices;
$('ytAllowOnlineVoice').onchange=()=>setOnlineVoiceAllowed($('ytAllowOnlineVoice').checked);
$('ytTestVoice').onclick=()=>speak('I can listen first, then say it in my own words.',{practice:false,onStatus:(message,error)=>{$('ytSpeechStatus').textContent=message;$('ytSpeechStatus').className='tiny '+(error?'error':'');}});
window.addEventListener('beforeunload',()=>{discardKoreanWarmup();koreanJob?.controller.abort();koreanJob?.translator?.destroy?.();});
renderKoreanPractice();renderParagraphSelection();refreshVoices();refreshKoreanMeanings();
