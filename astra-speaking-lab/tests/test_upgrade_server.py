import asyncio, copy, json, sys
from pathlib import Path
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
sys.path.insert(0,str(Path(__file__).parent))
import test_server as base
import server

@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(server,'API_KEY','')
    return TestClient(server.app,base_url='http://127.0.0.1:8765')

def verify(d,text=None):
    server.verify_grade(server.GradeResult.model_validate(d),text or base.grade_body()['transcript'],['g04_05'])

def test_final_paragraph_cannot_invent_an_extra_event():
    d=base.result();d['corrected_text']+=' I bought a car.'
    with pytest.raises(ValueError,match='최종'):verify(d)

def test_correct_label_cannot_silently_change_words():
    d=base.result();d['sentence_reviews'][0].update(status='correct',corrections=[])
    with pytest.raises(ValueError,match='단어'):verify(d)

def test_optional_label_cannot_hide_negation_error():
    d=base.result();d['sentence_reviews'][0]['status']='optional'
    with pytest.raises(ValueError):verify(d)

def test_required_correction_needs_error_evidence():
    d=base.result();d['sentence_reviews'][0]['corrections']=[]
    with pytest.raises(ValueError):verify(d)

def test_unicode_words_cannot_be_silently_omitted():
    with pytest.raises(ValueError,match='마지막'):verify(base.result(),base.grade_body()['transcript']+' déjà')

def test_not_used_status_cannot_claim_quoted_usage():
    d=base.result();d['phrase_checks'][0]['status']='not_used'
    with pytest.raises(ValueError):verify(d)

def test_case_and_sentence_punctuation_are_not_errors():
    d=base.result();d['corrected_text']=d['corrected_text'].upper().replace('.', '!')
    verify(d)

def test_missing_content_length_still_obeys_actual_byte_limit(client,monkeypatch):
    monkeypatch.setattr(server,'MAX_REQUEST_BYTES',100)
    r=client.post('/api/grade',content=iter([b'x'*60,b'y'*60]),headers={**base.headers(),'Content-Type':'application/json'})
    assert r.status_code==413

def test_oversize_declared_body_is_rejected(client,monkeypatch):
    monkeypatch.setattr(server,'MAX_REQUEST_BYTES',20)
    assert client.post('/api/grade',json=base.grade_body(),headers=base.headers()).status_code==413

def test_model_validation_does_not_partially_mutate_reasoning(client,monkeypatch):
    monkeypatch.setattr(server,'REASONING_EFFORT','medium')
    r=client.post('/api/settings',json={'model':'bad model','reasoning_effort':'high'},headers=base.headers())
    assert r.status_code==400 and server.REASONING_EFFORT=='medium'

def test_reasoning_setting_roundtrip_and_no_key_exposure(client,monkeypatch):
    monkeypatch.setattr(server,'REASONING_EFFORT','medium')
    r=client.post('/api/settings',json={'reasoning_effort':'high','api_key':'fixture-hidden'},headers=base.headers())
    assert r.status_code==200 and r.json()['reasoning_effort']=='high'
    assert 'fixture-hidden' not in client.get('/api/config').text

def test_malformed_asr_result_is_controlled_error(client,monkeypatch):
    monkeypatch.setattr(server,'API_KEY','fixture')
    async def fake(*args,**kwargs):return {'text':None}
    monkeypatch.setattr(server,'openai_post',fake)
    r=client.post('/api/transcribe',files={'audio':('x.webm',b'fixture','audio/webm')},headers=base.headers())
    assert r.status_code==502

@pytest.mark.parametrize('status',['incomplete','failed','cancelled'])
def test_unfinished_provider_response_is_not_success(monkeypatch,status):
    async def fake(*args,**kwargs):return {'status':status,'output':[]}
    monkeypatch.setattr(server,'openai_post',fake)
    with pytest.raises(HTTPException) as e:asyncio.run(server.structured_call(server.GradeResult,'fixture',{}))
    assert e.value.status_code==502

def test_structured_request_uses_verified_schema_store_false_and_selected_effort(monkeypatch):
    monkeypatch.setattr(server,'REASONING_EFFORT','medium')
    async def fake(path,**kw):
        b=kw['body'];assert b['model']=='gpt-6-astra';assert b['store'] is False
        assert b['reasoning']['effort']=='medium'
        schema=b['text']['format']['schema'];assert schema['additionalProperties'] is False
        assert set(schema['required'])==set(schema['properties'])
        return {'status':'completed','output':[{'type':'message','content':[{'type':'output_text','text':json.dumps(base.result())}]}]}
    monkeypatch.setattr(server,'openai_post',fake)
    r,_=asyncio.run(server.structured_call(server.GradeResult,'fixture',{}))
    assert r.corrected_text==base.result()['corrected_text']

def test_refusal_and_non_json_are_controlled(monkeypatch):
    for piece in [{'type':'refusal','refusal':'no'},{'type':'output_text','text':'broken JSON'}]:
        async def fake(*args,**kwargs):return {'output':[{'content':[piece]}]}
        monkeypatch.setattr(server,'openai_post',fake)
        with pytest.raises(HTTPException):asyncio.run(server.structured_call(server.GradeResult,'fixture',{}))

def test_security_headers_and_private_files(client):
    r=client.get('/');assert r.headers['x-frame-options']=='DENY';assert r.headers['cache-control']=='no-store'
    for p in ['/.env','/server.py','/openapi.json','/static/../.env']:
        assert client.get(p).status_code==404

def test_too_many_duplicate_and_unknown_targets_rejected(client):
    b=base.grade_body();b['card_ids']=['g01_01']*6
    assert client.post('/api/grade',json=b,headers=base.headers()).status_code==422

def test_transfer_content_alignment():
    items=json.loads((server.ROOT/'data/transfer.json').read_text())
    assert len(items)==30
    for e in items:
        assert len(e['card_ids'])==1 and e['card_ids'][0] in server.CARD_MAP
        for a in e['alignment']:
            assert a['korean_cue'] in e['task_ko'] and a['english_use'] in e['sample_en']
