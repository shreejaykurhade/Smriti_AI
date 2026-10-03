import asyncio
import hashlib
import io
import os
import secrets
import time
import wave
from collections import deque
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException, Request, WebSocket
from fastapi.responses import Response
from pydantic import BaseModel, Field, model_validator
from smriti_core.research import answer_question
from .languages import FLORES, STYLES
from .models import Models

TTL = 900
MAX_AUDIO = 1_000_000  # 30 seconds, 16 kHz mono PCM16 WAV.

class JobInput(BaseModel):
    kind: Literal['narrate','research','transcribe','translate']
    text: str = Field(default='',max_length=3000)
    texts: list[str] = Field(default_factory=list,max_length=40)
    language: str = 'en'
    source_language: str = 'en'
    style: str = 'museum'
    gender: Literal['auto','female','male','original'] = 'auto'
    @model_validator(mode='after')
    def validate_options(self):
        if self.language not in FLORES or self.source_language not in FLORES or self.style not in STYLES:
            raise ValueError('Unsupported language or narrator style.')
        if self.kind in ('research','narrate') and not self.text.strip(): raise ValueError('Text is required.')
        if any(not isinstance(t,str) or len(t)>3000 for t in self.texts) or sum(map(len,self.texts))>15000:
            raise ValueError('Translation batch is too large.')
        return self

@dataclass
class Job:
    input: JobInput
    audio: bytes | None = None
    state: str = 'queued'
    result: dict = field(default_factory=dict)
    error: str = ''
    created: float = field(default_factory=time.monotonic)

class Runtime:
    def __init__(self, models=None):
        self.models=models or Models()
        self.jobs={}
        self.queue=asyncio.Queue(maxsize=8)
        self.tokens={}
        self.sockets=0
        self.requests=deque()
        self.lock=asyncio.Lock()  # REST and Pipecat share the same bounded inference lane.
        self.cache=Path(os.getenv('SMRITI_AUDIO_CACHE','./.audio-cache'))
        self.cache.mkdir(parents=True,exist_ok=True)
    def clean(self):
        now=time.monotonic()
        self.jobs={k:v for k,v in self.jobs.items() if now-v.created<TTL or v.state=='running'}
        self.tokens={k:v for k,v in self.tokens.items() if v['expires']>now}
    async def infer(self, fn, *args):
        async with self.lock:
            task=asyncio.create_task(asyncio.to_thread(fn,*args))
            try: return await asyncio.shield(task)
            except asyncio.CancelledError:
                await task  # Do not allow a second inference to race a still-running GPU thread.
                raise
    def rate_limit(self):
        now=time.monotonic()
        while self.requests and self.requests[0]<now-60: self.requests.popleft()
        if len(self.requests)>=30: raise HTTPException(429,'Voice service is busy. Please wait a minute.')
        self.requests.append(now)
    async def enqueue(self, payload, audio=None):
        self.clean(); self.rate_limit()
        if self.queue.full() or len(self.jobs)>=120: raise HTTPException(429,'Voice queue is full. Try again shortly.')
        job_id=secrets.token_urlsafe(24)
        self.jobs[job_id]=Job(payload,audio=audio)
        self.queue.put_nowait(job_id)
        return {'id':job_id,'state':'queued'}
    def execute(self,job):
        p=job.input
        if p.kind=='research': return answer_question(p.text,p.language,p.source_language,self.models.translate)
        if p.kind=='translate': return {'translations':self.models.translate(p.texts,p.source_language,p.language),'language':p.language}
        if p.kind=='transcribe': return {'transcript':self.models.transcribe(job.audio,p.language),'language':p.language}
        spoken=p.text if p.source_language==p.language else self.models.translate([p.text],p.source_language,p.language)[0]
        voice_id=getattr(self.models,'tts_provider','indic-parler')
        if isinstance(self.models,Models):
            from .voices import select_voice
            voice_id=select_voice(self.models,p.language,p.gender)['id']
        key=hashlib.sha256(f"v5|{voice_id}|{p.language}|{p.style}|{p.gender}|{spoken}".encode()).hexdigest()
        path=self.cache/f'{key}.wav'
        if path.exists() and time.time()-path.stat().st_mtime<86400:
            job.audio=path.read_bytes()
        else:
            job.audio=self.models.synthesize(spoken,p.language,p.style,p.gender)
            path.write_bytes(job.audio)
        # One-day narration cache; cap disk usage for public deployments.
        files=sorted(self.cache.glob('*.wav'),key=lambda f:f.stat().st_mtime)
        total=sum(f.stat().st_size for f in files)
        for file in files:
            if time.time()-file.stat().st_mtime>86400 or total>256_000_000:
                total-=file.stat().st_size;file.unlink(missing_ok=True)
        return {'text':spoken,'language':p.language,'format':'wav','gender':p.gender}
    async def worker(self):
        while True:
            job_id=await self.queue.get()
            try:
                job=self.jobs.get(job_id)
                if not job or job.state=='cancelled': continue
                job.state='running'
                job.result=await self.infer(self.execute,job)
                if job.state!='cancelled': job.state='done'
                else: job.audio=None;job.result={}
            except (ValueError,RuntimeError) as error:
                job.state='error';job.error=str(error)
            except Exception:
                job.state='error';job.error='Model inference failed. Check the model installation and server resources.'
            finally:
                # Recordings are ephemeral; never retain input microphone audio after transcription.
                if job and job.input.kind=='transcribe': job.audio=None
                self.queue.task_done()

