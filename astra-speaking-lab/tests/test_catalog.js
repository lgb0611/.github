/* Catalog coverage is checked against the real bundled lessons and source files. */
const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const Catalog=require('../static/material-catalog.js');
const root=path.join(__dirname,'..'),read=f=>JSON.parse(fs.readFileSync(path.join(root,'data',f)));
const data=read('library.json'),materials=read('materials.json'),videos=read('video-materials.json');
const input={...data,materials,videos,exercises:[...read('exercises.json'),...read('transfer.json'),...materials.flatMap(m=>m.exercises)]};
test('catalog covers all 26 bundled materials and all 3381 learning items exactly once',()=>{
 const entries=Catalog.build(input);assert.equal(entries.length,26);assert.equal(new Set(entries.map(e=>e.id)).size,26);
 assert.deepEqual(entries.filter(e=>e.kind!=='video').map(e=>e.id),data.lessons.map(l=>l.id));
 assert.deepEqual(entries.flatMap(e=>e.cards.map(c=>c.id)).sort(),data.cards.map(c=>c.id).sort());
 assert.deepEqual(Object.fromEntries(Catalog.groups.map(g=>[g.id,entries.filter(e=>e.group===g.id).length])),{gabriel:10,speech:11,kpop:1,interview:3,youtube:1});
 assert.equal(entries.reduce((n,e)=>n+e.exercises.length,0),87);
 for(const e of entries)for(const x of e.exercises)assert.ok(x.card_ids.every(id=>e.cards.some(c=>c.id===id)));
});
test('catalog exposes all 35 existing sources including KPOP script and all lecture captures',()=>{
 const entries=Catalog.build(input),sources=[...new Set(entries.flatMap(e=>e.sources).map(s=>s.href).filter(p=>p.startsWith('sources/')))];
 assert.deepEqual(sources.sort(),fs.readdirSync(path.join(root,'sources')).map(n=>'sources/'+n).sort());
 for(const file of sources)assert.ok(fs.statSync(path.join(root,file)).size>0);
 assert.equal(entries.find(e=>e.id==='kpop').sources.length,2);assert.equal(entries.find(e=>e.id==='g04').sources.length,1);
});
test('search combines category, Korean names, English expressions and empty results',()=>{
 const entries=Catalog.build(input);
 assert.deepEqual(Catalog.filter(entries,{query:'가브리엘 8강'}).map(e=>e.id),['g08']);
 assert.ok(Catalog.filter(entries,{query:'잡스'}).some(e=>e.id==='s03'));
 assert.deepEqual(Catalog.filter(entries,{group:'interview'}).map(e=>e.id),['pdf_jennie','pdf_elon','pdf_harvard']);
 assert.ok(Catalog.filter(entries,{query:'CONFIDENCE'}).length>0);
 assert.equal(Catalog.filter(entries,{query:'가브리엘',group:'speech'}).length,0);
 assert.equal(Catalog.filter(entries,{query:'no-such-material-827489'}).length,0);
});
test('saved video cards and current draft form distinct material entries, merging a bundled video by ID',()=>{
 const own=[{id:'a',lesson_id:'youtube',expression:'First sentence.',meaning_ko:'첫 문장',source_locator:'제니 인터뷰 · 0:12',media:{video_id:'M7lc1UVf-VE'}},{id:'b',lesson_id:'youtube',expression:'Second sentence.',meaning_ko:'둘째 문장',media:{video_id:videos[0].id}}];
 const entries=Catalog.build({...input,cards:[...input.cards,...own],draft:{videoId:'abcdefghijk',title:'새 영상 초안',transcript:'A draft sentence.'}});
 assert.equal(entries.length,28);assert.equal(entries.filter(e=>e.video?.id===videos[0].id).length,1);
 assert.equal(entries.find(e=>e.id==='video_M7lc1UVf-VE').title,'제니 인터뷰');
 assert.equal(entries.find(e=>e.id==='video_abcdefghijk').hasDraft,true);
 assert.equal(entries.find(e=>e.id==='video_abcdefghijk').cards.length,0);
 assert.equal(entries.find(e=>e.id===videos[0].lesson_id).cards.length,1);
 assert.equal(entries.find(e=>e.id===videos[0].lesson_id).hasDraft,false);
 assert.equal(Catalog.build(input).find(e=>e.id===videos[0].lesson_id).cards.length,0);
});
test('exact material filtering never mixes other speeches or other saved videos',()=>{
 assert.equal(data.cards.filter(c=>Catalog.matchesCard(c,'s03',data.lessons)).length,258);
 assert.equal(data.cards.filter(c=>Catalog.matchesCard(c,'speech',data.lessons)).length,2554);
 assert.equal(Catalog.matchesCard({lesson_id:'youtube',media:{video_id:'M7lc1UVf-VE'}},'video_hZWTGyXF0mI'),false);
 assert.equal(Catalog.matchesCard({lesson_id:'youtube',media:{video_id:'hZWTGyXF0mI'}},'video_hZWTGyXF0mI'),true);
});
test('catalog derivation preserves input state and rejects non-source links and invalid video IDs',()=>{
 const before=JSON.stringify(input);Catalog.build(input);assert.equal(JSON.stringify(input),before);
 const bad=Catalog.build({lessons:[{id:'x',title:'X',family:'other',images:['javascript:alert(1)','../secret.pdf','sources/../secret.pdf']}],cards:[{id:'q',lesson_id:'x',source_url:'https://invalid.example/tracker.png',media:{video_id:'bad'}}],draft:{videoId:'bad',title:'bad',transcript:'bad'}});
 assert.equal(bad.length,1);assert.equal(bad[0].sources.length,0);
});
