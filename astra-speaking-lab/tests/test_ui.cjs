/* DOM simulation, not a real browser or microphone. No network/paid API requests. */
const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {JSDOM,VirtualConsole}=require('jsdom');
const C=require('../static/core.js');
const HTML=fs.readFileSync(path.join(__dirname,'../OPEN_ME.html'),'utf8');
const NOW=Date.UTC(2026,8,9,9),KEY='astra.speaking.lab.v2';
const tick=()=>new Promise(r=>setTimeout(r,5));
function fixtureKorean(text){const known={'I was thinking of taking a break.':'잠깐 쉴까 생각하고 있었어요.','Then I came up with a different plan.':'그러다가 다른 계획을 생각해 냈어요.','This song brings back good memories.':'이 노래를 들으면 좋은 추억이 떠올라요.','I had no idea the cafe was closed.':'카페가 문을 닫았다는 사실을 전혀 몰랐어요.'};return known[text]||'친구에게 이야기할 내용 '+(text.match(/number (\d+)/)?.[1]||'하나')+'가 있었어요.';}
function cold(id='g01_01') {const s=C.initialState();s.lastExerciseId='single_'+id;s.lastLessonId=id.slice(0,3);s.draft={exerciseId:s.lastExerciseId,text:'',raw:'',mode:'paragraph',stage:'review',drillIndex:0,hints:false,hintUsed:false};return s;}
async function app(t,{state=null,raw=null,legacy=false,offline=false,connected=false,paid=false,mic=true,deferMic=false,translator=true,speech=false}={}){
 const errors=[],calls=[],vc=new VirtualConsole();vc.on('jsdomError',e=>errors.push(e.message));
 let micResolve;
 const dom=new JSDOM(HTML,{url:offline?'file:///lab/OPEN_ME.html':'http://localhost:8765/',runScripts:'dangerously',virtualConsole:vc,beforeParse(w){
  const NativeDate=w.Date;w.Date=class extends NativeDate{constructor(...args){super(...(args.length?args:[NOW]));}static now(){return NOW;}};
  if(raw!==null||state)w.localStorage.setItem(legacy?'astra.speaking.lab.v1':KEY,raw??JSON.stringify(state));
  w.confirm=()=>true;w.alert=msg=>w.__alert=msg;w.prompt=()=>null;
  w.HTMLElement.prototype.scrollIntoView=()=>{};w.HTMLMediaElement.prototype.pause=function(){this.__paused=true;this.__pauses=(this.__pauses||0)+1;};w.HTMLMediaElement.prototype.play=function(){this.__paused=false;this.__plays=(this.__plays||0)+1;return Promise.resolve();};Object.defineProperty(w.HTMLMediaElement.prototype,'paused',{get(){return this.__paused!==false;}});
  w.HTMLDialogElement.prototype.showModal=function(){this.open=true};w.HTMLDialogElement.prototype.close=function(){this.open=false};
  w.URL.createObjectURL=()=> 'blob:test';w.URL.revokeObjectURL=()=>{};
  w.SpeechSynthesisUtterance=class {constructor(text){this.text=text}};
  w.__spokenAll=[];w.__speechCancels=0;w.speechSynthesis={speak:u=>{w.__spoken=u;w.__spokenAll.push(u);},cancel(){w.__speechCancels++;},pause(){w.__speechPauses=(w.__speechPauses||0)+1;},resume(){w.__speechResumes=(w.__speechResumes||0)+1;},addEventListener:(name,fn)=>{w.__speechEvents=w.__speechEvents||{};w.__speechEvents[name]=fn;},getVoices:()=>[{lang:"en-US",localService:true}]};
  if(speech){w.__recognitions=[];w.webkitSpeechRecognition=class{constructor(){w.__recognitions.push(this);}start(){this.started=true;}stop(){this.stopped=true;setTimeout(()=>this.onend&&this.onend(),1);}abort(){this.aborted=true;}};}
  if(translator)w.Translator={create:async options=>{w.__translationCreates=(w.__translationCreates||0)+1;return {translate:async text=>{w.__translatedTexts=w.__translatedTexts||[];w.__translatedTexts.push(text);return w.__translate?await w.__translate(text):fixtureKorean(text);},destroy:()=>{w.__translatorDestroyed=true;}};}};
  Object.defineProperty(w.navigator,'clipboard',{value:{writeText:async x=>w.__clipboard=x}});
  w.fetch=async(url,options={})=>{calls.push({url,options});if(w.__fetch)return w.__fetch(url,options);return {ok:true,json:async()=>({connected,token:'fixture-token',model:'gpt-6-astra',transcribe_model:'gpt-transcribe',reasoning_effort:'medium'})};};
  if(mic)Object.defineProperty(w.navigator,'mediaDevices',{value:{getUserMedia:()=>deferMic?new Promise(r=>micResolve=r):Promise.resolve({getTracks:()=>[{stop:()=>w.__trackStopped=true}]})}});
  w.MediaRecorder=class {static isTypeSupported(){return true}constructor(){w.__recorder=this;this.state='inactive';this.mimeType='audio/webm'}start(){this.state='recording'}pause(){this.state='paused'}resume(){this.state='recording'}stop(){this.state='inactive'}finish(){this.ondataavailable({data:new w.Blob(['audio'],{type:'audio/webm'})});this.onstop();}};
 }});await tick();
 const w=dom.window,d=w.document,$=id=>d.getElementById(id),click=id=>$(id).click();
 if(paid){$('paidModeToggle').checked=true;$('paidModeToggle').dispatchEvent(new w.Event('change'));}
 const fill=(id,text)=>{$(id).value=text;$(id).dispatchEvent(new w.Event('input',{bubbles:true}));};
 t.after(async()=>{w.dispatchEvent(new w.Event('beforeunload'));await tick();assert.deepEqual(errors,[],'uncaught UI errors');dom.window.close();});
 return {w,d,$,click,fill,calls,resolveMic:()=>micResolve({getTracks:()=>[{stop:()=>w.__trackStopped=true}]})};
}
function rate(a,value='good'){a.$('ratingList').querySelectorAll('select').forEach(e=>e.value=value);a.click('saveReview');}
test('standalone offline app starts with real content and no network calls',async t=>{const a=await app(t,{offline:true});assert.ok(a.w.LabTest);assert.equal(a.w.LAB_DATA.cards.length,3381);assert.equal(a.w.LAB_DATA.cards.filter(c=>!c.material_id).length,2874);assert.equal(a.w.LAB_TRANSFER.length,30);assert.equal(a.calls.length,0);assert.ok(a.$('sampleBox').classList.contains('hidden'));});
test('v1 progress migrates while original v1 storage is retained',async t=>{const s={...cold(),version:1};delete s.exposures;delete s.seenTasks;delete s.session;const a=await app(t,{state:s,legacy:true});assert.equal(a.w.LabTest.getState().version,2);assert.equal(a.w.localStorage.getItem('astra.speaking.lab.v1'),JSON.stringify(s));});
test('corrupt backup remains intact and visible save warning persists',async t=>{const raw='{"version":2,"attempts":[null]}',a=await app(t,{raw});assert.equal(a.w.localStorage.getItem(KEY),raw);assert.match(a.$('storageNotice').textContent,/덮어쓰지/);a.fill('answerInput','I tried.');await tick();assert.equal(a.w.localStorage.getItem(KEY),raw);});
test('cold answer snapshot remains unassisted even after comparing the model',async t=>{const a=await app(t,{state:cold()});a.fill('answerInput','I was thinking of making a photo album.');a.click('selfCheck');rate(a);const s=a.w.LabTest.getState();assert.equal(s.attempts[0].hintUsed,false);assert.equal(s.cards.g01_01.independent,1);assert.equal(a.w.LabTest.isAssisted(),true);});
test('another answer after self-check cannot manufacture independent retrieval',async t=>{const a=await app(t,{state:cold()});a.fill('answerInput','I was thinking of making a photo album.');a.click('selfCheck');rate(a);a.fill('answerInput','I was thinking of making a photo album.');a.click('selfCheck');rate(a);assert.equal(a.w.LabTest.getState().attempts[1].hintUsed,true);assert.equal(a.w.LabTest.getState().cards.g01_01.independent,1);});
test('hint history survives lesson-stage toggles and single-drill entry',async t=>{const a=await app(t,{state:cold()});a.d.querySelector('[data-stage="learn"]').click();a.click('beginRecall');a.click('singleDrill');assert.equal(a.w.LabTest.isAssisted(),true);assert.ok(a.w.LabTest.getState().exposures.g01_01);});
test('stored hint history survives reload',async t=>{const s=cold();s.exposures.g01_01=NOW-1000;const a=await app(t,{state:s});assert.equal(a.w.LabTest.isAssisted(),true);});
test('oldest reference item can be reviewed offline without a paragraph',async t=>{const s=cold();s.cards.kpop_13_1={due:NOW-10};const a=await app(t,{state:s});a.click('smartReview');assert.equal(a.w.LabTest.getExercise().id,'single_kpop_13_1');assert.ok(a.$('taskText').textContent);assert.equal(a.calls.filter(x=>x.options.method==='POST').length,0);});
test('review list keeps English answers hidden until explicitly revealed',async t=>{const s=cold();s.cards.g01_01={due:NOW-10};const a=await app(t,{state:s});a.d.querySelector('[data-view="review"]').click();assert.equal(a.w.LabTest.isAssisted(),false);const detail=a.d.querySelector('.review-hint');assert.equal(detail.open,false);detail.open=true;detail.dispatchEvent(new a.w.Event('toggle'));assert.equal(a.w.LabTest.isAssisted(),true);});
test('session queue requires saved evaluation before proceeding',async t=>{const s=cold();s.cards.g02_01={due:NOW-10};const a=await app(t,{state:s});a.click('sessionStart');assert.equal(a.w.LabTest.getExercise().id,'single_g02_01');assert.equal(a.$('sessionNext').disabled,true);a.fill('answerInput',"You'll never guess what happened to me!");a.click('selfCheck');rate(a);assert.equal(a.$('sessionNext').disabled,false);a.click('sessionNext');assert.equal(a.w.LabTest.getState().session.index,1);});
test('session skip does not change the skipped item schedule',async t=>{const s=cold();s.cards.g02_01={due:NOW-10};const a=await app(t,{state:s});a.click('sessionStart');a.click('sessionSkip');assert.equal(a.w.LabTest.getState().cards.g02_01.due,NOW-10);assert.equal(a.w.LabTest.getState().session.skipped[0],'g02_01');});
test('recording remains locked until asynchronous stop finalizes',async t=>{const a=await app(t,{state:cold()});a.click('recordBtn');await tick();assert.equal(a.w.LabTest.recording(),true);a.click('stopBtn');assert.equal(a.w.LabTest.recording(),true);a.w.LabTest.loadExercise('g09_story_1');assert.equal(a.w.LabTest.getExercise().id,'single_g01_01');a.w.__recorder.finish();assert.equal(a.w.LabTest.recording(),false);assert.equal(a.w.__trackStopped,true);assert.equal(a.calls.filter(x=>x.options.method==='POST').length,0);});
test('pending microphone permission locks exercise changes',async t=>{const a=await app(t,{state:cold(),deferMic:true});a.click('recordBtn');assert.equal(a.w.LabTest.recording(),true);a.w.LabTest.loadExercise('g09_story_1');assert.equal(a.w.LabTest.getExercise().id,'single_g01_01');a.resolveMic();await tick();a.click('stopBtn');a.w.__recorder.finish();});
test('unsupported microphone explains fallback and does not lock app',async t=>{const a=await app(t,{state:cold(),mic:false});a.click('recordBtn');assert.match(a.$('statusLine').textContent,/녹음을 지원/);assert.equal(a.w.LabTest.recording(),false);});
test('recording pause and resume remain local actions',async t=>{const a=await app(t,{state:cold()});a.click('recordBtn');await tick();a.click('pauseBtn');assert.equal(a.w.__recorder.state,'paused');a.click('pauseBtn');assert.equal(a.w.__recorder.state,'recording');a.click('stopBtn');a.w.__recorder.finish();assert.equal(a.calls.filter(x=>x.options.method==='POST').length,0);});
test('model speech respects selected pace and marks assistance',async t=>{const a=await app(t,{state:cold()});a.$('speechRate').value='1.1';a.click('sampleToggle');a.click('listenSample');assert.equal(a.w.__spoken.rate,1.1);assert.equal(a.w.LabTest.isAssisted(),true);});
test('grade requires transcript confirmation and an API key',async t=>{const a=await app(t,{state:cold(),paid:true});a.fill('answerInput','I tried.');a.click('gradeBtn');assert.match(a.$('statusLine').textContent,/확인란/);a.$('confirmTranscript').checked=true;a.click('gradeBtn');assert.match(a.$('statusLine').textContent,/API 미연결/);assert.equal(a.w.LabTest.getState().attempts.length,0);});
test('transcription is explicit and its text is not automatically graded',async t=>{const s=cold();s.consent=true;const a=await app(t,{state:s,connected:true,paid:true});a.w.__fetch=async()=>({ok:true,json:async()=>({text:'I was thinking of going.'})});a.click('recordBtn');await tick();a.click('stopBtn');a.w.__recorder.finish();a.click('transcribeBtn');await tick();assert.equal(a.$('answerInput').value,'I was thinking of going.');assert.equal(a.$('confirmTranscript').checked,false);assert.equal(a.w.LabTest.getState().attempts.length,0);assert.equal(a.calls.filter(x=>x.url==='/api/transcribe').length,1);assert.equal(a.calls.filter(x=>x.url==='/api/grade').length,0);});
test('failed API grade retains answer and produces no invented evaluation',async t=>{const s=cold();s.consent=true;const a=await app(t,{state:s,connected:true,paid:true});a.w.__fetch=async()=>({ok:false,json:async()=>({detail:'fixture failure'})});a.fill('answerInput','I was thinking of going.');a.$('confirmTranscript').checked=true;a.click('gradeBtn');assert.equal(a.$('answerInput').readOnly,true);await tick();assert.equal(a.$('answerInput').readOnly,false);assert.equal(a.$('answerInput').value,'I was thinking of going.');assert.equal(a.w.LabTest.getState().attempts.length,0);});
test('new situation favors an unseen short variant and labels a repeat accurately',async t=>{const a=await app(t,{state:cold('g08_01')});a.click('newSituation');assert.equal(a.w.LabTest.getExercise().id,'transfer_g08_01');assert.equal(a.w.LabTest.getStage(),'transfer');});
test('external exercise import rejects invented alignment without mutation',async t=>{const a=await app(t,{state:cold()});a.$('exerciseJson').value=JSON.stringify({title:'t',card_ids:['g01_01'],task_ko:'생각',sample_en:'I think.',situation_ko:'계획',alignment:[]});a.click('importExerciseSave');assert.equal(a.w.LabTest.getState().customExercises.length,0);assert.match(a.$('exerciseImportStatus').textContent,/대응/);});
test('external exercise import escapes markup and remembers answer exposure',async t=>{const a=await app(t,{state:cold()});a.$('exerciseJson').value=JSON.stringify({title:'<img src=x onerror="alert(1)">',card_ids:['g01_01'],task_ko:'생각하고 있었어',sample_en:'I was thinking of going.',situation_ko:'계획',alignment:[{card_id:'g01_01',korean_cue:'생각',english_use:'thinking of going'}]});a.click('importExerciseSave');assert.equal(a.w.LabTest.getState().customExercises.length,1);assert.equal(a.$('taskTitle').querySelector('img'),null);assert.equal(a.w.LabTest.isAssisted(),true);});
test('quota failure cannot be reported as a successfully saved schedule',async t=>{const a=await app(t,{state:cold()});a.fill('answerInput','I was thinking of going.');a.click('selfCheck');a.w.Storage.prototype.setItem=function(){throw Error('QuotaExceeded')};rate(a);assert.match(a.$('storageNotice').textContent,/실패/);assert.match(a.$('scheduleNote').textContent,/저장하지 못/);});
test('cross-tab updates stop this tab from overwriting newer data',async t=>{const a=await app(t,{state:cold()});a.w.dispatchEvent(new a.w.StorageEvent('storage',{key:KEY,newValue:'{}'}));assert.match(a.$('storageNotice').textContent,/다른 탭/);const before=a.w.localStorage.getItem(KEY);a.click('sampleToggle');assert.equal(a.w.localStorage.getItem(KEY),before);});
test('copy-to-ChatGPT preserves actual words and English-only recap',async t=>{const a=await app(t,{state:cold()});a.fill('answerInput','I was thinking of going.');a.$('confirmTranscript').checked=true;a.click('copyPrompt');await tick();assert.match(a.w.__clipboard,/I was thinking of going/);a.click('selfCheck');a.click('exportSummary');await tick();assert.ok(!/[가-힣]/.test(a.w.__clipboard));});
function feedbackFixture(){return {summary_ko:'전치사 뒤에는 동명사를 씁니다.',sentence_reviews:[{original:'I was thinking of buy a bag.',corrected:'I was thinking of buying a bag.',status:'needs_fix',corrections:[{kind:'grammar',original:'of buy',replacement:'of buying',reason_ko:'전치사 of 뒤에는 동명사 buying이 필요합니다.'}]}],phrase_checks:[{card_id:'g01_01',status:'incorrect',evidence:'thinking of buy',explanation_ko:'동명사가 필요합니다.'}],omissions:[],corrected_text:'I was thinking of buying a bag.',next_drill_ko:'자전거를 빌릴까 생각하고 있었어.',study_summary_en:['think of + -ing']};}
test('successful fixture grade preserves submission-time hint state and populates error notebook',async t=>{const s=cold();s.consent=true;const a=await app(t,{state:s,connected:true,paid:true});let resolve;a.w.__fetch=()=>new Promise(r=>resolve=r);a.fill('answerInput','I was thinking of buy a bag.');a.$('confirmTranscript').checked=true;a.click('gradeBtn');a.d.querySelector('[data-view="library"]').click();assert.equal(a.w.LabTest.isAssisted(),true);resolve({ok:true,json:async()=>({result:feedbackFixture(),model:'FIXTURE',usage:{input_tokens:1,output_tokens:1}})});await tick();const attempt=a.w.LabTest.getState().attempts[0];assert.equal(attempt.hintUsed,false);assert.equal(attempt.transcript,'I was thinking of buy a bag.');assert.match(a.$('feedbackContent').textContent,/먼저 고칠/);a.d.querySelector('[data-view="review"]').click();assert.equal(a.d.querySelectorAll('.error-retry').length,1);a.d.querySelector('.error-retry').click();assert.equal(a.w.LabTest.getStage(),'retry');assert.ok(a.$('feedbackPanel').classList.contains('hidden'));});
test('malformed imported progress does not replace working state',async t=>{const a=await app(t,{state:cold()});const before=a.w.localStorage.getItem(KEY);await a.w.LabTest.importProgress({size:100,text:async()=>JSON.stringify({version:2,cards:{},attempts:[null],customExercises:[]})});assert.equal(a.w.localStorage.getItem(KEY),before);assert.match(a.w.__alert,/가져오기 실패/);});
test('single-card exercise survives export and fresh-start restore',async t=>{const a=await app(t,{state:cold()});a.click('sessionStart');a.fill('answerInput','My draft.');await new Promise(r=>setTimeout(r,550));const saved=JSON.parse(a.w.localStorage.getItem(KEY));assert.ok(C.validateState(saved));const b=await app(t,{state:saved});assert.equal(b.$('answerInput').value,'My draft.');assert.equal(b.w.LabTest.getExercise().id,a.w.LabTest.getExercise().id);});
test('free mode blocks paid requests even with stored consent and a connected key',async t=>{const s=cold();s.consent=true;const a=await app(t,{state:s,connected:true});assert.match(a.$('connectionText').textContent,/무료/);assert.ok(a.$('gradeBtn').classList.contains('hidden'));assert.ok(a.$('generatePicked').classList.contains('hidden'));a.fill('answerInput','I tried.');a.$('confirmTranscript').checked=true;a.$('gradeBtn').onclick();a.$('transcribeBtn').onclick();a.$('generatePicked').onclick();assert.equal(a.calls.filter(c=>c.options.method==='POST').length,0);assert.equal(a.w.LabTest.getState().attempts.length,0);});
test('audio-only self-check stores a genuine self-rating without fabricated transcript',async t=>{const a=await app(t,{state:cold()});a.click('recordBtn');await tick();a.click('stopBtn');a.w.__recorder.finish();a.click('selfCheck');assert.equal(a.d.querySelectorAll('.self-checklist input').length,3);assert.ok(a.$('feedbackContent').querySelector('audio'));rate(a);const s=a.w.LabTest.getState();assert.equal(s.attempts[0].inputKind,'audio');assert.equal(s.attempts[0].transcript,'');assert.equal(s.attempts[0].result,null);assert.equal(s.cards.g01_01.independent,1);assert.equal(a.calls.filter(c=>c.options.method==='POST').length,0);a.w.LabTest.renderReview();assert.match(a.$('attemptList').textContent,/텍스트 미입력/);});
test('empty self-check cannot create a practice record',async t=>{const a=await app(t,{state:cold()});a.click('selfCheck');assert.equal(a.w.LabTest.getState().attempts.length,0);});
async function copiedRequest(a){a.fill('answerInput','I was thinking of buy a bag.');a.$('confirmTranscript').checked=true;a.click('copyPrompt');await tick();return a.w.LabTest.getState().bridge;}
test('ChatGPT bridge imports reviewed feedback and error notebook without any API calls',async t=>{const a=await app(t,{state:cold()});const p=await copiedRequest(a);a.click('importFeedbackOpen');a.$('feedbackJson').value=JSON.stringify({request_id:p.request_id,result:feedbackFixture()});a.click('importFeedbackSave');assert.match(a.$('feedbackContent').textContent,/buying a bag/);assert.equal(a.w.LabTest.getState().bridge,null);assert.equal(a.w.LabTest.getState().attempts[0].hintUsed,false);rate(a,'again');a.w.LabTest.renderReview();assert.equal(a.d.querySelectorAll('.error-retry').length,1);assert.equal(a.calls.filter(c=>c.options.method==='POST').length,0);});
test('bridge rejects mismatched current text and restores original submission before import',async t=>{const a=await app(t,{state:cold()});const p=await copiedRequest(a);a.fill('answerInput','Another answer.');a.click('importFeedbackOpen');a.$('feedbackJson').value=JSON.stringify({request_id:p.request_id,result:feedbackFixture()});a.click('importFeedbackSave');assert.equal(a.w.LabTest.getState().attempts.length,0);assert.match(a.$('feedbackImportStatus').textContent,/바뀌/);a.click('restoreBridge');assert.equal(a.$('answerInput').value,p.attempt.transcript);a.click('importFeedbackSave');assert.equal(a.w.LabTest.getState().attempts.length,1);a.$('importFeedbackSave').onclick();assert.equal(a.w.LabTest.getState().attempts.length,1);});
test('pending ChatGPT request survives a reload and copied snapshot stays immutable',async t=>{const a=await app(t,{state:cold()});const p=await copiedRequest(a);a.click('sampleToggle');a.click('copyPrompt');await tick();assert.equal(a.w.LabTest.getState().bridge.request_id,p.request_id);assert.equal(a.w.LabTest.getState().bridge.attempt.hintUsed,false);const saved=JSON.parse(a.w.localStorage.getItem(KEY));const b=await app(t,{state:saved});assert.equal(b.w.LabTest.getState().bridge.request_id,p.request_id);b.click('importFeedbackOpen');b.$('feedbackJson').value=JSON.stringify({request_id:p.request_id,result:feedbackFixture()});b.click('importFeedbackSave');assert.equal(b.w.LabTest.getState().attempts.length,1);});
test('late imported correction cannot overwrite a newer review schedule',async t=>{const a=await app(t,{state:cold()});const p=await copiedRequest(a);const newer={due:NOW+C.DAY,lastSeen:NOW+1000,independent:2};a.w.LabTest.getState().cards.g01_01=newer;a.click('importFeedbackOpen');a.$('feedbackJson').value=JSON.stringify({request_id:p.request_id,result:feedbackFixture()});a.click('importFeedbackSave');rate(a,'again');assert.deepEqual(a.w.LabTest.getState().cards.g01_01,newer);assert.match(a.$('scheduleNote').textContent,/더 최근/);});
test('free launcher config disables the paid-mode switch',async t=>{const a=await app(t);a.w.__fetch=async()=>({ok:true,json:async()=>({server:false,free_only:true,connected:false})});await a.w.LabTest.refreshConfig();assert.equal(a.$('paidModeToggle').disabled,true);assert.equal(a.$('saveSettings').disabled,true);});
test('device speech never silently selects an online voice',async t=>{const a=await app(t,{state:cold()});a.w.speechSynthesis.getVoices=()=>[{lang:'en-US',localService:false}];a.click('sampleToggle');a.click('listenSample');assert.equal(a.w.__spoken,undefined);assert.match(a.$('statusLine').textContent,/영어 음성/);});
function youtubeSetup(a){a.fill('ytUrl','https://www.youtube.com/watch?v=M7lc1UVf-VE');a.click('ytLoad');a.fill('ytTranscript','0:12\nI was thinking of taking a break.\n0:17\nThen I came up with a different plan.');a.click('ytParse');}
test('learning shows Korean immediately while English stays hidden',async t=>{const a=await app(t);assert.ok(a.$('cardList').classList.contains('hidden'));assert.ok(!a.$('taskText').classList.contains('hidden'));a.click('toggleCards');assert.ok(!a.$('cardList').classList.contains('hidden'));a.click('beginRecall');assert.ok(!a.$('taskText').classList.contains('hidden'));});
test('YouTube source selection and phrase practice work without paid API calls',async t=>{const a=await app(t);youtubeSetup(a);assert.equal(a.d.querySelectorAll('.yt-candidate').length,2);a.d.querySelector('.yt-candidate').click();a.click('ytAddCard');const s=a.w.LabTest.getState();assert.equal(s.customCards.length,1);assert.ok(a.w.LabTest.getExercise().id.startsWith('single_yt_'));a.click('listenFirst');assert.equal(a.d.querySelectorAll('iframe').length,0);assert.ok(a.$('practiceSourceLink').href.includes('t=12s'));assert.equal(a.w.__spoken.text,'I was thinking of taking a break.');a.fill('answerInput','I was thinking of taking a break.');a.click('selfCheck');rate(a);assert.ok(s.cards[s.customCards[0].id]);assert.equal(a.calls.filter(c=>c.options.method==='POST').length,0);});
test('saved YouTube card restores in a fresh app and remains available for review',async t=>{const a=await app(t);youtubeSetup(a);a.d.querySelector('.yt-candidate').click();a.click('ytAddCard');const s=JSON.parse(a.w.localStorage.getItem(KEY));const b=await app(t,{state:s});assert.equal(b.w.LabTest.getState().customCards.length,1);assert.equal(b.w.LabTest.getExercise().card_ids[0],s.customCards[0].id);assert.equal(b.d.querySelectorAll('iframe').length,0);});
test('YouTube extraction rejects invented expression before altering saved records',async t=>{const a=await app(t);youtubeSetup(a);a.d.querySelector('.yt-candidate').click();a.fill('ytExpression','Invented quote');a.click('ytAddCard');assert.equal(a.w.LabTest.getState().customCards.length,0);assert.match(a.$('ytStatus').textContent,/원문/);});
test('manual YouTube ChatGPT extraction adds an independently labelled transfer exercise',async t=>{const a=await app(t);youtubeSetup(a);a.$('ytImportJson').value=JSON.stringify({video_id:'M7lc1UVf-VE',items:[{cue_id:'cue_0',source_text:'I was thinking of taking a break.',expression:'thinking of',meaning_ko:'~할까 생각하다',new_task_ko:'다른 직업을 알아볼까 고민이라고 말하세요.',new_sample_en:'I was thinking of looking for another job.'}]});a.click('ytImport');const s=a.w.LabTest.getState();assert.equal(s.customCards.length,1);assert.equal(s.customExercises.length,1);assert.match(s.customExercises[0].origin,/ChatGPT/);});
test('caption fetch keeps sub-second timing and never automatically displays answers',async t=>{const a=await app(t);a.w.__fetch=async(url)=>url==='/api/config'?{ok:true,json:async()=>({server:false,free_only:true,youtube_available:true,youtube_token:'test'})}:{ok:true,json:async()=>({video_id:'M7lc1UVf-VE',is_generated:true,cues:[{text:'I was thinking of going.',start:.1,duration:.3}]})};await a.w.LabTest.refreshConfig();a.fill('ytUrl','https://youtu.be/M7lc1UVf-VE');a.click('ytLoad');a.click('ytFetch');await tick();assert.match(a.$('ytTranscript').value,/00\.100/);assert.ok(a.$('ytCandidates').classList.contains('hidden'));assert.equal(a.$('ytTranscriptPanel').open,false);assert.equal(a.calls.filter(c=>c.url==='/api/grade').length,0);});
test('a blocked caption request keeps the pasted transcript and gives a manual continuation',async t=>{const a=await app(t);youtubeSetup(a);const before=a.$('ytTranscript').value;a.w.__fetch=async(url)=>url==='/api/config'?{ok:true,json:async()=>({server:false,free_only:true,youtube_available:true,youtube_token:'test'})}:{ok:false,json:async()=>({detail:'YouTube 접근 제한'})};await a.w.LabTest.refreshConfig();a.click('ytFetch');await tick();assert.equal(a.$('ytTranscript').value,before);assert.match(a.$('ytStatus').textContent,/붙여넣기/);});
test('online device voice is allowed only after user opts in',async t=>{const a=await app(t,{state:cold()});a.w.speechSynthesis.getVoices=()=>[{lang:'en-US',name:'Online English',voiceURI:'online-en',localService:false}];a.click('refreshVoices');a.click('testVoice');assert.equal(a.w.__spoken,undefined);a.$('allowOnlineVoice').checked=true;a.$('allowOnlineVoice').dispatchEvent(new a.w.Event('change'));a.click('testVoice');assert.equal(a.w.__spoken.voice.voiceURI,'online-en');assert.equal(a.calls.filter(c=>c.options.method==='POST').length,0);});
test('microphone starts without loading a blocked YouTube iframe',async t=>{const a=await app(t);youtubeSetup(a);a.click('ytPlay');assert.ok(a.$('ytPlay').href.includes('youtube.com/watch'));assert.equal(a.d.querySelectorAll('iframe').length,0);a.click('recordBtn');await tick();assert.equal(a.d.querySelectorAll('iframe').length,0);a.click('stopBtn');a.w.__recorder.finish();});

