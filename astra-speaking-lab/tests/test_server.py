"""No real OpenAI calls. All cloud responses in these tests are controlled fixtures."""
import copy
import json
import sys
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import server

@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(server,'API_KEY','')
    return TestClient(server.app,base_url='http://127.0.0.1:8765')

def headers(**more): return {'X-Local-Token':server.TOKEN,**more}

def result():
    return {'summary_ko':'부정어가 빠져 뜻이 반대가 됩니다.',
      'sentence_reviews':[{'original':"I am up for anything as long as it is too cold.",
        'corrected':"I am up for anything as long as it is not too cold.", 'status':'needs_fix',
        'corrections':[{'kind':'meaning','original':'it is too cold','replacement':'it is not too cold','reason_ko':'너무 춥지만 않으면이라는 뜻에는 not이 필요합니다.'}]}],
      'phrase_checks':[{'card_id':'g04_05','status':'incorrect','evidence':'as long as it is too cold','explanation_ko':'부정어 누락'}],
      'omissions':[],'corrected_text':"I am up for anything as long as it is not too cold.",
      'next_drill_ko':'너무 비싸지만 않으면 뭐든 좋아.','study_summary_en':['as long as it is not too cold']}

def grade_body():
    return {'card_ids':['g04_05'],'task_ko':'너무 춥지만 않으면 뭐든 좋아.','transcript':result()['sentence_reviews'][0]['original'],'confirmed':True}

def test_home_and_no_key_leak(client):
    r=client.get('/')
    assert r.status_code==200 and '말한 답변 자가 점검' in r.text
    c=client.get('/api/config').json()
    assert not c['connected'] and 'api_key' not in c
    assert c['model']=='gpt-6-astra'

def test_missing_local_token(client):
    assert client.post('/api/grade',json=grade_body()).status_code==403

def test_foreign_origin_rejected(client):
    assert client.post('/api/grade',json=grade_body(),headers=headers(Origin='https://evil.example')).status_code==403

def test_untrusted_host_rejected(client):
    assert client.get('/api/config',headers={'Host':'evil.example'}).status_code==400

def test_confirmation_required(client):
    b=grade_body();b['confirmed']=False
    assert client.post('/api/grade',json=b,headers=headers()).status_code==400

def test_key_missing_fails_closed(client):
    r=client.post('/api/grade',json=grade_body(),headers=headers())
    assert r.status_code==503 and '키' in r.json()['detail']

def test_unknown_card_rejected(client):
    b=grade_body();b['card_ids']=['invented']
    assert client.post('/api/grade',json=b,headers=headers()).status_code==400

def test_duplicate_card_rejected(client):
    b=grade_body();b['card_ids']*=2
    assert client.post('/api/grade',json=b,headers=headers()).status_code==400

def test_model_id_validation_is_transactional(client,monkeypatch):
    monkeypatch.setattr(server,'API_KEY','old-test-key')
    r=client.post('/api/settings',json={'api_key':'new-test-key','model':'bad model'},headers=headers())
    assert r.status_code==400 and server.API_KEY=='old-test-key'

def test_local_settings_never_return_key(client,monkeypatch):
    r=client.post('/api/settings',json={'api_key':'fixture-secret'},headers=headers())
    assert r.status_code==200 and r.json()['connected']
    assert 'fixture-secret' not in r.text
    r=client.post('/api/settings',json={'clear_key':True},headers=headers())
    assert not r.json()['connected']

def test_valid_negation_feedback_verifies():
    r=server.GradeResult.model_validate(result())
    server.verify_grade(r,grade_body()['transcript'],['g04_05'])

def test_invented_learner_quote_rejected():
    d=result();d['sentence_reviews'][0]['original']='The user said it correctly.'
    with pytest.raises(ValueError):server.verify_grade(server.GradeResult.model_validate(d),grade_body()['transcript'],['g04_05'])

