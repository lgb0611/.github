/* The catalog lists every source. PDF study shares the existing audio transport. */
const studyMaterials=window.LAB_MATERIALS||[],MATERIAL_PAGE_SIZE=20;
let catalogGroup='all';
function catalogSummary(entry){
 if(entry.kind==='pdf')return `${esc(entry.material.unit_label||'문장·응답')} ${entry.cards.length}개 · 한국어 뜻 · 응용 문단 ${entry.exercises.length}개`;
 if(entry.kind==='video')return entry.cards.length?`저장한 학습 문장 ${entry.cards.length}개`:(entry.hasDraft?'자막 초안 있음 · 학습 문장 준비 가능':'자막 불러오기 필요');
 return `표현·단어 ${entry.cards.length}개${entry.exercises.length?' · 문단 연습 '+entry.exercises.length+'개':''}`;
}
function catalogTile(e){
 const done=e.cards.filter(c=>state.cards[c.id]?.attempts>0).length;
 let description=e.kind==='pdf'?e.material.description:e.group==='gabriel'?'강의 핵심 표현과 한국어 예문을 익히고, 준비된 한글 문단을 영어로 말해 보세요.':e.group==='speech'?'원자료의 표현·뜻·인용 예문을 찾아 듣고, 뜻을 보고 직접 문장으로 말해 보세요.':e.group==='kpop'?'표현집과 대본을 함께 확인하고, 뜻·예문·준비된 문단으로 연습하세요.':'';
 if(e.kind==='video')description=e.cards.length?'저장한 문장은 바로 공부할 수 있습니다. 자막·대본 열기에서 전체 듣기와 문장 추가를 이어가세요.':e.hasDraft?'불러온 자막을 열어 문장 듣기와 말하기를 준비하세요.':'영어 자막을 불러온 뒤 문장 듣기·반복·한글 보고 말하기로 이어집니다.';
 let buttons='';
 if(e.kind==='pdf')buttons=`<button class="btn primary small material-open" data-material="${esc(e.id)}" aria-pressed="false">이 자료로 공부하기 →</button>`;
 else if(e.kind==='video')buttons=(e.cards.length?`<button class="btn primary small catalog-action" data-entry="${esc(e.id)}" data-action="expressions">저장한 문장 공부하기 →</button>`:'')+`<button class="btn ${e.cards.length?'':'primary'} small saved-video-open" data-video="${esc(e.video.id)}">${e.cards.length?'자막·대본 열기':'이 영상으로 학습 시작'} →</button>`;
 else buttons=(e.exercises.length?`<button class="btn primary small catalog-action" data-entry="${esc(e.id)}" data-action="practice">한글 문단으로 말하기 →</button>`:'')+`<button class="btn ${e.exercises.length?'':'primary'} small catalog-action" data-entry="${esc(e.id)}" data-action="expressions">표현 ${e.cards.length}개 ${e.exercises.length?'보기':'공부하기'} →</button>`;
 const sourceKind=e.kind==='pdf'?e.material.source_kind:e.kind==='video'?(e.video.channel||'내가 저장한 영상'):e.group==='gabriel'?'강의 캡처 · 핵심 표현':e.group==='speech'?'연설문 해설 · 단어·표현 포함':'표현집 · 대본 PDF';
 return `<article class="material-tile catalog-tile" data-entry="${esc(e.id)}"><span class="eyebrow">${esc(sourceKind)}</span><h3>${esc(e.title)}</h3><p class="catalog-count">${catalogSummary(e)}</p><p class="catalog-description">${esc(description)}</p>${e.kind==='video'&&!e.cards.length&&!e.hasDraft?'<p class="tiny">첫 자막 불러오기: 인터넷·무료 자막 실행기 필요</p>':''}${done?`<p class="tiny">연습한 항목 ${done} / ${e.cards.length}개</p>`:''}<div class="task-actions">${buttons}</div><details class="catalog-sources"><summary>원본 자료 ${e.sources.length}개</summary><div class="task-actions">${e.sources.map(s=>`<a class="btn small catalog-source-link" href="${esc(s.href)}" target="_blank" rel="noopener">${esc(s.label)} ↗</a>`).join('')}</div></details></article>`;
}
function bindCatalogActions(container){
 container.querySelectorAll('.saved-video-open').forEach(b=>b.onclick=()=>openSavedVideo(b.dataset.video));
 container.querySelectorAll('.material-open').forEach(b=>b.onclick=()=>openStudyMaterial(b.dataset.material));
 container.querySelectorAll('.catalog-action').forEach(b=>b.onclick=()=>{
  if(recording()||busy||ytFetching)return;
  const entry=catalogEntries().find(e=>e.id===b.dataset.entry);if(!entry)return;
  if(b.dataset.action==='expressions')openCatalogExpressions(entry.id);
  else {const selected=entry.exercises.find(e=>e.id===state.lastExerciseId)||entry.exercises[0];if(selected)loadExercise(selected.id,{newStage:'recall'});}
 });
 container.querySelectorAll('button').forEach(b=>b.disabled=busy||recording()||ytFetching);
}
function renderMaterialCatalog(){
 const entries=catalogEntries(),query=$('materialSearch').value,filtered=window.LabCatalog.filter(entries,{query,group:catalogGroup});
 const groups=[...window.LabCatalog.groups,...(entries.some(e=>e.group==='other')?[{id:'other',label:'기타 자료'}]:[])];
 $('materialFilters').innerHTML=[{id:'all',label:'전체'},...groups].map(g=>`<button class="btn small" data-group="${g.id}" aria-pressed="${catalogGroup===g.id}">${g.label} <span>${g.id==='all'?entries.length:entries.filter(e=>e.group===g.id).length}</span></button>`).join('');
 $('materialFilters').querySelectorAll('button').forEach(b=>b.onclick=()=>{catalogGroup=b.dataset.group;renderMaterialCatalog();$('materialFilters').querySelector(`[data-group="${catalogGroup}"]`).focus({preventScroll:true});});
 const bundled=entries.filter(e=>e.bundled).length,user=entries.length-bundled;
 $('materialCatalogStats').textContent=`전체 ${entries.length}개 자료 중 ${filtered.length}개 표시 · 기본 자료 ${bundled}개${user?' + 내 유튜브 '+user+'개':''} · 학습 항목 ${entries.reduce((n,e)=>n+e.cards.length,0).toLocaleString()}개`;
 $('materialCatalogGroups').innerHTML=groups.map(g=>{const items=filtered.filter(e=>e.group===g.id);return items.length?`<section class="catalog-group" aria-label="${g.label}"><h2>${g.label} <span class="tiny">${items.length}개</span></h2><div class="material-tiles">${items.map(catalogTile).join('')}</div></section>`:'';}).join('');
 $('materialCatalogEmpty').classList.toggle('hidden',!!filtered.length);
 bindCatalogActions($('materialCatalogGroups'));
}
function openCatalogExpressions(id){
 if(recording()||busy||ytFetching)return false;
 renderLessonOptions();const entry=catalogEntries().find(e=>e.id===id);if(!entry)return false;
 $('lessonSelect').value=id;state.lastLessonId=id;updateExerciseOptions();
 $('librarySearch').value='';$('librarySource').value=id;$('coreOnly').checked=false;libraryLimit=30;picked.clear();
 showView('library');$('libraryTitle').scrollIntoView({block:'start',behavior:'smooth'});return true;
}
async function openSavedVideo(id){
 if(recording()||busy||ytFetching)return false;
 const video=catalogEntries().find(e=>e.video?.id===id)?.video;if(!video)return false;
 const previous={url:$('ytUrl').value,title:$('ytTitle').value};
 $('ytUrl').value=video.url;
 if(ytVideo?.id!==video.id||!$('ytTitle').value.trim())$('ytTitle').value=video.study_title;
 if(!loadYoutube()){$('ytUrl').value=previous.url;$('ytTitle').value=previous.title;return false;}
 showView('youtube');$('ytScope').value='all';
 await buildFromLink();renderSavedVideoCatalog();return true;
}
function renderSavedVideoCatalog(){
 const entries=catalogEntries().filter(e=>e.kind==='video');
 $('videoCatalog').innerHTML='<b>유튜브 학습 자료</b><div class="task-actions">'+entries.map(e=>`<button class="btn saved-video-open" data-video="${esc(e.video.id)}">${esc(e.title)}${e.cards.length?' · 저장 '+e.cards.length+'문장':''}</button>`).join('')+'</div>';
 $('videoQuickLinks').innerHTML=videoMaterials.map(v=>`<button class="btn small saved-video-open" data-video="${esc(v.id)}">${esc(v.short_title||v.study_title)}</button>`).join('');
 bindCatalogActions($('videoCatalog'));bindCatalogActions($('videoQuickLinks'));
}
let materialCurrent=null,materialPending=null,materialPage=0,materialPicked=new Set();
function materialFilteredRows(){return materialCurrent?.rows.filter(r=>$('materialSection').value==='all'||r.section_id===$('materialSection').value)||[];}
function materialPageRows(){return materialFilteredRows().slice(materialPage,materialPage+MATERIAL_PAGE_SIZE);}
function materialStatus(message){$('materialPickStatus').textContent=message;}
function renderMaterialSelection(){
 const count=materialPicked.size;
 $('materialParagraph').disabled=count<2||busy||recording();
 $('materialParagraph').textContent=count<2?'문장을 2개 이상 선택하세요':`선택한 ${count}문장 · 한글 문단으로 말하기 →`;
 $('materialClear').disabled=!count||busy||recording();
 materialStatus(count?`${count} / 5개 선택 · ${[...materialPicked].map(id=>materialCurrent.rows.findIndex(r=>r.card_id===id)+1+'번').join(', ')} 문장을 이어 말합니다.`:'2~5개 문장을 선택하면 한글을 문단으로 이어 말할 수 있습니다.');
 document.querySelectorAll('.material-pick').forEach(e=>e.checked=materialPicked.has(e.dataset.id));
}
function renderMaterialCards(){
 const filtered=materialFilteredRows(),visible=materialPageRows();
 $('materialCards').replaceChildren();
 for(const row of visible){
  const index=materialCurrent.rows.indexOf(row),card=document.createElement('article');card.className='material-card';card.dataset.cardId=row.card_id;
  card.innerHTML=`<div class="sectionhead"><span class="eyebrow">${index+1} · ${esc(scriptRowSource(row))}${row.source_item?' · 원자료 '+row.source_item+'번':''}</span><label class="check"><input class="material-pick" type="checkbox" data-id="${esc(row.card_id)}" aria-label="${index+1}번 문장을 문단에 활용">문단에 활용</label></div><p class="material-english" lang="en">${esc(row.text)}</p><p class="material-meaning" lang="ko">${esc(row.korean_text)}</p><p class="tiny">${esc(row.translation_origin)}</p><div class="task-actions"><button class="btn primary small material-listen">▷ 음성 듣기 · 이 문장만</button><button class="btn small material-loop">↻ 이 문장 반복</button><button class="btn small material-speak">한글 보고 말하기 →</button></div>`;
  const play=mode=>{if(busy||recording())return;selectScriptRange(index,index);startTranscriptPlayback({mode,from:index,to:index});};
  card.querySelector('.material-listen').onclick=()=>play('single');
  card.querySelector('.material-loop').onclick=()=>play('range');
  card.querySelector('.material-speak').onclick=()=>koreanSingle(row.card_id);
  card.querySelector('.material-pick').onchange=e=>{
   if(busy||recording()){e.target.checked=materialPicked.has(row.card_id);return;}
   if(e.target.checked&&materialPicked.size>=5){e.target.checked=false;materialStatus('문단에는 최대 5문장을 사용합니다. 선택한 문장을 해제하고 다시 고르세요.');return;}
   if(e.target.checked)materialPicked.add(row.card_id);else materialPicked.delete(row.card_id);renderMaterialSelection();
  };
  $('materialCards').append(card);
 }
 $('materialPage').textContent=filtered.length?`${materialPage+1}–${materialPage+visible.length} / ${filtered.length}개`:'문장 없음';
 $('materialPrev').disabled=materialPage===0;$('materialNext').disabled=materialPage+MATERIAL_PAGE_SIZE>=filtered.length;
 $('materialSequence').textContent=`이 묶음 ${visible.length}개 · 한글 보고 말하기 →`;
 $('materialListenSection').textContent=$('materialSection').value==='all'?'▷ 자료 전체 듣기':'▷ 선택 주제 듣기';
 renderMaterialSelection();
 if(!$('materialsView').classList.contains('hidden'))expose(visible.map(r=>r.card_id));
}
function setStudyMaterial(material){
 const changed=materialCurrent!==material;materialCurrent=material;
 if(changed){
  materialPage=0;materialPicked.clear();
  $('materialTitle').textContent=material.title;$('materialKind').textContent=material.source_kind;
  $('materialOriginal').href='sources/'+material.source_file;$('materialSourceNote').textContent=material.source_note;
  $('materialSection').innerHTML='<option value="all">전체 · '+material.rows.length+'개 '+esc(material.unit_label||'문장·응답')+'</option>'+material.sections.map(s=>`<option value="${esc(s.id)}">${esc(s.title_ko)} · ${material.rows.filter(r=>r.section_id===s.id).length}개</option>`).join('');
  $('materialExercise').innerHTML=material.exercises.map(e=>`<option value="${esc(e.id)}">${esc(e.title)} · ${e.card_ids.length}개 학습 문장</option>`).join('');
  $('materialGlossary').classList.toggle('hidden',!material.glossary.length);
  $('materialGlossaryList').innerHTML=material.glossary.length?'<table><thead><tr><th>원자료 표현</th><th>원자료 한국어</th></tr></thead><tbody>'+material.glossary.map(g=>`<tr><td lang="en">${esc(g.expression)}</td><td>${esc(g.meaning_ko)}</td></tr>`).join('')+'</tbody></table>':'';
 }
 $('materialWorkspace').classList.remove('hidden');
 $('materialCatalog').classList.add('hidden');
 $('lessonSelect').value=material.id;updateExerciseOptions();
 document.querySelectorAll('.material-tile button').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.material===material.id)));
 $('materialListeningHost').append($('ytAudioControls'),$('ytTranscriptPlayer'));
 scriptMaterial=material;syncTranscriptPlayer();renderMaterialCards();
}
function openStudyMaterial(id){
 if(recording()||busy)return;const material=studyMaterials.find(m=>m.id===id);if(!material)return;
 // Show the target first, so exposure and the shared transport have one active source.
 materialPending=material;showView('materials');materialPending=null;$('materialTitle').scrollIntoView({block:'start',behavior:'smooth'});
}
function updateMaterialView(name){
 if(name==='materials'||name==='youtube'){renderSavedVideoCatalog();renderLessonOptions();}
 if(name==='materials'){
  renderMaterialCatalog();
  if(materialPending)setStudyMaterial(materialPending);
  else{$('materialCatalog').classList.remove('hidden');$('materialWorkspace').classList.add('hidden');}
 }
 else if(name==='youtube'){
  $('ytListeningHome').append($('ytAudioControls'),$('ytTranscriptPlayer'));
  scriptMaterial=null;syncTranscriptPlayer();
 }
}
const resetCatalog=()=>{catalogGroup='all';$('materialSearch').value='';renderMaterialCatalog();};
$('materialSearch').oninput=()=>renderMaterialCatalog();
$('materialSearchClear').onclick=()=>{$('materialSearch').value='';renderMaterialCatalog();$('materialSearch').focus();};
$('materialCatalogReset').onclick=resetCatalog;
$('materialBack').onclick=()=>{if(!recording()&&!busy){showView('materials');$('materialSearch').focus({preventScroll:true});}};
$('allMaterialsShortcut').onclick=()=>{if(!recording()&&!busy)showView('materials');};
$('libraryBackMaterials').onclick=()=>{if(!recording()&&!busy)showView('materials');};
$('openLessonMaterial').onclick=()=>openStudyMaterial($('lessonSelect').value);
$('materialSection').onchange=()=>{if(recording()||busy)return;materialPage=0;materialPicked.clear();renderMaterialCards();};
$('materialPrev').onclick=()=>{if(recording()||busy||materialPage===0)return;materialPage=Math.max(0,materialPage-MATERIAL_PAGE_SIZE);renderMaterialCards();};
$('materialNext').onclick=()=>{if(recording()||busy||materialPage+MATERIAL_PAGE_SIZE>=materialFilteredRows().length)return;materialPage+=MATERIAL_PAGE_SIZE;renderMaterialCards();};
$('materialSequence').onclick=()=>koreanSequence(materialPageRows().map(r=>r.card_id));
$('materialListenSection').onclick=()=>{
 if(busy||recording())return;const rows=materialFilteredRows();if(!rows.length)return;
 const from=materialCurrent.rows.indexOf(rows[0]),to=materialCurrent.rows.indexOf(rows.at(-1));
 startTranscriptPlayback({settings:{mode:'range',from,to,repeat:1,gap:0}});
 $('ytTranscriptPlayer').scrollIntoView({block:'center',behavior:'smooth'});
};
$('materialClear').onclick=()=>{if(busy||recording())return;materialPicked.clear();renderMaterialSelection();};
$('materialParagraph').onclick=()=>createParagraphPractice([...materialPicked]);
$('materialPractice').onclick=()=>loadExercise($('materialExercise').value,{newStage:'recall'});
renderMaterialCatalog();renderSavedVideoCatalog();
document.querySelectorAll('.material-shortcuts').forEach(bindCatalogActions);