test('saved video expressions appear in the default library and new daily session',async t=>{const a=await app(t);youtubeSetup(a);a.d.querySelector('.yt-candidate').click();a.click('ytAddCard');const id=a.w.LabTest.getState().customCards[0].id;a.click('sessionStart');assert.equal(a.w.LabTest.getState().session.ids[0],id);a.d.querySelector('[data-view="library"]').click();a.$('librarySource').value='youtube';a.$('librarySource').dispatchEvent(new a.w.Event('change'));assert.equal(a.d.querySelectorAll('.library-card').length,1);assert.match(a.$('libraryList').textContent,/내가 저장한 영상 표현/);assert.ok(a.$('coreOnly').checked);});
test('late voice loading refreshes selection and a test sentence does not count as an expression hint',async t=>{const a=await app(t,{state:cold()});a.w.speechSynthesis.getVoices=()=>[];a.click('refreshVoices');a.click('testVoice');assert.equal(a.w.__spoken,undefined);a.w.speechSynthesis.getVoices=()=>[{lang:'en-US',name:'Installed English',voiceURI:'local-en',localService:true}];a.w.__speechEvents.voiceschanged();assert.equal(a.$('voiceSelect').value,'local-en');a.click('testVoice');a.w.__spoken.onstart();assert.equal(a.w.LabTest.isAssisted(),false);a.click('listenFirst');a.w.__spoken.onstart();assert.equal(a.w.LabTest.isAssisted(),true);});

