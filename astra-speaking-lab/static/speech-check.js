/* Free speaking check: word comparison and optional browser dictation. No network code here. */
(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;else root.LabSpeech=api;})(typeof window!=='undefined'?window:this,function(){
'use strict';
// Past forms and participles mapped to the base form, so "came up with" can match "come up with".
const IRREGULAR={am:'be',is:'be',are:'be',was:'be',were:'be',been:'be',being:'be',has:'have',had:'have',having:'have',does:'do',did:'do',done:'do',doing:'do',goes:'go',went:'go',gone:'go',came:'come',got:'get',gotten:'get',made:'make',took:'take',taken:'take',gave:'give',given:'give',said:'say',says:'say',told:'tell',thought:'think',brought:'bring',bought:'buy',felt:'feel',kept:'keep',left:'leave',knew:'know',known:'know',saw:'see',seen:'see',found:'find',ran:'run',began:'begin',begun:'begin',became:'become',wrote:'write',written:'write',spoke:'speak',spoken:'speak',ate:'eat',eaten:'eat',drank:'drink',drunk:'drink',drove:'drive',driven:'drive',fell:'fall',fallen:'fall',forgot:'forget',forgotten:'forget',grew:'grow',grown:'grow',held:'hold',lost:'lose',met:'meet',paid:'pay',sent:'send',sat:'sit',slept:'sleep',spent:'spend',stood:'stand',taught:'teach',understood:'understand',won:'win',wore:'wear',worn:'wear',broke:'break',broken:'break',chose:'choose',chosen:'choose',caught:'catch',fought:'fight',heard:'hear',led:'lead',meant:'mean',built:'build',learnt:'learn',dreamt:'dream',sang:'sing',sung:'sing',swam:'swim',threw:'throw',thrown:'throw',flew:'fly',flown:'fly',drew:'draw',drawn:'draw',shown:'show',rose:'rise',risen:'rise',rode:'ride',woke:'wake',woken:'wake',hid:'hide',hidden:'hide',shook:'shake',stole:'steal',stolen:'steal',sold:'sell',stuck:'stick',struck:'strike',swore:'swear',tore:'tear',fed:'feed',fled:'flee',dealt:'deal',dug:'dig',hung:'hang',lit:'light',lent:'lend',bent:'bend',sought:'seek',spun:'spin',burnt:'burn',an:'a'};
const NUMBERS={zero:'0',one:'1',two:'2',three:'3',four:'4',five:'5',six:'6',seven:'7',eight:'8',nine:'9',ten:'10',eleven:'11',twelve:'12',thirteen:'13',fourteen:'14',fifteen:'15',sixteen:'16',seventeen:'17',eighteen:'18',nineteen:'19',twenty:'20',thirty:'30',forty:'40',fifty:'50',sixty:'60',seventy:'70',eighty:'80',ninety:'90',hundred:'100'};
const IS_HAS=new Set(['it','that','there','here','what','where','who','he','she','how','this','everything','nothing','something','someone','everyone']);
const GAP_WORDS=new Set(['someone','somebody','something','sb','sth']);
const POSSESSIVE=new Set(["one's","someone's","somebody's"]);
const REFLEXIVE=['myself','yourself','himself','herself','itself','ourselves','yourselves','themselves','oneself'];
const WORD=/[A-Za-z0-9\u00C0-\u024F]+(?:'[A-Za-z\u00C0-\u024F]+)*/g;
const MAX_CELLS=4000000;

function forms(word){
 const w=String(word).toLowerCase(),out=new Set([w]);
 const add=x=>{if(x.length>=3)out.add(x);};
 if(NUMBERS[w])out.add(NUMBERS[w]);
 if(IRREGULAR[w])out.add(IRREGULAR[w]);
 if(w.length>3){
  if(/i(?:es|ed)$/.test(w))add(w.slice(0,-3)+'y');
  if(w.endsWith('es'))add(w.slice(0,-2));
  if(w.endsWith('s')&&!w.endsWith('ss'))add(w.slice(0,-1));
  if(w.endsWith('ed')){add(w.slice(0,-2));add(w.slice(0,-1));if(/([b-df-hj-np-tv-z])\1ed$/.test(w))add(w.slice(0,-3));}
  if(w.endsWith('ing')){const s=w.slice(0,-3);if(s.length>=3){add(s);add(s+'e');if(/([b-df-hj-np-tv-z])\1$/.test(s))add(s.slice(0,-1));}}
 }
 return out;
}
const formSet=(...words)=>{const out=new Set();for(const w of words)for(const f of forms(w))out.add(f);return out;};
// Contractions become separate words so "I'm" and "I am" compare as the same answer.
function expand(word){
 const w=word.toLowerCase();let m;
 if(w==="let's")return [formSet('let'),formSet('us')];
 if(w==="can't"||w==='cannot')return [formSet('can'),formSet('not')];
 if(w==="won't")return [formSet('will'),formSet('not')];
 if(w==="shan't")return [formSet('shall'),formSet('not')];
 if(w==="ain't")return [formSet('am','is','are'),formSet('not')];
 if((m=w.match(/^(.+)n't$/)))return [...expand(m[1]),formSet('not')];
 if((m=w.match(/^(.+)'(m|re|ve|ll|d|s)$/))){
  const [,base,suffix]=m,tail={m:['am'],re:['are'],ve:['have'],ll:['will'],d:['would','had']}[suffix];
  if(tail)return [...expand(base),formSet(...tail)];
  if(IS_HAS.has(base))return [...expand(base),formSet('is','has')];
  return [formSet(w,base)];
 }
 return [formSet(w)];
}
function tokenize(text){
 const s=String(text??'').replace(/[’‘`]/g,"'"),out=[];
 for(const m of s.matchAll(WORD))for(const f of expand(m[0]))out.push({forms:f,start:m.index,end:m.index+m[0].length});
 return out;
}
function same(a,b){const [small,large]=a.size<=b.size?[a,b]:[b,a];for(const x of small)if(large.has(x))return true;return false;}
// Longest common subsequence: which example words were said, in the same order.
function align(a,b){
 const n=a.length,m=Math.min(b.length,Math.floor(MAX_CELLS/(n+1))),w=m+1,dp=new Uint16Array((n+1)*w),pairs=[];
 for(let i=n-1;i>=0;i--)for(let j=m-1;j>=0;j--)dp[i*w+j]=same(a[i].forms,b[j].forms)?dp[(i+1)*w+j+1]+1:Math.max(dp[(i+1)*w+j],dp[i*w+j+1]);
 let i=0,j=0;while(i<n&&j<m){if(same(a[i].forms,b[j].forms)){pairs.push([i,j]);i++;j++;}else if(dp[(i+1)*w+j]>=dp[i*w+j+1])i++;else j++;}
 return pairs;
}
function compare(said,sample){
 const text=String(sample??''),want=tokenize(text),got=tokenize(said),pairs=align(want,got);
 const hit=new Set(pairs.map(p=>p[0])),spans=new Map();
 want.forEach((t,i)=>{const key=t.start+':'+t.end,span=spans.get(key)||{start:t.start,end:t.end,all:true};span.all=span.all&&hit.has(i);spans.set(key,span);});
 const segments=[];let cursor=0;
 for(const s of spans.values()){if(s.start>cursor)segments.push({kind:'plain',text:text.slice(cursor,s.start)});segments.push({kind:s.all?'hit':'miss',text:text.slice(s.start,s.end)});cursor=s.end;}
 if(cursor<text.length)segments.push({kind:'plain',text:text.slice(cursor)});
 const total=want.length,hits=pairs.length;
 return {segments,total,hits,ratio:total?hits/total:0,saidWords:got.length,extra:got.length-hits};
}
// Placeholders such as ~, someone, one's and A/B can stand for any short run of words.
function pattern(expression){
 const src=String(expression??'').replace(/[’‘`]/g,"'");
 const alternatives=src.includes('=')?src.replace(/[()]/g,' ').split('='):[src];
 return alternatives.map(alt=>{
  alt=alt.replace(/\([^()]*[^\x00-\x7f][^()]*\)/g,' ').replace(/\([^()]*\)/g,' ~ ').replace(/…|\.{3}/g,' ~ ').replace(/~[A-Za-z]*/g,' ~ ');
  const letters=/\bA\b/.test(alt)&&/\bB\b/.test(alt),items=[];
  const gap=(min,max)=>{const last=items[items.length-1];if(last?.gap){last.min=Math.max(last.min,min);last.max+=max;}else items.push({gap:true,min,max});};
  for(const piece of alt.split(/\s+/)){
   if(!piece)continue;
   const clean=piece.replace(/^[^\p{L}\p{N}~']+|[^\p{L}\p{N}~']+$/gu,'');
   const lower=clean.toLowerCase();
   if(!/[\p{L}\p{N}~]/u.test(clean))continue;
   if(clean==='~')gap(0,6);
   else if(/[^\x00-ɏ]/.test(clean))gap(1,4);
   else if(letters&&/^[ABC]$/.test(clean))gap(1,6);
   else if(GAP_WORDS.has(lower))gap(1,4);
   else if(POSSESSIVE.has(lower))gap(1,3);
   else if(lower==='oneself')items.push({forms:formSet(...REFLEXIVE)});
   else if(clean.includes('/'))items.push({forms:formSet(...clean.split('/').filter(Boolean))});
   else for(const t of tokenize(clean))items.push({forms:t.forms});
  }
  while(items[0]?.gap)items.shift();while(items[items.length-1]?.gap)items.pop();
  return items;
 }).filter(items=>items.some(x=>!x.gap));
}
function matchFrom(items,tokens,pi,ti){
 if(pi===items.length)return ti;
 const p=items[pi];
 if(p.gap){for(let k=p.min;k<=p.max&&ti+k<=tokens.length;k++){const end=matchFrom(items,tokens,pi+1,ti+k);if(end>=0)return end;}return -1;}
 return ti<tokens.length&&same(p.forms,tokens[ti].forms)?matchFrom(items,tokens,pi+1,ti+1):-1;
}
function findExpression(said,expression){
 const text=String(said??''),tokens=tokenize(text),alternatives=pattern(expression);
 if(!alternatives.length)return {status:'skip',words:0};
 const words=Math.max(...alternatives.map(items=>items.filter(x=>!x.gap).length));
 for(const items of alternatives)for(let start=0;start<tokens.length;start++){
  const end=matchFrom(items,tokens,0,start);
  if(end>start)return {status:'found',words,evidence:text.slice(tokens[start].start,tokens[end-1].end)};
 }
 let best=0;
 for(const items of alternatives){const plain=items.filter(x=>!x.gap);best=Math.max(best,align(plain,tokens).length/plain.length);}
 return {status:words>=4&&best>=.75?'partial':'missing',words,ratio:best};
}
// Browser speech recognition wrapper. The Recognition class is injected so it can be tested without a browser.
function createDictation(Recognition,{lang='en-US',onChange=()=>{},onError=()=>{},now=()=>Date.now(),wait=(fn,ms)=>setTimeout(fn,ms)}={}){
 let rec=null,wanted=false,fatal=false,committed='',session='',interim='',waiters=[],startedAt=0,quickEnds=0;
 const join=(...parts)=>parts.map(p=>String(p||'').trim()).filter(Boolean).join(' ');
 const text=()=>join(committed,session,interim);
 const settle=()=>{committed=join(committed,session,interim);session='';interim='';};
 const release=()=>{const list=waiters;waiters=[];list.forEach(fn=>fn(text()));};
 function fail(code){fatal=true;wanted=false;onError(code);}
 function launch(){
  if(rec||fatal)return;
  let r;
  try{r=new Recognition();}catch(e){fail('start-failed');return;}
  rec=r;r.lang=lang;r.continuous=true;r.interimResults=true;r.maxAlternatives=1;
  r.onresult=e=>{
   if(r!==rec)return;
   let done='',live='';
   for(let i=0;i<e.results.length;i++){const result=e.results[i],words=result?.[0]?.transcript||'';if(result.isFinal)done=join(done,words);else live=join(live,words);}
   session=done;interim=live;onChange(text());
  };
  r.onerror=e=>{if(r!==rec)return;const code=String(e?.error||'unknown');if(code!=='no-speech'&&code!=='aborted')fail(code);};
  r.onend=()=>{
   if(r!==rec)return;
   rec=null;settle();onChange(text());
   if(wanted&&!fatal){
    // Browsers end a session after silence; restart it while the recording continues.
    quickEnds=now()-startedAt<1000?quickEnds+1:0;
    if(quickEnds>=5)fail('restart-loop');else{launch();return;}
   }
   release();
  };
  startedAt=now();
  try{r.start();}catch(e){rec=null;fail('start-failed');}
 }
 return {
  start(){committed='';session='';interim='';fatal=false;quickEnds=0;wanted=true;launch();},
  pause(){wanted=false;try{rec?.stop();}catch(e){}},
  resume(){if(fatal)return;wanted=true;launch();},
  stop(timeout=2500){
   wanted=false;
   return new Promise(resolve=>{
    if(!rec){settle();resolve(text());return;}
    waiters.push(resolve);
    try{rec.stop();}catch(e){}
    wait(()=>{if(!waiters.includes(resolve))return;const r=rec;rec=null;try{r?.abort();}catch(e){}settle();release();},timeout);
   });
  },
  abort(){wanted=false;const r=rec;rec=null;try{r?.abort();}catch(e){}committed='';session='';interim='';release();},
  text,
  get failed(){return fatal;},
  get listening(){return !!rec;}
 };
}
// On-device checks (SpeechRecognition.available) are deliberately not used: the call crashed a headless Chromium 141 page in testing.
return {forms,tokenize,compare,pattern,findExpression,createDictation};
});
