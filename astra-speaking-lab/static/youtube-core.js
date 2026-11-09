/* Local text processing only. No network and no language model. */
(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;else root.LabYouTube=api;})(typeof window!=='undefined'?window:this,function(){
'use strict';
const validId=id=>typeof id==='string'&&/^[A-Za-z0-9_-]{11}$/.test(id);
const text=(s,n=4000)=>typeof s==='string'&&s.length<=n;
const seconds=n=>Number.isFinite(n)&&n>=0&&n<=86400;
function time(s){
 s=String(s??'').trim().replace(',','.');
 if(/^\d+(?:\.\d+)?$/.test(s))return seconds(Number(s))?Number(s):null;
 if(!/^\d{1,2}:\d{2}(?::\d{2})?(?:\.\d{1,3})?$/.test(s))return null;
 const parts=s.split(':').map(Number);if(parts.slice(1).some(n=>n>=60))return null;
 const n=parts.reduce((a,b)=>a*60+b,0);return seconds(n)?n:null;
}
function stamp(s){if(s==null)return '시간 미지정';const n=Math.floor(s);return [Math.floor(n/3600),Math.floor(n/60)%60,n%60].filter((_,i)=>i>0||n>=3600).map((v,i)=>i?v.toString().padStart(2,'0'):v).join(':');}
function captionStamp(s){const ms=Math.floor(s*1000),sec=ms/1000;return Math.floor(sec/3600)+':'+String(Math.floor(sec/60)%60).padStart(2,'0')+':'+(sec%60).toFixed(3).padStart(6,'0');}
function video(input){
 let u;try{u=new URL(String(input).trim());}catch(e){throw Error('YouTube 영상 링크 전체를 입력하세요.');}
 if(!['http:','https:'].includes(u.protocol)||u.username||u.password||u.port)throw Error('올바른 YouTube 영상 링크를 사용하세요.');
 const host=u.hostname.toLowerCase(),parts=u.pathname.split('/').filter(Boolean);let id;
 if(host==='youtu.be'&&parts.length===1)id=parts[0];
 else if(['youtube.com','www.youtube.com','m.youtube.com','music.youtube.com'].includes(host))id=u.pathname==='/watch'?u.searchParams.get('v'):['shorts','embed','live'].includes(parts[0])&&parts.length===2?parts[1]:null;
 if(!validId(id))throw Error('동영상 한 편의 YouTube 링크가 필요합니다. 채널·재생목록 링크는 사용할 수 없습니다.');
 const t=u.searchParams.get('t')||u.searchParams.get('start')||'0';let start=time(t);
 if(start===null&&/^(?:\d+h)?(?:\d+m)?(?:\d+s)?$/.test(t))start=Number(t.match(/(\d+)h/)?.[1]||0)*3600+Number(t.match(/(\d+)m/)?.[1]||0)*60+Number(t.match(/(\d+)s/)?.[1]||0);
 if(!seconds(start))throw Error('영상 시작 시간을 확인하세요.');
 return {id,start,url:watch(id,start)};
}
function watch(id,start=0){if(!validId(id)||!seconds(start))throw Error('영상 정보가 올바르지 않습니다.');return 'https://www.youtube.com/watch?v='+id+'&t='+Math.floor(start)+'s';}
function embed(id,start,end){if(validId(id)&&start===null&&end===null)return 'https://www.youtube.com/embed/'+id+'?autoplay=0&playsinline=1&rel=0';if(!validId(id)||!seconds(start)||!seconds(end)||end<=start)throw Error('재생 구간을 확인하세요.');return 'https://www.youtube.com/embed/'+id+'?start='+Math.floor(start)+'&end='+Math.ceil(end)+'&autoplay=0&playsinline=1&rel=0&cc_lang_pref=en';}
function clean(s){return s.replace(/<[^>]*>/g,'').replace(/&amp;/g,'&').replace(/&quot;/g,'"').replace(/&#39;|&apos;/g,"'").replace(/&nbsp;/g,' ').replace(/&lt;/g,'<').replace(/&gt;/g,'>').replace(/\s+/g,' ').trim();}
function cues(raw){
 if(!text(raw,200000)||!raw.trim())throw Error('영어 자막을 붙여 넣으세요. 최대 200,000자입니다.');
 const lines=raw.replace(/\r/g,'').split('\n'),out=[];let current=null;
 const push=()=>{if(current?.text.trim()){current.text=clean(current.text);if(current.text&&current.text.length<=4000)out.push(current);else if(current.text.length>4000)throw Error('한 자막이 너무 깁니다. 문장별로 줄을 나눠 주세요.');}current=null;};
 for(let i=0;i<lines.length;i++){
  const line=lines[i].trim();if(!line||/^WEBVTT|^NOTE|^Kind:|^Language:/i.test(line)||/^\d+$/.test(line)&&lines[i+1]?.includes('-->'))continue;
  const range=line.match(/^(\d{1,2}:\d{2}(?::\d{2})?(?:[.,]\d{1,3})?)\s*-->\s*(\d{1,2}:\d{2}(?::\d{2})?(?:[.,]\d{1,3})?)(?:\s.*)?$/);
  const single=line.match(/^\[?(\d{1,2}:\d{2}(?::\d{2})?(?:[.,]\d{1,3})?)\]?(?:\s+(.*))?$/);
  if(range||single){push();const start=time((range||single)[1]),end=range?time(range[2]):null;if(start===null||range&&(end===null||end<=start))throw Error('자막의 시간 표기를 확인하세요.');current={start,end,text:range?'':single?.[2]||'',estimated:!range};}
  else if(current)current.text+=' '+line;
  else{current={start:null,end:null,text:line,estimated:false};if(!lines[i+1]||!/^\d/.test(lines[i+1]))push();}
 }
 push();if(!out.length||out.length>3000)throw Error('자막을 읽지 못했거나 너무 깁니다. 3,000구간 이하로 나눠 주세요.');
 for(let i=0;i<out.length;i++){const c=out[i];if(c.start!==null&&c.end===null)c.end=out[i+1]?.start>c.start?Math.min(c.start+30,out[i+1].start):Math.min(86400,c.start+8);if(c.end!==null&&c.end<=c.start)throw Error('자막 끝 시간을 확인하세요.');c.id='cue_'+i;}
 return out;
}
function sentenceParts(s){
 const parts=[];let from=0;
 for(let i=0;i<s.length;i++){
  if(!/[.!?]/.test(s[i]))continue;
  if(s[i]==='.'&&(/\d/.test(s[i-1]||'')&&/\d/.test(s[i+1]||'')||/(?:\b(?:Mr|Mrs|Ms|Dr|Prof|St|vs|etc)|\b[A-Z]|\b(?:e\.g|i\.e))$/i.test(s.slice(0,i))))continue;
  let j=i+1;while(j<s.length&&/[.!?"'”’)]/.test(s[j]))j++;
  if(j<s.length&&!/\s/.test(s[j]))continue;
  parts.push(s.slice(from,j).trim());from=j;i=j-1;
 }
 if(s.slice(from).trim())parts.push(s.slice(from).trim());
 return parts.filter(Boolean);
}
const MAX_CHUNK_WORDS=90;
const LABEL=/^\s*(?:\[(?:music|applause|laughter|laughing|cheering|silence)\]|\((?:music|applause|laughter|laughing|cheering|silence)\))\s*[.!?]?\s*$/i;
// Auto captions usually have no full stops. These word lists estimate where a spoken sentence ends:
// never after an article, preposition, conjunction, auxiliary or subject pronoun; gladly before "yeah", "oh", "I think".
const NO_END=new Set(("a an the this these those my your his its our their some any every each of to in on at for with from by about into onto over under after "+
 "before between through during without within like as than and or but because so that which who whom whose if when while although though unless until since "+
 "where whether will would can could should may might must shall i we they he she not very just really "+
 "gonna wanna gotta kind sort more most less such also even still i'm you're we're they're it's that's there's he's she's what's i've you've we've they've i'll "+
 "you'll we'll they'll i'd you'd we'd they'd don't doesn't didn't can't won't wouldn't couldn't shouldn't isn't aren't wasn't weren't haven't hasn't hadn't").split(' '));
// Verbs like "do" or "is" usually continue, but can also end a clause ("what you do"): a lighter penalty.
const SOFT_END=new Set('is are was were am be been being have has had do does did'.split(' '));
const GOOD_END={yeah:3,yes:3,yep:3,yup:3,okay:3,ok:3,right:2,too:2,though:2,anyway:2,ago:2,again:1.5,really:1,me:1,him:1,them:1,us:1,you:.5,it:.5,there:.5,here:.5,now:.5,today:1,tonight:1,yesterday:1,tomorrow:1};
const STARTS={yeah:4,yes:4,yep:4,yup:4,oh:4,okay:4,ok:4,alright:4,well:3,wow:4,hey:4,hi:4,hello:4,um:3,uh:3,hmm:3,anyway:3,thanks:4,thank:4,please:3,absolutely:3,exactly:3,honestly:3,"let's":3,"what's":1.5,"that's":1.5,so:2.5,but:2.5,and:1.5,then:1.5,now:1,actually:1.5,because:1,no:2,i:2};
const PAIRS={'i think':2,'i mean':2,'i guess':2,'i feel':1.5,'i remember':2,'i believe':1.5,'i love':1,'do you':2.5,'did you':2.5,'can you':2.5,'could you':2.5,'have you':2.5,'would you':2.5,'what do':2,'what did':2,'how do':2,'how did':2,'why do':2,'let me':2,'you know':-1.5};
const CONTINUES=new Set(['of','than','which','whom','whose','to','as']);
const bare=w=>String(w||'').toLowerCase().replace(/[’‘]/g,"'").replace(/[^a-z0-9']/g,'').replace(/^'+|'+$/g,'');
function boundaryScore(tokens,i){
 // Higher means "a new sentence probably starts at tokens[i]".
 const before=tokens[i-1]||'',prev=bare(before),next=bare(tokens[i]),after=bare(tokens[i+1]);
 let v=0;
 // Written punctuation is the best evidence; word lists only matter when it is missing.
 if(/[.!?]["'”’)]*$/.test(before))v+=8;else if(/(?:[,;:]["'”’)]*|--|—)$/.test(before))v+=2.5;
 else{if(NO_END.has(prev))v-=5;else if(SOFT_END.has(prev))v-=2.5;if(/^\d/.test(prev))v-=3;}
 v+=GOOD_END[prev]||0;
 if(CONTINUES.has(next))v-=3;
 v+=STARTS[next]||0;
 v+=PAIRS[next+' '+after]||0;
 return v;
}
const SPEECH_MIN=8,SPEECH_MAX=40,SPEECH_TARGET=24,STRONG_BOUNDARY=4;
function speechChunks(xs){
 // For captions without full stops: cut where wording and pauses suggest a sentence ends,
 // keeping each chunk between 8 and 40 words and its real caption start/end times.
 const out=[];let toks=[];
 const sameRun=(a,b)=>a.start===null&&b.start===null||a.start!==null&&b.start!==null&&b.start>=a.start&&b.start-a.end<=2;
 const emit=()=>{
  const n=toks.length;if(!n)return;
  const words=toks.map(t=>t.word),score=[0];
  for(let i=1;i<n;i++)score.push(boundaryScore(words,i)+toks[i].pause);
  const span=(a,b)=>toks[a].cue.start===null?0:toks[b].cue.start-toks[a].cue.start;
  let s=0;
  while(s<n){
   let hi=Math.min(n-1,s+SPEECH_MAX);while(hi>s+1&&span(s,hi)>45)hi--;
   const lo=s+SPEECH_MIN,last=Math.min(hi,n-4);let cut=-1;
   for(let i=lo;i<=last;i++)if(score[i]>=STRONG_BOUNDARY){cut=i;break;}
   if(cut<0&&n-s<=SPEECH_MAX&&span(s,n-1)<=45)cut=n;
   if(cut<0){let best=-Infinity;for(let i=Math.min(lo,hi);i<=hi;i++){const v=score[i]-Math.abs(i-s-SPEECH_TARGET)*.05;if(v>best){best=v;cut=i;}}}
   if(cut<=s)cut=Math.min(n,s+SPEECH_MAX);
   const first=toks[s],end=toks[cut-1],text=words.slice(s,cut).join(' ');
   const whole=/[.!?]["'”’)]*$/.test(text)&&(s===0||/[.!?]["'”’)]*$/.test(words[s-1]));
   out.push({...first.cue,text,end:end.cue.end,chunk_kind:whole?'sentence':'speech',estimated:!first.first||!end.last||toks.slice(s,cut).some(t=>t.cue.estimated)});
   s=cut;
  }
  toks=[];
 };
 for(const cue of xs){
  if(LABEL.test(cue.text)){emit();out.push({...cue});continue;}
  const prev=toks.at(-1)?.cue;
  if(prev&&!sameRun(prev,cue))emit();
  const gap=prev&&sameRun(prev,cue)&&prev.end!==null&&cue.start!==null?cue.start-prev.end:0;
  const words=cue.text.split(/\s+/).filter(Boolean);
  words.forEach((word,k)=>toks.push({word,cue,first:k===0,last:k===words.length-1,pause:k===0&&gap>=1.2?3:k===0&&gap>=.6?1.5:0}));
 }
 emit();
 return out;
}
function speechPieces(text,{maxWords=26,maxChars=180}={}){
 // Browsers can stop reading a long utterance after about 15 seconds (Chrome's online voices),
 // so read long sentences as consecutive pieces cut at commas or clause starts.
 // 26 words take about 13 seconds even at the slowest 0.75x setting.
 const out=[];
 for(const part of sentenceParts(String(text??''))){
  const toks=part.split(/\s+/).filter(Boolean);let s=0;
  while(s<toks.length){
   const rest=toks.slice(s).join(' ');
   if(toks.length-s<=maxWords&&rest.length<=maxChars){out.push(rest);break;}
   let hi=Math.min(toks.length-3,s+maxWords);while(hi>s+1&&toks.slice(s,hi).join(' ').length>maxChars)hi--;
   let cut=-1,best=-Infinity;
   for(let i=Math.min(s+4,hi);i<=hi;i++){const v=boundaryScore(toks,i)+(i-s)*.08;if(v>best){best=v;cut=i;}}
   if(cut<=s)cut=Math.max(s+1,hi);
   out.push(toks.slice(s,cut).join(' '));s=cut;
  }
 }
 return out;
}
function studyCues(xs){
 // Mostly unpunctuated captions (auto-generated): estimate sentence ends from wording and pauses.
 const spoken=xs.filter(c=>!LABEL.test(c.text)).map(c=>c.text).join(' '),wordCount=spoken.split(/\s+/).filter(Boolean).length;
 // Commas count too: a long but properly punctuated sentence keeps the sentence-based path.
 const marks=(spoken.match(/[.!?,;:]["'”’)]*(?=\s|$)/g)||[]).length;
 if(wordCount>=30&&marks*25<wordCount)return speechChunks(xs).map((cue,i)=>({...cue,id:'cue_'+i}));
 // Join caption fragments, then split at sentence boundaries. Keep actual caption ranges.
 const joined=[];let pending=null;
 const flush=()=>{if(pending)joined.push(pending);pending=null;};
 for(const cue of xs){
  if(LABEL.test(cue.text)){flush();joined.push({...cue});continue;}
  const parts=sentenceParts(cue.text);
  for(const part of parts){
   const next={...cue,text:part,estimated:cue.estimated||parts.length>1};
   const adjacent=pending&&(pending.start===null&&next.start===null||pending.start!==null&&next.start!==null&&next.start>=pending.start&&next.start-pending.end<=2&&next.end-pending.start<=45);
   if(adjacent&&pending.text.length+part.length<1000&&pending.text.split(/\s+/).length<40){pending.text+=' '+part;if(next.end!==null)pending.end=Math.max(pending.end,next.end);pending.estimated||=next.estimated;}
   else{flush();pending=next;}
   if(/[.!?]["'”’)]?$/.test(part))flush();
  }
 }
 flush();
 // Joining above stops at 40 words or 45 seconds even mid-sentence. When the captions are punctuated,
 // glue such a cut piece back to the words that finish its sentence, so meaning and translation stay whole.
 const ends=t=>/[.!?]["'”’)]?$/.test(t),words=t=>t.split(/\s+/).length,punctuated=joined.some(c=>ends(c.text)),whole=[];
 for(const cue of joined){
  const prev=whole.at(-1),nearby=prev&&(prev.start===null&&cue.start===null||prev.start!==null&&cue.start!==null&&cue.start>=prev.start&&cue.start-prev.end<=3);
  if(punctuated&&nearby&&!ends(prev.text)&&!/^\s*[\[(]/.test(cue.text)&&!/^\s*[\[(]/.test(prev.text)&&words(prev.text)+words(cue.text)<=MAX_CHUNK_WORDS&&prev.text.length+cue.text.length<1000){prev.text+=' '+cue.text;if(cue.end!==null)prev.end=Math.max(prev.end,cue.end);prev.estimated||=cue.estimated;}
  else whole.push({...cue});
 }
 const out=[];
 for(const cue of whole){
  let rest=cue.text,split=false;
  // A whole punctuated sentence may run to 90 words; unpunctuated speech is still cut near 35 words.
  const limit=punctuated&&ends(rest)?MAX_CHUNK_WORDS:60;
  while(rest.split(/\s+/).length>limit||rest.length>1000){
   const words=[...rest.matchAll(/\S+/g)];let cut=words[Math.min(35,words.length-1)].index;
   if(!cut)break;
   for(let i=15;i<Math.min(40,words.length);i++)if(/^(?:but|because|although|when|then|so|and)$/i.test(words[i][0])||/[,;:]$/.test(words[i-1][0])){cut=words[i].index;break;}
   out.push({...cue,text:rest.slice(0,cut).trim(),chunk_kind:'speech',estimated:true});rest=rest.slice(cut).trim();split=true;
  }
  if(rest)out.push({...cue,text:rest,chunk_kind:!split&&/[.!?]["'”’)]?$/.test(rest)?'sentence':'speech',estimated:cue.estimated||split});
 }
 return out.map((cue,i)=>({...cue,id:'cue_'+i}));
}
const patterns=[
 [/\b(?:I (?:was|am)|I'm) thinking (?:of|about)\b/i,'~할까 생각 중이다'],
 [/\byou(?:'|’)ll never guess\b/i,'무슨 일이 있었는지 짐작도 못할 것이다'],
 [/\b(?:look|looking) forward to\b/i,'~을 기대하다'],[/\b(?:get|getting|got) used to\b/i,'~에 익숙해지다'],[/\bused to\b/i,'예전에는 ~하곤 했다'],
 [/\b(?:end|ended|ends|ending) up\b/i,'결국 ~하게 되다'],[/\b(?:turn|turned|turns) out\b/i,'알고 보니 ~이다'],[/\bas long as\b/i,'~하기만 하면'],[/\beven if\b/i,'설령 ~하더라도'],[/\bas soon as\b/i,'~하자마자'],
 [/\b(?:make|made|making) sure\b/i,'반드시 확인하다'],[/\b(?:figure|figured|figuring) out\b/i,'알아내다'],[/\b(?:come|came|coming) up with\b/i,'생각해 내다'],[/\b(?:run|ran|running) out of\b/i,'~을 다 쓰다'],
 [/\b(?:I|we) (?:had|have) no idea\b/i,'전혀 몰랐다 / 모른다'],[/\b(?:it|that) depends on\b/i,'~에 달려 있다'],[/\bin case\b/i,'~할 경우에 대비해'],[/\bthere(?:'|’)s no point in\b/i,'~해 봐야 소용없다'],[/\bI (?:wonder|was wondering) if\b/i,'~인지 궁금하다 / 조심스럽게 부탁하다'],
 [/\bthe way (?:I|you|we|they)\b/i,'~하는 방식'],[/\binstead of\b/i,'~하는 대신에'],[/\bno matter (?:what|how|where|when)\b/i,'무엇을 / 어떻게 하든'],[/\b(?:be|am|is|are|was|were) supposed to\b/i,'~하기로 되어 있다'],[/\b(?:be|am|is|are|was|were) about to\b/i,'막 ~하려던 참이다'],
 [/\bit takes\b/i,'~하는 데 시간이 걸리다'],[/\bwhat if\b/i,'만약 ~하면 어떨까'],[/\b(?:keep|kept) in mind\b/i,'명심하다'],[/\bat least\b/i,'적어도'],[/\bwhen it comes to\b/i,'~에 관해서라면'],[/\b(?:take|took|taking) care of\b/i,'돌보다 / 처리하다']
];
function suggest(xs){const found=[],seen=new Set();for(const c of xs)for(const [re,meaning]of patterns){const match=c.text.match(re);if(match&&!seen.has(match[0].toLowerCase())){seen.add(match[0].toLowerCase());found.push({cue_id:c.id,expression:match[0],meaning_ko:meaning});}}return found.slice(0,30);}
function validPractice(c){const keys=['practice_task_ko','practice_sample_en','practice_origin'];return keys.every(k=>c[k]===undefined)||keys.every(k=>text(c[k],k==='practice_origin'?200:2000)&&c[k].trim());}
function validCard(c){return !!c&&typeof c==='object'&&/^yt_[A-Za-z0-9_-]{1,100}$/.test(c.id)&&c.lesson_id==='youtube'&&validPractice(c)&&(c.source_cue_id===undefined||typeof c.source_cue_id==='string'&&/^cue_\d+$/.test(c.source_cue_id))&&['expression','meaning_ko','cue_ko'].every(k=>text(c[k],k==='expression'?1000:500)&&c[k].trim())&&(c.chunk_kind===undefined||['sentence','speech'].includes(c.chunk_kind))&&(c.meaning_source===undefined||['none','local_ai'].includes(c.meaning_source))&&text(c.source_quote)&&c.source_quote.includes(c.expression)&&text(c.example_en)&&c.example_en===c.source_quote&&text(c.note)&&text(c.source_locator,300)&&c.media&&validId(c.media.video_id)&&((c.media.start===null&&c.media.end===null)||(seconds(c.media.start)&&seconds(c.media.end)&&c.media.end>c.media.start&&c.media.end-c.media.start<=120))&&c.source_url===watch(c.media.video_id,c.media.start??0);}
function card(v,c,item){
 if(!validId(v.id)||!c||!text(item.expression,1000)||!item.expression.trim()||!c.text.includes(item.expression)||!text(item.meaning_ko,500)||!item.meaning_ko.trim())throw Error('원문에 실제로 있는 표현과 한국어 뜻을 입력하세요.');
 const start=item.start??c.start,end=item.end??c.end;if(!(start===null&&end===null)&&(!seconds(start)||!seconds(end)||end<=start||end-start>120))throw Error('0초 이상, 길이 120초 이하의 재생 구간을 지정하세요.');
 const result={id:'yt_'+v.id+'_'+Date.now().toString(36)+'_'+Math.random().toString(36).slice(2,8),lesson_id:'youtube',core:true,expression:item.expression.trim(),meaning_ko:item.meaning_ko.trim(),cue_ko:item.use_case_ko?.trim()||`‘${item.meaning_ko.trim()}’라는 뜻을 쓸 법한 상황을 떠올리고 영어 한 문장으로 말하세요.`,source_quote:c.text,source_locator:(v.title||'YouTube')+' · '+stamp(start),source_url:watch(v.id,start??0),quote_type:'가져온 YouTube 자막 · 실제 음성과 대조',source_explanation:'자막은 자동 인식 오류가 있을 수 있습니다. 영상에서 이 구간을 직접 확인하세요.',note:item.note_ko||'한국어 뜻은 이 문맥에서 직접 확인하세요. 예문은 영상의 자막 원문입니다.',example_en:c.text,media:{video_id:v.id,start,end}};
 if(!validCard(result))throw Error('표현 카드의 내용이나 재생 구간을 확인하세요.');return result;
}
function importItems(raw,v,xs){
 if(!text(raw,1000000))throw Error('1,000,000자 이하의 JSON을 사용하세요.');let obj;try{obj=JSON.parse(raw.trim().replace(/^```(?:json)?\s*/,'').replace(/\s*```$/,''));}catch(e){throw Error('ChatGPT가 준 JSON 객체 전체를 붙여 넣으세요.');}
 if(obj.video_id!==v.id||!Array.isArray(obj.items)||!obj.items.length||obj.items.length>100)throw Error('현재 영상의 문장 1~100개가 들어 있는 JSON이 필요합니다.');
 const seen=new Set();return obj.items.map(item=>{const c=xs.find(c=>c.id===item?.cue_id),key=JSON.stringify([item?.cue_id,item?.expression]);if(!c||item.source_text!==c.text||seen.has(key))throw Error('자막 근거가 바뀌었거나 원문에 없는 표현입니다.');seen.add(key);const made=card(v,c,{...item,start:c.start,end:c.end});if(item.new_task_ko!==undefined&&(!text(item.new_task_ko,2000)||!item.new_task_ko.trim()||!text(item.new_sample_en,2000)||!item.new_sample_en.trim()))throw Error('새 상황의 한글 문제와 영어 예문을 함께 입력하세요.');return {card:made,task:item.new_task_ko||'',sample:item.new_sample_en||''};});
}
return {validId,time,stamp,captionStamp,video,watch,embed,cues,sentenceParts,speechPieces,boundaryScore,studyCues,suggest,validCard,card,importItems};
});
