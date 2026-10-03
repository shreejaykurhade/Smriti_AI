"""Opt-in prototype adapter for AI4Bharat's public Gradio demo.
Never downloads gated weights or substitutes another language. Shared GPU quota applies.
"""
import io,json,re,time,urllib.request,urllib.error
from urllib.parse import quote
import numpy as np
import soundfile as sf

BASE='https://ai4bharat-indic-parler-tts.hf.space'
LANGUAGES={'as':'Assamese','mai':'Maithili','or':'Odia','pa':'Punjabi','ks':'Kashmiri','sa':'Sanskrit','mni':'Manipuri','sd':'Sindhi'}

def request_audio(text,language,gender,style):
    pace={'museum':'a thoughtful, engaging narration with natural pauses','conversation':'a friendly, expressive conversation at a moderate pace','calm':'a slow, gentle narration with natural pauses'}[style]
    description=f'A {gender} {LANGUAGES[language]} speaker delivers {pace}. The recording has very clear audio, with no background noise.'
    endpoint=BASE+'/gradio_api/call/generate_finetuned'
    request=urllib.request.Request(endpoint,data=json.dumps({'data':[text,description]}).encode(),headers={'Content-Type':'application/json'})
    deadline=time.monotonic()+110
    try:
        with urllib.request.urlopen(request,timeout=15) as response:event=json.load(response)
        event_id=event.get('event_id','')
        if not re.fullmatch(r'[a-f0-9]{32}',event_id):raise RuntimeError('The shared AI4Bharat demo did not accept this request.')
        output=None;event_type=''
        with urllib.request.urlopen(endpoint+'/'+event_id,timeout=90) as stream:
            for raw in stream:
                if time.monotonic()>deadline:raise TimeoutError()
                line=raw.decode().strip()
                if line.startswith('event:'):event_type=line[6:].strip()
                if line.startswith('data:'):
                    data=json.loads(line[5:].strip())
                    if event_type=='error':raise RuntimeError('The shared AI4Bharat demo is busy or its free quota is exhausted. Try later or choose a local speaker.')
                    if event_type in ('complete','generating') and isinstance(data,list) and data:output=data[0]
                    if event_type=='complete':break
        path=output.get('path','') if isinstance(output,dict) else ''
        if not re.fullmatch(r'/tmp/gradio/[a-f0-9]{64}/audio(?:\.wav)?',path):raise RuntimeError('The shared voice demo returned no playable audio.')
        # Gradio 5.7's demo URL currently contains a duplicated proxy prefix.
        # Its documented FileData path maps to /gradio_api/file=<path> on this same host.
        with urllib.request.urlopen(BASE+'/gradio_api/file='+quote(path,safe='/'),timeout=25) as response:
            audio=response.read(8_000_001)
        if len(audio)>8_000_000:raise RuntimeError('The voice sample exceeded the audio limit.')
        samples,rate=sf.read(io.BytesIO(audio),dtype='float32')
        if samples.ndim>1:samples=samples.mean(axis=1)
        if len(samples)<rate//5 or not np.isfinite(samples).all():raise RuntimeError('The voice demo returned invalid audio.')
        peak=float(np.max(np.abs(samples)))
        if peak>0.95:samples=samples*(0.95/peak)
        return samples,rate
    except (urllib.error.URLError,TimeoutError,OSError) as error:
        raise RuntimeError('The shared AI4Bharat voice demo is unavailable. Try later or choose a local speaker.') from error

def remote_audio(models,text,language,gender,style):
    pieces=[];rate=None
    for chunk in models.chunks(text,250):
        samples,current_rate=request_audio(chunk,language,gender,style)
        if rate is not None and current_rate!=rate:raise RuntimeError('The voice demo changed its audio format. Please retry.')
        rate=current_rate;pieces.extend([samples,np.zeros(int(rate*.18),dtype=np.float32)])
    out=io.BytesIO();sf.write(out,np.concatenate(pieces),rate,format='WAV',subtype='PCM_16')
    return out.getvalue()
