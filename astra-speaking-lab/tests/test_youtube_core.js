const {test}=require('node:test'),assert=require('node:assert/strict');
const Y=require('../static/youtube-core.js'),C=require('../static/core.js');
const ID='M7lc1UVf-VE'; // Official YouTube developer documentation demo ID; captions below are synthetic.
const RAW="00:12.200 --> 00:16.700\nI was thinking of taking a break.\n\n00:17.100 --> 00:21.000\nThen I came up with a different plan.";
const make=()=>Y.card({id:ID,title:'Fixture'},Y.cues(RAW)[0],{expression:'thinking of',meaning_ko:'~할까 생각하다'});
test('YouTube links normalize common formats and reject foreign or executable URLs',()=>{for(const url of ['https://youtu.be/'+ID+'?t=1m2s','https://www.youtube.com/watch?v='+ID+'&t=62','https://www.youtube.com/shorts/'+ID+'?start=62'])assert.deepEqual(Y.video(url),{id:ID,start:62,url:Y.watch(ID,62)});for(const url of ['javascript:alert(1)','https://youtube.com.evil.example/watch?v='+ID,'https://youtube.com@evil.example/watch?v='+ID,'https://youtube.com/playlist?list=foo','https://youtube.com/watch?v=no'])assert.throws(()=>Y.video(url));});
test('caption times preserve fractions and reject invalid ranges',()=>{assert.equal(Y.time('01:02:03,125'),3723.125);assert.equal(Y.time('1:67'),null);assert.equal(Y.time('-2'),null);assert.equal(Y.time(Y.captionStamp(.125)),.125);assert.equal(Y.time(Y.captionStamp(86400)),86400);assert.throws(()=>Y.cues('0:15 --> 0:12\nText'));});
test('SRT, VTT and copied YouTube captions preserve grounded source lines',()=>{const srt=Y.cues('1\n00:00:01,250 --> 00:00:03,750\nI was thinking of going.\n\n2\n00:00:04,000 --> 00:00:06,000\nLet us make sure.');assert.equal(srt[0].start,1.25);assert.equal(srt[0].end,3.75);assert.equal(srt.length,2);const vtt=Y.cues('WEBVTT\n\n00:01.200 --> 00:03.500 align:start\n<b>Take care of</b> it.');assert.equal(vtt[0].text,'Take care of it.');const copy=Y.cues('0:12\nI was thinking of going.\n0:17\nI came up with a plan.');assert.equal(copy[0].end,17);assert.equal(copy[1].estimated,true);});
test('untimed text never gets fabricated source timestamps',()=>{const xs=Y.cues('I was thinking of leaving.\nBut I changed my mind.');assert.equal(xs[0].start,null);assert.equal(xs[0].end,null);const c=Y.card({id:ID},xs[0],{expression:'thinking of',meaning_ko:'생각하다'});assert.equal(c.media.start,null);assert.equal(c.media.end,null);assert.ok(!Y.embed(ID,null,null).includes('start='));});
test('rule candidates are actual source substrings and cannot invent expression matches',()=>{const xs=Y.cues(RAW);const found=Y.suggest(xs);assert.equal(found.length,2);for(const p of found)assert.ok(xs.find(c=>c.id===p.cue_id).text.includes(p.expression));assert.deepEqual(Y.suggest(Y.cues('0:00\nPurple flowers.')),[]);});
test('custom YouTube cards reject unsafe links and fabricated quotes',()=>{const c=make();assert.ok(Y.validCard(c));for(const edit of [x=>x.source_url='javascript:alert(1)',x=>x.media.video_id='invalid',x=>x.expression='not in the original',x=>x.media.end=x.media.start-1,x=>x.id='g01_01']){const bad=structuredClone(c);edit(bad);assert.equal(Y.validCard(bad),false);}});
test('YouTube cards and their review history survive a fresh backup import',()=>{const c=make(),s=C.initialState();s.customCards=[c];s.cards[c.id]={due:123};s.lastExerciseId='single_'+c.id;s.lastLessonId='youtube';const restored=C.migrateState(JSON.parse(JSON.stringify(s)),new Map());assert.equal(restored.customCards[0].id,c.id);assert.equal(restored.cards[c.id].due,123);const bad=structuredClone(s);bad.customCards[0].source_url='https://evil.example/';assert.throws(()=>C.migrateState(bad,new Map()));});
test('ChatGPT expression import verifies video and exact source, ignores model timestamps',()=>{const xs=Y.cues(RAW),reply={video_id:ID,items:[{cue_id:xs[0].id,source_text:xs[0].text,expression:'thinking of',meaning_ko:'생각하다',start:800,end:820,new_task_ko:'휴가 계획을 말하세요.',new_sample_en:'I was thinking of taking a week off.'}]};const got=Y.importItems(JSON.stringify(reply),{id:ID},xs);assert.equal(got[0].card.media.start,xs[0].start);assert.ok(got[0].task);reply.items[0].source_text='Invented quote.';assert.throws(()=>Y.importItems(JSON.stringify(reply),{id:ID},xs));});

