import json
import urllib.error
import pytest
from api.index import app
from smriti_core import answer_service as service


@pytest.fixture(autouse=True)
def isolate(monkeypatch):
    monkeypatch.setenv('GROQ_API_KEY','test-server-only-secret')
    monkeypatch.delenv('VOICE_BACKEND_URL',raising=False)
    monkeypatch.delenv('VOICE_API_KEY',raising=False)
    service._cache.clear()


def supported(text='The two works use academic analysis and personal recollection.'):
    return {'answer':text,'supported':True,'record_ids':['castes-india','waiting-visa']}


def test_server_resolves_citations_only_from_official_registry(monkeypatch):
    monkeypatch.setattr(service,'_completion',lambda *args:supported())
    response=app.test_client().post('/api/ask',json={'question':'Compare the evidence in these works.'})
    packet=response.get_json()
    assert response.status_code==200 and response.headers['Cache-Control']=='no-store'
    assert packet['mode']=='source-grounded-answer'
    assert [c['id'] for c in packet['citations']]==['castes-india','waiting-visa']
    assert all(c['pdfUrl'].startswith('https://www.mea.gov.in/') for c in packet['citations'])
    assert 'test-server-only-secret' not in response.get_data(as_text=True)


@pytest.mark.parametrize('language',list(service.LANGUAGE_NAMES))
def test_selected_language_reaches_answer_service_and_narration(monkeypatch,language):
    def completion(question,selected):
        assert selected==language and question=='Compare the works.'
        return supported(service.FALLBACKS[language])
    monkeypatch.setattr(service,'_completion',completion)
    packet=app.test_client().post('/api/ask',json={'question':'Compare the works.','language':language}).get_json()
    assert packet['language']==language and packet['mode']=='source-grounded-answer'
    assert packet['spoken_text']==packet['answer']


@pytest.mark.parametrize('packet',[
    {'answer':'A fabricated source','supported':True,'record_ids':['invented-book']},
    {'answer':'Uncited history','supported':True,'record_ids':[]},
    {'answer':'False supported statement','supported':False,'record_ids':['castes-india']},
    {'answer':'See https://fake-source.test','supported':True,'record_ids':['castes-india']},
    {'answer':'<script>evil</script>','supported':True,'record_ids':['castes-india']},
    {'answer':'x'*1201,'supported':True,'record_ids':['castes-india']},
    {'answer':'Invalid sources','supported':True,'record_ids':{'id':'castes-india'}},
    {'answer':'','supported':True,'record_ids':['castes-india']},
])
def test_bad_model_output_falls_back_without_breaking_site(monkeypatch,packet):
    monkeypatch.setattr(service,'_completion',lambda *args:packet)
    result=service.museum_answer('What is social democracy?')
    assert result['mode']=='curated-source-guide'
    assert result['citations'][0]['id']=='constitution-speech'


def test_model_abstention_does_not_return_keyword_matched_false_claims(monkeypatch):
    monkeypatch.setattr(service,'_completion',lambda *args:{'answer':'Unsupported.','supported':False,'record_ids':[]})
    result=service.museum_answer('Did Ambedkar recommend Bitcoin to defeat caste?','mr')
    assert result['citations']==[] and result['answer']==service.FALLBACKS['mr']


@pytest.mark.parametrize('code',[401,403,429,503])
def test_upstream_auth_quota_and_outage_are_safe_fallbacks(monkeypatch,code):
    def unavailable(*args):
        raise urllib.error.HTTPError(service.ENDPOINT,code,'test-server-only-secret',{},None)
    monkeypatch.setattr(service,'_completion',unavailable)
    response=app.test_client().post('/api/ask',json={'question':'What is social democracy?','language':'hi'})
    assert response.status_code==200 and response.get_json()['mode']=='curated-source-guide'
    assert 'test-server-only-secret' not in response.get_data(as_text=True)


def test_timeout_and_missing_key_keep_existing_guide(monkeypatch):
    def timeout(*args):raise TimeoutError('timeout')
    monkeypatch.setattr(service,'_completion',timeout)
    assert service.museum_answer('What is social democracy?')['mode']=='curated-source-guide'
    monkeypatch.delenv('GROQ_API_KEY')
    monkeypatch.setattr(service,'_completion',lambda *args:pytest.fail('Missing key called provider'))
    assert service.museum_answer('What is social democracy?')['citations']


def test_answer_cache_does_not_mix_languages_and_uses_no_plain_question_key(monkeypatch):
    calls=[]
    def complete(question,language):
        calls.append(language);return supported(service.FALLBACKS[language])
    monkeypatch.setattr(service,'_completion',complete)
    first=service.museum_answer('Compare the works.','en')
    first['citations'].clear()
    assert service.museum_answer('Compare the works.','en')['citations']
    assert service.museum_answer('Compare the works.','mr')['answer']==service.FALLBACKS['mr']
    assert calls==['en','mr']
    assert all(len(key)==64 and 'Compare' not in key for key in service._cache)


@pytest.mark.parametrize('payload',[['not a question object'],{'question':[]},{'question':'x'*1201},
                                          {'question':'q','language':['mr']}])
def test_invalid_requests_never_call_model(monkeypatch,payload):
    monkeypatch.setattr(service,'_completion',lambda *args:pytest.fail('Invalid request called provider'))
    assert app.test_client().post('/api/ask',json=payload).status_code==400


def test_completion_contract_keeps_credentials_out_of_prompt_and_validates_truncation(monkeypatch):
    class Response:
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def read(self,limit):
            return json.dumps({'choices':[{'finish_reason':'length','message':{'content':json.dumps(supported())}}]}).encode()
    def request(req,timeout):
        body=json.loads(req.data)
        assert timeout==18 and req.full_url==service.ENDPOINT
        assert 'test-server-only-secret' not in json.dumps(body)
        assert body['response_format']['json_schema']['strict'] is True
        assert json.loads(body['messages'][1]['content'])['output_language']=='Marathi'
        return Response()
    monkeypatch.setattr(service.urllib.request,'urlopen',request)
    with pytest.raises(ValueError,match='Incomplete'):
        service._completion('Compare the works.','mr')


def test_mixed_regional_scripts_fall_back_to_native_guide(monkeypatch):
    # Reproduces real Malayalam output containing Kannada words.
    monkeypatch.setattr(service,'_completion',lambda *args:supported('ഡോ. അംബേദ്കർ ವಿನಿಮಯ ನೀತിയും സംബന്ധിച്ചുള്ള പഠനം അവതരിപ്പിച്ചു.'))
    result=service.museum_answer('What did Ambedkar write about the rupee?','ml')
    assert result['mode']=='curated-source-guide'
    assert result['prepared_translation']


def test_english_only_output_is_not_presented_as_regional_answer(monkeypatch):
    monkeypatch.setattr(service,'_completion',lambda *args:supported())
    result=service.museum_answer('What is social democracy?','hi')
    assert result['mode']=='curated-source-guide' and 'लोकतंत्र' in result['answer']


def test_compound_query_keeps_both_topic_sources_and_unknown_uses_all_records():
    evidence=service._evidence_for('Compare caste and monetary policy.','en')
    ids={record['id'] for record in evidence['records']}
    assert {'annihilation-caste','problem-rupee'}<=ids
    assert len(service._evidence_for('Unrecognised request.','mr')['records'])==13
    comparison=service._evidence_for('Compare Castes in India with Waiting for a Visa.','mr')
    assert {'castes-india','waiting-visa'}<={record['id'] for record in comparison['records']}
