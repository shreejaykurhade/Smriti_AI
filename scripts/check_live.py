"""Real-model WebSocket smoke test. Uses generated demo audio, never your microphone."""
import asyncio
import base64
import io
import json
import urllib.request
from pathlib import Path
import numpy as np
import soundfile as sf
from scipy.signal import resample_poly
import websockets

async def main():
    req=urllib.request.Request('http://127.0.0.1:3003/api/voice/session',data=json.dumps({'kind':'transcribe','language':'en','gender':'male'}).encode(),headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(req) as r:session=json.load(r)
    samples,rate=sf.read('tests/fixtures/neural-en.wav',dtype='float32')
    from math import gcd
    divisor=gcd(rate,16000);samples=resample_poly(samples,16000//divisor,rate//divisor)
    pcm=(np.clip(samples,-1,1)*32767).astype('<i2').tobytes()
    async with websockets.connect(session['url'],origin='http://localhost:3003') as ws:
        await ws.send(json.dumps({'token':session['token']}))
        assert json.loads(await asyncio.wait_for(ws.recv(),10))['type']=='ready'
        await ws.send(json.dumps({'type':'start'}))
        for i in range(0,len(pcm),2560):await ws.send(json.dumps({'type':'audio','audio':base64.b64encode(pcm[i:i+2560]).decode()}))
        await ws.send(json.dumps({'type':'end'}))
        types=set()
        for _ in range(200):
            message=json.loads(await asyncio.wait_for(ws.recv(),90));types.add(message['type'])
            if message['type']=='transcript':print('Whisper:',message['text'],flush=True)
            if message['type']=='answer':print('Evidence:',[c['id'] for c in message['citations']],flush=True)
            if message['type']=='error':raise RuntimeError(message['message'])
            if message['type']=='audio':break
        assert {'transcript','answer','audio'}<=types
        print('Real Whisper → catalogue answer → neural speech via Pipecat passed.',flush=True)
asyncio.run(main())
