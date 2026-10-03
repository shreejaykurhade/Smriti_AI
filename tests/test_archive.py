from api.index import app

def test_english_research_without_paid_key(monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY',raising=False)
    client=app.test_client()
    result=client.post('/api/ask',json={'question':'What is social democracy?'}).get_json()
    assert result['citations'][0]['id']=='constitution-speech'
    assert result['evidence_scope']=='curated summaries linked to verified primary editions'
    assert result['citations'][0]['pdfUrl'].startswith('https://elibrary.sansad.in/')

def test_regional_abstention_without_a_model_host_is_not_a_server_error(monkeypatch):
    monkeypatch.delenv('VOICE_BACKEND_URL',raising=False)
    response=app.test_client().post('/api/ask',json={'question':'अज्ञात विषयावर तपशीलवार प्रश्न','language':'mr','question_language':'mr'})
    assert response.status_code==200
    assert response.get_json()['citations']==[]
    assert 'पुरेसा पुरावा' in response.get_json()['answer']

def test_unrelated_question_has_no_fake_citations(monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY',raising=False)
    response=app.test_client().post('/api/ask',json={'question':'What is Bitcoin worth?'}).get_json()
    assert response['citations']==[]

def test_every_curated_record_has_an_original_pdf_and_provenance():
    from smriti_core.research import RECORDS
    from urllib.parse import urlparse
    assert len(RECORDS)==13
    for record in RECORDS:
        assert urlparse(record['pdfUrl']).hostname in {'www.mea.gov.in','elibrary.sansad.in'}
        assert record['sourceUrl'].startswith('https://')
        assert len(record['sourceSha256'])==64
        assert 1 <= record['pdfPage'] <= record['pdfPageCount']
        if record['excerpt']:assert record['excerptPage'] is not None

def test_prepared_regional_question_needs_no_model_server(monkeypatch):
    from smriti_core.research import GUIDE_LOCALES, answer_question
    monkeypatch.delenv('VOICE_BACKEND_URL',raising=False)
    packet=GUIDE_LOCALES['mr']['democracy']
    def unavailable(*args):raise AssertionError('A prepared response must not call a model')
    result=answer_question(packet['question'],'mr','mr',unavailable)
    assert result['prepared_translation']
    assert result['answer']==packet['answer']
    assert result['citations'][0]['excerptPage']==60

def test_questions_with_ambedkar_name_do_not_bypass_evidence():
    from smriti_core.research import answer_question
    assert answer_question('What did Ambedkar say about Bitcoin?')['citations']==[]

def test_official_volume_library_contains_only_checked_pdfs():
    import json
    from pathlib import Path
    volumes=json.loads(Path('smriti_core/source-library.json').read_text())
    assert len(volumes)==60
    assert sum(v['language']=='English' for v in volumes)==20
    assert sum(v['language']=='Hindi' for v in volumes)==40
    assert all(v['verifiedAt']=='2026-10-03' and v['httpStatus'] in (200,206) for v in volumes)


def test_native_democracy_transcript_skips_retranslation():
    from smriti_core.research import answer_question
    def unavailable(*args):
        raise AssertionError('A common native topic should not need another translation pass')
    result=answer_question('आमबेड करान्ना सामाजिक लोक्षाही मनजे काई अभिप्रेत होते।','mr','mr',unavailable)
    assert result['topic']=='democracy'
    assert result['prepared_translation']
    assert result['citations'][0]['id']=='constitution-speech'

def test_vercel_ready_questions_cover_every_narrated_language_without_models(monkeypatch):
    from smriti_core.research import GUIDE_LOCALES, TOPICS
    monkeypatch.delenv('VOICE_BACKEND_URL',raising=False)
    monkeypatch.delenv('VOICE_API_KEY',raising=False)
    client=app.test_client()
    for language in ['en','bn','gu','hi','kn','ml','mr','ne','ta','te','ur']:
        for topic in TOPICS:
            question=GUIDE_LOCALES[language][topic['id']]['question'] if language!='en' else topic['question']
            result=client.post('/api/ask',json={'question':question,'language':language,'question_language':language})
            assert result.status_code==200
            assert result.get_json()['topic']==topic['id']
            assert result.get_json()['citations']

def test_native_questions_without_exact_preset_wording_can_use_curated_topics():
    from smriti_core.research import answer_question
    assert answer_question('बाबासाहेबांनी जाती व्यवस्थेबद्दल काय म्हटले?','mr','mr')['topic']=='caste'
    assert answer_question('बाबासाहेब ने महिलाओं के अधिकारों के लिए क्या किया?','hi','hi')['topic']=='women'

def test_unknown_regional_topics_never_get_canned_source_claims():
    from smriti_core.research import answer_question
    result=answer_question('आंबेडकर आणि बिटकॉइनची आजची किंमत काय?','mr','mr')
    assert result['topic'] is None
    assert result['citations']==[]