const SCREENSHOT_SENTENCE="Has that been such a surprise to see how like massive it's gotten just right when your album comes out.";
const SCREENSHOT_CAPTION="It's like no. "+SCREENSHOT_SENTENCE+" It's crazy. I was just saying even";
async function autoScreenshot(a){a.fill('ytUrl','https://youtu.be/M7lc1UVf-VE');a.click('ytLoad');a.fill('ytTranscript','0:02\n'+SCREENSHOT_SENTENCE);a.click('ytFromTranscript');await tick();}
async function manyCaptions(a,n=65){a.fill('ytUrl','https://youtu.be/M7lc1UVf-VE');a.click('ytLoad');a.fill('ytTranscript',Array.from({length:n},(_,i)=>a.w.LabYouTube.captionStamp(i*10)+'\nI would like to tell you about project number '+i+'.').join('\n'));a.click('ytFromTranscript');await tick();}
test('screenshot creates a whole sentence without handwritten fields or tiny duplicate cards',async t=>{const a=await app(t);await autoScreenshot(a);const s=a.w.LabTest.getState();assert.equal(s.customCards.length,1);assert.equal(s.customCards[0].expression,SCREENSHOT_SENTENCE);for(const id of ['ytExpression','ytMeaning','ytSituation'])assert.equal(a.$(id).value,'');a.click('ytAutoPractice');await tick();a.click('beginRecall');a.fill('answerInput',SCREENSHOT_SENTENCE);a.click('selfCheck');assert.ok(a.$('feedbackContent').textContent.includes(SCREENSHOT_SENTENCE));rate(a);a.click('sessionNext');assert.equal(s.session.index,1);assert.equal(a.calls.filter(c=>c.options.method==='POST').length,0);});
test('all 223 sentences are extracted and translated at once, with display paging only',async t=>{const a=await app(t);await manyCaptions(a,223);const s=a.w.LabTest.getState();assert.equal(s.customCards.length,223);assert.equal(a.$('ytAutoCount'),null);assert.equal(a.$('ytAutoMore'),null);assert.match(a.$('ytAutoStatus').textContent,/전체 223개 문장 추출 완료/);assert.equal(a.d.querySelectorAll('.auto-expression-card').length,10);assert.match(a.$('ytShowMore').textContent,/전체 223/);a.click('ytShowMore');await tick();assert.equal(a.d.querySelectorAll('.auto-expression-card').length,20);assert.equal(s.customCards.length,223);assert.equal(a.w.__translatedTexts.length,223);assert.equal(s.customCards.at(-1).expression,'I would like to tell you about project number 222.');a.click('ytAutoPractice');await tick();assert.equal(s.session.ids.length,223);assert.equal(new Set(s.session.ids).size,223);const restored=C.migrateState(JSON.parse(a.w.localStorage.getItem(KEY)),new Map(a.w.LAB_DATA.cards.map(c=>[c.id,c])));assert.equal(restored.session.ids.length,223);assert.equal(a.calls.filter(c=>c.options.method==='POST').length,0);});
test('new deck and sequence survive reopening without loss of recorded review',async t=>{const a=await app(t);await manyCaptions(a,25);a.click('ytAutoPractice');await tick();const s=a.w.LabTest.getState();s.cards[s.customCards[0].id]={due:NOW+86400000,independent:1};a.click('sessionSkip');const b=await app(t,{state:JSON.parse(a.w.localStorage.getItem(KEY))});assert.equal(b.w.LabTest.getState().session.index,1);assert.equal(b.w.LabTest.getState().customCards.length,25);assert.equal(b.d.querySelectorAll('.auto-expression-card').length,10);assert.equal(b.w.LabTest.getState().cards[s.customCards[0].id].due,NOW+86400000);});
test('same transcript extraction does not duplicate sentences or reset schedule',async t=>{const a=await app(t);await autoScreenshot(a);const s=a.w.LabTest.getState(),id=s.customCards[0].id;s.cards[id]={due:NOW+86400000,independent:1};a.click('ytAutoExtract');await tick();assert.equal(s.customCards.length,1);assert.equal(s.customExercises.length,0);assert.equal(s.cards[id].due,NOW+86400000);});
async function readyAI(a,extract){a.w.__fetch=async(url,options)=>{if(url==='/api/config')return {ok:true,json:async()=>({server:false,free_only:true,youtube_available:true,youtube_token:'fixture-token',local_ai:true})};if(url==='/local-ai/status')return {ok:true,json:async()=>({running:true,ready:true,model:'qwen3.5:4b',setup:{}})};if(url==='/youtube/extract')return extract(options);throw Error('Unexpected route '+url);};await a.w.LabTest.refreshConfig();}
function aiLesson(){return {video_id:'M7lc1UVf-VE',engine:'local_ai',items:[{cue_id:'cue_0',source_text:'This song brings back good memories.',expression:'This song brings back good memories.',meaning_ko:'이 노래를 들으면 좋은 추억이 떠올라요.',use_case_ko:'노래를 듣고 좋은 추억이 떠오른다고 말하기',note_ko:'문장 전체의 회상을 연습합니다.',new_task_ko:'사진이 학창 시절의 추억을 떠올리게 한다고 말하기',new_sample_en:'This photo brings back memories of school.'}]};}
async function localCaption(a){a.fill('ytUrl','https://youtu.be/M7lc1UVf-VE');a.click('ytLoad');a.fill('ytTranscript','0:10\nThis song brings back good memories.');a.click('ytFromTranscript');await tick();}
test('local AI adds full sentence meaning and a separately aligned transfer exercise',async t=>{const a=await app(t);await readyAI(a,async()=>({ok:true,json:async()=>aiLesson()}));await localCaption(a);a.click('ytEnrich');await tick();const s=a.w.LabTest.getState(),c=s.customCards[0];assert.equal(c.expression,aiLesson().items[0].expression);assert.equal(c.meaning_source,'local_ai');assert.equal(c.practice_sample_en,c.expression);a.d.querySelector('.auto-transfer').click();assert.equal(a.w.LabTest.getExercise().sample_en,aiLesson().items[0].new_sample_en);assert.equal(a.w.LabTest.getExercise().task_ko,aiLesson().items[0].new_task_ko);a.click('ytAutoExtract');await tick();assert.equal(c.meaning_source,'local_ai');assert.equal(s.customCards.length,1);assert.equal(a.calls.filter(c=>c.url==='/youtube/extract').length,1);assert.equal(a.calls.filter(c=>/^\/api\/(grade|generate|transcribe)/.test(c.url)).length,0);});
test('cancelled enrichment ignores a late model answer while retaining immediately usable sentences',async t=>{const a=await app(t);let finish;await readyAI(a,()=>new Promise(r=>finish=r));await localCaption(a);a.click('ytEnrich');await tick();assert.equal(a.$('ytAutoCancel').classList.contains('hidden'),false);a.click('ytAutoCancel');finish({ok:true,json:async()=>aiLesson()});await tick();assert.equal(a.w.LabTest.getState().customCards.length,1);assert.equal(a.w.LabTest.getState().customCards[0].meaning_source,'none');assert.equal(a.$('recordBtn').disabled,false);assert.match(a.$('ytAutoStatus').textContent,/중단/);});
test('pending meaning cannot attach to changed captions',async t=>{const a=await app(t);let finish;await readyAI(a,()=>new Promise(r=>finish=r));await localCaption(a);a.click('ytEnrich');await tick();a.$('ytTranscript').value='0:10\nChanged caption.';finish({ok:true,json:async()=>aiLesson()});await tick();assert.equal(a.w.LabTest.getState().customCards[0].meaning_source,'none');assert.match(a.$('ytAutoStatus').textContent,/바뀌/);});
test('AI is optional for unknown sentences and unavailable AI keeps the deck usable',async t=>{const a=await app(t);await localCaption(a);assert.equal(a.w.LabTest.getState().customCards.length,1);assert.equal(a.$('ytCandidates').open,false);a.click('ytEnrich');await tick();assert.equal(a.$('localAISetup').open,true);a.click('ytAutoPractice');await tick();assert.equal(a.w.LabTest.getState().session.ids.length,1);});
test('enrichment batches a large deck and preserves successful batches on later failure',async t=>{const a=await app(t);let calls=0;await readyAI(a,async options=>{const p=JSON.parse(options.body);assert.ok(p.cues.length<=4);assert.equal(p.count,p.cues.length);calls++;if(calls===2)return {ok:false,json:async()=>({detail:'fixture failure'})};return {ok:true,json:async()=>({video_id:p.video_id,engine:'local_ai',items:p.cues.map(c=>({...aiLesson().items[0],cue_id:c.id,expression:c.text,source_text:c.text}))})};});await manyCaptions(a,10);a.click('ytEnrich');await tick();await tick();const s=a.w.LabTest.getState();assert.equal(calls,2);assert.equal(s.customCards.length,10);assert.equal(s.customCards.filter(c=>c.meaning_source==='local_ai').length,4);assert.match(a.$('ytAutoStatus').textContent,/fixture failure/);a.click('ytAutoPractice');await tick();assert.equal(s.session.ids.length,10);});
test('untimed sentence listening uses device speech and keeps original time explicitly unknown',async t=>{const a=await app(t);a.fill('ytUrl','https://youtu.be/M7lc1UVf-VE');a.click('ytLoad');a.fill('ytTranscript','I was thinking of taking a break.');a.click('ytFromTranscript');await tick();const c=a.w.LabTest.getState().customCards[0];a.click('ytAutoPractice');await tick();a.click('listenFirst');assert.equal(c.media.start,null);assert.equal(a.w.__spoken.text,c.expression);assert.equal(a.d.querySelectorAll('iframe').length,0);assert.match(a.$('practiceSourceLink').textContent,/시간 정보 없음/);});
test('a YouTube link loads captions and prepares sentence study in one action',async t=>{const a=await app(t);a.w.__fetch=async(url)=>url==='/api/config'?{ok:true,json:async()=>({server:false,free_only:true,youtube_available:true,youtube_token:'fixture-token'})}:{ok:true,json:async()=>({video_id:'M7lc1UVf-VE',cues:[{text:SCREENSHOT_CAPTION,start:2,duration:12}]})};await a.w.LabTest.refreshConfig();a.fill('ytUrl','https://youtu.be/M7lc1UVf-VE');a.click('ytAutoBuild');await tick();assert.equal(a.w.LabTest.getState().customCards.length,4);assert.equal(a.w.LabTest.getState().customCards[1].expression,SCREENSHOT_SENTENCE);assert.equal(a.calls.filter(c=>c.url==='/youtube/transcript').length,1);});
test('source buttons expose canonical timestamp links and no blocked embedding request',async t=>{const a=await app(t);await autoScreenshot(a);const link=a.d.querySelector('.auto-source');assert.equal(link.href,'https://www.youtube.com/watch?v=M7lc1UVf-VE&t=2s');assert.equal(link.target,'_blank');a.d.querySelector('.auto-file').click();assert.equal(a.d.querySelectorAll('iframe').length,0);assert.match(a.$('ytPlayer').textContent,/내장 YouTube 재생 대신/);assert.equal(a.calls.filter(c=>c.options.method==='POST').length,0);});
test('sentence speech and hide toggle work without marking an unrelated lesson as heard',async t=>{const a=await app(t,{state:cold()});await autoScreenshot(a);a.d.querySelector('.auto-tts').click();assert.equal(a.w.__spoken.text,SCREENSHOT_SENTENCE);a.w.__spoken.onstart();assert.equal(a.w.LabTest.getState().exposures.g01_01,undefined);const hide=a.d.querySelector('.auto-hide');hide.click();assert.equal(hide.getAttribute('aria-pressed'),'true');assert.ok(a.d.querySelector('.chunk-answer').classList.contains('hidden'));hide.click();assert.equal(hide.getAttribute('aria-pressed'),'false');});
function attachSource(a){Object.defineProperty(a.$('ytMediaFile'),'files',{configurable:true,value:[new a.w.File(['fixture'],'source.mp4',{type:'video/mp4'})]});a.$('ytMediaFile').dispatchEvent(new a.w.Event('change'));a.d.querySelector('.auto-file').click();return a.$('ytPlayer').querySelector('video');}
test('local source file seeks subtitle bounds, pauses at end and stops before recording without upload',async t=>{const a=await app(t);await autoScreenshot(a);const m=attachSource(a);assert.ok(m);Object.defineProperty(m,'duration',{value:100});m.dispatchEvent(new a.w.Event('loadedmetadata'));assert.equal(m.currentTime,2);assert.equal(m.__plays,1);m.currentTime=10;m.dispatchEvent(new a.w.Event('timeupdate'));assert.ok(m.__pauses);a.click('recordBtn');await tick();assert.equal(a.$('ytPlayer').children.length,0);assert.ok(m.__pauses>=2);a.click('stopBtn');a.w.__recorder.finish();assert.equal(a.calls.filter(c=>c.options.method==='POST').length,0);});
test('local source repeat restarts at source start and rejects out-of-range files',async t=>{const a=await app(t);await autoScreenshot(a);let m=attachSource(a);Object.defineProperty(m,'duration',{value:100});m.dispatchEvent(new a.w.Event('loadedmetadata'));a.$('ytPlayer').querySelector('input').checked=true;m.currentTime=10;m.dispatchEvent(new a.w.Event('timeupdate'));assert.equal(m.currentTime,2);assert.equal(m.__plays,2);m=attachSource(a);Object.defineProperty(m,'duration',{value:1});m.dispatchEvent(new a.w.Event('loadedmetadata'));assert.equal(m.__plays,undefined);assert.match(a.$('ytPlayer').textContent,/벗어/);});
test('changing video releases source file and edited captions invalidate the previous deck',async t=>{const a=await app(t);await autoScreenshot(a);let revoked=0;a.w.URL.revokeObjectURL=()=>revoked++;attachSource(a);a.fill('ytUrl','https://youtu.be/dQw4w9WgXcQ');a.click('ytLoad');assert.equal(revoked,1);assert.equal(a.$('ytPlayer').children.length,0);assert.equal(a.$('ytAutoPractice').classList.contains('hidden'),true);a.fill('ytTranscript','We should go back there next summer.');a.click('ytFromTranscript');await tick();assert.equal(a.$('ytAutoPractice').classList.contains('hidden'),false);a.fill('ytTranscript','We should travel somewhere else this year.');assert.equal(a.$('ytAutoPractice').classList.contains('hidden'),true);});
test('reopening a saved sentence deck and viewing English counts as a current hint',async t=>{const a=await app(t);await autoScreenshot(a);const s=JSON.parse(a.w.localStorage.getItem(KEY)),id=s.customCards[0].id;s.exposures[id]=NOW-2*C.DAY;s.cards[id]={due:NOW-1,independent:1};const b=await app(t,{state:s});assert.equal(b.w.LabTest.getState().exposures[id],NOW-2*C.DAY);b.d.querySelector('[data-view="youtube"]').click();assert.equal(b.w.LabTest.getState().exposures[id],NOW);b.click('ytAutoPractice');await tick();b.click('beginRecall');b.fill('answerInput',SCREENSHOT_SENTENCE);b.click('selfCheck');rate(b);assert.equal(b.w.LabTest.getState().attempts[0].hintUsed,true);assert.equal(b.w.LabTest.getState().cards[id].independent,1);});

// v2.5: the Translator and speech engines below are test doubles, not real audio or translation.
const KO_LINES=[['I was thinking of taking a break.','잠깐 쉴까 생각하고 있었어요.'],['Then I came up with a different plan.','그러다가 다른 계획을 생각해 냈어요.'],['I had no idea the cafe was closed.','카페가 문을 닫았다는 사실을 전혀 몰랐어요.']];
async function koreanDeck(a){a.d.querySelector('[data-view="youtube"]').click();a.w.__translate=async text=>KO_LINES.find(x=>x[0]===text)?.[1]||fixtureKorean(text);a.fill('ytUrl','https://youtu.be/M7lc1UVf-VE');a.click('ytLoad');a.fill('ytTranscript',KO_LINES.map((x,i)=>a.w.LabYouTube.captionStamp(i*10)+'\n'+x[0]).join('\n'));a.click('ytFromTranscript');await tick();}
function paragraphFixture(rows){
 const ko=['주말에 동네 행사를 열까 생각하고 있었어요.','그래서 친구가 온라인으로 진행하자는 다른 계획을 생각해 냈어요.','하지만 공간을 예약해야 한다는 사실을 전혀 몰랐어요.'];
 const en=['I was thinking of hosting a neighborhood event this weekend.','So my friend came up with a different plan to hold it online.','I had no idea we needed to reserve a venue.'];
 return {title:'동네 행사 계획',task_ko:[ko[0],ko[2],ko[1]].join(' '),sample_en:[en[0],en[2],en[1]].join(' '),situation_ko:'동네 행사를 온라인으로 바꾸기',alignment:rows.map((r,i)=>({card_id:r.id,source_expression:['I was thinking of','came up with','I had no idea'][i],korean_cue:ko[i],english_use:en[i]}))};
}
test('each audio button speaks only its own complete sentence and cancels the previous sentence',async t=>{const a=await app(t);await koreanDeck(a);const buttons=a.d.querySelectorAll('.auto-tts'),before=a.w.__speechCancels,requests=a.calls.length;buttons[0].click();assert.equal(a.w.__spokenAll.at(-1).text,KO_LINES[0][0]);buttons[1].click();assert.equal(a.w.__spokenAll.at(-1).text,KO_LINES[1][0]);assert.equal(a.w.__spokenAll.length,2);assert.ok(a.w.__speechCancels>=before+2);assert.equal(a.calls.length,requests);assert.equal(a.d.querySelectorAll('iframe').length,0);assert.equal(a.d.querySelector('.original-source').open,false);a.w.__spoken.onend();assert.match(a.$('ytSpeechStatus').textContent,/마쳤/);});
test('sentence audio honors the voice and speed chosen beside the extracted cards',async t=>{const a=await app(t);await koreanDeck(a);a.w.speechSynthesis.getVoices=()=>[{lang:'en-US',name:'Local A',voiceURI:'a',localService:true},{lang:'en-GB',name:'Local B',voiceURI:'b',localService:true}];a.click('ytVoiceRefresh');a.$('ytVoiceSelect').value='b';a.$('ytVoiceSelect').dispatchEvent(new a.w.Event('change'));a.$('ytSpeechRate').value='0.75';a.$('ytSpeechRate').dispatchEvent(new a.w.Event('change'));a.d.querySelector('.auto-tts').click();assert.equal(a.w.__spoken.voice.voiceURI,'b');assert.equal(a.w.__spoken.rate,.75);a.click('ytSpeechStop');assert.match(a.$('ytSpeechStatus').textContent,/멈췄/);});
test('a sentence exercise starts with its complete Korean version and hidden English answer',async t=>{const a=await app(t);await koreanDeck(a);a.d.querySelector('.auto-practice').click();await tick();assert.equal(a.$('taskText').textContent,KO_LINES[0][1]);assert.equal(a.$('taskText').classList.contains('hidden'),false);assert.equal(a.$('cardList').classList.contains('hidden'),true);assert.equal(a.$('sampleBox').classList.contains('hidden'),true);assert.ok(a.d.querySelector('.task-panel').compareDocumentPosition(a.d.querySelector('.lesson-panel'))&a.w.Node.DOCUMENT_POSITION_FOLLOWING);a.fill('answerInput',KO_LINES[0][0]);a.click('selfCheck');rate(a);assert.equal(a.w.LabTest.getState().attempts[0].task_ko,KO_LINES[0][1]);});
test('on-device Korean preparation makes no paid request and cached versions survive reopening',async t=>{const a=await app(t);await koreanDeck(a);const saved=JSON.parse(a.w.localStorage.getItem(KEY));assert.equal(Object.keys(saved.translations).length,3);assert.equal(a.calls.filter(c=>c.options.method==='POST').length,0);const b=await app(t,{state:saved});b.d.querySelector('[data-view="youtube"]').click();b.click('ytAutoPractice');await tick();assert.equal(b.$('taskText').textContent,KO_LINES[0][1]);assert.equal(b.w.__translationCreates,undefined);});
test('source paragraph uses all selected sentences with Korean first and matching English comparison',async t=>{const a=await app(t);await koreanDeck(a);a.click('ytParagraph');await tick();const e=a.w.LabTest.getExercise();assert.equal(e.card_ids.length,3);assert.equal(e.paragraph_mode,'source');assert.equal(a.$('taskText').textContent,KO_LINES.map(x=>x[1]).join(' '));assert.equal(a.$('cardList').classList.contains('hidden'),true);assert.equal(a.$('sampleBox').classList.contains('hidden'),true);a.fill('answerInput',e.sample_en);a.click('selfCheck');rate(a);const s=a.w.LabTest.getState();assert.equal(s.attempts[0].card_ids.length,3);assert.equal(s.attempts[0].sample_en,e.sample_en);for(const id of e.card_ids)assert.ok(s.cards[id]);const b=await app(t,{state:JSON.parse(a.w.localStorage.getItem(KEY))});assert.equal(b.w.LabTest.getExercise().paragraph_mode,'source');assert.equal(b.$('taskText').textContent,e.task_ko);});
test('paragraph selection uses the requested cards instead of silently practicing only the first',async t=>{const a=await app(t);await koreanDeck(a);const picks=a.d.querySelectorAll('.paragraph-pick');picks[0].click();picks[2].click();a.click('ytParagraph');await tick();const e=a.w.LabTest.getExercise(),s=a.w.LabTest.getState();assert.deepEqual(Array.from(e.card_ids),[s.customCards[0].id,s.customCards[2].id]);assert.equal(a.$('taskText').textContent,KO_LINES[0][1]+' '+KO_LINES[2][1]);});
test('a local AI paragraph reuses learned sentence structures and compares the aligned new situation',async t=>{const a=await app(t);await koreanDeck(a);let expected;a.w.__fetch=async(url,options)=>{if(url==='/api/config')return {ok:true,json:async()=>({server:false,free_only:true,local_ai:true,youtube_available:true,youtube_token:'token'})};if(url==='/local-ai/status')return {ok:true,json:async()=>({running:true,ready:true,setup:{}})};if(url==='/local-ai/paragraph'){expected=paragraphFixture(JSON.parse(options.body).cards);return {ok:true,json:async()=>({engine:'local_ai',paragraph:expected})};}throw Error('Unexpected '+url);};await a.w.LabTest.refreshConfig();a.click('ytParagraph');await tick();const e=a.w.LabTest.getExercise();assert.equal(e.paragraph_mode,'local_ai');assert.equal(a.$('taskText').textContent,expected.task_ko);assert.equal(a.$('sampleBox').classList.contains('hidden'),true);a.fill('answerInput',expected.sample_en);a.click('selfCheck');assert.ok(a.$('feedbackContent').textContent.includes(expected.sample_en));assert.ok(!a.$('feedbackContent').textContent.includes(KO_LINES[0][0]));assert.equal(a.calls.filter(c=>/^\/api\/(generate|grade|transcribe)/.test(c.url)).length,0);});
test('an invalid generated paragraph falls back to grounded source content without saving the invalid answer',async t=>{const a=await app(t);await koreanDeck(a);a.w.__fetch=async(url,options)=>url==='/api/config'?{ok:true,json:async()=>({server:false,free_only:true,local_ai:true})}:url==='/local-ai/status'?{ok:true,json:async()=>({running:true,ready:true,setup:{}})}:{ok:true,json:async()=>({engine:'local_ai',paragraph:{...paragraphFixture(JSON.parse(options.body).cards),alignment:[]}})};await a.w.LabTest.refreshConfig();a.click('ytParagraph');await tick();assert.equal(a.w.LabTest.getExercise().paragraph_mode,'source');assert.match(a.$('statusLine').textContent,/완료하지 못해/);assert.equal(a.w.LabTest.getState().customExercises.filter(e=>e.paragraph_mode==='local_ai').length,0);});
test('missing translation engines give an explicit setup state without an invented Korean version',async t=>{const a=await app(t,{translator:false});await autoScreenshot(a);assert.equal(Object.keys(a.w.LabTest.getState().translations).length,0);assert.match(a.$('ytKoStatus').textContent,/한국어 자동 번역/);a.d.querySelector('.auto-tts').click();assert.equal(a.w.__spoken.text,SCREENSHOT_SENTENCE);const before=a.w.LabTest.getExercise().id;a.click('ytAutoPractice');await tick();assert.equal(a.w.LabTest.getExercise().id,before);});
test('translation cancellation preserves finished sentences and ignores a late translated result',async t=>{const a=await app(t);a.d.querySelector('[data-view="youtube"]').click();let finish;a.w.__translate=async text=>text===KO_LINES[1][0]?new Promise(r=>finish=r):KO_LINES[0][1];a.fill('ytUrl','https://youtu.be/M7lc1UVf-VE');a.click('ytLoad');a.fill('ytTranscript','0:00\n'+KO_LINES[0][0]+'\n0:10\n'+KO_LINES[1][0]);a.click('ytFromTranscript');await tick();assert.equal(Object.keys(a.w.LabTest.getState().translations).length,1);a.click('ytKoCancel');finish(KO_LINES[1][1]);await tick();assert.equal(Object.keys(a.w.LabTest.getState().translations).length,1);assert.equal(a.$('recordBtn').disabled,false);assert.equal(a.w.__translatorDestroyed,true);});
test('caption changes while translating cannot attach a late Korean result to the changed source',async t=>{const a=await app(t);a.d.querySelector('[data-view="youtube"]').click();let finish;a.w.__translate=()=>new Promise(r=>finish=r);a.fill('ytUrl','https://youtu.be/M7lc1UVf-VE');a.click('ytLoad');a.fill('ytTranscript','0:00\n'+KO_LINES[0][0]);a.click('ytFromTranscript');await tick();a.$('ytTranscript').value='0:00\nWe changed the transcript completely today.';finish(KO_LINES[0][1]);await tick();assert.equal(Object.keys(a.w.LabTest.getState().translations).length,0);assert.match(a.$('ytKoStatus').textContent,/바뀌/);});
test('library selection of multiple learned sentences creates one Korean paragraph',async t=>{const a=await app(t);a.d.querySelector('[data-view="library"]').click();const boxes=a.d.querySelectorAll('.pick-card');boxes[0].click();boxes[1].click();a.click('practicePicked');await tick();const e=a.w.LabTest.getExercise();assert.equal(e.card_ids.length,2);assert.equal(e.paragraph_mode,'source');assert.equal(a.$('taskText').classList.contains('hidden'),false);assert.equal(a.$('sampleBox').classList.contains('hidden'),true);});
test('without browser translation the free local translator supplies exact Korean versions automatically',async t=>{const a=await app(t,{translator:false});a.w.__fetch=async(url,options)=>{if(url==='/api/config')return {ok:true,json:async()=>({server:false,free_only:true,local_ai:true,youtube_available:true,youtube_token:'local-token'})};if(url==='/local-ai/status')return {ok:true,json:async()=>({running:true,ready:true,setup:{}})};if(url==='/local-ai/translate'){const rows=JSON.parse(options.body).cards;assert.equal(options.headers['X-Local-Token'],'local-token');return {ok:true,json:async()=>({engine:'local_ai',translations:rows.map(c=>({card_id:c.id,source_en:c.sentence_en,korean_text:KO_LINES.find(x=>x[0]===c.sentence_en)[1],engine:'local_ai'}))})};}throw Error('Unexpected '+url);};await a.w.LabTest.refreshConfig();await koreanDeck(a);const s=a.w.LabTest.getState();assert.equal(Object.keys(s.translations).length,3);assert.equal(Object.values(s.translations)[0].engine,'local_ai');a.click('ytAutoPractice');await tick();assert.equal(a.$('taskText').textContent,KO_LINES[0][1]);assert.equal(a.calls.filter(c=>/^\/api\/(generate|grade|transcribe)/.test(c.url)).length,0);});

