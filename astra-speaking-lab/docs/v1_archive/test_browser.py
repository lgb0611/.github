"""Chromium rendering / interaction tests with simulated browser I/O.
The build environment blocks navigation and audio capture by browser policy.
The page is rendered using set_content; storage, microphone, clipboard and fetch
are controlled test fixtures. Backend HTTP behavior is tested separately by pytest.
No paid API calls or actual microphone capture are made here.
"""
from pathlib import Path
import json, os, shutil
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'docs'/'screenshots';OUT.mkdir(exist_ok=True)
HTML=(ROOT/'OPEN_ME.html').read_text(encoding='utf-8')
passed=[]
def ok(name,condition=True):
    assert condition,name
    passed.append(name);print('PASS',name)

HARNESS=r'''
window.__store = INITIAL_STORE;
Object.defineProperty(window,'localStorage',{value:{getItem:k=>window.__store[k]??null,setItem:(k,v)=>window.__store[k]=v,removeItem:k=>delete window.__store[k]},configurable:true});
window.__clipboard='';
Object.defineProperty(navigator,'clipboard',{value:{writeText:async t=>{window.__clipboard=t},readText:async()=>window.__clipboard},configurable:true});
window.__requests=[];
window.__apiResponses={};
window.fetch=async(url,options={})=>{
 window.__requests.push({url,method:options.method||'GET',body:options.body});
 const payload=window.__apiResponses[url]||{};
 return {ok:true,status:200,json:async()=>payload};
};
Object.defineProperty(navigator,'mediaDevices',{value:{getUserMedia:async()=>({getTracks:()=>[{stop(){}}]})},configurable:true});
window.MediaRecorder=class {
 static isTypeSupported(){return true;}
 constructor(stream,options={}){this.state='inactive';this.mimeType=options.mimeType||'audio/webm';}
 start(){this.state='recording';}
 pause(){this.state='paused';}
 resume(){this.state='recording';}
 stop(){this.state='inactive';if(this.ondataavailable)this.ondataavailable({data:new Blob(['simulated-audio'],{type:this.mimeType})});setTimeout(()=>this.onstop&&this.onstop(),10);}
};
'''
def prepare(page,store=None):
    page.evaluate('(()=>{' + HARNESS.replace('INITIAL_STORE',json.dumps(store or {})) + ';return true;})()')
    page.set_content(HTML,wait_until='load')
    page.wait_for_selector('#taskText')

