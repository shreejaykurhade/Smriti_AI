"""Exercise the real local queue with regional questions and playable narration."""
import io
import json
import time
import urllib.request
import wave
from pathlib import Path

import os
base=os.getenv('SMRITI_PREVIEW_URL','http://127.0.0.1:3003').rstrip('/')+'/api/voice/'
def request(path,payload=None):
    r=urllib.request.Request(base+path,data=json.dumps(payload).encode() if payload is not None else None,headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(r,timeout=30) as response:return json.load(response)
def job(payload):
    id=request('jobs',payload)['id']
    for _ in range(300):
        state=request('jobs/'+id)
        if state['state']=='error':raise RuntimeError(state['error'])
        if state['state']=='done':return id,state['result']
        time.sleep(.5)
    raise RuntimeError('Job timed out')
for language,question in [('en','What is social democracy?'),('hi','बाबासाहेब आंबेडकर के सामाजिक लोकतंत्र के विचार क्या थे?'),('mr','बाबासाहेब आंबेडकरांच्या सामाजिक लोकशाहीच्या कल्पना काय होत्या?')]:
    _,answer=job({'kind':'research','text':question,'language':language,'source_language':language})
    assert answer['citations'], answer
    print(language,answer['answer'],flush=True)
    id,_=job({'kind':'narrate','text':answer['spoken_text'],'language':language,'source_language':language})
    with urllib.request.urlopen(base+'jobs/'+id+'/audio') as response:audio=response.read()
    with wave.open(io.BytesIO(audio)) as wav:print('Audio seconds:',round(wav.getnframes()/wav.getframerate(),1),flush=True)
    Path(f'tests/fixtures/answer-{language}.wav').write_bytes(audio)