def test_invented_evidence_rejected():
    d=result();d['phrase_checks'][0]['evidence']='I said not too cold.'
    with pytest.raises(ValueError):server.verify_grade(server.GradeResult.model_validate(d),grade_body()['transcript'],['g04_05'])

def test_missed_sentence_rejected():
    text=grade_body()['transcript']+' I omitted this second sentence.'
    with pytest.raises(ValueError):server.verify_grade(server.GradeResult.model_validate(result()),text,['g04_05'])

def test_error_cannot_be_labeled_correct():
    d=result();d['sentence_reviews'][0]['status']='correct'
    with pytest.raises(ValueError):server.verify_grade(server.GradeResult.model_validate(d),grade_body()['transcript'],['g04_05'])

def test_grade_mocked_structured_response(client,monkeypatch):
    async def fake(schema,instructions,payload):
        assert payload['learner_transcript']==grade_body()['transcript']
        assert 'polarity' in instructions
        return schema.model_validate(result()),{'input_tokens':100,'output_tokens':100}
    monkeypatch.setattr(server,'structured_call',fake)
    r=client.post('/api/grade',json=grade_body(),headers=headers())
    assert r.status_code==200 and 'not too cold' in r.json()['result']['corrected_text']

def test_stt_upload_is_explicit_and_no_expected_answer(client,monkeypatch):
    monkeypatch.setattr(server,'API_KEY','fixture')
    calls=[]
    async def fake(path,**kw):
        calls.append((path,kw));return {'text':'I said this wrong.'}
    monkeypatch.setattr(server,'openai_post',fake)
    r=client.post('/api/transcribe',files={'audio':('voice.webm',b'fixture-not-real-audio','audio/webm')},headers=headers())
    assert r.status_code==200 and r.json()['text']=='I said this wrong.'
    assert len(calls)==1
    assert 'g04' not in calls[0][1]['data']['prompt']
    assert calls[0][1]['data']['model']=='gpt-transcribe'
    assert calls[0][1]['data']['languages[]']=='en'
    assert 'language' not in calls[0][1]['data']

def test_empty_and_bad_file_rejected(client,monkeypatch):
    monkeypatch.setattr(server,'API_KEY','fixture')
    assert client.post('/api/transcribe',files={'audio':('empty.webm',b'','audio/webm')},headers=headers()).status_code==400
    assert client.post('/api/transcribe',files={'audio':('evil.exe',b'xxx','application/octet-stream')},headers=headers()).status_code==400

def test_generated_missing_alignment_rejected(client,monkeypatch):
    async def fake(schema,instructions,payload):
        return schema.model_validate({'title':'새 장면','task_ko':'문장','sample_en':'Sentence.','situation_ko':'상황','alignment':[]}),{}
    monkeypatch.setattr(server,'structured_call',fake)
    assert client.post('/api/generate',json={'card_ids':['g04_05']},headers=headers()).status_code==502

def test_content_counts_and_sources():
    assert len(server.LIBRARY['cards'])==3381
    assert len([c for c in server.LIBRARY['cards'] if not c.get('material_id')])==2874
    assert len([c for c in server.LIBRARY['cards'] if c['level']=='core'])==607
    assert len([c for c in server.LIBRARY['cards'] if c['lesson_id']=='kpop'])==220
    assert len(server.CARD_MAP)==3381
    exercises=json.loads((server.ROOT/'data/exercises.json').read_text())
    assert len(exercises)==42
    assert len(set(e['task_ko'] for e in exercises))==42
    assert set(c['id'] for c in server.LIBRARY['cards'] if c['level']=='core' and not c.get('material_id')) <= set(i for e in exercises for i in e['card_ids'])
    for e in exercises:
        assert len(e['card_ids'])==5
        assert all(i in server.CARD_MAP for i in e['card_ids'])
        assert e['sample_en'] and e['task_ko'] and e['situation_ko']
    for c in server.LIBRARY['cards']:
        url=c['source_url'].split('#')[0]
        assert (server.ROOT/url.lstrip('/')).exists(),url
