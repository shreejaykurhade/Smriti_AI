#!/usr/bin/env python3
"""Cache verified welcome previews, never invent answers or relabel another speaker."""
import hashlib,json,os,sys
from pathlib import Path
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
from speech_service.models import Models
from speech_service.voices import select_voice
models=Models();cache=Path(os.getenv('SMRITI_AUDIO_CACHE',str(root/'.audio-cache')));cache.mkdir(exist_ok=True,parents=True)
manifest=json.loads((root/'tests/fixtures/voice-preview-manifest.json').read_text())
count=0
for item in manifest:
    language=item['language'];path=root/'tests/fixtures'/item['file']
    if not path.exists() or hashlib.sha256(path.read_bytes()).hexdigest()!=item['sha256']:continue
    try:voice=select_voice(models,language,item['gender'])
    except ValueError:continue
    if voice['id']!=item['voice_id']:continue
    # Old samples use a different pacing preset and must not be relabeled.
    if item.get('preset_version')!='calm-guide-v2':continue
    text=item['text']
    key=hashlib.sha256(f"v5|{voice['id']}|{language}|museum|{item['gender']}|{text}".encode()).hexdigest()
    (cache/f'{key}.wav').write_bytes(path.read_bytes());count+=1
print(f'Prepared {count} genuine welcome previews. Other passages are synthesized on demand.')