with sync_playwright() as p:
    executable=os.getenv('TEST_CHROMIUM_PATH') or shutil.which('chromium')
    browser=p.chromium.launch(executable_path=executable,headless=True) if executable else p.chromium.launch(headless=True)
    ctx=browser.new_context(viewport={'width':1440,'height':1100})
    page=ctx.new_page();errors=[]
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.on('dialog',lambda d:d.accept())
    prepare(page)
    ok('page renders real expression content',page.locator('.expression-row').count()==5)
    ok('model answer initially hidden',not page.locator('#sampleBox').is_visible())
    ok('real progress starts at zero',page.locator('#todayCount').inner_text()=='0')
    page.screenshot(path=str(OUT/'desktop.png'),full_page=True)
    page.locator('#beginRecall').click()
    ok('recall hides target expressions',not page.locator('#cardList').is_visible())
    page.locator('#recordBtn').click();page.wait_for_timeout(400)
    ok('simulated microphone enters recording state',page.evaluate('LabTest.recording()'))
    page.wait_for_timeout(3000)
    ok('a pause in speech never auto-submits',page.evaluate('window.__requests.length')==0)
    page.locator('#pauseBtn').click();page.wait_for_timeout(100)
    ok('pause is still not submission',page.locator('#recordStatus').inner_text()=='일시정지')
    page.locator('#pauseBtn').click();page.wait_for_timeout(100)
    page.locator('#stopBtn').click();page.wait_for_timeout(200)
    ok('explicit stop only exposes audio playback controls',page.locator('#audioRow').is_visible() and not page.evaluate('LabTest.recording()'))
    ok('stopping never calls STT or grading',page.evaluate('window.__requests.length')==0)
    page.locator('#answerInput').fill('I tried it on, but it did not fit.')
    page.locator('#gradeBtn').click()
    ok('transcript confirmation is required','확인란' in page.locator('#statusLine').inner_text())
    page.locator('#confirmTranscript').check();page.locator('#gradeBtn').click()
    ok('no API key never creates fake feedback','API 미연결' in page.locator('#statusLine').inner_text() and not page.locator('#feedbackPanel').is_visible())
    page.locator('#copyPrompt').click()
    clipboard=page.evaluate('window.__clipboard')
    ok('ChatGPT fallback includes actual learner wording','I tried it on, but it did not fit.' in clipboard and '발음은 이 텍스트로 평가할 수 없습니다' in clipboard)
    page.locator('#selfCheck').click()
    ok('self-comparison is explicitly not automatic grading','자동으로 정답 판정을 하지 않았습니다' in page.locator('#feedbackContent').inner_text())
    page.locator('.rating-select').first.select_option('again')
    page.locator('#saveReview').click()
    ok('review schedule serializes',len(page.evaluate('LabTest.getState().cards'))==5)
    page.locator('#newSituation').click()
    ok('different scenario uses same target phrases',page.evaluate('LabTest.getStage()')=='transfer' and page.evaluate('LabTest.getExercise().id')=='g08_story_2')
    page.locator('#answerInput').fill('Draft survives a reload.')
    page.wait_for_timeout(650)
    stored=page.evaluate('window.__store')
    page.close();page=ctx.new_page();page.on('pageerror',lambda e:errors.append(str(e)));page.on('dialog',lambda d:d.accept());prepare(page,stored)
    ok('draft restores from serialized state',page.locator('#answerInput').input_value()=='Draft survives a reload.')
    page.locator('[data-view="library"]').click()
    ok('core library is filtered to 100','100개' in page.locator('#libraryStats').inner_text())
    page.locator('#coreOnly').uncheck();page.locator('#librarySource').select_option('kpop')
    ok('KPOP index preserves duplicate-number entry','220개' in page.locator('#libraryStats').inner_text())
    page.locator('#librarySearch').fill('have my back')
    ok('source expression is searchable',page.locator('.library-card').count()==1)
    page.locator('.pick-card').check();page.locator('#copyGenerate').click()
    ok('copy generation request uses selected source','Have my back' in page.evaluate('window.__clipboard'))
    page.locator('#librarySearch').fill('');page.locator('#librarySource').select_option('gabriel');page.locator('#coreOnly').check()
    page.screenshot(path=str(OUT/'library.png'),full_page=True)
    page.locator('[data-view="review"]').click()
    page.locator('.history-entry summary').first.click()
    ok('history shows actual text','I tried it on, but it did not fit.' in page.locator('#attemptList').inner_text())
    page.screenshot(path=str(OUT/'review.png'),full_page=True)
    page.locator('[data-view="practice"]').click();page.locator('#answerInput').fill('')
    page.evaluate("LabTest.loadExercise('g04_story_1')")
    page.evaluate("config={...config,server:true,connected:true,token:'test-only'}; state.consent=true; renderConfig();")
    page.locator('#beginRecall').click()
    page.evaluate("window.__apiResponses['/api/transcribe']={text:'I am up for anything as long as it is too cold.',model:'MOCK_STT'}")
    page.locator('#audioFile').set_input_files({'name':'test.webm','mimeType':'audio/webm','buffer':b'not-real-audio'})
    page.locator('#transcribeBtn').click();page.wait_for_timeout(300)
    ok('STT text is not silently corrected','too cold.' in page.locator('#answerInput').input_value() and 'not too cold' not in page.locator('#answerInput').input_value())
    ok('raw transcript is separately preserved',page.locator('#rawText').text_content()=='I am up for anything as long as it is too cold.')
    ids=page.evaluate('LabTest.getExercise().card_ids')
    text='I am up for anything as long as it is too cold.'
    result={'summary_ko':'테스트용 응답: 부정어 not이 빠졌습니다.', 'sentence_reviews':[{'original':text,'corrected':text.replace('it is too cold','it is not too cold'),'status':'needs_fix','corrections':[{'kind':'meaning','original':'it is too cold','replacement':'it is not too cold','reason_ko':'너무 춥지만 않으면이라는 뜻에는 not이 필요합니다.'}]}], 'phrase_checks':[{'card_id':id,'status':'incorrect' if n==4 else 'not_used','evidence':'as long as it is too cold' if n==4 else '', 'explanation_ko':'테스트용 근거'} for n,id in enumerate(ids)], 'omissions':[],'corrected_text':text.replace('it is too cold','it is not too cold'),'next_drill_ko':'너무 비싸지만 않으면 뭐든 좋아.','study_summary_en':['as long as it is not too cold']}
    page.evaluate("x=>window.__apiResponses['/api/grade']=x",{'result':result,'model':'MOCK_ONLY_NOT_LIVE','usage':{},'disclaimer':'자동화 테스트용 고정 응답입니다. 실제 AI 평가가 아닙니다.'})
    before=page.evaluate("window.__requests.filter(r=>r.url==='/api/grade').length")
    page.wait_for_timeout(400)
    ok('transcription completion does not initiate grading',page.evaluate("window.__requests.filter(r=>r.url==='/api/grade').length")==before)
    page.locator('#confirmTranscript').check();page.locator('#gradeBtn').click();page.wait_for_timeout(300)
    ok('grading occurs only after explicit submit',page.evaluate("window.__requests.filter(r=>r.url==='/api/grade').length")==before+1)
    ok('meaning error renders with reason','not이 필요합니다' in page.locator('#feedbackContent').inner_text())
    ok('original quote is preserved',page.locator('.original').inner_text()=='I am up for anything as long as it is too cold.')
    page.screenshot(path=str(OUT/'feedback_MOCK.png'),full_page=True)
    page.locator('#retryBtn').click()
    ok('retry hides correction and does not count mastery',page.evaluate('LabTest.getStage()')=='retry' and not page.locator('#feedbackPanel').is_visible() and not page.locator('#cardList').is_visible())
    ok('no JavaScript runtime errors',not errors)
    mob=browser.new_context(viewport={'width':390,'height':844},is_mobile=True,has_touch=True)
    m=mob.new_page();prepare(m)
    ok('mobile has no horizontal overflow',m.evaluate('document.documentElement.scrollWidth <= innerWidth+1'))
    m.screenshot(path=str(OUT/'mobile.png'),full_page=True)
    ok('standalone mode displays its limitation','단독 HTML' in m.locator('#connectionText').inner_text())
    browser.close()
report={'checks_passed':len(passed),'checks':passed,'live_openai_calls':False,
'microphone':'Simulated MediaRecorder/getUserMedia, not actual audio capture',
'browser':'System Chromium headless, set_content fixture because environment browser policy blocks URL navigation/capture',
'storage':'simulated localStorage serialization/reload',
'screenshots':'feedback_MOCK.png contains a mocked response, not a live AI evaluation'}
(ROOT/'docs'/'browser_test_results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(f'{len(passed)} UI checks passed.')
