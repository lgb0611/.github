/* Automatic lessons: local model when ready, clearly labelled authored fallback. */
const AutoLessons=window.LabAutoLessons;
let autoLessonCards=[],autoJob=null,autoDisabled=[],aiPoll=null,aiPollCount=0;
let localAIState={running:false,ready:false,model:'qwen3.5:4b',setup:{}};
const autoMessage=(message,error=false)=>{$('ytAutoStatus').textContent=message;$('ytAutoStatus').className='statusline '+(error?'error':'ok');};

function renderAutoCapability(){
 const supported=!!config.free_only&&!!config.local_ai&&location.protocol!=='file:';
 $('ytAISetup').disabled=!supported||busy||!!localAIState.setup?.running||localAIState.ready;
 $('ytAIRefresh').disabled=!supported||busy;
 if(!supported)$('ytAIStatus').textContent='기본 자동 추출을 바로 쓸 수 있습니다. 문장 전체 뜻·새 상황 AI를 쓰려면 새 ZIP의 start_youtube_windows.bat으로 실행하세요.';
}
function renderLocalAI(){
 const s=localAIState,setup=s.setup||{};
 $('ytAIStatus').textContent=setup.running?'무료 AI 모델 준비 중 · '+(setup.message||'다운로드 중'):s.ready?'무료 AI 준비 완료 · '+s.model+' · 이 PC에서 문맥 자동 추출':setup.error?setup.error:s.running?'Ollama 실행 확인 · 무료 AI 준비를 누르면 모델을 내려받습니다.':'Ollama를 한 번 설치·실행하고 상태 확인 → 무료 AI 준비를 누르세요. 지금도 문장 추출·듣기·말하기를 바로 쓸 수 있습니다.';
 $('ytAIProgress').classList.toggle('hidden',!setup.running);
 if(setup.total>0)$('ytAIProgress').value=Math.min(100,100*setup.completed/setup.total);else $('ytAIProgress').removeAttribute('value');
 renderAutoCapability();
}
async function refreshLocalAI(signal){
 if(!config.free_only||!config.local_ai||location.protocol==='file:'){localAIState={running:false,ready:false,setup:{}};renderAutoCapability();return localAIState;}
 try{const r=await fetch('/local-ai/status',{cache:'no-store',signal});if(!r.ok)throw Error();const s=await r.json();if(typeof s.ready!=='boolean'||typeof s.running!=='boolean')throw Error();localAIState=s;renderLocalAI();return s;}
 catch(e){if(e.name==='AbortError')throw e;localAIState={running:false,ready:false,setup:{}};renderLocalAI();return localAIState;}
}
async function pollLocalAI(){
 clearTimeout(aiPoll);await refreshLocalAI();
 if(localAIState.ready&&typeof autoPrepareKoreanDeck==='function')await autoPrepareKoreanDeck();
 if(localAIState.setup?.running&&aiPollCount++<1800)aiPoll=setTimeout(pollLocalAI,2000);
}
async function prepareLocalAI(){
 if(recording()||busy||!config.free_only||!config.local_ai)return;
 $('ytAISetup').disabled=true;$('ytAIStatus').textContent='무료 AI 준비 요청 중입니다. 처음에는 모델을 내려받습니다.';
 try{const r=await fetch('/local-ai/setup',{method:'POST',headers:{'Content-Type':'application/json','X-Local-Token':config.youtube_token||''},body:'{}'});const s=await r.json();if(!r.ok)throw Error(s.detail||'모델 준비 요청이 실패했습니다.');localAIState=s;renderLocalAI();aiPollCount=0;await pollLocalAI();}
 catch(e){$('ytAIStatus').textContent=e.message;renderAutoCapability();}
}
function resetAutomaticResults(){autoLessonCards=[];autoSourceCues=[];autoVisible=10;$('ytAutoExtract').textContent='전체 문장 추출';$('ytAutoResults').replaceChildren();for(const id of ['ytAutoPractice','ytEnrich','ytShowMore','ytParagraph','ytParagraphSelection','ytParagraphDock'])$(id).classList.add('hidden');autoMessage('');}
function lockAutomatic(value){
 if(value){
  autoDisabled=[...document.querySelectorAll('#youtubeView button,#youtubeView input,#youtubeView textarea,#youtubeView select,.nav')].map(el=>[el,el.disabled]);
  setBusy(true);autoDisabled.forEach(([el])=>el.disabled=true);$('ytAutoCancel').disabled=false;$('ytAutoCancel').classList.remove('hidden');
 }else{
  setBusy(false);autoDisabled.forEach(([el,was])=>el.disabled=was);autoDisabled=[];$('ytAutoCancel').classList.add('hidden');youtubeCapability();renderAutoCapability();
 }
}
function cancelAutomatic(){
 if(!autoJob)return;const job=autoJob;autoJob=null;clearTimeout(job.timer);job.controller.abort();lockAutomatic(false);renderAutomaticCards();
 autoMessage('추출 대기를 중단했습니다. 입력과 기존 학습 기록은 유지됩니다. PC의 AI 처리가 끝나기까지 잠시 걸릴 수 있습니다.');
}
let autoSourceCues=[],autoVisible=10;
function markVisibleChunks(){if($('youtubeView').classList.contains('hidden'))return;expose([...document.querySelectorAll('.auto-expression-card')].filter(a=>!a.querySelector('.chunk-answer').classList.contains('hidden')).map(a=>a.dataset.cardId));}
function renderAutomaticCards(){
 const list=autoLessonCards,shown=list.slice(0,autoVisible);
 $('ytAutoExtract').textContent=list.length?'전체 문장 다시 추출':'전체 문장 추출';
 $('ytAutoResults').innerHTML='<p class="tiny">'+'전체 '+list.length+'개 문장 추출 완료 · 현재 '+shown.length+'개 표시 · 각 문장으로 따라 말하기 → 가리고 재현 → 내 이야기로 바꿔 말하기. 시간은 자막 구간 기준입니다.</p><div class="auto-card-grid">'+shown.map((c,i)=>`<article class="auto-expression-card" data-card-id="${esc(c.id)}"><label class="paragraph-pick-label"><input class="paragraph-pick" type="checkbox" data-id="${esc(c.id)}"> <span class="paragraph-pick-text">문단에 활용</span></label><span class="eyebrow">CHUNK ${String(i+1).padStart(2,'0')} · ${c.chunk_kind==='speech'?'긴 발화 청크':'문장 청크'} · ${Y.stamp(c.media.start)}</span><div class="chunk-answer"><h3>${esc(c.expression)}</h3></div><p class="chunk-hidden hidden">문장을 가렸습니다. 들었던 내용을 한 문장으로 말해 보세요.</p><p class="auto-meaning">${esc(window.LabKorean.ko(c,state.translations[c.id])||'한국어 뜻을 자동으로 준비합니다…')}</p><details class="auto-help"><summary class="tiny">표현 도움말</summary><p class="tiny">${esc(c.note)}</p></details><div class="task-actions"><button class="btn primary small auto-tts" data-id="${esc(c.id)}">▷ 음성 듣기 · 이 문장만</button><button class="btn small auto-loop" data-id="${esc(c.id)}">↻ 이 문장 반복</button><button class="btn small auto-hide" aria-pressed="false">문장 가리기</button><button class="btn small auto-practice" data-id="${esc(c.id)}">녹음하고 연습</button></div><details class="original-source"><summary>원본 자료 확인 · 선택</summary><div class="task-actions source-options"><a class="auto-source" data-id="${esc(c.id)}" href="${esc(c.source_url)}" target="_blank" rel="noopener">YouTube 원본 ${c.media.start===null?'영상':Y.stamp(c.media.start)} ↗</a><button class="btn small auto-file" data-id="${esc(c.id)}">내 파일로 구간 듣기</button>${c.meaning_source==='local_ai'?`<button class="btn small auto-transfer" data-id="${esc(c.id)}">AI 새 상황으로 말하기</button>`:''}</div></details></article>`).join('')+'</div>';
 document.querySelectorAll('.auto-tts').forEach(b=>b.onclick=()=>{const c=cards.get(b.dataset.id);if(c)speak(c.expression,{ids:[c.id],single:true,onStatus:(message,error)=>{$('ytSpeechStatus').textContent=message;$('ytSpeechStatus').className='tiny '+(error?'error':'');}});});
 document.querySelectorAll('.auto-hide').forEach(b=>b.onclick=()=>{if(recording()||busy)return;const a=b.closest('article'),hide=b.getAttribute('aria-pressed')!=='true';a.querySelector('.chunk-answer').classList.toggle('hidden',hide);a.querySelector('.chunk-hidden').classList.toggle('hidden',!hide);b.setAttribute('aria-pressed',String(hide));b.textContent=hide?'문장 다시 보기':'문장 가리기';if(!hide)expose([a.dataset.cardId]);});
 document.querySelectorAll('.auto-loop').forEach(b=>b.onclick=()=>{if(typeof repeatStudyCard==='function')repeatStudyCard(b.dataset.id);});
 document.querySelectorAll('.auto-practice').forEach(b=>b.onclick=()=>typeof koreanSingle==='function'?koreanSingle(b.dataset.id):practiceCard(b.dataset.id));
 document.querySelectorAll('.auto-source').forEach(b=>b.onclick=e=>{if(recording()||busy)e.preventDefault();else{stopAudio();expose([b.dataset.id]);}});
 document.querySelectorAll('.auto-file').forEach(b=>b.onclick=()=>{const c=cards.get(b.dataset.id);if(c)mountYoutube($('ytPlayer'),c.media.video_id,c.media.start,c.media.end);});
 document.querySelectorAll('.auto-transfer').forEach(b=>b.onclick=()=>{const e=[...state.customExercises].reverse().find(e=>e.card_ids.length===1&&e.card_ids[0]===b.dataset.id&&e.origin?.startsWith('로컬 AI'));if(e)loadExercise(e.id,{newStage:'transfer'});});
 for(const id of ['ytAutoPractice','ytEnrich'])$(id).classList.toggle('hidden',!list.length);
 $('ytAutoPractice').textContent=list.length+'개 · 한글 보고 한 문장씩 말하기 →';
 $('ytShowMore').classList.toggle('hidden',shown.length>=list.length);
 $('ytShowMore').textContent='추출된 문장 더 보기 ('+shown.length+' / 전체 '+list.length+'개 표시)';
 markVisibleChunks();
 if(typeof renderParagraphSelection==='function')renderParagraphSelection();
 if(typeof refreshKoreanMeanings==='function')refreshKoreanMeanings();
}
function importAutomatic(result,snapshot,engine){
 // Validate every item before saving the whole deck once. The JSON import's
 // 100-item bound is for external input, not an extraction limit.
 const items=[],byId=new Map(snapshot.cues.map(c=>[c.id,c]));
 for(let i=0;i<result.items.length;i+=100)items.push(...Y.importItems(JSON.stringify({...result,items:result.items.slice(i,i+100)}),snapshot.video,snapshot.cues));
 items.forEach((item,i)=>{
  const cue=byId.get(result.items[i].cue_id);
  if(!cue||cue.text!==item.card.expression)throw Error('문장 전체가 원문과 일치하지 않습니다.');
  Object.assign(item.card,{source_cue_id:cue.id,chunk_kind:cue.chunk_kind||'speech',meaning_source:engine==='local_ai'?'local_ai':'none',
   practice_task_ko:engine==='local_ai'?item.card.meaning_ko:item.task,
   practice_sample_en:item.card.expression,practice_origin:'자막 원문 · 문장 전체 회상'});
  item.origin=engine==='local_ai'?'로컬 AI가 만든 새 상황 · 내용 확인 필요':'자막 원문 · 문장 전체 회상';
  if(engine!=='local_ai'){item.task='';item.sample='';}
  if(!Y.validCard(item.card))throw Error('문장 카드 형식을 확인하지 못했습니다.');
 });
 return addYoutubeCards(items,{exposeAll:false});
}
// When sentence boundaries improve, cut pieces from an older extraction are no longer in the deck.
// Remove only pieces that no record points to; anything reviewed, practised or queued is kept.
function pruneReplacedChunks(videoId,saved){
 const keep=new Set(saved.map(c=>c.id)),used=new Set(Object.keys(state.cards));
 for(const list of [state.session?.ids||[],...state.attempts.map(a=>a.card_ids),...state.customExercises.map(e=>e.card_ids),state.bridge?.attempt.card_ids||[]])list.forEach(id=>used.add(id));
 for(const id of [state.draft?.exerciseId,state.lastExerciseId,exercise?.id])if(id?.startsWith('single_'))used.add(id.slice(7));
 const stale=state.customCards.filter(c=>c.media?.video_id===videoId&&c.chunk_kind&&c.source_cue_id&&!keep.has(c.id)&&!used.has(c.id));
 if(!stale.length)return;
 const gone=new Set(stale.map(c=>c.id));
 state.customCards=state.customCards.filter(c=>!gone.has(c.id));
 library.cards=library.cards.filter(c=>!gone.has(c.id));
 for(const id of gone){cards.delete(id);delete state.translations[id];delete state.exposures[id];}
 saveState();
}
function prepareAutomaticDeck(){
 const chosen=AutoLessons.pool(ytCues);
 if(!chosen.length)throw Error('영어 문장이 없습니다. 영어 자막을 불러오거나 다른 영상을 선택하세요.');
 const snapshot={video:{...ytVideo,title:$('ytTitle').value},cues:chosen};
 const saved=importAutomatic(AutoLessons.builtin(snapshot.video,chosen),snapshot,'builtin');
 pruneReplacedChunks(snapshot.video.id,saved);
 autoLessonCards=saved;autoSourceCues=chosen;autoVisible=10;renderAutomaticCards();
 const excluded=ytCues.length-chosen.length;
 autoMessage('전체 '+saved.length+'개 문장 추출 완료 · 마지막 문장까지 준비했습니다. '+(excluded?'음악·박수 등 영어 발화가 아닌 자막 '+excluded+'개는 제외했습니다. ':'')+'한국어 뜻은 순서대로 준비합니다. 아래에서 듣고 말하거나 여러 문장을 골라 문단으로 연습하세요.');
}
async function extractAutomatic(){
 if(recording()||busy||autoJob||!ytVideo)return;
 if(storageBlocked){autoMessage('기록 저장이 중단되어 있습니다. 위의 저장 안내를 확인하세요.',true);return;}
 try{
  prepareAutomaticDeck();
  if(typeof prepareKoreanCards==='function')await prepareKoreanCards(autoLessonCards.map(c=>c.id));
 }catch(e){autoMessage(e.message,true);}
}
async function enrichAutomatic(){
 if(recording()||busy||autoJob||!autoLessonCards.length||storageBlocked)return;
 const snapshot={video:{...ytVideo,title:$('ytTitle').value},cues:autoSourceCues.filter((c,i)=>autoLessonCards[i]?.meaning_source!=='local_ai').map(c=>({...c})),raw:$('ytTranscript').value};
 if(!snapshot.cues.length){autoMessage('현재 문장에는 한국어 뜻·새 상황이 모두 준비되어 있습니다.');return;}
 const job={controller:new AbortController(),timer:null};autoJob=job;lockAutomatic(true);let done=0;
 try{
  const ai=await refreshLocalAI(job.controller.signal);if(!ai.ready){$('localAISetup').open=true;throw Error('문장 연습은 이미 준비되어 있습니다. 한국어 뜻·새 상황 자동 생성은 무료 AI를 한 번 준비한 뒤 누르세요.');}
  for(let i=0;i<snapshot.cues.length;i+=4){
   const batch=snapshot.cues.slice(i,i+4);autoMessage('한국어 뜻·새 상황 추가 중 · '+i+' / '+snapshot.cues.length+'문장. 중단해도 준비된 문장과 완료된 뜻은 남습니다.');
   job.timer=setTimeout(()=>job.controller.abort(),390000);
   const r=await fetch('/youtube/extract',{method:'POST',headers:{'Content-Type':'application/json','X-Local-Token':config.youtube_token||''},body:JSON.stringify({video_id:snapshot.video.id,cues:batch.map(c=>({id:c.id,text:c.text})),count:batch.length}),signal:job.controller.signal});
   const result=await r.json();clearTimeout(job.timer);
   if(autoJob!==job)return;
   if(snapshot.video.id!==ytVideo?.id||snapshot.raw!==$('ytTranscript').value)throw Error('영상이나 자막이 바뀌어 결과를 적용하지 않았습니다.');
   if(!r.ok||result.engine!=='local_ai')throw Error(result.detail||'AI 결과를 확인하지 못했습니다.');
   const saved=importAutomatic(result,{...snapshot,cues:batch},'local_ai');done+=saved.length;
  }
  autoMessage(done+' / '+snapshot.cues.length+'개 문장에 한국어 뜻·새 상황을 추가했습니다. 원문 회상 또는 AI 새 상황을 선택해 말하세요.');
 }catch(e){if(autoJob===job)autoMessage((e.name==='AbortError'?'AI 응답 대기 시간을 넘었습니다.':e.message)+' 완료된 뜻 '+done+'개와 문장 연습은 그대로 남습니다.',true);}
 finally{clearTimeout(job.timer);if(autoJob===job){autoJob=null;lockAutomatic(false);renderAutomaticCards();}}
}
async function buildFromTranscript(){
 if(recording()||busy)return;
 if(!ytVideo){try{Y.video($('ytUrl').value);loadYoutube();}catch(e){autoMessage(e.message,true);return;}}
 if(parseYoutubeTranscript({all:true}))await extractAutomatic();
}
async function buildFromLink(){
 if(recording()||busy)return;
 try{const chosen=Y.video($('ytUrl').value);if(chosen.id!==ytVideo?.id)loadYoutube();if(ytVideo?.id!==chosen.id)return;
  if($('ytTranscript').value.trim()){await buildFromTranscript();return;}
  if(!config.youtube_available||!config.free_only){$('ytTranscriptPanel').open=true;ytStatus('자막 자동 불러오기를 쓰려면 start_youtube_windows.bat으로 실행하세요. 자막이 준비되면 표현·뜻·새 상황은 자동으로 만들어집니다.',true);return;}
  if(typeof primeKoreanTranslation==='function')primeKoreanTranslation();
  if(await fetchYoutubeTranscript())await extractAutomatic();
 }catch(e){ytStatus(e.message,true);}
 finally{if(typeof discardKoreanWarmup==='function')discardKoreanWarmup();}
}
function startAutomaticPractice(){
 if(recording()||busy||!autoLessonCards.length||!mayLeave())return;
 resetResponse();state.session={ids:[...new Set(autoLessonCards.map(c=>c.id))],index:0,completed:[],skipped:[],at:Date.now()};saveState();sessionCard();renderSession();
 status('준비된 문장을 하나씩 듣고 글자를 가린 뒤 말해 보세요. 자가 점검 후 다음 표현으로 이어집니다.');
}
$('ytAutoBuild').onclick=buildFromLink;$('ytAutoExtract').onclick=buildFromTranscript;$('ytFromTranscript').onclick=buildFromTranscript;
$('ytShowMore').onclick=async()=>{if(recording()||busy)return;autoVisible+=10;renderAutomaticCards();if(typeof autoPrepareKoreanDeck==='function')await autoPrepareKoreanDeck();};$('ytEnrich').onclick=enrichAutomatic;
$('ytAutoPractice').onclick=startAutomaticPractice;$('ytAutoCancel').onclick=cancelAutomatic;
$('ytAIRefresh').onclick=async()=>{await refreshLocalAI();if(localAIState.ready&&typeof autoPrepareKoreanDeck==='function')await autoPrepareKoreanDeck();};$('ytAISetup').onclick=prepareLocalAI;
$('ytFetch').onclick=async()=>{if(typeof primeKoreanTranslation==='function')primeKoreanTranslation();try{if(await fetchYoutubeTranscript())await extractAutomatic();}finally{if(typeof discardKoreanWarmup==='function')discardKoreanWarmup();}};
const previousCaptionImport=$('ytCaptionFile').onchange;
$('ytCaptionFile').onchange=async()=>{if(typeof primeKoreanTranslation==='function')primeKoreanTranslation();try{await previousCaptionImport();if(!recording()&&!busy&&$('ytTranscript').value.trim())await buildFromTranscript();}finally{if(typeof discardKoreanWarmup==='function')discardKoreanWarmup();}};
window.addEventListener('beforeunload',()=>{clearTimeout(aiPoll);autoJob?.controller.abort();});
renderAutoCapability();

// Older versions saved only the first batch. Fill the rest from the saved
// transcript on reopening, retaining existing card IDs, meanings and reviews.
if(ytVideo&&ytCues.length&&!storageBlocked&&state.customCards.some(c=>c.media.video_id===ytVideo.id&&c.chunk_kind)){try{prepareAutomaticDeck();}catch(e){autoMessage(e.message,true);}}
