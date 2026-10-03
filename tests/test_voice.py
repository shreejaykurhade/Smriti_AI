import asyncio
import base64
import io
import json
import time
import wave
import numpy as np
import pytest
from fastapi.testclient import TestClient
from speech_service.app import create_app
from speech_service.live import BrowserSerializer
from pipecat.frames.frames import VADUserStartedSpeakingFrame, InputAudioRawFrame, TTSAudioRawFrame
from smriti_core.research import answer_question

class FakeModels:
    def capabilities(self):return dict(tts=True,stt=True,translation=True,tts_languages=['en','mr'],stt_languages=['en','mr'])
    def translate(self,texts,source,target):return [f'{target}: {text}' for text in texts]
    def transcribe(self,audio,language):return 'What is social democracy?'
    def synthesize(self,text,language,style,gender="auto"):
        out=io.BytesIO()
        with wave.open(out,'wb') as wav:
            wav.setnchannels(1);wav.setsampwidth(2);wav.setframerate(24000);wav.writeframes(np.zeros(4800,dtype='<i2').tobytes())
        return out.getvalue()

@pytest.fixture
def client(monkeypatch,tmp_path):
    monkeypatch.setenv('VOICE_API_KEY','test-key')
    monkeypatch.setenv('PUBLIC_VOICE_URL','http://localhost:8000')
    monkeypatch.setenv('SMRITI_AUDIO_CACHE',str(tmp_path))
    monkeypatch.delenv('OPENAI_API_KEY',raising=False)
    with TestClient(create_app(FakeModels())) as instance:
        instance.headers['x-smriti-key']='test-key'
        yield instance

def finished(client,job):
    for _ in range(100):
        result=client.get('/jobs/'+job).json()
        if result['state'] in ('done','error'):return result
        time.sleep(.01)
    raise AssertionError('Job did not complete')

def test_auth_and_unrelated_question(client):
    assert client.get('/capabilities',headers={'x-smriti-key':'wrong'}).status_code==401
    result=answer_question('What is the weather tomorrow?')
    assert not result['citations']
    assert 'enough evidence' in result['answer']

def test_regional_query_translated_before_research(client):
    calls=[]
    def translate(texts,source,target):
        calls.append((source,target))
        return ['social democracy'] if target=='en' else ['लोकशाही']
    result=answer_question('लोकांच्या स्वातंत्र्याविषयी त्यांचे विचार सांगा.','mr','mr',translate)
    assert calls==[('mr','en')]  # The recognised topic uses its prepared native answer.
    assert result['prepared_translation']
    assert 'लोकशाही' in result['answer']
    assert result['citations'][0]['id']=='constitution-speech'

def test_narration_job_and_audio(client):
    response=client.post('/jobs',json={'kind':'narrate','text':'Hello museum visitor.'})
    job=response.json()['id'];result=finished(client,job)
    assert result['state']=='done'
    audio=client.get(f'/jobs/{job}/audio')
    assert audio.headers['content-type']=='audio/wav'
    assert audio.content.startswith(b'RIFF')
    assert audio.headers['cache-control']=='no-store'

def test_input_validation(client):
    assert client.post('/transcribe',content=b'not wav').status_code==400
    assert client.post('/transcribe',content=b'x'*1_000_001).status_code==413
    assert client.post('/jobs',json={'kind':'narrate','text':'Hello','language':'fake'}).status_code==422
    assert client.post('/jobs',json={'kind':'research','text':''}).status_code==422
    assert client.get('/jobs/not-a-real-id/audio').status_code==404

def test_transcribe_ephemeral(client):
    wav=FakeModels().synthesize('test','en','museum')
    # WAV must be 16 kHz input, not narration's 24 kHz output.
    out=io.BytesIO()
    with wave.open(out,'wb') as w:
        w.setnchannels(1);w.setsampwidth(2);w.setframerate(16000);w.writeframes(b'\0'*32000)
    job=client.post('/transcribe?language=en',content=out.getvalue()).json()['id']
    assert finished(client,job)['result']['transcript']=='What is social democracy?'
    assert client.app.state.runtime.jobs[job].audio is None

@pytest.mark.asyncio
async def test_pcm_serializer_limits():
    serializer=BrowserSerializer()
    assert isinstance(await serializer.deserialize(json.dumps({'type':'start'})),VADUserStartedSpeakingFrame)
    assert isinstance(await serializer.deserialize(json.dumps({'type':'audio','audio':base64.b64encode(b'\0'*320).decode()})),InputAudioRawFrame)
    with pytest.raises(ValueError):await serializer.deserialize(json.dumps({'type':'audio','audio':'!invalid!'}))
    frame=TTSAudioRawFrame(audio=b'\0'*10,sample_rate=24000,num_channels=1)
    assert json.loads(await serializer.serialize(frame))['sample_rate']==24000