test('adjacent subtitle fragments form one grounded phrase with the actual time span',()=>{const raw=Y.cues('00:00:10.100 --> 00:00:12.000\nI was thinking\n\n00:00:12.000 --> 00:00:14.300\nof taking a break.\n\n00:00:20.000 --> 00:00:22.000\nA different scene.');const merged=Y.studyCues(raw);assert.equal(raw.length,3);assert.equal(merged.length,2);assert.equal(merged[0].text,'I was thinking of taking a break.');assert.equal(merged[0].start,10.1);assert.equal(merged[0].end,14.3);assert.equal(Y.suggest(merged)[0].expression,'I was thinking of');assert.equal(Y.studyCues(Y.cues('Untimed phrase.\nAnother untimed phrase.')).length,2);});
test('a caption piece cut mid-sentence is joined with the words that finish it',()=>{
 const raw='7:20\nSo I want to ask you a question.\n7:33\nBut if you don\'t know why you do what you do, and people respond to why you do what you do, then how will you ever get people to vote for you, or buy something from you, or, more importantly, be loyal\n7:46\nand want to be a part of what it is that you do.\n7:50\nAgain, the goal is not just to sell.';
 const out=Y.studyCues(Y.cues(raw));
 assert.equal(out.length,3);assert.match(out[1].text,/be loyal and want to be a part of what it is that you do\.$/);assert.equal(out[1].chunk_kind,'sentence');
 assert.equal(out[1].start,453);assert.equal(out[1].end,470);
});
test('joining stops at 90 words and never runs over a long pause or unpunctuated captions',()=>{
 const long=Array.from({length:7},(_,i)=>Y.captionStamp(i*4)+'\n'+'we kept talking about the plan for the week and '.repeat(2).trim()).join('\n')+'\n0:28\nthen we stopped.';
 assert.ok(Y.studyCues(Y.cues(long)).every(c=>c.text.split(/\s+/).length<=90));
 const gap=Y.studyCues(Y.cues('0:00 --> 0:04\nI went to the market\n0:30 --> 0:34\nand bought some bread.'));assert.equal(gap.length,2);
 const flat=Array.from({length:12},(_,i)=>Y.captionStamp(i*3)+'\nso we went to the store and then we talked about it for a while').join('\n');
 assert.ok(Y.studyCues(Y.cues(flat)).every(c=>c.text.split(/\s+/).length<=60));
});