// v2.5.1 regressions: reproduce online-only voices in the YouTube view and act on selections there.
test('YouTube online-only voices offer a visible permission and resume exactly the pending sentence',async t=>{
 const a=await app(t);await koreanDeck(a);
 a.w.speechSynthesis.getVoices=()=>[{lang:'en-US',name:'Online English',voiceURI:'online-en',localService:false}];
 a.click('ytVoiceRefresh');
 assert.equal(a.$('practiceView').classList.contains('hidden'),true);
 assert.equal(a.$('ytAllowOnlineVoice').closest('.hidden'),null);
 assert.match(a.$('ytVoiceSelect').textContent,/허용 필요/);
 assert.equal(a.$('ytAudioControls').querySelectorAll('[role="status"]').length,1);
 assert.equal(a.$('ytVoiceNote'),null);
 a.d.querySelectorAll('.auto-tts')[1].click();assert.equal(a.w.__spoken,undefined);
 assert.match(a.$('ytSpeechStatus').textContent,/온라인 영어 음성 사용/);
 assert.equal(a.d.activeElement,a.$('ytAllowOnlineVoice'));
 const before=a.calls.length;a.$('ytAllowOnlineVoice').click();
 assert.equal(a.w.__spokenAll.length,1);assert.equal(a.w.__spoken.text,KO_LINES[1][0]);
 assert.equal(a.w.__spoken.voice.voiceURI,'online-en');assert.equal(a.$('allowOnlineVoice').checked,true);
 assert.equal(a.w.LabTest.getState().voice.online,true);assert.equal(a.calls.length,before);
 a.w.__spoken.onstart();assert.match(a.$('ytSpeechStatus').textContent,/읽고 있습니다/);
 a.w.__spoken.onend();assert.match(a.$('ytSpeechStatus').textContent,/마쳤/);
 const saved=JSON.parse(a.w.localStorage.getItem(KEY)),b=await app(t,{state:saved});
 assert.equal(b.$('ytAllowOnlineVoice').checked,true);assert.equal(b.$('allowOnlineVoice').checked,true);
});
test('voice permission only replays the latest blocked sentence and stop clears that request',async t=>{
 const a=await app(t);await koreanDeck(a);a.w.speechSynthesis.getVoices=()=>[{lang:'en-US',voiceURI:'online',localService:false}];
 const buttons=a.d.querySelectorAll('.auto-tts');buttons[0].click();buttons[2].click();a.$('ytAllowOnlineVoice').click();
 assert.equal(a.w.__spokenAll.length,1);assert.equal(a.w.__spoken.text,KO_LINES[2][0]);
 a.$('ytAllowOnlineVoice').click();assert.equal(a.$('allowOnlineVoice').checked,false);
 buttons[0].click();a.click('ytSpeechStop');a.$('ytAllowOnlineVoice').click();assert.equal(a.w.__spokenAll.length,1);
});
test('leaving the video clears pending permission playback and does not speak an old sentence',async t=>{
 const a=await app(t);await koreanDeck(a);a.w.speechSynthesis.getVoices=()=>[{lang:'en-US',voiceURI:'online',localService:false}];
 a.d.querySelector('.auto-tts').click();a.d.querySelector('[data-view="practice"]').click();a.$('allowOnlineVoice').click();
 assert.equal(a.w.__spokenAll.length,0);assert.equal(a.$('ytAllowOnlineVoice').checked,true);
});
test('late online voices appear in the YouTube selector after permission without a settings detour',async t=>{
 const a=await app(t);await koreanDeck(a);a.w.speechSynthesis.getVoices=()=>[];a.click('ytVoiceRefresh');
 a.$('ytAllowOnlineVoice').click();a.click('ytTestVoice');assert.equal(a.w.__spoken,undefined);
 a.w.speechSynthesis.getVoices=()=>[{lang:'en-US',name:'Late English',voiceURI:'late',localService:false}];
 a.w.__speechEvents.voiceschanged();assert.equal(a.$('ytVoiceSelect').value,'late');a.click('ytTestVoice');
 assert.equal(a.w.__spoken.voice.voiceURI,'late');assert.match(a.$('ytSpeechStatus').textContent,/시작합니다/);
 a.w.__spoken.onerror({error:'network'});assert.match(a.$('ytSpeechStatus').textContent,/인터넷 연결/);
 assert.doesNotMatch(a.$('ytSpeechStatus').textContent,/원본 영상/);
});
test('a speech request that never starts produces an actionable message and ignores late events',async t=>{
 const a=await app(t);await koreanDeck(a);const original=a.w.setTimeout;let stalled;
 a.w.setTimeout=(fn,ms,...args)=>{if(ms===8000){stalled=fn;return 0;}return original(fn,ms,...args);};
 a.d.querySelector('.auto-tts').click();const utterance=a.w.__spoken;assert.ok(stalled);stalled();
 assert.match(a.$('ytSpeechStatus').textContent,/시작하지 못했/);utterance.onstart();utterance.onend();
 assert.match(a.$('ytSpeechStatus').textContent,/시작하지 못했/);
});
test('paragraph checkboxes immediately show selected cards and a working bottom start action',async t=>{
 const a=await app(t);await koreanDeck(a);const picks=a.d.querySelectorAll('.paragraph-pick');
 assert.equal(a.$('ytParagraphDock').classList.contains('hidden'),true);picks[0].click();
 assert.equal(a.$('ytParagraphDock').closest('.hidden'),null);assert.match(a.$('ytParagraphCount').textContent,/1개/);
 assert.equal(a.$('ytParagraphStart').disabled,true);assert.equal(picks[0].closest('article').classList.contains('is-selected'),true);
 assert.match(picks[0].closest('label').textContent,/선택됨/);picks[2].click();
 assert.equal(a.$('ytParagraphStart').disabled,false);assert.match(a.$('ytParagraphStart').textContent,/선택한 2문장/);
 assert.equal(a.$('ytParagraphChips').children.length,2);a.click('ytParagraphStart');await tick();
 const e=a.w.LabTest.getExercise(),s=a.w.LabTest.getState();
 assert.deepEqual(Array.from(e.card_ids),[s.customCards[0].id,s.customCards[2].id]);
 assert.equal(a.$('practiceView').classList.contains('hidden'),false);assert.equal(a.$('youtubeView').classList.contains('hidden'),true);
 assert.equal(a.$('taskText').textContent,KO_LINES[0][1]+' '+KO_LINES[2][1]);assert.equal(a.$('sampleBox').classList.contains('hidden'),true);
 assert.match(a.$('ytKoStatus').textContent,/준비 완료/);assert.match(a.$('ytParagraphStatus').textContent,/준비 완료/);
});
test('paragraph chips and clear action keep the checkboxes, highlight and selected IDs in sync',async t=>{
 const a=await app(t);await koreanDeck(a);const picks=a.d.querySelectorAll('.paragraph-pick');picks[0].click();picks[1].click();
 a.$('ytParagraphChips').firstElementChild.click();assert.equal(picks[0].checked,false);assert.equal(picks[1].checked,true);
 assert.equal(picks[0].closest('article').classList.contains('is-selected'),false);assert.equal(a.$('ytParagraphStart').disabled,true);
 a.click('ytParagraphClear');assert.equal(picks[1].checked,false);assert.equal(a.$('ytParagraphDock').classList.contains('hidden'),true);
 assert.equal(a.$('ytParagraph').disabled,false);assert.equal(a.$('youtubeView').classList.contains('has-paragraph-selection'),false);
});
test('a sixth paragraph selection is rejected with feedback beside the start button',async t=>{
 const a=await app(t);await manyCaptions(a,7);const picks=a.d.querySelectorAll('.paragraph-pick');
 for(let i=0;i<6;i++)picks[i].click();assert.equal(picks[5].checked,false);assert.equal(a.$('ytParagraphChips').children.length,5);
 assert.match(a.$('ytParagraphStatus').textContent,/최대 5문장/);assert.match(a.$('ytParagraphStart').textContent,/선택한 5문장/);
});
test('paragraph preparation shows progress and can be cancelled directly from the selection bar',async t=>{
 const a=await app(t);await koreanDeck(a);let finish;
 a.w.__fetch=async(url,options)=>url==='/api/config'?{ok:true,json:async()=>({server:false,free_only:true,local_ai:true,youtube_token:'token'})}:url==='/local-ai/status'?{ok:true,json:async()=>({running:true,ready:true,setup:{}})}:new Promise(r=>finish=()=>r({ok:true,json:async()=>({engine:'local_ai',paragraph:paragraphFixture(JSON.parse(options.body).cards)})}));
 await a.w.LabTest.refreshConfig();const picks=a.d.querySelectorAll('.paragraph-pick');picks[0].click();picks[1].click();
 a.click('ytParagraphStart');await tick();assert.match(a.$('ytParagraphStatus').textContent,/문단/);
 assert.equal(a.$('ytParagraphStart').disabled,true);assert.equal(a.$('ytParagraphCancel').disabled,false);
 assert.equal(a.$('ytParagraphCancel').closest('.hidden'),null);a.click('ytParagraphCancel');
 finish();await tick();assert.match(a.$('ytParagraphStatus').textContent,/중단/);assert.equal(a.$('ytParagraphStart').disabled,false);
 assert.equal(a.w.LabTest.getState().customExercises.filter(e=>e.paragraph_mode).length,0);
});

// v2.5.2: Korean meanings are automatic, shown directly below English, and updated per sentence.
test('Korean meanings appear below English immediately per completed sentence without rebuilding cards',async t=>{
 const a=await app(t);a.d.querySelector('[data-view="youtube"]').click();let finish;
 a.w.__translate=async text=>text===KO_LINES[1][0]?new Promise(r=>finish=r):KO_LINES.find(x=>x[0]===text)[1];
 a.fill('ytUrl','https://youtu.be/M7lc1UVf-VE');a.click('ytLoad');a.fill('ytTranscript',KO_LINES.map((x,i)=>`${i*10}:00\n${x[0]}`).join('\n'));
 a.click('ytFromTranscript');await tick();const articles=a.d.querySelectorAll('.auto-expression-card'),first=articles[0],meaning=first.querySelector('.auto-meaning');
 assert.equal(meaning.textContent,KO_LINES[0][1]);assert.equal(meaning.dataset.translation,'ready');
 assert.ok(first.querySelector('h3').compareDocumentPosition(meaning)&a.w.Node.DOCUMENT_POSITION_FOLLOWING);
 assert.equal(articles[1].querySelector('.auto-meaning').dataset.translation,'translating');
 assert.equal(articles[2].querySelector('.auto-meaning').dataset.translation,'waiting');
 assert.equal(a.$('ytPrepareKorean').classList.contains('hidden'),true);assert.match(a.$('ytTranslationCount').textContent,/1 \/ 3/);
 finish(KO_LINES[1][1]);await tick();assert.equal(a.d.querySelector('.auto-expression-card'),first);
 assert.deepEqual(Array.from(a.d.querySelectorAll('.auto-meaning'),e=>e.textContent),KO_LINES.map(x=>x[1]));
 assert.match(a.$('ytTranslationCount').textContent,/3 \/ 3/);
});
test('opening a saved video automatically fills only missing Korean meanings without a prepare click',async t=>{
 const a=await app(t);await koreanDeck(a);const saved=JSON.parse(a.w.localStorage.getItem(KEY)),ids=saved.customCards.map(c=>c.id);
 delete saved.translations[ids[1]];delete saved.translations[ids[2]];
 const b=await app(t,{state:saved});assert.equal(b.w.__translatedTexts,undefined);
 b.d.querySelector('[data-view="youtube"]').click();await tick();
 assert.deepEqual(Array.from(b.w.__translatedTexts),KO_LINES.slice(1).map(x=>x[0]));
 assert.deepEqual(Array.from(b.d.querySelectorAll('.auto-meaning'),e=>e.textContent),KO_LINES.map(x=>x[1]));
 assert.equal(b.$('ytPrepareKorean').classList.contains('hidden'),true);assert.match(b.$('ytTranslationCount').textContent,/3 \/ 3/);
});
test('saved Korean meanings show on the first render even when no translation engine is available',async t=>{
 const a=await app(t);await koreanDeck(a);const saved=JSON.parse(a.w.localStorage.getItem(KEY)),b=await app(t,{state:saved,translator:false});
 assert.deepEqual(Array.from(b.d.querySelectorAll('.auto-meaning'),e=>e.textContent),KO_LINES.map(x=>x[1]));
 b.d.querySelector('[data-view="youtube"]').click();await tick();assert.equal(b.$('ytPrepareKorean').classList.contains('hidden'),true);
 assert.equal(b.calls.filter(c=>/translate|local-ai/.test(c.url)).length,0);
});
test('showing more saved sentences automatically resumes missing meanings when translation becomes available',async t=>{
 const a=await app(t,{translator:false});a.d.querySelector('[data-view="youtube"]').click();await manyCaptions(a,15);
 assert.equal(a.$('ytPrepareKorean').classList.contains('hidden'),false);
 a.w.Translator={create:async()=>({translate:async text=>fixtureKorean(text),destroy(){}})};
 a.click('ytShowMore');await tick();assert.equal(a.d.querySelectorAll('.auto-meaning').length,15);
 assert.ok([...a.d.querySelectorAll('.auto-meaning')].every(e=>e.dataset.translation==='ready'&&/[가-힣]/.test(e.textContent)));
 assert.match(a.$('ytTranslationCount').textContent,/15 \/ 15/);assert.equal(a.$('ytPrepareKorean').classList.contains('hidden'),true);
});
test('the link click prepares browser translation before delayed caption retrieval loses user activation',async t=>{
 const a=await app(t);let activated=false,creates=0,finishCaption;
 a.w.Translator={create:options=>{assert.equal(activated,true,'Translator.create must run under the original link click');creates++;return Promise.resolve({translate:async text=>fixtureKorean(text),destroy(){}});}};
 a.w.__fetch=async url=>url==='/api/config'?{ok:true,json:async()=>({server:false,free_only:true,youtube_available:true,youtube_token:'token'})}:new Promise(r=>finishCaption=()=>r({ok:true,json:async()=>({video_id:'M7lc1UVf-VE',cues:KO_LINES.map((x,i)=>({text:x[0],start:i*10,duration:5}))})}));
 await a.w.LabTest.refreshConfig();a.d.querySelector('[data-view="youtube"]').click();a.fill('ytUrl','https://youtu.be/M7lc1UVf-VE');
 activated=true;a.click('ytAutoBuild');activated=false;assert.equal(creates,1);finishCaption();await tick();
 assert.equal(creates,1);assert.deepEqual(Array.from(a.d.querySelectorAll('.auto-meaning'),e=>e.textContent),KO_LINES.map(x=>x[1]));
});
test('one failed browser translation does not leave all later sentences without Korean meanings',async t=>{
 const a=await app(t);a.d.querySelector('[data-view="youtube"]').click();a.w.__translate=async text=>text===KO_LINES[1][0]?'Untranslated output':fixtureKorean(text);
 a.fill('ytUrl','https://youtu.be/M7lc1UVf-VE');a.click('ytLoad');a.fill('ytTranscript',KO_LINES.map((x,i)=>`${i*10}:00\n${x[0]}`).join('\n'));a.click('ytFromTranscript');await tick();
 const rows=a.d.querySelectorAll('.auto-meaning');assert.equal(rows[0].textContent,KO_LINES[0][1]);assert.equal(rows[1].dataset.translation,'error');assert.equal(rows[2].textContent,KO_LINES[2][1]);
 assert.match(a.$('ytTranslationCount').textContent,/2 \/ 3/);assert.equal(a.$('ytPrepareKorean').classList.contains('hidden'),false);
 const previous=a.w.__translatedTexts.length;a.w.__translate=async text=>fixtureKorean(text);a.click('ytPrepareKorean');await tick();
 assert.equal(a.w.__translatedTexts.length,previous+1);assert.deepEqual(Array.from(rows,e=>e.textContent),KO_LINES.map(x=>x[1]));
});

