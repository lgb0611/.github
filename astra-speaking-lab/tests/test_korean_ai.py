"""Translation and paragraph contracts. Model generation uses fixtures."""
import copy
import json
import unittest
from unittest.mock import patch
import local_ai as ai
from tests.test_local_ai import AppEndpointTests

CARDS = [
 {'id':'g01_01','sentence_en':'I was thinking of taking a break.','korean_text':'잠깐 쉴까 생각하고 있었어요.'},
 {'id':'g01_02','sentence_en':'Then I came up with a different plan.','korean_text':'그러다가 다른 계획을 생각해 냈어요.'}]

def paragraph():
    first='주말에 행사를 열까 생각하고 있었어요.'
    second='그러다가 온라인으로 진행하는 다른 계획을 생각해 냈어요.'
    en1='I was thinking of hosting an event this weekend.'
    en2='Then I came up with a different plan to hold it online.'
    return {'title':'주말 행사 계획','task_ko':first+' '+second,'sample_en':en1+' '+en2,'situation_ko':'행사를 온라인으로 바꾼 계획',
      'alignment':[{'card_id':'g01_01','source_expression':'I was thinking of','korean_cue':first,'english_use':en1},
                   {'card_id':'g01_02','source_expression':'came up with','korean_cue':second,'english_use':en2}]}

def reply(data):return {'done':True,'message':{'content':json.dumps(data)}}

class KoreanAI(unittest.TestCase):
    def test_input_rejects_unknown_fields_duplicate_ids_and_non_korean_context(self):
        for data in [{'cards':CARDS,'model':'remote'},{'cards':[CARDS[0]]},{'cards':[CARDS[0],CARDS[0]]},{'cards':[CARDS[0],CARDS[1]|{'korean_text':'English only'}]}]:
            with patch.object(ai,'request') as req:
                with self.assertRaises(ai.LocalAIError):ai.paragraph(data)
                req.assert_not_called()
    def test_translation_uses_entire_sentence_and_derives_source_from_input(self):
        cards=[{'id':c['id'],'sentence_en':c['sentence_en']} for c in CARDS]
        response={'translations':[{'card_id':c['id'],'korean_text':c['korean_text'],'source_en':'invented'} for c in CARDS]}
        with patch.object(ai,'status',return_value={'ready':True}),patch.object(ai,'request',side_effect=[{},reply(response)]) as req:
            got=ai.translate({'cards':cards})
            self.assertEqual(got['translations'][0]['source_en'],CARDS[0]['sentence_en'])
            self.assertEqual(got['translations'][1]['korean_text'],CARDS[1]['korean_text'])
            self.assertEqual(req.call_args.args[1]['model'],ai.MODEL)
            self.assertIn('ENTIRE',req.call_args.args[1]['messages'][0]['content'])
    def test_translation_requires_every_card_once_and_korean_text(self):
        good=[{'card_id':c['id'],'korean_text':c['korean_text']} for c in CARDS]
        for rows in [good[:1],[good[0],good[0]],[good[0],good[1]|{'card_id':'unknown'}],[good[0],good[1]|{'korean_text':'English'}]]:
            with self.assertRaises(ai.LocalAIError):ai.checked_translations({'translations':rows},CARDS)
    def test_paragraph_reuses_every_learned_sentence_in_an_aligned_new_scene(self):
        with patch.object(ai,'status',return_value={'ready':True}),patch.object(ai,'request',side_effect=[{},reply(paragraph())]):
            got=ai.paragraph({'cards':CARDS})
            self.assertEqual(got['engine'],'local_ai')
            self.assertEqual(got['paragraph']['task_ko'],paragraph()['task_ko'])
            self.assertNotIn(CARDS[0]['sentence_en'],got['paragraph']['sample_en'])
    def test_paragraph_rejects_missing_duplicate_and_fabricated_alignment(self):
        mutations=[lambda p:p['alignment'].pop(),lambda p:p['alignment'][0].update(card_id='unknown'),lambda p:p['alignment'][0].update(source_expression='invented words here'),lambda p:p['alignment'][0].update(english_use='Not part of the paragraph.'),lambda p:p['alignment'][1].update(card_id='g01_01'),lambda p:p['alignment'][0].update(korean_cue='문단에 없는 내용')]
        for edit in mutations:
            p=paragraph();edit(p)
            with self.assertRaises(ai.LocalAIError):ai.checked_paragraph(p,CARDS)
    def test_remote_models_never_generate_translations_or_paragraphs(self):
        with patch.object(ai,'status',return_value={'ready':True}),patch.object(ai,'request',return_value={'remote_model':'cloud'}) as req:
            with self.assertRaises(ai.LocalAIError):ai.paragraph({'cards':CARDS})
            self.assertEqual(req.call_count,1)
    def test_incomplete_model_output_is_retried_once_without_saving(self):
        bad=reply(paragraph())|{'done_reason':'length'}
        with patch.object(ai,'status',return_value={'ready':True}),patch.object(ai,'request',side_effect=[{},bad,bad]) as req:
            with self.assertRaises(ai.LocalAIError):ai.paragraph({'cards':CARDS})
            self.assertEqual(req.call_count,3)
        self.assertFalse(ai.LOCK.locked())
    def test_connection_failure_is_not_repeated(self):
        with patch.object(ai,'status',return_value={'ready':True}),patch.object(ai,'request',side_effect=[{},ai.LocalAIError('offline')]) as req:
            with self.assertRaises(ai.LocalAIError):ai.paragraph({'cards':CARDS})
            self.assertEqual(req.call_count,2)

class KoreanRoutes(AppEndpointTests):
    # Only run new HTTP cases here; base endpoint tests run in their original module.
    def test_korean_routes_reject_foreign_origin_and_missing_token(self):
        for route in ['/local-ai/translate','/local-ai/paragraph']:
            for headers in [{'Origin':'https://foreign.example'},{'X-Local-Token':'wrong'}]:
                with patch.object(ai,'translate') as tr,patch.object(ai,'paragraph') as pa:
                    self.assertEqual(self.post(route,{'cards':CARDS},headers)[0],403)
                    tr.assert_not_called();pa.assert_not_called()
    def test_paragraph_route_dispatches_to_local_generation(self):
        result={'engine':'local_ai','paragraph':paragraph()}
        with patch.object(ai,'paragraph',return_value=result) as generate:
            self.assertEqual(self.post('/local-ai/paragraph',{'cards':CARDS}),(200,result))
            generate.assert_called_once_with({'cards':CARDS})
    def test_translation_route_dispatches_to_local_translation(self):
        result={'engine':'local_ai','translations':[]}
        with patch.object(ai,'translate',return_value=result) as generate:
            self.assertEqual(self.post('/local-ai/translate',{'cards':CARDS}),(200,result))
            generate.assert_called_once_with({'cards':CARDS})

# unittest discovers inherited tests too; hide the inherited cases in this suite.
for _name in AppEndpointTests.__dict__:
    if _name.startswith('test_'):setattr(KoreanRoutes,_name,None)
del AppEndpointTests
if __name__=='__main__':unittest.main()