// v2.12.0: auto captions without full stops are cut where a spoken sentence most likely ends.
const SCREENSHOT="when I was in elementary school were you yeah it's actually one of the reasons why I didn't get an agent because I auditioned and I had like a punk rock haircut and I dress like a little you know street dancer and they rejected me oh yeah yeah I disagree with that because I met you I think you were like 16 years old and you had just on This Boy's Life which was your first film really it was on Hollywood Boulevard right yes we were at an after party and I remember thinking this kid is going to be huge";
function autoCaptions(text,rate=2.4){const words=text.split(' '),lines=[];let t=13;for(let i=0;i<words.length;){const n=5+(i%4);lines.push(Y.captionStamp(t)+' --> '+Y.captionStamp(t+n/rate+.4)+'\n'+words.slice(i,i+n).join(' '));t+=n/rate;i+=n;}return lines.join('\n\n');}
test('unpunctuated auto captions break at likely sentence ends, not mid-phrase',()=>{
 const out=Y.studyCues(Y.cues(autoCaptions(SCREENSHOT)));
 assert.deepEqual(out.map(c=>c.text.split(' ').slice(0,3).join(' ')),['when I was','yeah it\'s actually','oh yeah yeah','I think you','yes we were']);
 assert.match(out[2].text,/because I met you$/);assert.match(out[3].text,/^I think you were like 16/);
 assert.equal(out.map(c=>c.text).join(' '),SCREENSHOT);
 for(const c of out){assert.equal(c.chunk_kind,'speech');assert.ok(c.text.split(' ').length>=8&&c.text.split(' ').length<=40);assert.ok(c.end>c.start);}
 assert.ok(out.every((c,i)=>!i||c.start>=out[i-1].start),'chunks keep caption order and times');
});
test('a chunk never ends on an article, preposition, conjunction or subject pronoun when a better place exists',()=>{
 const text='so today I want to talk about something that I think matters a lot to all of us and that is how we learn new things you know when we were kids we learned by playing and making mistakes and nobody told us that mistakes were bad but somewhere along the way we started to believe that being wrong is something to avoid and I think that belief is holding a lot of people back so what can we do about it well the first thing is to notice when you are afraid of being wrong and ask yourself what would happen if I tried anyway thank you';
 const out=Y.studyCues(Y.cues(autoCaptions(text,2.5)));
 assert.ok(out.length>=3);assert.equal(out.map(c=>c.text).join(' '),text);
 for(const c of out.slice(0,-1))assert.doesNotMatch(c.text,/\b(?:a|an|the|of|to|and|but|because|that|I|we|they|is|was)$/,c.text);
});
test('question marks in otherwise unpunctuated captions are honoured and labels stay separate',()=>{
 const raw='0:00 --> 0:04\nso what did you think about the show when you\n0:04 --> 0:08\nfirst saw it on stage last year in London?\n0:08 --> 0:12\nhonestly I was shocked by how good the music was\n0:12 --> 0:14\n[Music]\n0:14 --> 0:18\nand the dancers were incredible from start to finish';
 const out=Y.studyCues(Y.cues(raw));
 assert.equal(out[0].text,'so what did you think about the show when you first saw it on stage last year in London?');
 assert.ok(out.some(c=>c.text==='[Music]'));assert.ok(out.every(c=>!/\[Music\]./.test(c.text)));
});
test('long sentences are read as short pieces that keep every word in order',()=>{
 const sentence="But if you don't know why you do what you do, and people respond to why you do what you do, then how will you ever get people to vote for you, or buy something from you, or, more importantly, be loyal and want to be a part of what it is that you do.";
 const pieces=Y.speechPieces(sentence);
 assert.ok(pieces.length>=2);assert.equal(pieces.join(' '),sentence);
 for(const p of pieces){assert.ok(p.split(' ').length<=26);assert.ok(p.length<=180);}
 assert.match(pieces[0],/,$/,'the first cut falls after a comma');
 assert.deepEqual(Y.speechPieces('I was thinking of taking a break.'),['I was thinking of taking a break.']);
 const flat=SCREENSHOT.split(' ').slice(0,40).join(' ');assert.equal(Y.speechPieces(flat).join(' '),flat);assert.ok(Y.speechPieces(flat).every(p=>p.split(' ').length<=26));
 assert.deepEqual(Y.speechPieces(''),[]);
 const long='x'.repeat(30)+' '+Array.from({length:40},(_,i)=>'word'+i).join(' ');assert.equal(Y.speechPieces(long).join(' '),long);
});