// v2.6: native speech events are simulated; no real voice output is claimed.
function transcriptOnly(a,lines=KO_LINES.map(x=>x[0])){
 a.d.querySelector('[data-view="youtube"]').click();a.fill('ytUrl','https://youtu.be/M7lc1UVf-VE');a.click('ytLoad');
 a.fill('ytTranscript',lines.map((text,i)=>a.w.LabYouTube.captionStamp(i*10)+'\n'+text).join('\n'));a.click('ytParse');
 return lines;
}
function change(a,id,value){a.$(id).value=String(value);a.$(id).dispatchEvent(new a.w.Event('change'));}
async function finishSpeech(a){const u=a.w.__spoken;assert.ok(u);u.onstart?.();u.onend?.();await tick();return u;}
function openScript(a){a.$('ytScriptDetails').open=true;a.$('ytScriptDetails').dispatchEvent(new a.w.Event('toggle'));}
test('full transcript playback and extracted cards include all 65 sentences in source order',async t=>{
 const a=await app(t);a.d.querySelector('[data-view="youtube"]').click();await manyCaptions(a,65);
 assert.equal(a.w.LabTest.getState().customCards.length,65);assert.equal(a.$('ytScriptFrom').options.length,65);assert.match(a.$('ytScriptSummary').textContent,/65문장/);
 const before=a.calls.length;a.click('ytScriptPlayAll');await tick();
 for(let i=0;i<65;i++){assert.equal(a.w.__spoken.text,'I would like to tell you about project number '+i+'.');assert.equal(a.$('ytScriptNowKorean').textContent,fixtureKorean(a.w.__spoken.text));assert.equal(a.$('ytScriptNowKorean').classList.contains('hidden'),false);await finishSpeech(a);}
 assert.equal(a.w.__spokenAll.length,65);assert.equal(a.$('ytScriptProgress').value,65);assert.match(a.$('ytScriptStatus').textContent,/전체 재생을 마쳤/);assert.equal(a.$('ytScriptPause').disabled,true);assert.equal(a.calls.length,before);
});
test('transcript-only playback preserves short answers, repeated sentences and final fragments without learning cards',async t=>{
 const a=await app(t),lines=transcriptOnly(a,['Yes.','That is right.','Yes.','Thanks!','One last thing']);
 assert.equal(a.w.LabTest.getState().customCards.length,0);a.click('ytScriptPlayAll');await tick();
 for(const line of lines){assert.equal(a.w.__spoken.text,line);await finishSpeech(a);}
 assert.deepEqual(a.w.__spokenAll.map(u=>u.text),lines);assert.equal(a.$('ytScriptNext').disabled,true);
});
test('inclusive range repeats exactly three times and ignores duplicate or stale end events',async t=>{
 const a=await app(t),lines=transcriptOnly(a);change(a,'ytScriptFrom',1);change(a,'ytScriptTo',2);change(a,'ytScriptGap',0);a.click('ytScriptPlayRange');await tick();
 for(let i=0;i<6;i++){assert.equal(a.w.__spoken.text,lines[1+i%2]);const old=a.w.__spoken;old.onstart();old.onend();old.onend();await tick();old.onend();}
 assert.equal(a.w.__spokenAll.length,6);assert.match(a.$('ytScriptStatus').textContent,/3회 반복했습니다/);assert.equal(a.$('ytScriptStop').disabled,true);
});
test('infinite single sentence repeat stops immediately and rejects late callbacks',async t=>{
 const a=await app(t),lines=transcriptOnly(a);change(a,'ytScriptRepeat',0);change(a,'ytScriptGap',0);openScript(a);
 a.d.querySelectorAll('.script-loop')[1].click();await tick();for(let i=0;i<4;i++){assert.equal(a.w.__spoken.text,lines[1]);await finishSpeech(a);}
 const old=a.w.__spoken,count=a.w.__spokenAll.length;a.click('ytScriptStop');old.onstart();old.onend();await tick();
 assert.equal(a.w.__spokenAll.length,count);assert.match(a.$('ytScriptStatus').textContent,/멈췄/);
});
test('pause and resume keep the current sentence; an end received while paused advances only on resume',async t=>{
 const a=await app(t),lines=transcriptOnly(a);a.click('ytScriptPlayAll');await tick();const first=a.w.__spoken;first.onstart();a.click('ytScriptPause');
 assert.equal(a.w.__speechPauses,1);assert.match(a.$('ytScriptPause').textContent,/이어 듣기/);const before=a.w.__speechResumes;a.click('ytScriptPause');assert.equal(a.w.__speechResumes,before+1);assert.equal(a.w.__spokenAll.length,1);
 a.click('ytScriptPause');first.onend();await tick();assert.equal(a.w.__spokenAll.length,1);a.click('ytScriptPause');await tick();assert.equal(a.w.__spoken.text,lines[1]);assert.equal(a.w.__spokenAll.length,2);
});
test('repeat gap applies between complete ranges and retains the remaining gap across pause',async t=>{
 const a=await app(t);transcriptOnly(a);change(a,'ytScriptTo',1);change(a,'ytScriptRepeat',2);change(a,'ytScriptGap',2);
 const jobs=[],native=a.w.setTimeout.bind(a.w),clear=a.w.clearTimeout.bind(a.w);let now=1000;
 Object.defineProperty(a.w.performance,'now',{value:()=>now});a.w.setTimeout=(fn,ms,...args)=>{if(ms===2000||ms===1500){const job={fn,ms,cancelled:false};jobs.push(job);return job;}return native(fn,ms,...args);};a.w.clearTimeout=id=>{if(id&&typeof id==='object')id.cancelled=true;else clear(id);};
 a.click('ytScriptPlayRange');await tick();await finishSpeech(a);assert.equal(jobs.length,0);await finishSpeech(a);assert.equal(jobs[0].ms,2000);
 now=1500;a.click('ytScriptPause');assert.equal(jobs[0].cancelled,true);jobs[0].fn();assert.equal(a.w.__spokenAll.length,2);a.click('ytScriptPause');assert.equal(jobs[1].ms,1500);
 jobs[1].fn();assert.equal(a.w.__spokenAll.length,3);await finishSpeech(a);await finishSpeech(a);assert.equal(a.w.__spokenAll.length,4);assert.match(a.$('ytScriptStatus').textContent,/2회 반복했습니다/);
});
test('previous and next respect range bounds and moving while paused waits for resume',async t=>{
 const a=await app(t),lines=transcriptOnly(a);a.click('ytScriptPlayAll');await tick();const first=a.w.__spoken;assert.equal(a.$('ytScriptPrev').disabled,true);
 a.click('ytScriptNext');await tick();assert.equal(a.w.__spoken.text,lines[1]);first.onend();await tick();assert.equal(a.w.__spokenAll.length,2);
 a.click('ytScriptPause');a.click('ytScriptNext');await tick();assert.match(a.$('ytScriptPosition').textContent,/3 \/ 3/);assert.equal(a.w.__spokenAll.length,2);assert.equal(a.$('ytScriptNext').disabled,true);
 a.click('ytScriptPrev');a.click('ytScriptPause');assert.equal(a.w.__spoken.text,lines[1]);assert.equal(a.w.__spokenAll.length,3);
});
test('learning-card repeat selects its full source sentence and uses the configured repeat count',async t=>{
 const a=await app(t);await koreanDeck(a);change(a,'ytScriptRepeat',2);change(a,'ytScriptGap',0);a.d.querySelectorAll('.auto-loop')[1].click();
 assert.equal(a.$('ytScriptFrom').value,'1');assert.equal(a.$('ytScriptTo').value,'1');assert.equal(a.w.__spoken.text,KO_LINES[1][0]);await finishSpeech(a);await finishSpeech(a);assert.equal(a.w.__spokenAll.length,2);assert.match(a.$('ytScriptStatus').textContent,/2회 반복했습니다/);
});
test('online voice permission resumes the complete pending range and stop clears a pending full play',async t=>{
 const a=await app(t);transcriptOnly(a);a.w.speechSynthesis.getVoices=()=>[{lang:'en-US',voiceURI:'online',localService:false}];a.click('ytVoiceRefresh');
 change(a,'ytScriptTo',1);change(a,'ytScriptRepeat',2);change(a,'ytScriptGap',0);a.click('ytScriptPlayRange');await tick();assert.equal(a.w.__spoken,undefined);assert.equal(a.d.activeElement,a.$('ytAllowOnlineVoice'));
 a.$('ytAllowOnlineVoice').click();await tick();for(let i=0;i<4;i++)await finishSpeech(a);assert.deepEqual(a.w.__spokenAll.map(u=>u.text),[KO_LINES[0][0],KO_LINES[1][0],KO_LINES[0][0],KO_LINES[1][0]]);
 a.$('ytAllowOnlineVoice').click();await tick();a.click('ytScriptPlayAll');await tick();a.click('ytScriptStop');a.$('ytAllowOnlineVoice').click();await tick();assert.equal(a.w.__spokenAll.length,4);
});
test('card audio and starting microphone permission cancel transcript loops with no later restart',async t=>{
 const a=await app(t,{deferMic:true});await koreanDeck(a);a.click('ytScriptPlayAll');await tick();const full=a.w.__spoken;a.d.querySelector('.auto-tts').click();full.onend();await tick();assert.equal(a.w.__spokenAll.length,2);assert.equal(a.w.__spoken.text,KO_LINES[0][0]);
 a.click('ytScriptPlayAll');await tick();const second=a.w.__spoken;a.click('recordBtn');assert.equal(a.w.LabTest.recording(),true);second.onend();await tick();assert.equal(a.w.__spokenAll.length,3);assert.equal(a.$('ytScriptPlayAll').disabled,true);
 a.resolveMic();await tick();a.click('stopBtn');a.w.__recorder.finish();assert.equal(a.$('ytScriptPlayAll').disabled,false);a.click('ytScriptPlayAll');await tick();assert.equal(a.w.__spokenAll.length,4);
});
test('source edits clear old repeat settings; extraction range never truncates the complete transcript',async t=>{
 const a=await app(t);transcriptOnly(a);a.click('ytScriptPlayAll');await tick();const old=a.w.__spoken;change(a,'ytScope','range');change(a,'ytStart','0:10');change(a,'ytEnd','0:20');assert.equal(a.$('ytScriptFrom').options.length,3);
 a.fill('ytTranscript','0:00\nWe have a completely different story today.');old.onend();await tick();assert.equal(a.$('ytScriptFrom').options.length,0);assert.equal(a.$('ytScriptPlayAll').disabled,true);assert.equal(a.w.__spokenAll.length,1);
 change(a,'ytScope','all');a.click('ytParse');assert.equal(a.$('ytScriptFrom').options.length,1);a.click('ytScriptPlayAll');await tick();assert.equal(a.w.__spoken.text,'We have a completely different story today.');
});
test('reopening a previously heard transcript restores meanings and playback without translation requests',async t=>{
 const a=await app(t);const lines=transcriptOnly(a);a.click('ytScriptPlayAll');await tick();for(const line of lines)await finishSpeech(a);const b=await app(t,{state:JSON.parse(a.w.localStorage.getItem(KEY)),translator:false});b.d.querySelector('[data-view="youtube"]').click();
 assert.equal(b.$('ytScriptFrom').options.length,3);b.click('ytScriptPlayAll');for(const line of lines){assert.equal(b.w.__spoken.text,line);await finishSpeech(b);}assert.equal(b.calls.filter(c=>c.options.method==='POST').length,0);
});
test('caption fetch and automatic extraction populate the full player and restore its controls',async t=>{
 const a=await app(t);a.w.__fetch=async url=>url==='/api/config'?{ok:true,json:async()=>({free_only:true,youtube_available:true,youtube_token:'token'})}:{ok:true,json:async()=>({video_id:'M7lc1UVf-VE',cues:KO_LINES.map((x,i)=>({start:i*10,duration:5,text:x[0]}))})};await a.w.LabTest.refreshConfig();
 a.d.querySelector('[data-view="youtube"]').click();a.fill('ytUrl','https://youtu.be/M7lc1UVf-VE');a.click('ytLoad');a.click('ytFetch');await tick();assert.equal(a.$('ytScriptFrom').options.length,3);assert.equal(a.w.LabTest.getState().customCards.length,3);assert.equal(a.$('ytScriptPause').disabled,true);a.click('ytScriptPlayAll');await tick();assert.equal(a.w.__spoken.text,KO_LINES[0][0]);
});
test('speech failure or failure to start ends playback without advancing or retrying indefinitely',async t=>{
 const a=await app(t);transcriptOnly(a);const native=a.w.setTimeout.bind(a.w);let timeout;a.w.setTimeout=(fn,ms,...args)=>{if(ms===8000)timeout=fn;return native(fn,ms,...args);};
 a.click('ytScriptPlayAll');await tick();const first=a.w.__spoken;timeout();first.onstart();first.onend();await tick();assert.equal(a.w.__spokenAll.length,1);assert.match(a.$('ytScriptStatus').textContent,/시작되지 않았/);
 a.click('ytScriptPlayAll');await tick();const second=a.w.__spoken;second.onerror({error:'network'});second.onend();await tick();assert.equal(a.w.__spokenAll.length,2);assert.match(a.$('ytScriptStatus').textContent,/연결이 끊겼/);assert.equal(a.$('ytScriptPause').disabled,true);
});
test('changing voice or speed cancels the active sequence and the next play uses the new choice',async t=>{
 const a=await app(t);transcriptOnly(a);a.w.speechSynthesis.getVoices=()=>[{lang:'en-US',name:'A',voiceURI:'a',localService:true},{lang:'en-GB',name:'B',voiceURI:'b',localService:true}];a.click('ytVoiceRefresh');a.click('ytScriptPlayAll');await tick();const first=a.w.__spoken;
 change(a,'ytVoiceSelect','b');first.onend();await tick();assert.equal(a.w.__spokenAll.length,1);a.click('ytScriptPlayAll');await tick();assert.equal(a.w.__spoken.voice.voiceURI,'b');const second=a.w.__spoken;
 change(a,'ytSpeechRate',.75);second.onend();await tick();assert.equal(a.w.__spokenAll.length,2);a.click('ytScriptPlayAll');await tick();assert.equal(a.w.__spoken.rate,.75);
});
test('manual transcript paging and range endpoints support sentences beyond the first 40',async t=>{
 const a=await app(t);a.d.querySelector('[data-view="youtube"]').click();await manyCaptions(a,65);openScript(a);a.click('ytScriptPageNext');assert.match(a.$('ytScriptPageLabel').textContent,/41–65/);assert.equal(a.$('ytScriptFollow').checked,false);
 a.d.querySelectorAll('.script-from')[3].click();a.d.querySelectorAll('.script-to')[5].click();assert.equal(a.$('ytScriptFrom').value,'43');assert.equal(a.$('ytScriptTo').value,'45');assert.equal(a.d.querySelectorAll('.script-row.in-range').length,3);
 a.click('ytScriptPlayRange');await tick();assert.equal(a.w.__spoken.text,'I would like to tell you about project number 43.');assert.equal(a.d.querySelector('.script-row[aria-current="true"]').dataset.index,'43');
});
test('navigation and a new source invalidate pending callbacks and remove the old transcript range',async t=>{
 const a=await app(t);transcriptOnly(a);a.click('ytScriptPlayAll');await tick();const first=a.w.__spoken;a.d.querySelector('[data-view="practice"]').click();first.onend();await tick();assert.equal(a.w.__spokenAll.length,1);
 a.d.querySelector('[data-view="youtube"]').click();a.click('ytScriptPlayAll');await tick();const second=a.w.__spoken;a.fill('ytUrl','https://youtu.be/dQw4w9WgXcQ');a.click('ytLoad');second.onend();await tick();assert.equal(a.w.__spokenAll.length,2);assert.equal(a.$('ytScriptFrom').options.length,0);assert.equal(a.$('ytScriptPlayAll').disabled,true);
});
test('starting translation stops the current transcript and does not resurrect it when translation finishes',async t=>{
 const a=await app(t);transcriptOnly(a);a.click('ytScriptPlayAll');await tick();const first=a.w.__spoken;let finish;a.w.__translate=()=>new Promise(r=>finish=r);a.click('ytFromTranscript');await tick();
 first.onend();assert.equal(a.$('ytScriptPlayAll').disabled,true);a.click('ytKoCancel');finish(KO_LINES[0][1]);await tick();assert.equal(a.w.__spokenAll.length,1);assert.equal(a.$('ytScriptPlayAll').disabled,false);assert.equal(a.$('ytScriptPause').disabled,true);
});