def test_ws_auth_and_single_use_session(client):
    session=client.post('/session',json={'kind':'transcribe'}).json()
    with client.websocket_connect('/conversation',headers={'origin':'http://localhost:3000'}) as ws:
        ws.send_json({'token':session['token']})
        assert ws.receive_json()['type']=='ready'
    with pytest.raises(Exception):
        with client.websocket_connect('/conversation',headers={'origin':'https://evil.invalid'}) as ws:ws.receive_json()
    with pytest.raises(Exception):
        with client.websocket_connect('/conversation',headers={'origin':'http://localhost:3000'}) as ws:
            ws.send_json({'token':session['token']});ws.receive_json()

def test_pipecat_end_to_end_frames(client):
    session=client.post('/session',json={'kind':'transcribe'}).json()
    with client.websocket_connect('/conversation',headers={'origin':'http://localhost:3000'}) as ws:
        ws.send_json({'token':session['token']})
        assert ws.receive_json()['type']=='ready'
        ws.send_json({'type':'start'})
        # One second PCM input, streamed in 80 ms frames, then explicit end.
        for _ in range(13):ws.send_json({'type':'audio','audio':base64.b64encode(b'\0'*2560).decode()})
        ws.send_json({'type':'end'})
        seen=set()
        for _ in range(100):
            message=ws.receive_json();seen.add(message['type'])
            if 'audio' in seen:break
        assert {'transcript','answer','audio'}<=seen


def test_cancel_and_tts_language_boundaries(client):
    job=client.post('/jobs',json={'kind':'narrate','text':'Welcome.'}).json()['id']
    assert client.delete('/jobs/'+job).json()['state']=='cancelled'
    assert client.get('/jobs/'+job+'/audio').status_code==404
    assert client.post('/session',json={'kind':'transcribe','language':'pa'}).status_code==400

def test_honorifics_are_not_split():
    from speech_service.models import Models
    assert Models.chunks('Dr. B. R. Ambedkar spoke about equality. Explore his work.')[0]=='Dr. B. R. Ambedkar spoke about equality.'

def test_gender_is_validated_and_cached_separately(client):
    calls=[]
    original=client.app.state.runtime.models.synthesize
    def synthesize(text,language,style,gender='auto'):
        calls.append(gender)
        return original(text,language,style,gender)
    client.app.state.runtime.models.synthesize=synthesize
    for gender in ('female','male','female'):
        job=client.post('/jobs',json={'kind':'narrate','text':'Same passage.','gender':gender}).json()['id']
        assert finished(client,job)['state']=='done'
    assert calls==['female','male']
    assert client.post('/jobs',json={'kind':'narrate','text':'Hello','gender':'fake'}).status_code==422

def test_live_session_retains_speaker_choice(client):
    session=client.post('/session',json={'kind':'transcribe','language':'mr','gender':'male','style':'calm'}).json()
    stored=client.app.state.runtime.tokens[session['token']]
    assert stored['gender']=='male'
    assert stored['language']=='mr' and stored['style']=='calm'

def test_capabilities_only_offer_installed_local_models(monkeypatch,tmp_path):
    from speech_service.models import Models
    from speech_service.voices import select_voice
    monkeypatch.setenv('SMRITI_MODEL_DIR',str(tmp_path))
    monkeypatch.setenv('SMRITI_TTS_PROVIDER','hybrid')
    monkeypatch.setenv('SMRITI_REMOTE_PARLER','0')
    model=Models()
    assert 'as' not in model.capabilities()['tts_languages']
    path=tmp_path/'mms/as';path.mkdir(parents=True);(path/'config.json').write_text('{}')
    assert 'as' not in model.capabilities()['tts_languages']  # Incomplete download is not ready.
    (path/'model.safetensors').write_bytes(b'model')
    assert select_voice(model,'as')['gender']=='original'
    with pytest.raises(ValueError):select_voice(model,'as','female')
    assert select_voice(model,'ur','female')['id']=='ur-IN-GulNeural'
    assert select_voice(model,'mr','male')['id']=='mr-IN-ManoharNeural'
    monkeypatch.setenv('SMRITI_REMOTE_PARLER','1')
    assert select_voice(model,'sa','female')['provider']=='parler-demo'
    assert select_voice(model,'ks','male')['experimental'] is True

@pytest.mark.asyncio
async def test_live_tts_uses_chosen_gender(client):
    from speech_service.live import IndicNarrator
    calls=[]
    original=client.app.state.runtime.models.synthesize
    def synthesize(text,language,style,gender='auto'):
        calls.append((language,style,gender));return original(text,language,style,gender)
    client.app.state.runtime.models.synthesize=synthesize
    narrator=IndicNarrator(client.app.state.runtime,'mr','calm','male')
    frames=[frame async for frame in narrator.run_tts('Museum answer','test-context')]
    assert calls==[('mr','calm','male')]
    assert frames and all(isinstance(frame,TTSAudioRawFrame) for frame in frames)
    assert narrator._settings.model is not None and narrator._settings.voice=='male'
