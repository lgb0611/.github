const {test}=require('node:test');
const assert=require('node:assert/strict');
const S=require('../static/speech-check.js');
const C=require('../static/core.js');

const kinds=r=>r.segments.filter(s=>s.kind!=='plain').map(s=>s.kind[0]+':'+s.text).join(' ');
test('word comparison keeps the example text and marks said and missing words in order',()=>{
 const sample='I was thinking of making a photo album for my mom\'s birthday.',r=S.compare('I was thinking of making a photo album.',sample);
 assert.equal(r.segments.map(s=>s.text).join(''),sample);
 assert.equal(r.total,12);assert.equal(r.hits,8);
 assert.match(kinds(r),/m:for m:my m:mom's m:birthday$/);
});
test('contractions, number words and verb endings count as the same words',()=>{
 const r=S.compare("I'm 30 and I can't wait. We stopped there.","I am thirty and I cannot wait. We stop there.");
 assert.equal(r.hits,r.total);
 assert.equal(S.compare('It\'s done','it is done').hits,3);
});
test('short unrelated words are not stretched into matches',()=>{
 assert.equal(S.compare('the','thing').hits,0);assert.equal(S.compare('bed','be').hits,0);
 assert.equal(S.compare('','Anything at all.').hits,0);assert.equal(S.compare('Anything','').total,0);
});
test('comparison stays bounded for very long spoken input',()=>{
 const said=Array.from({length:20000},(_,i)=>'word'+(i%50)).join(' '),start=Date.now(),r=S.compare(said,'word1 word2 word3 missing');
 assert.equal(r.hits,3);assert.ok(Date.now()-start<5000);
});
test('target expressions are found through tense changes and placeholders',()=>{
 const found=(said,expression,evidence)=>{const r=S.findExpression(said,expression);assert.equal(r.status,'found',expression);assert.equal(r.evidence,evidence);};
 found('Then I came up with a different plan.','come up with','came up with');
 found('I was thinking of taking a break.','I was thinking of ~ing','I was thinking of');
 found('I asked her out yesterday.','ask someone out','asked her out');
 found('He raised his voice at me.',"raise one's voice",'raised his voice');
 found('I felt good about myself.','feel good about oneself','felt good about myself');
 found('Please put the book back in the box.','Put (something) back in','put the book back in');
 found('Can you tell the copy from the original?','Tell A from B','tell the copy from');
 found('He is so tired that he slept.','so ~ that …','so tired that');
 found('I can not wait to see you.','Can’t wait to','can not wait to');
 found("Let's go.","let us (= let's)","Let's");
 found('We fulfill the promise.','fulfil(영국식) = fulfill(미국식)','fulfill');
 found('I regiment my day.','regiment(동사)','regiment');
});
test('missing, nearly-said and unusable expressions are reported honestly',()=>{
 assert.equal(S.findExpression('I was thinking about lunch.','Needless to say').status,'missing');
 const partial=S.findExpression('money itself could start losing its importance','Money itself could begin losing its importance.');
 assert.equal(partial.status,'partial');assert.ok(partial.ratio>=.75);
 assert.equal(S.findExpression('anything','—').status,'skip');
 assert.equal(S.findExpression('','come up with').status,'missing');
});

function fakeRecognition(){
 const made=[];
 class Fake{constructor(){made.push(this);this.started=0;}start(){this.started++;}stop(){this.stopped=true;}abort(){this.aborted=true;}}
 Fake.prototype.processLocally=false;
 return {Fake,made};
}
const heard=(...parts)=>({results:parts.map(([text,final])=>Object.assign([{transcript:text}],{isFinal:final}))});
test('dictation keeps words across automatic restarts, pause and resume',async()=>{
 const {Fake,made}=fakeRecognition(),changes=[];let clock=0;
 const d=S.createDictation(Fake,{onChange:t=>changes.push(t),now:()=>clock});
 d.start();assert.equal(made.length,1);assert.equal(made[0].lang,'en-US');assert.equal(made[0].continuous,true);assert.equal(made[0].interimResults,true);
 made[0].onresult(heard(['I was',true],['think',false]));assert.equal(changes.at(-1),'I was think');
 made[0].onresult(heard(['I was',true],['thinking',true]));
 clock=5000;made[0].onend();assert.equal(made.length,2,'silence ends a browser session; recording continues');
 made[1].onresult(heard(['of taking',true]));assert.equal(d.text(),'I was thinking of taking');
 d.pause();assert.equal(made[1].stopped,true);made[1].onend();assert.equal(made.length,2);
 d.resume();assert.equal(made.length,3);made[2].onresult(heard(['a break.',true]));
 const done=d.stop();assert.equal(made[2].stopped,true);made[2].onend();
 assert.equal(await done,'I was thinking of taking a break.');
});
test('stop falls back to the heard text when the browser never ends the session',async()=>{
 const {Fake,made}=fakeRecognition();let later;
 const d=S.createDictation(Fake,{wait:fn=>later=fn});d.start();made[0].onresult(heard(['almost',false]));
 const done=d.stop();later();assert.equal(await done,'almost');assert.equal(made[0].aborted,true);
});
test('fatal errors are reported once and stop restarts; silence is not an error',async()=>{
 const {Fake,made}=fakeRecognition(),errors=[];let clock=0;
 const d=S.createDictation(Fake,{onError:e=>errors.push(e),now:()=>clock});
 d.start();made[0].onerror({error:'no-speech'});clock=9000;made[0].onend();assert.equal(made.length,2);assert.deepEqual(errors,[]);
 made[1].onerror({error:'not-allowed'});made[1].onend();assert.deepEqual(errors,['not-allowed']);assert.equal(made.length,2);assert.equal(d.failed,true);
 d.resume();assert.equal(made.length,2);assert.equal(await d.stop(),'');
});
test('a browser that ends instantly is not restarted forever',()=>{
 const {Fake,made}=fakeRecognition(),errors=[];
 const d=S.createDictation(Fake,{onError:e=>errors.push(e),now:()=>0});d.start();
 for(let i=0;i<10&&made.at(-1).onend;i++){const r=made.at(-1);r.onend();if(made.at(-1)===r)break;}
 assert.equal(errors[0],'restart-loop');assert.ok(made.length<=6);
});
test('start failures and abort leave no stale words',async()=>{
 class Broken{start(){throw Error('busy');}}
 const errors=[],d=S.createDictation(Broken,{onError:e=>errors.push(e)});d.start();assert.deepEqual(errors,['start-failed']);
 const {Fake,made}=fakeRecognition(),e=S.createDictation(Fake);e.start();made[0].onresult(heard(['old words',true]));e.abort();
 made[0].onresult(heard(['late event',true]));assert.equal(e.text(),'');assert.equal(made[0].aborted,true);assert.equal(await e.stop(),'');
});
test('dictation never calls the on-device availability check',()=>{
 const {Fake,made}=fakeRecognition();let asked=0;Fake.available=async()=>{asked++;return 'available';};
 S.createDictation(Fake).start();assert.equal(asked,0);assert.equal(made[0].processLocally,false);assert.equal('localAvailable' in S,false);
});
test('saved dictation preference must be a boolean',()=>{
 const s=C.initialState();assert.equal(C.validateState(s),true);
 s.voice={uri:'',online:false,dictation:true};assert.equal(C.validateState(s),true);assert.equal(C.migrateState(s).voice.dictation,true);
 s.voice.dictation='yes';assert.equal(C.validateState(s),false);
});