// v2.6.1: current transcript Korean must be ready before speech, including non-card sentences.
test('sentence 55 of 116 gets its own Korean meaning before audio without adding a learning card',async t=>{
 const a=await app(t);a.d.querySelector('[data-view="youtube"]').click();a.fill('ytUrl','https://youtu.be/M7lc1UVf-VE');a.click('ytLoad');a.fill('ytTranscript',Array.from({length:116},(_,i)=>a.w.LabYouTube.captionStamp(i*10)+'\nI would like to tell you about project number '+i+'.').join('\n'));a.click('ytParse');
 const text='I would like to tell you about project number 54.',ko='54번 프로젝트에 대해 이야기하고 싶어요.';let finish;
 a.w.__translate=en=>en===text?new Promise(r=>finish=r):fixtureKorean(en);change(a,'ytScriptFrom',54);change(a,'ytScriptTo',54);a.click('ytScriptPlayRange');await tick();
 assert.equal(a.w.__spoken,undefined);assert.equal(a.$('ytScriptNow').textContent,text);assert.match(a.$('ytScriptNowKorean').textContent,/뜻을 준비/);assert.equal(a.$('ytScriptNowKorean').classList.contains('hidden'),false);
 finish(ko);await tick();assert.equal(a.w.__spoken.text,text);assert.equal(a.$('ytScriptNowKorean').textContent,ko);assert.equal(a.$('ytScriptNowKorean').dataset.translation,'ready');assert.equal(a.w.LabTest.getState().customCards.length,0);
 const saved=JSON.parse(a.w.localStorage.getItem(KEY));assert.equal(saved.transcriptTranslations.find(t=>t.source_en===text).korean_text,ko);a.click('ytScriptPause');assert.equal(a.$('ytScriptNowKorean').textContent,ko);a.click('ytScriptStop');assert.equal(a.$('ytScriptNowKorean').textContent,ko);
});
test('the next sentence is prefetched and waits for its own meaning instead of showing a blank or the previous translation',async t=>{
 const a=await app(t),lines=transcriptOnly(a);let finish;a.w.__translate=en=>en===lines[1]?new Promise(r=>finish=r):KO_LINES.find(x=>x[0]===en)[1];a.click('ytScriptPlayAll');await tick();
 assert.equal(typeof finish,'function');assert.equal(a.$('ytScriptNowKorean').textContent,KO_LINES[0][1]);await finishSpeech(a);assert.equal(a.w.__spokenAll.length,1);assert.equal(a.$('ytScriptNow').textContent,lines[1]);assert.notEqual(a.$('ytScriptNowKorean').textContent,KO_LINES[0][1]);assert.equal(a.$('ytScriptNowKorean').classList.contains('hidden'),false);
 finish(KO_LINES[1][1]);await tick();assert.equal(a.w.__spoken.text,lines[1]);assert.equal(a.$('ytScriptNowKorean').textContent,KO_LINES[1][1]);await finishSpeech(a);assert.equal(a.$('ytScriptNowKorean').textContent,KO_LINES[2][1]);
});
test('Korean finishing while paused updates the current sentence without starting audio',async t=>{
 const a=await app(t),lines=transcriptOnly(a);let finish;a.w.__translate=en=>new Promise(r=>finish=r);a.click('ytScriptPlayAll');await tick();a.click('ytScriptPause');finish(KO_LINES[0][1]);await tick();
 assert.equal(a.w.__spoken,undefined);assert.equal(a.$('ytScriptNowKorean').textContent,KO_LINES[0][1]);assert.match(a.$('ytScriptPause').textContent,/이어 듣기/);a.click('ytScriptPause');assert.equal(a.w.__spoken.text,lines[0]);assert.equal(a.$('ytScriptNowKorean').textContent,KO_LINES[0][1]);
});
test('stopping or changing source during translation rejects late meaning and audio',async t=>{
 const a=await app(t);transcriptOnly(a);let finish;a.w.__translate=()=>new Promise(r=>finish=r);a.click('ytScriptPlayAll');await tick();a.click('ytScriptStop');finish('잠깐 쉴까 생각하고 있었어요.');await tick();assert.equal(a.w.__spoken,undefined);assert.equal(a.w.LabTest.getState().transcriptTranslations.length,0);
 a.click('ytScriptPlayAll');await tick();const late=finish;a.fill('ytTranscript','0:00\nThe story has changed completely.');a.click('ytParse');late('이전 문장에 대한 뜻입니다.');await tick();assert.equal(a.w.__spoken,undefined);assert.equal(a.w.LabTest.getState().transcriptTranslations.length,0);assert.equal(a.$('ytScriptNow').textContent,'');
});
test('jumping ahead while translation is pending cannot attach an earlier meaning to the new sentence',async t=>{
 const a=await app(t),lines=transcriptOnly(a);let finish;a.w.__translate=en=>en===lines[0]?new Promise(r=>finish=r):KO_LINES.find(x=>x[0]===en)[1];a.click('ytScriptPlayAll');await tick();a.click('ytScriptNext');assert.equal(a.$('ytScriptNow').textContent,lines[1]);finish(KO_LINES[0][1]);await tick();assert.equal(a.$('ytScriptNowKorean').textContent,KO_LINES[1][1]);assert.deepEqual(a.w.__spokenAll.map(u=>u.text),[lines[1]]);
});
test('local free translation supplies a non-card current sentence with exact source binding',async t=>{
 const a=await app(t,{translator:false});a.w.__fetch=async(url,options)=>{
  if(url==='/api/config')return {ok:true,json:async()=>({free_only:true,local_ai:true,youtube_token:'token'})};
  if(url==='/local-ai/status')return {ok:true,json:async()=>({running:true,ready:true,setup:{}})};
  assert.equal(url,'/local-ai/translate');const c=JSON.parse(options.body).cards[0];assert.equal(options.headers['X-Local-Token'],'token');return {ok:true,json:async()=>({engine:'local_ai',translations:[{card_id:c.id,source_en:c.sentence_en,korean_text:fixtureKorean(c.sentence_en),engine:'local_ai'}]})};
 };await a.w.LabTest.refreshConfig();const lines=transcriptOnly(a);change(a,'ytScriptTo',0);a.click('ytScriptPlayRange');await tick();assert.equal(a.$('ytScriptNowKorean').textContent,KO_LINES[0][1]);assert.equal(a.w.__spoken.text,lines[0]);assert.equal(a.w.LabTest.getState().customCards.length,0);assert.equal(a.w.LabTest.getState().transcriptTranslations[0].engine,'local_ai');assert.equal(a.calls.filter(c=>/^\/api\/(generate|grade|transcribe)/.test(c.url)).length,0);
});
test('unavailable translation keeps a visible explanation and retry supplies the meaning before playback',async t=>{
 const a=await app(t,{translator:false});transcriptOnly(a);a.click('ytScriptPlayAll');await tick();assert.equal(a.w.__spoken,undefined);assert.equal(a.$('ytScriptNowKorean').classList.contains('hidden'),false);assert.match(a.$('ytScriptNowKorean').textContent,/준비하지 못했습니다/);assert.equal(a.$('ytScriptKoRetry').classList.contains('hidden'),false);
 a.w.Translator={create:async()=>({translate:async en=>fixtureKorean(en),destroy(){}})};a.click('ytScriptKoRetry');await tick();assert.equal(a.$('ytScriptNowKorean').textContent,KO_LINES[0][1]);assert.equal(a.w.__spoken.text,KO_LINES[0][0]);assert.equal(a.$('ytScriptKoRetry').classList.contains('hidden'),true);
});
test('a mismatched local translation is never displayed or cached as the current Korean meaning',async t=>{
 const a=await app(t,{translator:false});a.w.__fetch=async url=>url==='/api/config'?{ok:true,json:async()=>({free_only:true,local_ai:true})}:url==='/local-ai/status'?{ok:true,json:async()=>({running:true,ready:true,setup:{}})}:{ok:true,json:async()=>({engine:'local_ai',translations:[{card_id:'script_sentence',source_en:'A different sentence.',korean_text:'다른 문장의 뜻입니다.',engine:'local_ai'}]})};await a.w.LabTest.refreshConfig();transcriptOnly(a);a.click('ytScriptPlayRange');await tick();assert.equal(a.w.__spoken,undefined);assert.equal(a.w.LabTest.getState().transcriptTranslations.length,0);assert.notEqual(a.$('ytScriptNowKorean').textContent,'다른 문장의 뜻입니다.');assert.equal(a.$('ytScriptNowKorean').dataset.translation,'error');
});
test('repeat and later replay reuse transcript meanings without another translation call',async t=>{
 const a=await app(t);const lines=transcriptOnly(a,['Yes.','Yes.']);change(a,'ytScriptTo',1);change(a,'ytScriptRepeat',2);change(a,'ytScriptGap',0);a.click('ytScriptPlayRange');await tick();for(let i=0;i<4;i++)await finishSpeech(a);assert.deepEqual(a.w.__translatedTexts,['Yes.']);assert.equal(a.w.LabTest.getState().transcriptTranslations.length,1);
 const b=await app(t,{state:JSON.parse(a.w.localStorage.getItem(KEY)),translator:false});b.d.querySelector('[data-view="youtube"]').click();b.click('ytScriptPlayAll');assert.equal(b.w.__spoken.text,lines[0]);assert.equal(b.$('ytScriptNowKorean').textContent,fixtureKorean('Yes.'));assert.equal(b.$('ytScriptNowKorean').classList.contains('hidden'),false);
});
test('translation engine is primed under the playback click even when the first sentences already have card meanings',async t=>{
 const a=await app(t);a.d.querySelector('[data-view="youtube"]').click();await manyCaptions(a,25);const partial=a.w.LabTest.getState();for(const c of partial.customCards.slice(20))delete partial.translations[c.id];let activated=false,createdUnderClick=false;a.w.Translator={create:()=>{createdUnderClick=activated;return Promise.resolve({translate:async text=>fixtureKorean(text),destroy(){}});}};
 activated=true;a.click('ytScriptPlayAll');activated=false;assert.equal(createdUnderClick,true);assert.equal(a.w.__spoken.text,'I would like to tell you about project number 0.');
});
test('a failed sentence translation does not prevent the next sentence from receiving its Korean meaning',async t=>{
 const a=await app(t),lines=transcriptOnly(a);a.w.__translate=text=>text===lines[0]?'English-only invalid result':fixtureKorean(text);a.click('ytScriptPlayAll');await tick();assert.equal(a.$('ytScriptNowKorean').dataset.translation,'error');assert.equal(a.w.__spoken,undefined);assert.equal(a.$('ytScriptNext').disabled,false);
 a.click('ytScriptNext');await tick();assert.equal(a.$('ytScriptNowKorean').textContent,KO_LINES[1][1]);assert.equal(a.w.__spoken.text,lines[1]);assert.equal(a.w.__translationCreates,1);
});
test('translation timeout stays visible and retry recovers without a late translation replacing the meaning',async t=>{
 const a=await app(t),lines=transcriptOnly(a);const native=a.w.setTimeout.bind(a.w);let timeout,late,startTimers=0;a.w.setTimeout=(fn,ms,...args)=>{if(ms===120000)timeout=fn;if(ms===8000)startTimers++;return native(fn,ms,...args);};a.w.__translate=()=>new Promise(r=>late=r);a.click('ytScriptPlayRange');await tick();assert.equal(startTimers,0);timeout();await tick();assert.equal(a.$('ytScriptNowKorean').dataset.translation,'error');assert.match(a.$('ytScriptStatus').textContent,/대기가 길어|초과/);assert.equal(a.w.__spoken,undefined);
 a.w.__translate=text=>fixtureKorean(text);a.click('ytScriptKoRetry');await tick();assert.equal(a.w.__spoken.text,lines[0]);assert.equal(a.$('ytScriptNowKorean').textContent,KO_LINES[0][1]);late('늦게 도착한 다른 뜻입니다.');await tick();assert.equal(a.$('ytScriptNowKorean').textContent,KO_LINES[0][1]);assert.equal(startTimers,1);
});
test('stopped translation does not pretend to keep loading and retry while paused never starts audio',async t=>{
 const a=await app(t);transcriptOnly(a);let finish;a.w.__translate=()=>new Promise(r=>finish=r);a.click('ytScriptPlayAll');await tick();a.click('ytScriptStop');assert.equal(a.$('ytScriptNowKorean').getAttribute('aria-busy'),'false');assert.match(a.$('ytScriptNowKorean').textContent,/재생을 시작하면/);finish(KO_LINES[0][1]);await tick();
 a.click('ytScriptPlayAll');await tick();a.click('ytScriptPause');finish('English-only invalid result');await tick();assert.match(a.$('ytScriptPause').textContent,/이어 듣기/);assert.equal(a.w.__spoken,undefined);
 a.w.__translate=text=>fixtureKorean(text);a.click('ytScriptKoRetry');await tick();assert.equal(a.$('ytScriptNowKorean').textContent,KO_LINES[0][1]);assert.equal(a.w.__spoken,undefined);a.click('ytScriptPause');assert.equal(a.w.__spoken.text,KO_LINES[0][0]);
});

// v2.7: bundled PDFs work without transcription, translation or paid API calls.
function openMaterial(a,id='pdf_jennie'){a.d.querySelector('.material-open[data-material="'+id+'"]').click();return a.w.LAB_MATERIALS.find(m=>m.id===id);}
test('PDFs open offline with Korean on every visible card and one shared audio transport',async t=>{
 const a=await app(t,{offline:true,translator:false}),m=openMaterial(a);assert.equal(a.$('materialsView').classList.contains('hidden'),false);assert.equal(a.d.querySelectorAll('.material-card').length,20);assert.equal(a.$('ytScriptFrom').options.length,60);assert.equal(a.$('ytAudioControls').parentElement.id,'materialListeningHost');assert.equal(a.$('ytTranscriptPlayer').parentElement.id,'materialListeningHost');
 assert.deepEqual(Array.from(a.d.querySelectorAll('.material-card .material-meaning'),e=>e.textContent),Array.from(m.rows.slice(0,20),r=>r.korean_text));assert.equal(a.calls.length,0);assert.equal(a.w.__translationCreates,undefined);const ids=Array.from(a.d.querySelectorAll('[id]'),e=>e.id);assert.equal(new Set(ids).size,ids.length);
});
test('PDF playback keeps the right Korean on current, next, paused and stopped sentences',async t=>{
 const a=await app(t,{offline:true,translator:false}),m=openMaterial(a);a.click('ytScriptPlayAll');assert.equal(a.w.__spoken.text,m.rows[0].text);assert.equal(a.$('ytScriptNowKorean').textContent,m.rows[0].korean_text);await finishSpeech(a);assert.equal(a.w.__spoken.text,m.rows[1].text);assert.equal(a.$('ytScriptNowKorean').textContent,m.rows[1].korean_text);a.w.__spoken.onstart();a.click('ytScriptPause');assert.equal(a.$('ytScriptNowKorean').textContent,m.rows[1].korean_text);a.click('ytScriptStop');assert.equal(a.$('ytScriptNowKorean').textContent,m.rows[1].korean_text);assert.equal(a.calls.length,0);
});
test('switching PDF sources cancels stale playback and never marks the other material as seen',async t=>{
 const a=await app(t,{translator:false}),elon=openMaterial(a,'pdf_elon');assert.equal(Object.keys(a.w.LabTest.getState().exposures).filter(id=>id.startsWith('pdf_jennie')).length,0);a.click('ytScriptPlayAll');const old=a.w.__spoken;assert.equal(old.text,elon.rows[0].text);const j=openMaterial(a);old.onend();await tick();assert.equal(a.w.__spokenAll.length,1);assert.equal(a.$('ytScriptFrom').options.length,j.rows.length);a.d.querySelector('.material-listen').click();assert.equal(a.w.__spoken.text,j.rows[0].text);
});
test('PDF source switching preserves the complete YouTube draft and restores its player',async t=>{
 const a=await app(t),lines=transcriptOnly(a);const draft=JSON.stringify(a.w.LabTest.getState().youtubeDraft);openMaterial(a,'pdf_elon');a.d.querySelector('[data-view="youtube"]').click();assert.equal(JSON.stringify(a.w.LabTest.getState().youtubeDraft),draft);assert.equal(a.$('ytScriptFrom').options.length,lines.length);assert.equal(a.$('ytAudioControls').parentElement.id,'ytListeningHome');assert.equal(a.$('ytTranscriptPlayer').parentElement.id,'ytListeningHome');a.click('ytScriptPlayAll');await tick();assert.equal(a.w.__spoken.text,lines[0]);assert.equal(a.$('ytScriptNowSource').textContent,'');
});
test('PDF sentence ranges repeat exact text with prepared meanings without translation',async t=>{
 const a=await app(t,{offline:true,translator:false}),m=openMaterial(a);change(a,'ytScriptFrom',1);change(a,'ytScriptTo',2);change(a,'ytScriptRepeat',2);change(a,'ytScriptGap',0);a.click('ytScriptPlayRange');
 for(let i=0;i<4;i++){const row=m.rows[1+i%2];assert.equal(a.w.__spoken.text,row.text);assert.equal(a.$('ytScriptNowKorean').textContent,row.korean_text);await finishSpeech(a);}assert.equal(a.w.__spokenAll.length,4);assert.match(a.$('ytScriptStatus').textContent,/2회 반복/);assert.equal(a.calls.length,0);
});
test('PDF topic filters retain whole playback and reach the final source sentence',async t=>{
 const a=await app(t,{offline:true,translator:false}),m=openMaterial(a,'pdf_elon');change(a,'materialSection','elon_39');const filtered=m.rows.filter(r=>r.section_id==='elon_39');assert.equal(a.d.querySelectorAll('.material-card').length,filtered.length);assert.equal(a.$('ytScriptFrom').options.length,363);a.click('materialListenSection');assert.equal(a.w.__spoken.text,filtered[0].text);assert.match(a.$('ytScriptNowSource').textContent,/약 5년 뒤/);for(const row of filtered){assert.equal(a.w.__spoken.text,row.text);assert.equal(a.$('ytScriptNowKorean').textContent,row.korean_text);await finishSpeech(a);}assert.match(a.$('ytScriptStatus').textContent,/1회 반복/);assert.equal(a.$('ytScriptProgress').value,363);assert.equal(a.calls.length,0);
});
test('PDF single practice starts with Korean and keeps English hidden until requested',async t=>{
 const a=await app(t,{offline:true,translator:false}),m=openMaterial(a);a.d.querySelector('.material-speak').click();await tick();assert.equal(a.w.LabTest.getExercise().card_ids[0],m.rows[0].card_id);assert.equal(a.$('taskText').textContent,m.rows[0].korean_text);assert.equal(a.$('sampleBox').classList.contains('hidden'),true);assert.match(a.$('taskOrigin').textContent,/PDF 연습지/);assert.equal(a.calls.length,0);
});
test('PDF selected sentences become a Korean paragraph without any AI service',async t=>{
 const a=await app(t,{offline:true,translator:false}),m=openMaterial(a);const boxes=a.d.querySelectorAll('.material-pick');boxes[0].click();assert.equal(a.$('materialParagraph').disabled,true);boxes[2].click();assert.equal(a.$('materialParagraph').disabled,false);assert.match(a.$('materialPickStatus').textContent,/2 \/ 5/);a.click('materialParagraph');await tick();await tick();assert.equal(a.$('taskText').textContent,m.rows[0].korean_text+' '+m.rows[2].korean_text);assert.equal(a.$('sampleBox').classList.contains('hidden'),true);assert.equal(a.w.LabTest.getState().customCards.length,0);assert.equal(a.calls.length,0);
});
test('PDF selections have a five-sentence cap and topic changes clear the selection',async t=>{
 const a=await app(t),m=openMaterial(a);const boxes=a.d.querySelectorAll('.material-pick');for(let i=0;i<6;i++)boxes[i].click();assert.equal(boxes[5].checked,false);assert.match(a.$('materialPickStatus').textContent,/최대 5/);a.click('materialNext');assert.match(a.$('materialPickStatus').textContent,/5 \/ 5/);change(a,'materialSection','jn_extend_4');assert.equal(a.$('materialParagraph').disabled,true);assert.ok(Array.from(a.d.querySelectorAll('.material-pick'),e=>!e.checked).every(Boolean));
});
test('PDF batches start a 20-item speaking session and authored paragraph exercises stay separate',async t=>{
 const a=await app(t,{offline:true,translator:false}),m=openMaterial(a);a.click('materialNext');a.click('materialSequence');await tick();assert.equal(a.w.LabTest.getState().session.ids.length,20);assert.equal(a.w.LabTest.getState().session.ids[0],m.rows[20].card_id);assert.equal(a.$('taskText').textContent,m.rows[20].korean_text);openMaterial(a);a.click('materialPractice');assert.equal(a.w.LabTest.getExercise().id,m.exercises[0].id);assert.equal(a.$('taskText').textContent,m.exercises[0].task_ko);assert.match(a.$('sampleOrigin').textContent,/앱 작성 응용/);assert.equal(a.$('sampleBox').classList.contains('hidden'),true);assert.equal(a.calls.length,0);
});
test('PDF material cards and exercises survive saved-state restoration and remain available in the library',async t=>{
 const a=await app(t,{translator:false}),m=openMaterial(a);a.d.querySelector('.material-speak').click();await tick();a.fill('answerInput',m.rows[0].text);a.click('selfCheck');rate(a);const saved=JSON.parse(a.w.localStorage.getItem(KEY));const b=await app(t,{state:saved,translator:false});assert.equal(b.w.LabTest.getState().cards[m.rows[0].card_id].attempts,1);assert.equal(b.$('taskText').textContent,m.rows[0].korean_text);b.d.querySelector('[data-view="library"]').click();change(b,'librarySource','pdf_elon');assert.equal(b.d.querySelectorAll('.library-card').length,30);assert.match(b.$('libraryList').textContent,/PDF에 실린 발언/);
});
test('online voice permission remains visible on PDF materials and resumes only the requested sentence',async t=>{
 const a=await app(t,{translator:false}),m=openMaterial(a);a.w.speechSynthesis.getVoices=()=>[{lang:'en-US',voiceURI:'online',localService:false}];a.click('ytVoiceRefresh');a.d.querySelector('.material-listen').click();assert.equal(a.w.__spoken,undefined);assert.equal(a.$('ytAllowOnlineVoice').closest('#materialListeningHost').id,'materialListeningHost');a.$('ytAllowOnlineVoice').click();assert.equal(a.w.__spoken.text,m.rows[0].text);assert.equal(a.$('ytScriptNowKorean').textContent,m.rows[0].korean_text);
});

