(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;else root.LabCore=api;})(typeof window!=='undefined'?window:this,function(){
'use strict';
const Y=typeof module==='object'&&module.exports?require('./youtube-core.js'):window.LabYouTube;
const K=typeof module==='object'&&module.exports?require('./korean-core.js'):window.LabKorean;
const DAY=86400000,INTERVALS=[1,3,7,14,30];
const MAX_CUSTOM_CARDS=10000;
const object=x=>!!x&&typeof x==='object'&&!Array.isArray(x);
const finite=x=>Number.isFinite(x)&&x>=0&&x<=8640000000000000;
const safeKey=x=>typeof x==='string'&&/^[a-zA-Z0-9_-]{1,150}$/.test(x)&&!['__proto__','constructor','prototype'].includes(x);
const string=(x,max=10000)=>typeof x==='string'&&x.length<=max;
function escapeHTML(v){return String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
function norm(s){return String(s??'').replace(/[’‘]/g,"'").replace(/[“”]/g,'"').toLowerCase().replace(/\s+/g,' ').trim();}
function initialState(){return {version:2,cards:{},attempts:[],customExercises:[],customCards:[],translations:{},transcriptTranslations:[],youtubeDraft:null,voice:{uri:'',online:false},lastExerciseId:'g08_story_1',lastLessonId:'g08',draft:null,consent:false,exposures:{},seenTasks:{},session:null,bridge:null};}
function validateExercise(e,known){
 return object(e)&&safeKey(e.id)&&Array.isArray(e.card_ids)&&e.card_ids.length>0&&e.card_ids.length<=5&&new Set(e.card_ids).size===e.card_ids.length&&e.card_ids.every(id=>safeKey(id)&&(!known||known.has(id)))&&['title','task_ko','sample_en','situation_ko'].every(k=>string(e[k],k==='title'?200:10000)&&e[k].trim())&&(!e.lesson_id||safeKey(e.lesson_id));
}
function validateFeedback(r){
 return object(r)&&string(r.corrected_text)&&string(r.summary_ko)&&string(r.next_drill_ko)&&Array.isArray(r.study_summary_en)&&r.study_summary_en.every(x=>string(x))&&Array.isArray(r.sentence_reviews)&&r.sentence_reviews.length>0&&r.sentence_reviews.every(s=>object(s)&&string(s.original)&&string(s.corrected)&&['correct','needs_fix','optional','uncertain'].includes(s.status)&&Array.isArray(s.corrections)&&s.corrections.every(c=>object(c)&&['meaning','grammar','collocation','optional','asr_uncertain'].includes(c.kind)&&['original','replacement','reason_ko'].every(k=>string(c[k]))))&&Array.isArray(r.phrase_checks)&&r.phrase_checks.every(c=>object(c)&&safeKey(c.card_id)&&['correct','incorrect','not_used','alternative','uncertain'].includes(c.status)&&string(c.evidence)&&string(c.explanation_ko));
}
function validateState(x,known){
 if(!object(x)||![1,2].includes(x.version)||!object(x.cards)||!Array.isArray(x.attempts)||!Array.isArray(x.customExercises))return false;
 if(x.customCards!==undefined&&(!Array.isArray(x.customCards)||x.customCards.length>MAX_CUSTOM_CARDS||x.customCards.some(c=>!Y.validCard(c))||new Set(x.customCards.map(c=>c.id)).size!==x.customCards.length))return false;
 if(known)known=new Map([...known,...(x.customCards||[]).map(c=>[c.id,c])]);
 if(x.translations!==undefined&&(!object(x.translations)||Object.keys(x.translations).length>20000||Object.entries(x.translations).some(([id,t])=>!safeKey(id)||(known&&!known.has(id))||!K.validTranslation(t,known?K.target(known.get(id)):undefined))))return false;
 if(x.transcriptTranslations!==undefined&&!K.validTranscriptCache(x.transcriptTranslations))return false;
 if(x.voice!==undefined&&(!object(x.voice)||!string(x.voice.uri,500)||typeof x.voice.online!=='boolean'||(x.voice.dictation!==undefined&&typeof x.voice.dictation!=='boolean')))return false;
 if(x.youtubeDraft!=null&&(!object(x.youtubeDraft)||!Y.validId(x.youtubeDraft.videoId)||!string(x.youtubeDraft.title,200)||!string(x.youtubeDraft.transcript,200000)))return false;
 if(x.attempts.length>20000||x.customExercises.length>2000||Object.keys(x.cards).length>20000)return false;
 if(Object.entries(x.cards).some(([id,p])=>!safeKey(id)||(known&&!known.has(id))||!object(p)||!finite(p.due)||['independent','step','lapses','attempts'].some(k=>p[k]!==undefined&&(!Number.isInteger(p[k])||p[k]<0))||['firstSuccess','lastIndependent','lastFailure','lastSeen'].some(k=>p[k]!=null&&!finite(p[k]))))return false;
 if(x.attempts.some(a=>!object(a)||!safeKey(a.id)||!finite(a.at)||!string(a.transcript)||!string(a.title,200)||!safeKey(a.exerciseId)||!Array.isArray(a.card_ids)||a.card_ids.length>5||a.card_ids.some(id=>!safeKey(id)||(known&&!known.has(id)))||(a.rawTranscript!==undefined&&!string(a.rawTranscript))||(a.duration!==undefined&&!finite(a.duration))||(a.result!=null&&!validateFeedback(a.result))))return false;
 if(new Set(x.attempts.map(a=>a.id)).size!==x.attempts.length)return false;
 if(x.customExercises.some(e=>!validateExercise(e,known))||new Set(x.customExercises.map(e=>e.id)).size!==x.customExercises.length)return false;
 for(const k of ['exposures','seenTasks'])if(x[k]!==undefined&&(!object(x[k])||Object.entries(x[k]).some(([id,t])=>!safeKey(id)||!finite(t))))return false;
 if(x.lastExerciseId!==undefined&&!safeKey(x.lastExerciseId))return false;
 if(x.lastLessonId!==undefined&&!safeKey(x.lastLessonId))return false;
 if(x.draft!=null&&(!object(x.draft)||!safeKey(x.draft.exerciseId)||!string(x.draft.text)||!['paragraph','single','situation'].includes(x.draft.mode)||!['learn','recall','retry','transfer','review'].includes(x.draft.stage)||!Number.isInteger(x.draft.drillIndex)||x.draft.drillIndex<0))return false;
 if(x.session!=null&&(!object(x.session)||!Array.isArray(x.session.ids)||x.session.ids.length>20000||new Set(x.session.ids).size!==x.session.ids.length||x.session.ids.some(id=>!safeKey(id)||(known&&!known.has(id)))||!Number.isInteger(x.session.index)||x.session.index<0||x.session.index>x.session.ids.length||!Array.isArray(x.session.completed)||!Array.isArray(x.session.skipped)||[...x.session.completed,...x.session.skipped].some(id=>!x.session.ids.includes(id))))return false;
 if(x.bridge!=null&&(!object(x.bridge)||!safeKey(x.bridge.request_id)||!object(x.bridge.attempt)||!validateState({version:2,cards:{},attempts:[x.bridge.attempt],customExercises:[]},known)||!x.bridge.attempt.card_ids.length||!safeKey(x.bridge.attempt.taskKey)||!['learn','recall','retry','transfer','review'].includes(x.bridge.attempt.stage)||!['paragraph','single','situation'].includes(x.bridge.attempt.mode)||!string(x.bridge.attempt.task_ko)||!string(x.bridge.attempt.sample_en)))return false;
 if(x.attempts.some(a=>a.inputKind!==undefined&&!['text','audio'].includes(a.inputKind)))return false;
 return true;
}
function migrateState(x,known){
 if(!validateState(x,known))throw Error('백업의 날짜·표현·답변 구조가 올바르지 않습니다.');
 const y=initialState();for(const k of Object.keys(y))if(Object.hasOwn(x,k))y[k]=JSON.parse(JSON.stringify(x[k]));y.version=2;return y;
}
function updateSchedule(previous,rating,{now=Date.now(),hintUsed=false,stage='recall',exerciseId='',newContext=false}={}){
 if(!['again','hint','good'].includes(rating)||!finite(now))throw Error('Invalid review');
 const p={independent:0,step:0,lapses:0,firstSuccess:null,lastIndependent:null,lastFailure:null,transferSuccess:false,attempts:0,...previous};
 p.attempts++;p.lastSeen=now;p.lastRating=rating;p.lastExerciseId=exerciseId;
 if(rating==='again'){
  p.lapses++;p.step=0;p.independent=0;p.firstSuccess=null;p.lastIndependent=null;p.lastFailure=now;p.transferSuccess=false;p.due=now+600000;return p;
 }
 const recentlyFailed=p.lastFailure!=null&&now-p.lastFailure<DAY;
 if(rating==='hint'||hintUsed||stage==='retry'||recentlyFailed){
  p.due=p.due>now?Math.min(p.due,now+DAY):now+DAY;p.lastRating='hint';return p;
 }
 const eligible=(p.lastIndependent===null||now-p.lastIndependent>=DAY)&&(!p.due||now>=p.due);
 if(!eligible)return p;
 const previouslyLearned=p.independent>0;
 p.independent++;p.step=Math.min(p.independent-1,INTERVALS.length-1);p.lastIndependent=now;
 if(p.firstSuccess===null)p.firstSuccess=now;
 if(newContext&&previouslyLearned&&['transfer','review','recall'].includes(stage))p.transferSuccess=true;
 p.due=now+INTERVALS[p.step]*DAY;return p;
}
function mastery(p){return !!p&&p.lastRating==='good'&&p.independent>=3&&p.transferSuccess&&p.lastIndependent-p.firstSuccess>=2*DAY;}
function dueCards(cards,progress,now=Date.now()){return cards.filter(c=>progress[c.id]&&progress[c.id].due<=now).sort((a,b)=>progress[a.id].due-progress[b.id].due||a.id.localeCompare(b.id));}
function chooseReviewExercise(exercises,progress,now=Date.now()){
 const score=e=>e.card_ids.reduce((v,id)=>v+(progress[id]&&progress[id].due<=now?1:0),0);
 return [...exercises].filter(e=>score(e)>0).sort((a,b)=>score(b)-score(a))[0]||null;
}
function makeSession(cards,progress,{now=Date.now(),lessonId='g08',limit=8,newLimit=3}={}){
 const due=dueCards(cards,progress,now).slice(0,limit).map(c=>c.id);
 const fresh=cards.filter(c=>(c.level==='core'||c.lesson_id==='youtube')&&c.lesson_id===lessonId&&!progress[c.id]).slice(0,Math.min(newLimit,limit-due.length)).map(c=>c.id);
 return {ids:[...due,...fresh],index:0,completed:[],skipped:[],at:now};
}
function cardExercise(c,translation){const korean=K.ko(c,translation);return {id:'single_'+c.id,lesson_id:c.lesson_id,card_ids:[c.id],title:c.chunk_kind?'한국어를 보고 한 문장 말하기':'한 표현 꺼내기',task_ko:korean||c.practice_task_ko||c.cue_ko||`다음 뜻을 담은 영어 문장을 직접 만드세요: ${c.meaning_ko}`,sample_en:c.practice_sample_en||c.example_en||c.source_quote,situation_ko:korean||c.practice_task_ko||c.cue_ko||c.meaning_ko,origin:c.practice_origin|| (c.media?'영상 표현 · 짧은 상황 단서':c.cue_ko?'앱 작성 단문 연습':'자동 추출 참고 항목 · 예문은 원자료이며 별도 검증 필요')};}
function taskKey(exercise,mode='paragraph',id=''){return exercise.id+(mode==='single'?'_'+id:'');}
function assisted(ids,exposures,now=Date.now()){return ids.some(id=>exposures[id]!==undefined&&now-exposures[id]<DAY);}
function parseExercise(text,known){
 const x=JSON.parse(String(text).trim().replace(/^```(?:json)?\s*/,'').replace(/\s*```$/,''));
 const e={...x,id:'import_'+Date.now()+'_'+Math.random().toString(36).slice(2,8),lesson_id:'custom',origin:'외부에서 가져온 새 연습문단 · 내용 확인 필요'};
 if(!validateExercise(e,known))throw Error('제목·표현 ID·한글 문제·영어 예문·상황 키워드를 확인하세요.');
 if(!Array.isArray(e.alignment)||e.alignment.length!==e.card_ids.length||new Set(e.alignment.map(a=>a?.card_id)).size!==e.card_ids.length||e.alignment.some(a=>!object(a)||!e.card_ids.includes(a.card_id)||!string(a.korean_cue)||!a.korean_cue.trim()||!e.task_ko.includes(a.korean_cue)||!string(a.english_use)||!a.english_use.trim()||!e.sample_en.includes(a.english_use)))throw Error('표현별 한글 단서와 영어 활용 구절의 대응이 맞지 않습니다.');
 return e;
}
function parseFeedback(text,pending){
 if(!pending?.attempt||!safeKey(pending.request_id))throw Error('먼저 교정 요청을 복사하세요.');
 if(typeof text!=='string'||text.length>100000)throw Error('교정 결과는 100,000자 이하로 붙여 넣으세요.');
 let x;try{x=JSON.parse(text.trim().replace(/^```(?:json)?\s*/,'').replace(/\s*```$/,''));}catch(e){throw Error('ChatGPT가 준 JSON 전체를 붙여 넣으세요. 설명 문장은 제외하세요.');}
 if(!object(x)||x.request_id!==pending.request_id)throw Error('다른 답변의 교정 결과입니다. 마지막으로 복사한 요청의 결과를 사용하세요.');
 const r=x.result,a=pending.attempt;
 if(!validateFeedback(r)||r.sentence_reviews.length>100||r.phrase_checks.length!==a.card_ids.length||new Set(r.phrase_checks.map(p=>p.card_id)).size!==a.card_ids.length||r.phrase_checks.some(p=>!a.card_ids.includes(p.card_id))||!Array.isArray(r.omissions)||r.omissions.some(o=>!object(o)||!['korean_meaning','suggestion_en','reason_ko'].every(k=>string(o[k]))))throw Error('교정 결과의 문장·표현·누락 항목 구조를 확인하세요.');
 const compact=s=>String(s).replace(/\s+/gu,''),letters=s=>String(s).match(/[\p{L}\p{N}]+/gu)?.map(x=>x.toLowerCase()).join('|')||'';
 let cursor=0;
 for(const s of r.sentence_reviews){
  const at=a.transcript.indexOf(s.original,cursor);
  if(!s.original.trim()||!s.corrected.trim()||at<0||a.transcript.slice(cursor,at).trim())throw Error('문장 인용이 제출한 답변과 다르거나 일부 문장이 빠졌습니다.');
  cursor=at+s.original.length;
  if(s.corrections.some(c=>!c.original.trim()||!s.original.includes(c.original)||(c.replacement&&!s.corrected.includes(c.replacement))))throw Error('수정 근거가 실제 문장이나 수정문에 없습니다.');
  const required=s.corrections.some(c=>['meaning','grammar','collocation'].includes(c.kind));
  if((s.status==='correct'&&(s.corrections.length||letters(s.original)!==letters(s.corrected)))||(s.status==='needs_fix'&&!required)||(s.status==='optional'&&s.corrections.some(c=>c.kind!=='optional')))throw Error('문장의 판정과 수정 근거가 일치하지 않습니다.');
 }
 if(a.transcript.slice(cursor).trim()||compact(r.corrected_text)!==compact(r.sentence_reviews.map(s=>s.corrected).join(' ')))throw Error('전체 답변과 문장별 교정이 일치하지 않습니다.');
 if(r.phrase_checks.some(p=>p.status==='not_used'?!!p.evidence.trim():!p.evidence.trim()||!a.transcript.includes(p.evidence)))throw Error('표현별 근거가 실제 제출문과 일치하지 않습니다.');
 return r;
}
function words(text){return (String(text).match(/[A-Za-z]+(?:['’][A-Za-z]+)*/g)||[]).length;}
return {DAY,INTERVALS,MAX_CUSTOM_CARDS,escapeHTML,norm,initialState,validateState,migrateState,validateExercise,updateSchedule,mastery,dueCards,chooseReviewExercise,makeSession,cardExercise,taskKey,assisted,parseExercise,parseFeedback,words};
});
