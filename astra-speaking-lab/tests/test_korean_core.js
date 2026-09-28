const {test}=require('node:test'),assert=require('node:assert/strict');
const K=require('../static/korean-core'),C=require('../static/core'),Y=require('../static/youtube-core');
const chosen=[{id:'one',sentence_en:'I was thinking of taking a break.',korean_text:'잠깐 쉴까 생각하고 있었어요.'},{id:'two',sentence_en:'Then I came up with a different plan.',korean_text:'그러다가 다른 계획을 생각해 냈어요.'}];
function card(){const c=Y.card({id:'M7lc1UVf-VE'},Y.cues('0:00\n'+chosen[0].sentence_en)[0],{expression:chosen[0].sentence_en,meaning_ko:'원문 문장 연습'});c.chunk_kind='sentence';c.meaning_source='none';return c;}
test('Korean cache is bound to the exact English sentence and survives backup',()=>{const c=card(),t={source_en:c.expression,korean_text:chosen[0].korean_text,engine:'browser'},s=C.initialState();s.customCards=[c];s.translations[c.id]=t;const restored=C.migrateState(JSON.parse(JSON.stringify(s)),new Map());assert.equal(C.cardExercise(c,restored.translations[c.id]).task_ko,chosen[0].korean_text);s.translations[c.id].source_en='A different English sentence.';assert.throws(()=>C.migrateState(s,new Map()));});
test('untranslated captions cannot masquerade as a Korean sentence version',()=>{const c=card();assert.equal(K.ko(c),'');assert.equal(K.validTranslation({source_en:c.expression,korean_text:'English only',engine:'browser'}),false);assert.equal(K.ko(c,{source_en:'Wrong sentence',korean_text:'다른 문장',engine:'browser'}),'');});
test('whole-sentence AI meaning replaces an old generic situation instruction',()=>{const c=card();c.meaning_source='local_ai';c.meaning_ko=chosen[0].korean_text;c.practice_task_ko='원래 장면을 떠올리며 말하세요.';assert.equal(C.cardExercise(c).task_ko,chosen[0].korean_text);});
test('source paragraph combines all Korean sentences and aligns the English sample',()=>{const p=K.sourceParagraph(chosen);assert.equal(p.task_ko,chosen.map(c=>c.korean_text).join(' '));assert.equal(p.sample_en,chosen.map(c=>c.sentence_en).join(' '));assert.ok(K.validateParagraph(p,chosen,{source:true}));assert.deepEqual(p.alignment.map(a=>a.card_id),['one','two']);});
test('paragraph requires multiple distinct sentences with actual Korean versions',()=>{for(const rows of [[chosen[0]],[chosen[0],chosen[0]],[chosen[0],{...chosen[1],korean_text:''}]])assert.throws(()=>K.sourceParagraph(rows));});
test('paragraph alignment rejects missing cards invented source phrases and foreign examples',()=>{const good=K.sourceParagraph(chosen);for(const edit of [p=>p.alignment.pop(),p=>p.alignment[1].card_id='one',p=>p.alignment[0].source_expression='made up words',p=>p.alignment[0].english_use='words not in the sample',p=>p.alignment[0].korean_cue='문단에 없는 내용']){const p=structuredClone(good);edit(p);assert.equal(K.validateParagraph(p,chosen),false);}});
test('transcript translations persist without a learning-card ID and match exact source text',()=>{
 const t={source_en:chosen[0].sentence_en,korean_text:chosen[0].korean_text,engine:'browser'},s=C.initialState();s.transcriptTranslations=K.cacheTranscriptMeaning([],t);
 const copy=C.migrateState(JSON.parse(JSON.stringify(s)),new Map());assert.equal(copy.customCards.length,0);assert.equal(K.transcriptMeaning(copy.transcriptTranslations,t.source_en),t.korean_text);assert.equal(K.transcriptMeaning(copy.transcriptTranslations,t.source_en+' Changed.'),'');
 const old=C.initialState();delete old.transcriptTranslations;assert.deepEqual(C.migrateState(old,new Map()).transcriptTranslations,[]);
});
test('invalid and duplicated transcript meanings cannot enter a restored backup',()=>{
 const good={source_en:chosen[0].sentence_en,korean_text:chosen[0].korean_text,engine:'browser'};
 for(const rows of [[{...good,korean_text:'English only'}],[{...good,engine:'untrusted'}],[good,good],{},[null]]){const s=C.initialState();s.transcriptTranslations=rows;assert.throws(()=>C.migrateState(s,new Map()));}
});
test('transcript cache replaces exact matches and bounds retained text without changing the new meaning',()=>{
 const t={source_en:'An exact sentence.',korean_text:'정확히 일치하는 문장입니다.',engine:'browser'};
 const old=Array.from({length:6000},(_,i)=>({source_en:'Sentence '+i+'.',korean_text:'뜻 '+i,engine:'browser'}));const next=K.cacheTranscriptMeaning(old,t);assert.equal(next.length,6000);assert.equal(next[0].source_en,'Sentence 1.');assert.ok(K.validTranscriptCache(next));
 const updated=K.cacheTranscriptMeaning(next,{...t,korean_text:'바꾼 한국어 뜻입니다.'});assert.equal(updated.length,next.length);assert.equal(K.transcriptMeaning(updated,t.source_en),'바꾼 한국어 뜻입니다.');
 const large=Array.from({length:450},(_,i)=>({source_en:'Sentence '+i+'.',korean_text:'가'.repeat(2000),engine:'browser'}));let cache=large;for(let i=0;i<100;i++)cache=K.cacheTranscriptMeaning(cache,{source_en:'New sentence '+i+'.',korean_text:'나'.repeat(2000),engine:'browser'});assert.ok(K.validTranscriptCache(cache));assert.ok(cache.length<550);assert.equal(cache.at(-1).source_en,'New sentence 99.');
});