// v2.7.1: a saved public video starts the existing local caption-learning pipeline.
const SAVED_VIDEO='hZWTGyXF0mI';
async function savedVideoFixture(a,{failure=false}={}){
 a.w.__fetch=async(url,options={})=>{
  if(url==='/api/config')return {ok:true,json:async()=>({free_only:true,youtube_available:true,local_ai:false,youtube_token:'fixture-local-token'})};
  if(url==='/youtube/transcript')return failure?{ok:false,json:async()=>({detail:'이 환경에서는 영어 자막 본문을 가져오지 못했습니다.'})}:{ok:true,json:async()=>({video_id:SAVED_VIDEO,language:'en',is_generated:true,cues:Array.from({length:25},(_,i)=>({start:i*8,duration:8,text:'I would like to tell you about project number '+i+'.'}))})};
  throw Error('Unexpected request: '+url);
 };
 await a.w.LabTest.refreshConfig();
}
function clickSavedVideo(a){a.d.querySelector('.saved-video-open[data-video="'+SAVED_VIDEO+'"]').click();}
test('saved video appears in the materials, YouTube catalog and lesson picker without an external load',async t=>{
 const a=await app(t,{offline:true});assert.equal(a.w.LAB_VIDEO_MATERIALS.length,1);assert.equal(a.w.LAB_VIDEO_MATERIALS[0].id,SAVED_VIDEO);assert.match(a.d.querySelector('.catalog-tile[data-entry="video_'+SAVED_VIDEO+'"]').textContent,/Arthur Brooks/);assert.match(a.$('videoCatalog').textContent,/하버드 교수입니다 제말 들으십쇼/);assert.ok(Array.from(a.$('lessonSelect').options).some(o=>o.value==='video_'+SAVED_VIDEO));assert.equal(a.w.LAB_DATA.cards.length,3381);assert.equal(a.calls.length,0);assert.equal(a.d.querySelectorAll('iframe,img[src^="https://"]').length,0);
});
test('selecting a saved video loads its captions and prepares all 25 Korean speaking cards with no paid API calls',async t=>{
 const a=await app(t);await savedVideoFixture(a);clickSavedVideo(a);await tick();await tick();
 const fetches=a.calls.filter(c=>c.url==='/youtube/transcript');assert.equal(fetches.length,1);assert.equal(JSON.parse(fetches[0].options.body).video_id,SAVED_VIDEO);assert.equal(fetches[0].options.headers['X-Local-Token'],'fixture-local-token');assert.equal(a.$('ytUrl').value,'https://www.youtube.com/watch?v='+SAVED_VIDEO);assert.match(a.$('ytTitle').value,/Arthur Brooks/);assert.equal(a.$('youtubeView').classList.contains('hidden'),false);assert.equal(a.w.LabTest.getState().customCards.length,25);assert.equal(a.$('ytScriptFrom').options.length,25);assert.match(a.$('ytTranslationCount').textContent,/25 \/ 25/);assert.match(a.$('videoCatalog').textContent,/저장 25문장/);assert.equal(a.calls.filter(c=>/^\/api\/(grade|transcribe|generate|settings)$/.test(c.url)).length,0);
});
test('the saved-video lesson selector opens the video workflow instead of an empty expression library',async t=>{
 const a=await app(t);await savedVideoFixture(a);change(a,'lessonSelect','video_'+SAVED_VIDEO);assert.match(a.$('loadExercise').textContent,/영상으로 학습 시작/);assert.match(a.$('sourceNotice').textContent,/12분 59초/);a.click('loadExercise');await tick();await tick();assert.equal(a.$('youtubeView').classList.contains('hidden'),false);assert.equal(a.w.LabTest.getState().customCards.length,25);change(a,'lessonSelect','pdf_jennie');assert.match(a.$('loadExercise').textContent,/상황으로 시작/);assert.ok(a.$('exerciseSelect').options.length>=5);
});
test('declining replacement of another video draft preserves inputs, caption text and current view',async t=>{
 const a=await app(t);transcriptOnly(a);a.fill('ytTitle','My original video title');const before={url:a.$('ytUrl').value,title:a.$('ytTitle').value,raw:a.$('ytTranscript').value,draft:JSON.stringify(a.w.LabTest.getState().youtubeDraft),calls:a.calls.length};a.d.querySelector('[data-view="materials"]').click();a.w.confirm=()=>false;clickSavedVideo(a);await tick();assert.equal(a.$('ytUrl').value,before.url);assert.equal(a.$('ytTitle').value,before.title);assert.equal(a.$('ytTranscript').value,before.raw);assert.equal(JSON.stringify(a.w.LabTest.getState().youtubeDraft),before.draft);assert.equal(a.$('materialsView').classList.contains('hidden'),false);assert.equal(a.calls.length,before.calls);
});
test('reopening a prepared saved video reuses its caption draft and meanings without duplicate cards',async t=>{
 const a=await app(t);await savedVideoFixture(a);clickSavedVideo(a);await tick();await tick();const initialTranslations=a.w.__translatedTexts.length;openMaterial(a,'pdf_elon');clickSavedVideo(a);await tick();await tick();assert.equal(a.calls.filter(c=>c.url==='/youtube/transcript').length,1);assert.equal(a.w.LabTest.getState().customCards.length,25);assert.equal(a.w.__translatedTexts.length,initialTranslations);assert.equal(a.$('ytAudioControls').parentElement.id,'ytListeningHome');assert.equal(a.$('ytScriptFrom').options.length,25);
});
test('failed saved-video captions show an actionable error without invented cards and permit another source',async t=>{
 const a=await app(t);await savedVideoFixture(a,{failure:true});clickSavedVideo(a);await tick();await tick();assert.match(a.$('ytStatus').textContent,/본문을 가져오지 못/);assert.equal(a.w.LabTest.getState().customCards.length,0);assert.equal(a.w.LabTest.getState().transcriptTranslations.length,0);assert.equal(a.$('ytScriptPlayAll').disabled,true);assert.equal(a.d.querySelector('.saved-video-open').disabled,false);openMaterial(a);assert.equal(a.$('materialsView').classList.contains('hidden'),false);assert.equal(a.$('ytScriptFrom').options.length,60);
});
test('a standalone saved-video click explains the free caption launcher without attempting a paid request',async t=>{
 const a=await app(t,{offline:true});clickSavedVideo(a);await tick();assert.equal(a.$('ytUrl').value,'https://www.youtube.com/watch?v='+SAVED_VIDEO);assert.match(a.$('ytStatus').textContent,/start_youtube_windows.bat/);assert.equal(a.calls.length,0);assert.equal(a.$('ytTranscriptPanel').open,true);assert.equal(a.w.__spoken,undefined);
});
test('recording blocks a saved-video launch and leaves the active recording intact',async t=>{
 const a=await app(t);a.click('recordBtn');await tick();const url=a.$('ytUrl').value;clickSavedVideo(a);await tick();assert.equal(a.$('ytUrl').value,url);assert.equal(a.w.LabTest.recording(),true);assert.equal(a.calls.filter(c=>c.url==='/youtube/transcript').length,0);a.click('stopBtn');a.w.__recorder.finish();
});
test('saved-video buttons recover after reopening a deck whose Korean preparation was still pending',async t=>{
 const a=await app(t);await savedVideoFixture(a);clickSavedVideo(a);await tick();await tick();const s=a.w.LabTest.getState(),card=s.customCards[0];delete s.translations[card.id];openMaterial(a);let finish;a.w.__translate=()=>new Promise(r=>finish=r);clickSavedVideo(a);await tick();assert.equal(a.d.querySelector('.saved-video-open').disabled,true);assert.equal(typeof finish,'function');finish('프로젝트에 대해 이야기하고 싶어요.');await tick();await tick();assert.equal(a.d.querySelector('.saved-video-open').disabled,false);assert.equal(s.translations[card.id].korean_text,'프로젝트에 대해 이야기하고 싶어요.');
});

// v2.8: the materials tab is the entry point for every existing source.
function catalog(a){a.d.querySelector('[data-view="materials"]').click();}
function entryAction(a,id,action='expressions'){a.d.querySelector('.catalog-action[data-entry="'+id+'"][data-action="'+action+'"]').click();}
test('unified catalog lists every sidebar material without opening a PDF or marking it as studied',async t=>{
 const a=await app(t,{offline:true,translator:false}),before=JSON.stringify(a.w.LabTest.getState().exposures);catalog(a);
 const shown=Array.from(a.d.querySelectorAll('.catalog-tile'),e=>e.dataset.entry),sidebar=Array.from(a.$('lessonSelect').options,o=>o.value);
 assert.equal(shown.length,26);assert.deepEqual(shown.sort(),sidebar.sort());assert.equal(a.$('lessonSelect').querySelectorAll('optgroup').length,5);
 assert.match(a.$('materialCatalogStats').textContent,/전체 26개 자료 중 26개 표시/);assert.match(a.$('materialCatalogStats').textContent,/3,381/);
 assert.equal(a.$('materialWorkspace').classList.contains('hidden'),true);assert.equal(a.$('materialCatalog').classList.contains('hidden'),false);
 assert.equal(JSON.stringify(a.w.LabTest.getState().exposures),before);assert.equal(a.calls.length,0);
 const sources=new Set(Array.from(a.d.querySelectorAll('.catalog-source-link'),e=>e.getAttribute('href')).filter(h=>h.startsWith('sources/')));assert.equal(sources.size,35);
});
test('catalog search and category counts narrow the list and return to all materials',async t=>{
 const a=await app(t,{offline:true});catalog(a);a.d.querySelector('#materialFilters [data-group="speech"]').click();assert.equal(a.d.querySelectorAll('.catalog-tile').length,11);
 a.fill('materialSearch','잡스');assert.ok(a.d.querySelector('.catalog-tile[data-entry="s03"]'));assert.equal(a.$('materialFilters').querySelector('[data-group="speech"]').getAttribute('aria-pressed'),'true');
 a.fill('materialSearch','no-material-873267');assert.equal(a.$('materialCatalogEmpty').classList.contains('hidden'),false);a.click('materialCatalogReset');assert.equal(a.d.querySelectorAll('.catalog-tile').length,26);
 a.fill('materialSearch','가브리엘 8강');assert.equal(a.d.querySelectorAll('.catalog-tile').length,1);a.click('materialSearchClear');assert.equal(a.d.querySelectorAll('.catalog-tile').length,26);
});
test('every existing lecture, KPOP and speech opens only its own expressions and resets stale search filters',async t=>{
 const a=await app(t,{offline:true,translator:false});
 for(const l of a.w.LAB_DATA.lessons.filter(l=>['gabriel','kpop','speech'].includes(l.family))){
  catalog(a);a.$('librarySearch').value='unrelated old search';a.$('coreOnly').checked=true;entryAction(a,l.id);
  assert.equal(a.$('libraryView').classList.contains('hidden'),false);assert.equal(a.$('libraryTitle').textContent,l.title);assert.equal(a.$('librarySource').value,l.id);assert.equal(a.$('lessonSelect').value,l.id);
  assert.equal(a.$('coreOnly').checked,false);assert.equal(a.$('librarySearch').value,'');
  const visible=Array.from(a.d.querySelectorAll('.pick-card'),e=>e.dataset.id);assert.ok(visible.length>0);assert.ok(visible.every(id=>a.w.LAB_DATA.cards.find(c=>c.id===id).lesson_id===l.id));
 }
 assert.equal(a.calls.length,0);
});
test('catalog lecture and KPOP paragraph actions start the matching Korean exercise without API calls',async t=>{
 const a=await app(t,{offline:true,translator:false});
 for(const id of ['g01','g08','g10','kpop']){catalog(a);entryAction(a,id,'practice');assert.equal(a.w.LabTest.getExercise().lesson_id,id);assert.match(a.$('taskText').textContent,/[가-힣]/);assert.equal(a.$('sampleBox').classList.contains('hidden'),true);assert.equal(a.$('practiceView').classList.contains('hidden'),false);}
 assert.equal(a.calls.length,0);
});
test('speech study actions use its source example and Korean meaning and the sidebar no longer opens all speeches',async t=>{
 const a=await app(t,{offline:true,translator:false});change(a,'lessonSelect','s03');a.click('loadExercise');assert.equal(a.$('librarySource').value,'s03');assert.match(a.$('libraryStats').textContent,/258/);
 const first=a.w.LAB_DATA.cards.find(c=>c.lesson_id==='s03');a.d.querySelector('.library-listen').click();assert.equal(a.w.__spoken.text,first.source_quote);
 a.d.querySelector('.library-practice').click();assert.equal(a.w.LabTest.getExercise().card_ids[0],first.id);assert.match(a.$('taskText').textContent,/[가-힣]/);assert.equal(a.$('sampleBox').classList.contains('hidden'),true);assert.equal(a.calls.length,0);
});
test('PDF back button restores catalog filters and does not erase the selected topic or YouTube draft',async t=>{
 const a=await app(t,{offline:true,translator:false});youtubeSetup(a);const draft=JSON.stringify(a.w.LabTest.getState().youtubeDraft);catalog(a);a.fill('materialSearch','제니');a.d.querySelector('#materialCatalogGroups .material-open').click();change(a,'materialSection','jn_extend_4');
 assert.equal(a.$('materialCatalog').classList.contains('hidden'),true);a.click('materialBack');assert.equal(a.$('materialWorkspace').classList.contains('hidden'),true);assert.equal(a.$('materialSearch').value,'제니');assert.equal(a.d.querySelectorAll('.catalog-tile').length,1);
 a.d.querySelector('#materialCatalogGroups .material-open').click();assert.equal(a.$('materialSection').value,'jn_extend_4');assert.equal(JSON.stringify(a.w.LabTest.getState().youtubeDraft),draft);
});
test('restored personal video cards appear separately, stay scoped offline and do not replace another draft',async t=>{
 const a=await app(t);youtubeSetup(a);a.fill('ytTitle','내 제니 인터뷰');a.d.querySelector('.yt-candidate').click();a.click('ytAddCard');
 const saved=JSON.parse(a.w.localStorage.getItem(KEY));saved.youtubeDraft={videoId:SAVED_VIDEO,title:'Arthur Brooks',transcript:'An unrelated draft.'};
 const b=await app(t,{state:saved,translator:false}),initialCalls=b.calls.length;b.w.__fetch=async()=>{throw Error('offline')};catalog(b);assert.equal(b.d.querySelectorAll('.catalog-tile').length,27);assert.match(b.$('materialCatalogStats').textContent,/내 유튜브 1개/);
 const tile=b.d.querySelector('.catalog-tile[data-entry="video_M7lc1UVf-VE"]');assert.match(tile.textContent,/내 제니 인터뷰/);assert.match(tile.textContent,/저장한 학습 문장 1개/);
 const before=JSON.stringify(b.w.LabTest.getState().youtubeDraft);entryAction(b,'video_M7lc1UVf-VE');assert.equal(b.d.querySelectorAll('.library-card').length,1);assert.equal(JSON.stringify(b.w.LabTest.getState().youtubeDraft),before);assert.equal(b.calls.length,initialCalls);
 b.d.querySelector('.library-practice').click();assert.equal(b.w.LabTest.getExercise().card_ids[0],saved.customCards[0].id);assert.equal(b.$('lessonSelect').value,'video_M7lc1UVf-VE');
});
test('a transcript draft with no saved cards is visible and a prepared bundled video appears only once',async t=>{
 const a=await app(t);youtubeSetup(a);a.fill('ytTitle','영상 초안');a.$('ytTitle').dispatchEvent(new a.w.Event('change'));catalog(a);assert.equal(a.d.querySelectorAll('.catalog-tile').length,27);const own=a.d.querySelector('.catalog-tile[data-entry="video_M7lc1UVf-VE"]');assert.match(own.textContent,/자막 초안 있음/);
 await savedVideoFixture(a);clickSavedVideo(a);await tick();await tick();catalog(a);assert.equal(a.d.querySelectorAll('.catalog-tile[data-entry="video_'+SAVED_VIDEO+'"]').length,1);assert.equal(a.d.querySelectorAll('.catalog-tile').length,26);assert.match(a.d.querySelector('.catalog-tile[data-entry="video_'+SAVED_VIDEO+'"]').textContent,/저장한 학습 문장 25개/);
});
test('catalog navigation cannot interrupt recording or discard a declined written answer',async t=>{
 const a=await app(t);a.fill('answerInput','Keep my answer.');a.w.confirm=()=>false;const previous=a.w.LabTest.getExercise().id;catalog(a);entryAction(a,'g01','practice');assert.equal(a.w.LabTest.getExercise().id,previous);assert.equal(a.$('answerInput').value,'Keep my answer.');
 a.w.confirm=()=>true;a.d.querySelector('[data-view="practice"]').click();a.click('recordBtn');await tick();entryAction(a,'s03');assert.equal(a.$('libraryView').classList.contains('hidden'),true);assert.equal(a.w.LabTest.recording(),true);a.click('stopBtn');a.w.__recorder.finish();
});

