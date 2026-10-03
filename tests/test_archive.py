from api.index import app

def test_english_research_without_paid_key(monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY',raising=False)
    client=app.test_client()
    result=client.post('/api/ask',json={'question':'What is social democracy?'}).get_json()
    assert result['citations'][0]['id']=='constitution-speech'
    assert result['evidence_scope']=='curated summaries linked to verified primary editions'
    assert result['citations'][0]['pdfUrl'].startswith('https://elibrary.sansad.in/')

def test_missing_translation_is_explicit(monkeypatch):
    monkeypatch.delenv('VOICE_BACKEND_URL',raising=False)
    response=app.test_client().post('/api/ask',json={'question':'अज्ञात विषयावर तपशीलवार प्रश्न','language':'mr','question_language':'mr'})
    assert response.status_code==503
    assert 'translation' in response.get_json()['error'].lower() or 'IndicTrans2' in response.get_json()['error']

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
