"""Pipecat push-to-talk transport; the browser never receives a model-service secret."""
import base64
import io
import json
import time
import numpy as np
import soundfile as sf
from scipy.signal import resample_poly
from math import gcd
from pipecat.frames.frames import (InputAudioRawFrame, OutputAudioRawFrame, OutputTransportMessageFrame, OutputTransportMessageUrgentFrame, VADUserStartedSpeakingFrame, VADUserStoppedSpeakingFrame, TranscriptionFrame, TextFrame, LLMFullResponseStartFrame, LLMFullResponseEndFrame, TTSAudioRawFrame, ErrorFrame)
from pipecat.serializers.base_serializer import FrameSerializer
from pipecat.services.stt_service import SegmentedSTTService
from pipecat.services.tts_service import TTSService
from pipecat.services.settings import TTSSettings,STTSettings
from pipecat.processors.frame_processor import FrameProcessor
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.worker import PipelineWorker, PipelineParams
from pipecat.workers.runner import WorkerRunner
from pipecat.transports.websocket.fastapi import FastAPIWebsocketTransport,FastAPIWebsocketParams
from smriti_core.research import answer_question
from .models import Models

class BrowserSerializer(FrameSerializer):
    def __init__(self):
        super().__init__();self.recording=False;self.bytes=0;self.started=0
    async def deserialize(self,data):
        if not isinstance(data,str) or len(data)>100000: raise ValueError('Invalid voice message.')
        item=json.loads(data)
        kind=item.get('type')
        if kind=='start' and not self.recording:
            self.recording=True;self.bytes=0;self.started=time.monotonic()
            return VADUserStartedSpeakingFrame()
        if kind=='end' and self.recording:
            self.recording=False;return VADUserStoppedSpeakingFrame()
        if kind=='audio' and self.recording:
            audio=base64.b64decode(item.get('audio',''),validate=True)
            self.bytes+=len(audio)
            if len(audio)%2 or self.bytes>960000 or time.monotonic()-self.started>32: raise ValueError('Recording limit exceeded.')
            return InputAudioRawFrame(audio=audio,sample_rate=16000,num_channels=1)
        return None
    async def serialize(self,frame):
        if isinstance(frame,OutputAudioRawFrame):
            return json.dumps({'type':'audio','audio':base64.b64encode(frame.audio).decode(),'sample_rate':frame.sample_rate})
        if isinstance(frame,(OutputTransportMessageFrame,OutputTransportMessageUrgentFrame)):
            return json.dumps(frame.message)
        return None

class BargeIn(FrameProcessor):
    async def process_frame(self,frame,direction):
        await super().process_frame(frame,direction)
        if isinstance(frame,VADUserStartedSpeakingFrame):await self.broadcast_interruption()
        await self.push_frame(frame,direction)

class SharedWhisper(SegmentedSTTService):
    def __init__(self,runtime,language):
        super().__init__(sample_rate=16000,audio_passthrough=False,settings=STTSettings(model="faster-whisper",language=language));self.runtime=runtime;self.language=language
    async def run_stt(self,audio):
        try:
            text=await self.runtime.infer(self.runtime.models.transcribe,audio,self.language)
            yield TranscriptionFrame(text=text,user_id='visitor',timestamp=str(time.time()))
        except Exception:
            yield OutputTransportMessageFrame(message={'type':'error','message':'Could not transcribe this recording. Try a shorter question.'})

class ArchiveGuide(FrameProcessor):
    def __init__(self,runtime,language): super().__init__();self.runtime=runtime;self.language=language
    async def process_frame(self,frame,direction):
        await super().process_frame(frame,direction)
        if isinstance(frame,TranscriptionFrame):
            await self.push_frame(OutputTransportMessageFrame(message={'type':'transcript','text':frame.text}))
            try:
                result=await self.runtime.infer(answer_question,frame.text,self.language,self.language,self.runtime.models.translate)
                await self.push_frame(OutputTransportMessageFrame(message={'type':'answer',**result}))
                await self.push_frame(LLMFullResponseStartFrame())
                await self.push_frame(TextFrame(text=result['spoken_text']))
                await self.push_frame(LLMFullResponseEndFrame())
            except Exception:
                await self.push_frame(OutputTransportMessageFrame(message={'type':'error','message':'The archive or translation service is unavailable.'}))
        else: await self.push_frame(frame,direction)

class IndicNarrator(TTSService):
    def __init__(self,runtime,language,style,gender="auto"):
        super().__init__(sample_rate=24000,push_start_frame=True,push_stop_frames=True,settings=TTSSettings(model=getattr(runtime.models,"tts_provider","museum"),voice=gender,language=language))
        self.runtime=runtime;self.language=language;self.style=style;self.gender=gender
    async def run_tts(self,text,context_id):
        try:
            for passage in Models.chunks(text,260):
                wav=await self.runtime.infer(self.runtime.models.synthesize,passage,self.language,self.style,self.gender)
                samples,rate=sf.read(io.BytesIO(wav),dtype='float32')
                divisor=gcd(rate,24000)
                samples=resample_poly(samples,24000//divisor,rate//divisor)
                pcm=(np.clip(samples,-1,1)*32767).astype('<i2').tobytes()
                for start in range(0,len(pcm),4800):
                    yield TTSAudioRawFrame(audio=pcm[start:start+4800],sample_rate=24000,num_channels=1,context_id=context_id)
        except Exception:
            yield OutputTransportMessageFrame(message={'type':'error','message':'Narration could not be generated. The text answer is still available.'})

async def run_conversation(ws,runtime,session):
    transport=FastAPIWebsocketTransport(websocket=ws,params=FastAPIWebsocketParams(audio_in_enabled=True,audio_out_enabled=True,audio_out_sample_rate=24000,serializer=BrowserSerializer(),add_wav_header=False,session_timeout=280))
    pipeline=Pipeline([transport.input(),BargeIn(),SharedWhisper(runtime,session['language']),ArchiveGuide(runtime,session['language']),IndicNarrator(runtime,session['language'],session['style'],session.get('gender','auto')),transport.output()])
    task=PipelineWorker(pipeline,enable_rtvi=False,params=PipelineParams(audio_in_sample_rate=16000,audio_out_sample_rate=24000))
    @transport.event_handler('on_client_disconnected')
    async def disconnected(transport,websocket): await task.cancel()
    @transport.event_handler('on_client_connected')
    async def connected(transport,websocket):await ws.send_json({'type':'ready'})
    runner=WorkerRunner(handle_sigint=False)
    await runner.add_workers(task)
    await runner.run()
