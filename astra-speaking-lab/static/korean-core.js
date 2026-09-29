/* Korean prompts and paragraph/source alignment. No network or model calls. */
(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;else root.LabKorean=api;})(typeof window!=='undefined'?window:this,function(){
'use strict';
const str=(x,n=4000)=>typeof x==='string'&&x.trim().length>0&&x.length<=n;
const id=x=>typeof x==='string'&&/^[A-Za-z0-9_-]{1,150}$/.test(x)&&!['__proto__','constructor','prototype'].includes(x);
const korean=x=>str(x)&&/[가-힣]/.test(x);
const norm=x=>String(x).replace(/[‘’]/g,"'").replace(/\s+/g,' ').toLowerCase().trim();
const target=c=>c.chunk_kind?c.expression:c.practice_sample_en||c.example_en||c.source_quote||c.expression;
function validTranslation(t,source){return !!t&&typeof t==='object'&&str(t.source_en)&&korean(t.korean_text)&&['browser','local_ai','deepl'].includes(t.engine)&&(source===undefined||t.source_en===source);}
const TRANSCRIPT_CACHE_LIMIT=6000,TRANSCRIPT_CACHE_CHARS=1000000;
function validTranscriptCache(rows){
 if(!Array.isArray(rows)||rows.length>TRANSCRIPT_CACHE_LIMIT)return false;
 let size=0;const seen=new Set();
 return rows.every(t=>{if(!validTranslation(t)||t.korean_text.length>2000||seen.has(t.source_en))return false;seen.add(t.source_en);size+=t.source_en.length+t.korean_text.length;return size<=TRANSCRIPT_CACHE_CHARS;});
}
function transcriptMeaning(rows,text){const t=(rows||[]).find(t=>t.source_en===text);return validTranslation(t,text)?t.korean_text:'';}
function cacheTranscriptMeaning(rows,t){
 if(!validTranslation(t)||t.korean_text.length>2000)throw Error('문장 전체의 한국어 뜻을 확인하지 못했습니다.');
 const next=(rows||[]).filter(x=>x.source_en!==t.source_en);next.push({source_en:t.source_en,korean_text:t.korean_text,engine:t.engine});
 let size=next.reduce((n,t)=>n+t.source_en.length+t.korean_text.length,0);
 while(next.length>TRANSCRIPT_CACHE_LIMIT||size>TRANSCRIPT_CACHE_CHARS){const old=next.shift();size-=old.source_en.length+old.korean_text.length;}
 return next;
}
function ko(c,cache){
 // A DeepL translation the learner chose replaces earlier machine meanings.
 if(cache?.engine==='deepl'&&validTranslation(cache,target(c)))return cache.korean_text;
 if(c.chunk_kind&&c.meaning_source==='local_ai'&&korean(c.meaning_ko))return c.meaning_ko;
 if(validTranslation(cache,target(c)))return cache.korean_text;
 if(!c.media&&korean(c.cue_ko))return c.cue_ko;
 return '';
}
function sourceParagraph(chosen){
 if(!Array.isArray(chosen)||chosen.length<2||chosen.length>5||new Set(chosen.map(c=>c.id)).size!==chosen.length||chosen.some(c=>!id(c.id)||!str(c.sentence_en)||!korean(c.korean_text)))throw Error('한국어가 준비된 문장 2~5개를 선택하세요.');
 return {title:'학습한 문장 이어 말하기',task_ko:chosen.map(c=>c.korean_text.trim()).join(' '),sample_en:chosen.map(c=>c.sentence_en.trim()).join(' '),situation_ko:chosen.map(c=>c.korean_text.trim()).join(' / '),
  alignment:chosen.map(c=>({card_id:c.id,korean_cue:c.korean_text.trim(),english_use:c.sentence_en.trim(),source_expression:c.sentence_en.trim()}))};
}
function validateParagraph(p,chosen,{source=false}={}){
 if(!p||!Array.isArray(chosen)||chosen.length<2||chosen.length>5||new Set(chosen.map(c=>c.id)).size!==chosen.length||!korean(p.title)||p.title.length>200||!korean(p.task_ko)||!korean(p.situation_ko)||!str(p.sample_en,6000)||!Array.isArray(p.alignment)||p.alignment.length!==chosen.length)return false;
 const byId=new Map(chosen.map(c=>[c.id,c]));const seen=new Set();
 return p.alignment.every(a=>{
  const c=byId.get(a?.card_id);if(!c||seen.has(c.id)||!korean(a.korean_cue)||!p.task_ko.includes(a.korean_cue)||!str(a.english_use)||!p.sample_en.includes(a.english_use)||!str(a.source_expression)||!c.sentence_en.includes(a.source_expression))return false;
  const words=a.source_expression.match(/[A-Za-z]+(?:['’][A-Za-z]+)?/g)||[];
  if(!source&&(words.length<3||!norm(a.english_use).includes(norm(a.source_expression))))return false;
  seen.add(c.id);return true;
 });
}
return {target,ko,korean,validTranslation,validTranscriptCache,transcriptMeaning,cacheTranscriptMeaning,sourceParagraph,validateParagraph};
});
