/* Built-in PDF coverage, source identity and Korean/example alignment. */
const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const C=require('../static/core.js'),K=require('../static/korean-core.js');
const root=path.join(__dirname,'..'),data=JSON.parse(fs.readFileSync(path.join(root,'data/library.json'))),materials=JSON.parse(fs.readFileSync(path.join(root,'data/materials.json'))),known=new Map(data.cards.map(c=>[c.id,c]));
test('PDF materials cover all worksheet items and 39 interview sections with stable source files',()=>{
 assert.equal(materials.length,3);assert.equal(data.cards.filter(c=>!c.material_id).length,2874);assert.equal(new Set(data.cards.map(c=>c.id)).size,data.cards.length);
 for(const m of materials){assert.equal(crypto.createHash('sha256').update(fs.readFileSync(path.join(root,'sources',m.source_file))).digest('hex'),m.source_sha256);assert.equal(new Set(m.rows.map(r=>r.card_id)).size,m.rows.length);assert.ok(m.sections.every(s=>m.rows.some(r=>r.section_id===s.id)));}
 const [j,e]=materials;assert.equal(j.rows.length,60);assert.equal(j.glossary.length,19);assert.equal(new Set(j.rows.filter(r=>r.page===2).map(r=>r.source_item)).size,15);assert.equal(new Set(j.rows.filter(r=>r.page===4).map(r=>r.source_item)).size,40);assert.equal(e.sections.length,39);assert.equal(e.rows.length,363);assert.equal(new Set(e.rows.map(r=>r.page)).size,20);
});
test('every PDF row has matching offline Korean and a valid single speaking exercise',()=>{
 for(const m of materials)for(const r of m.rows){const c=known.get(r.card_id);assert.ok(c);assert.equal(c.expression,r.text);assert.equal(c.source_quote,r.text);assert.equal(K.ko(c),r.korean_text);assert.match(r.korean_text,/[가-힣]/);assert.ok(r.page>=1&&r.page_end<=m.source_pages);assert.equal(c.media,undefined);assert.equal(C.cardExercise(c).task_ko,r.korean_text);assert.ok(C.validateExercise(C.cardExercise(c),known));}
});
test('authored paragraphs use several source sentences with exact bilingual alignment',()=>{
 const examples=materials.flatMap(m=>m.exercises);assert.equal(examples.length,15);
 for(const e of examples){assert.ok(C.validateExercise(e,known));assert.ok(e.card_ids.length>=3&&e.card_ids.length<=5);assert.match(e.origin,/앱 작성 응용/);const chosen=e.card_ids.map(id=>({id,sentence_en:K.target(known.get(id)),korean_text:K.ko(known.get(id))}));assert.ok(K.validateParagraph(e,chosen));}
});
test('editorial narration and future timeline labels remain distinct from quoted dialogue',()=>{
 const e=materials[1];assert.ok(e.rows.filter(r=>r.section_id==='elon_32').every(r=>r.kind==='editorial'));assert.ok(e.rows.filter(r=>['em_308','em_309'].includes(r.id)).every(r=>r.speaker==='자료의 상황 설명'));assert.equal(e.rows.find(r=>r.id==='em_349').context_ko,'약 5년 뒤 · 자료의 전망');assert.equal(e.rows.find(r=>r.id==='em_358').context_ko,'');assert.ok(materials[0].rows.every(r=>r.kind==='worksheet'));
});
test('saved video metadata identifies the requested public video without bundling an unverified transcript',()=>{
 const videos=JSON.parse(fs.readFileSync(path.join(root,'data/video-materials.json'))),Y=require('../static/youtube-core.js');assert.equal(videos.length,1);const v=videos[0];assert.equal(v.id,'hZWTGyXF0mI');assert.equal(Y.video(v.url).id,v.id);assert.equal(v.title,'하버드 교수입니다 제말 들으십쇼');assert.equal(v.channel,'BZCF | 비즈까페');assert.equal(v.duration_seconds,779);assert.equal(v.caption_language,'en');assert.equal(v.caption_kind,'asr');assert.equal(v.transcript,undefined);assert.equal(v.cues,undefined);
});
test('Harvard PDF has 84 prepared Korean units and 9 topics with summaries distinct from attributed speech',()=>{
 const h=materials.find(m=>m.id==='pdf_harvard');assert.ok(h);assert.equal(h.rows.length,84);assert.equal(h.sections.length,9);assert.equal(h.source_pages,6);assert.equal(h.exercises.length,5);assert.equal(h.source_sha256,'692a0bd825ca1493095dee053c0f3de6f385cc61237e805d5435f738fcab1fb2');
 assert.equal(h.rows.filter(r=>r.kind==='reported_speech').length,19);assert.equal(h.rows.filter(r=>r.kind==='summary').length,65);assert.ok(h.rows.filter(r=>r.kind==='summary').every(r=>r.speaker==='자료의 요약·설명'));
 assert.match(h.rows.find(r=>r.id==='hb_057').korean_text,/4억 달러/);assert.match(h.rows.find(r=>r.id==='hb_080').context_ko,/주당/);
 assert.ok(h.rows.every(r=>!r.media&&r.start===undefined));assert.match(h.source_note,/요약/);
});