def validate_wav(audio):
    if len(audio)>MAX_AUDIO: raise HTTPException(413,'Recording is too large.')
    try:
        with wave.open(io.BytesIO(audio),'rb') as wav:
            if wav.getnchannels()!=1 or wav.getsampwidth()!=2 or wav.getframerate()!=16000 or wav.getnframes()>480000:
                raise ValueError()
    except (wave.Error,EOFError,ValueError):
        raise HTTPException(400,'Use a mono 16 kHz PCM16 WAV recording of up to 30 seconds.')

def create_app(models=None):
    runtime=Runtime(models)
    @asynccontextmanager
    async def lifespan(app):
        if not os.getenv('VOICE_API_KEY'): raise RuntimeError('Set VOICE_API_KEY before starting the speech service.')
        task=asyncio.create_task(runtime.worker())
        yield
        task.cancel()
        try: await task
        except asyncio.CancelledError: pass
    app=FastAPI(title='SMRITI Voice',lifespan=lifespan)
    app.state.runtime=runtime
    @app.middleware('http')
    async def authorize(request:Request,call_next):
        key=os.getenv('VOICE_API_KEY','')
        if not key or not secrets.compare_digest(request.headers.get('x-smriti-key',''),key):
            return Response('Unauthorized',status_code=401)
        response=await call_next(request)
        response.headers['Cache-Control']='no-store'
        response.headers['X-Content-Type-Options']='nosniff'
        return response
    @app.get('/capabilities')
    async def capabilities(): return runtime.models.capabilities()
    @app.post('/jobs')
    async def submit(payload:JobInput): return await runtime.enqueue(payload)
    @app.post('/transcribe')
    async def transcribe(request:Request,language:str='en'):
        if language not in FLORES: raise HTTPException(400,'Unsupported language.')
        data=bytearray()
        async for chunk in request.stream():
            data.extend(chunk)
            if len(data)>MAX_AUDIO: raise HTTPException(413,'Recording is too large.')
        validate_wav(bytes(data))
        return await runtime.enqueue(JobInput(kind='transcribe',language=language),bytes(data))
    @app.get('/jobs/{job_id}')
    async def status(job_id:str):
        runtime.clean(); job=runtime.jobs.get(job_id)
        if not job: raise HTTPException(404,'Voice job expired or was not found.')
        return {'id':job_id,'state':job.state,'result':job.result if job.state=='done' else None,'error':job.error or None}
    @app.delete('/jobs/{job_id}')
    async def cancel(job_id:str):
        job=runtime.jobs.get(job_id)
        if not job: raise HTTPException(404,'Job not found.')
        job.state='cancelled';job.audio=None;job.result={}
        return {'state':'cancelled'}
    @app.get('/jobs/{job_id}/audio')
    async def audio(job_id:str):
        runtime.clean(); job=runtime.jobs.get(job_id)
        if not job or job.input.kind!='narrate' or job.state!='done' or not job.audio: raise HTTPException(404,'Audio is not ready or has expired.')
        return Response(job.audio,media_type='audio/wav')
    @app.post('/session')
    async def session(payload:JobInput):
        runtime.clean();runtime.rate_limit()
        caps=runtime.models.capabilities()
        if not caps['stt'] or not caps['tts'] or (payload.language!='en' and not caps['translation']):
            raise HTTPException(503,'Live voice needs the installed speech and translation models.')
        if payload.language not in set(caps['stt_languages'])&set(caps['tts_languages']): raise HTTPException(400,'Live voice is not supported for this language. Use a typed question.')
        public=os.getenv('PUBLIC_VOICE_URL','').rstrip('/')
        parsed=urlparse(public)
        if parsed.scheme not in ('http','https') or not parsed.netloc: raise HTTPException(503,'Set PUBLIC_VOICE_URL on the speech server.')
        from .voices import select_voice
        if isinstance(runtime.models,Models):
            try:select_voice(runtime.models,payload.language,payload.gender)
            except ValueError as error:raise HTTPException(400,str(error))
        if len(runtime.tokens)>=20: raise HTTPException(429,'Too many live sessions.')
        token=secrets.token_urlsafe(32)
        runtime.tokens[token]={'expires':time.monotonic()+60,'language':payload.language,'style':payload.style,'gender':payload.gender}
        return {'url':public.replace('https://','wss://').replace('http://','ws://')+'/conversation','token':token}
    @app.websocket('/conversation')
    async def conversation(ws:WebSocket):
        origins={x.strip() for x in os.getenv('VOICE_ALLOWED_ORIGINS','http://localhost:3000').split(',')}
        if ws.headers.get('origin') not in origins or runtime.sockets>=3:
            await ws.close(code=1008);return
        # Token sent in first message, not a URL that could leak into access logs.
        await ws.accept()
        try:
            hello=await asyncio.wait_for(ws.receive_json(),timeout=5)
            session=runtime.tokens.pop(str(hello.get('token','')),None)
            if not session or session['expires']<time.monotonic(): await ws.close(code=1008);return
            runtime.sockets+=1
            from .live import run_conversation
            await asyncio.wait_for(run_conversation(ws,runtime,session),timeout=300)
        except Exception:
            try: await ws.close(code=1011)
            except RuntimeError: pass
        finally:
            if 'session' in locals() and session: runtime.sockets=max(0,runtime.sockets-1)
    return app

app=create_app()
