#!/usr/bin/env python3
"""Launch the website, archive API and model host together with consistent local URLs."""
import argparse
import os
import signal
import subprocess
import sys
from pathlib import Path
from dotenv import load_dotenv

root=Path(__file__).resolve().parents[1];os.chdir(root)
parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,default=3000);parser.add_argument('--voice-port',type=int,default=8000);parser.add_argument('--archive-port',type=int,default=5001);args=parser.parse_args()
load_dotenv(root/'.env.local')
if not os.getenv('VOICE_API_KEY'):
    import secrets
    os.environ['VOICE_API_KEY']=secrets.token_urlsafe(32)
env=os.environ.copy();env.update(VOICE_BACKEND_URL=f'http://127.0.0.1:{args.voice_port}',PUBLIC_VOICE_URL=f'http://127.0.0.1:{args.voice_port}',LOCAL_ARCHIVE_URL=f'http://127.0.0.1:{args.archive_port}',VOICE_ALLOWED_ORIGINS=f'http://localhost:{args.port},http://127.0.0.1:{args.port}')
env.setdefault('SMRITI_BUILD_DIR','.next-preview');env.setdefault('TOKENIZERS_PARALLELISM','false');env.setdefault('SMRITI_TTS_PROVIDER','hybrid');env.setdefault('SMRITI_TRANSLATION_PROVIDER','nllb');env['SMRITI_REMOTE_PARLER']='0';env.setdefault('HF_HOME',str(root/'models'/'.hf'))
commands=[
    [sys.executable,'-m','uvicorn','speech_service.app:app','--host','127.0.0.1','--port',str(args.voice_port),'--ws-max-size','100000','--no-access-log'],
    [sys.executable,'-c',f"from api.index import app;app.run(host='127.0.0.1',port={args.archive_port})"],
    ['npm','run','start','--','--hostname','127.0.0.1','--port',str(args.port)],
]
processes=[]
if (root/'tests/fixtures/voice-preview-manifest.json').exists():
    subprocess.run([sys.executable,'scripts/prewarm_voice_cache.py'],env=env,check=True)
try:
    for command in commands:processes.append(subprocess.Popen(command,env=env))
    print(f'Open http://localhost:{args.port} and choose Ask SMRITI. Press Ctrl+C to stop all three services.',flush=True)
    import time
    stop_file=root/f'.preview-stop-{args.port}'
    stop_file.unlink(missing_ok=True)
    while all(process.poll() is None for process in processes):
        if stop_file.exists():stop_file.unlink();break
        time.sleep(.3)
except KeyboardInterrupt:pass
finally:
    for process in processes:
        if process.poll() is None:process.terminate()