// v2.8.1: the Harvard PDF includes local English and Korean, independent of video captions.
test('Harvard PDF opens from the searchable catalog offline with all Korean and source labels',async t=>{
 const a=await app(t,{offline:true,translator:false});catalog(a);a.fill('materialSearch','Harvard Prof');assert.equal(a.d.querySelectorAll('.catalog-tile[data-entry="pdf_harvard"]').length,1);assert.match(a.$('materialCatalogGroups').textContent,/84개/);
 a.d.querySelector('.catalog-tile[data-entry="pdf_harvard"] .material-open').click();const h=a.w.LAB_MATERIALS.find(m=>m.id==='pdf_harvard');assert.equal(a.$('ytScriptFrom').options.length,84);assert.equal(a.$('materialSection').options.length,10);assert.equal(a.$('materialExercise').options.length,5);assert.equal(a.$('lessonSelect').value,'pdf_harvard');
 assert.deepEqual(Array.from(a.d.querySelectorAll('.material-card .material-meaning'),e=>e.textContent),Array.from(h.rows.slice(0,20),r=>r.korean_text));assert.match(a.$('materialOriginal').getAttribute('href'),/Harvard_Prof.pdf$/);assert.equal(a.calls.length,0);assert.equal(a.w.__translationCreates,undefined);
});
test('Harvard PDF playback crosses all 84 units with persistent Korean and no translation requests',async t=>{
 const a=await app(t,{offline:true,translator:false}),h=openMaterial(a,'pdf_harvard');a.click('ytScriptPlayAll');
 for(const row of h.rows){assert.equal(a.w.__spoken.text,row.text);assert.equal(a.$('ytScriptNowKorean').textContent,row.korean_text);assert.match(a.$('ytScriptNowSource').textContent,new RegExp(row.speaker));await finishSpeech(a);}
 assert.equal(a.w.__spokenAll.length,84);assert.equal(a.$('ytScriptProgress').value,84);assert.equal(a.$('ytScriptNowKorean').textContent,h.rows.at(-1).korean_text);assert.equal(a.calls.length,0);
});
test('Harvard topic practice includes the final source sentence and exact two-unit repetition',async t=>{
 const a=await app(t,{offline:true,translator:false}),h=openMaterial(a,'pdf_harvard');change(a,'materialSection','harvard_09');assert.equal(a.d.querySelectorAll('.material-card').length,7);assert.equal(a.d.querySelectorAll('.material-english')[6].textContent,h.rows[83].text);
 change(a,'ytScriptFrom',82);change(a,'ytScriptTo',83);change(a,'ytScriptRepeat',2);change(a,'ytScriptGap',0);a.click('ytScriptPlayRange');for(let i=0;i<4;i++){assert.equal(a.w.__spoken.text,h.rows[82+i%2].text);assert.equal(a.$('ytScriptNowKorean').textContent,h.rows[82+i%2].korean_text);await finishSpeech(a);}assert.equal(a.w.__spokenAll.length,4);assert.equal(a.calls.length,0);
});
test('Harvard selected units and five authored paragraphs start Korean-first without an API',async t=>{
 const a=await app(t,{offline:true,translator:false}),h=openMaterial(a,'pdf_harvard');const picks=a.d.querySelectorAll('.material-pick');picks[2].click();picks[3].click();a.click('materialParagraph');await tick();assert.equal(a.$('taskText').textContent,h.rows[2].korean_text+' '+h.rows[3].korean_text);assert.equal(a.$('sampleBox').classList.contains('hidden'),true);
 for(const e of h.exercises){openMaterial(a,'pdf_harvard');change(a,'materialExercise',e.id);a.click('materialPractice');assert.equal(a.w.LabTest.getExercise().id,e.id);assert.equal(a.$('taskText').textContent,e.task_ko);assert.match(a.$('taskOrigin').textContent,/앱 작성 응용/);assert.equal(a.$('sampleBox').classList.contains('hidden'),true);}assert.equal(a.calls.length,0);
});
test('Harvard Korean-first practice and review survive saved-state restoration',async t=>{
 const a=await app(t,{translator:false}),h=openMaterial(a,'pdf_harvard');a.d.querySelector('.material-speak').click();await tick();a.fill('answerInput',h.rows[0].text);a.click('selfCheck');rate(a);const saved=JSON.parse(a.w.localStorage.getItem(KEY));const b=await app(t,{state:saved,translator:false});assert.equal(b.$('taskText').textContent,h.rows[0].korean_text);assert.equal(b.$('sampleBox').classList.contains('hidden'),true);assert.equal(b.w.LabTest.getState().cards[h.rows[0].card_id].attempts,1);
});

// v2.9.0: complete YouTube decks, backward-compatible progress, no batch controls.
test('an older 20-card draft fills all 65 sentences automatically while retaining IDs, translation and review position',async t=>{
 const a=await app(t);await manyCaptions(a,65);const old=JSON.parse(a.w.localStorage.getItem(KEY));old.customCards=old.customCards.slice(0,20);const ids=new Set(old.customCards.map(c=>c.id));old.translations=Object.fromEntries(Object.entries(old.translations).filter(([id])=>ids.has(id)));for(const c of old.customCards)delete c.source_cue_id;
 const first=old.customCards[0],last=old.customCards.at(-1);old.cards[first.id]={due:NOW+86400000,independent:1};old.session={ids:[...ids],index:7,completed:[],skipped:[],at:NOW};const b=await app(t,{state:old}),s=b.w.LabTest.getState();assert.equal(s.customCards.length,65);assert.equal(s.customCards[0].id,first.id);assert.equal(s.customCards[19].id,last.id);assert.equal(s.translations[first.id].korean_text,old.translations[first.id].korean_text);assert.equal(s.cards[first.id].due,NOW+86400000);assert.equal(s.session.index,7);assert.match(b.$('ytAutoPractice').textContent,/65개/);assert.equal(b.calls.filter(c=>c.url==='/youtube/transcript').length,0);assert.equal(JSON.parse(b.w.localStorage.getItem(KEY)).customCards.length,65);
});
test('all short and repeated source sentences have stable cards on extraction and reopening',async t=>{
 const a=await app(t);a.fill('ytUrl','https://youtu.be/M7lc1UVf-VE');a.click('ytLoad');a.fill('ytTranscript','0:00\nYes. Yes.\n0:05\nYes.\n0:10\n[Music]\n0:15\nI was just saying even');a.click('ytFromTranscript');await tick();const s=a.w.LabTest.getState();assert.deepEqual(Array.from(s.customCards,c=>c.expression),['Yes.','Yes.','Yes.','I was just saying even']);assert.equal(new Set(s.customCards.map(c=>c.id)).size,4);const ids=Array.from(s.customCards,c=>c.id);a.d.querySelectorAll('.auto-loop')[1].click();await tick();assert.equal(a.$('ytScriptFrom').value,'1');assert.equal(a.$('ytScriptTo').value,'1');a.click('ytScriptStop');a.click('ytAutoExtract');await tick();assert.deepEqual(Array.from(s.customCards,c=>c.id),ids);const b=await app(t,{state:JSON.parse(a.w.localStorage.getItem(KEY))});assert.deepEqual(Array.from(b.w.LabTest.getState().customCards,c=>c.id),ids);
});
test('a 623-sentence video crosses the previous 100-item import and 500-card storage bounds without truncation',async t=>{
 const a=await app(t);await manyCaptions(a,623);const s=a.w.LabTest.getState();assert.equal(s.customCards.length,623);assert.equal(Object.keys(s.translations).length,623);a.click('ytAutoPractice');await tick();assert.equal(s.session.ids.length,623);assert.equal(a.$('storageNotice').textContent,'');const saved=C.migrateState(JSON.parse(a.w.localStorage.getItem(KEY)),new Map(a.w.LAB_DATA.cards.map(c=>[c.id,c])));assert.equal(saved.customCards.at(-1).expression,'I would like to tell you about project number 622.');
});
test('manual source range cannot restrict the automatic whole-transcript deck',async t=>{
 const a=await app(t);await manyCaptions(a,25);change(a,'ytScope','range');change(a,'ytStart','0:10');change(a,'ytEnd','0:20');assert.match(a.$('ytAutoPractice').textContent,/25개/);a.click('ytAutoExtract');await tick();assert.equal(a.w.LabTest.getState().customCards.length,25);assert.match(a.$('ytAutoStatus').textContent,/전체 25/);
});
test('a capacity error leaves the old deck intact instead of claiming partial extraction is complete',async t=>{
 const a=await app(t);await manyCaptions(a,3);const ids=Array.from(a.w.LabTest.getState().customCards,c=>c.id);a.w.LabCore.MAX_CUSTOM_CARDS=4;await manyCaptions(a,6);assert.deepEqual(Array.from(a.w.LabTest.getState().customCards,c=>c.id),ids);assert.match(a.$('ytAutoStatus').textContent,/전체 문장.*저장 한도/);assert.ok(a.$('ytTranscript').value.includes('number 5.'));
});

test('caption file import also extracts every sentence without another button press',async t=>{
 const a=await app(t);a.fill('ytUrl','https://youtu.be/M7lc1UVf-VE');a.click('ytLoad');const text=Array.from({length:125},(_,i)=>'I would like to tell you about project number '+i+'.').join('\n');Object.defineProperty(a.$('ytCaptionFile'),'files',{configurable:true,value:[{size:text.length,text:async()=>text}]});a.$('ytCaptionFile').dispatchEvent(new a.w.Event('change'));await tick();await tick();const s=a.w.LabTest.getState();assert.equal(s.customCards.length,125);assert.equal(s.customCards.at(-1).expression,'I would like to tell you about project number 124.');assert.equal(Object.keys(s.translations).length,125);
});
test('the complete deck exists before translation finishes and survives cancellation and retry',async t=>{
 const a=await app(t);let finish;a.w.__translate=()=>new Promise(r=>finish=r);await manyCaptions(a,125);const s=a.w.LabTest.getState();assert.equal(s.customCards.length,125);assert.equal(Object.keys(s.translations).length,0);a.click('ytKoCancel');delete a.w.__translate;finish('이전 번역 요청의 결과입니다.');await tick();assert.equal(s.customCards.length,125);assert.equal(Object.keys(s.translations).length,0);a.click('ytPrepareKorean');await tick();assert.equal(Object.keys(s.translations).length,125);assert.match(a.$('ytTranslationCount').textContent,/125 \/ 125/);
});

// v2.10.0: optional free dictation and word comparison. Speech recognition is a mocked browser object.
const heard=(...parts)=>({results:parts.map(([text,final])=>Object.assign([{transcript:text}],{isFinal:final}))});
const settle=async()=>{for(let i=0;i<4;i++)await tick();};
function enableDictation(a){a.$('dictationToggle').checked=true;a.$('dictationToggle').dispatchEvent(new a.w.Event('change'));}
test('without browser speech recognition the dictation switch is disabled and self-check stays as before',async t=>{
 const a=await app(t,{state:cold()});assert.equal(a.$('dictationToggle').disabled,true);assert.match(a.$('dictationInfo').textContent,/Chrome 또는 Edge/);assert.match(a.$('privateNote').textContent,/자동 전송 없음/);
 a.click('recordBtn');await tick();a.click('stopBtn');a.w.__recorder.finish();assert.equal(a.w.LabTest.recording(),false);assert.ok(a.$('liveTranscript').classList.contains('hidden'));
 a.click('selfCheck');assert.equal(a.$('feedbackContent').querySelector('.word-compare'),null);assert.ok(a.$('feedbackContent').querySelector('.final-paragraph'));
});
test('dictation starts only after opting in and fills the answer without confirming it',async t=>{
 const a=await app(t,{state:cold(),speech:true});assert.equal(a.$('dictationToggle').disabled,false);assert.equal(a.$('dictationToggle').checked,false);
 a.click('recordBtn');await tick();assert.equal(a.w.__recognitions.length,0,'off by default');a.click('stopBtn');a.w.__recorder.finish();
 enableDictation(a);assert.equal(a.w.LabTest.getState().voice.dictation,true);assert.match(a.$('privateNote').textContent,/전송/);assert.match(a.$('dictationInfo').textContent,/Google/);
 a.click('recordBtn');await tick();const rec=a.w.__recognitions[0];assert.equal(rec.started,true);assert.equal(rec.lang,'en-US');assert.equal(rec.continuous,true);assert.equal(rec.interimResults,true);
 assert.equal(a.$('liveTranscript').classList.contains('hidden'),false);
 rec.onresult(heard(['I was thinking of',true],['making a photo',false]));assert.equal(a.$('liveTranscriptText').textContent,'I was thinking of making a photo');
 rec.onresult(heard(['I was thinking of',true],['making a photo album.',true]));
 a.click('stopBtn');a.w.__recorder.finish();assert.equal(a.w.LabTest.recording(),true,'answer area stays locked until dictation settles');
 a.w.LabTest.loadExercise('g09_story_1');assert.equal(a.w.LabTest.getExercise().id,'single_g01_01');
 await settle();assert.equal(a.w.LabTest.recording(),false);assert.equal(rec.stopped,true);
 assert.equal(a.$('answerInput').value,'I was thinking of making a photo album.');assert.equal(a.$('confirmTranscript').checked,false);
 assert.equal(a.$('rawText').textContent,'I was thinking of making a photo album.');assert.match(a.$('wordCount').textContent,/^8 words/);
 assert.equal(a.w.LabTest.getState().attempts.length,0);assert.equal(a.w.LabTest.getState().draft.raw,'I was thinking of making a photo album.');
 a.click('selfCheck');rate(a);const at=a.w.LabTest.getState().attempts[0];assert.equal(at.rawTranscript,'I was thinking of making a photo album.');assert.equal(at.inputKind,'text');
 assert.equal(a.calls.filter(c=>c.options.method==='POST').length,0);
});
test('declining the dictation notice keeps it off and recording stays local',async t=>{
 const a=await app(t,{state:cold(),speech:true});a.w.confirm=()=>false;enableDictation(a);assert.equal(a.$('dictationToggle').checked,false);assert.ok(!a.w.LabTest.getState().voice.dictation);
 a.click('recordBtn');await tick();assert.equal(a.w.__recognitions.length,0);a.click('stopBtn');a.w.__recorder.finish();
});
test('dictation follows pause and resume and survives the browser ending a silent session',async t=>{
 const s=cold();s.voice={uri:'',online:false,dictation:true};const a=await app(t,{state:s,speech:true});assert.equal(a.$('dictationToggle').checked,true);
 a.click('recordBtn');await tick();const first=a.w.__recognitions[0];first.onresult(heard(['I was thinking',true]));first.onend();
 assert.equal(a.w.__recognitions.length,2);a.click('pauseBtn');assert.equal(a.w.__recognitions[1].stopped,true);await settle();assert.equal(a.w.__recognitions.length,2);
 a.click('pauseBtn');assert.equal(a.w.__recognitions.length,3);a.w.__recognitions[2].onresult(heard(['of taking a break.',true]));
 a.click('stopBtn');a.w.__recorder.finish();await settle();assert.equal(a.$('answerInput').value,'I was thinking of taking a break.');
});
test('a dictation error keeps the recording and leaves the answer for the learner',async t=>{
 const s=cold();s.voice={uri:'',online:false,dictation:true};const a=await app(t,{state:s,speech:true});
 a.click('recordBtn');await tick();const rec=a.w.__recognitions[0];rec.onerror({error:'not-allowed'});
 assert.match(a.$('liveTranscriptStatus').textContent,/허용하지 않았습니다/);assert.equal(a.w.__recorder.state,'recording');
 a.click('stopBtn');a.w.__recorder.finish();await settle();assert.equal(a.$('answerInput').value,'');assert.match(a.$('statusLine').textContent,/받아쓴 영어가 없어/);assert.match(a.$('liveTranscriptStatus').textContent,/허용하지 않았습니다/);
 assert.ok(a.$('playback').getAttribute('src'));
});
test('typed words are never replaced by a later dictation result',async t=>{
 const s=cold();s.voice={uri:'',online:false,dictation:true};const a=await app(t,{state:s,speech:true});
 a.click('recordBtn');await tick();a.w.__recognitions[0].onresult(heard(['hello there',true]));a.fill('answerInput','My own words.');
 a.click('stopBtn');a.w.__recorder.finish();await settle();assert.equal(a.$('answerInput').value,'My own words.');assert.equal(a.$('rawText').textContent,'hello there');assert.match(a.$('statusLine').textContent,/바꾸지 않았습니다/);
});
test('self-check marks the example words, finds the target expression and escapes learner text',async t=>{
 const a=await app(t,{state:cold()});a.fill('answerInput','I was thinking of taking a <b>walk</b> <img src=x onerror=alert(1)>.');a.click('selfCheck');
 const box=a.$('feedbackContent').querySelector('.word-compare');assert.ok(box);assert.match(box.querySelector('.compare-meter').textContent,/개 중/);
 assert.ok(box.querySelectorAll('mark.said').length>=4);const found=box.querySelector('.expression-checks li.found');assert.ok(found);assert.match(found.textContent,/I was thinking of/);
 assert.equal(a.$('feedbackContent').querySelector('img'),null);assert.ok(!a.$('feedbackContent').innerHTML.includes('<b>walk</b>'));
 const sample=box.querySelector('.compare-sample').textContent;assert.equal(sample,a.$('sampleText').textContent);
 rate(a);assert.equal(a.w.LabTest.getState().attempts[0].transcript,'I was thinking of taking a <b>walk</b> <img src=x onerror=alert(1)>.');
});
test('sentence cards rely on the word comparison instead of an expression check',async t=>{
 const a=await app(t,{offline:true,translator:false}),h=openMaterial(a,'pdf_jennie');a.d.querySelector('.material-speak').click();await tick();
 assert.ok(a.w.LabTest.getExercise().card_ids.every(id=>a.w.LAB_DATA.cards.find(c=>c.id===id).chunk_kind));
 a.fill('answerInput','I did not know');a.click('selfCheck');const box=a.$('feedbackContent').querySelector('.word-compare');
 assert.ok(box.querySelectorAll('mark.missed').length>0);assert.ok(box.querySelectorAll('mark.said').length>0);assert.equal(box.querySelector('.expression-checks'),null);
});
