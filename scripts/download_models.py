#!/usr/bin/env python3
"""Download once, with resolved revisions recorded. No model download during public requests."""
import argparse
import json
import os
from pathlib import Path

parser=argparse.ArgumentParser()
parser.add_argument('--only',choices=['all','whisper','translation','tts','prototype'],default='all')
parser.add_argument('--whisper',choices=['tiny','small','medium','large-v3','large-v3-turbo'],default='small')
args=parser.parse_args()
root=Path(os.getenv('SMRITI_MODEL_DIR','./models')).resolve();root.mkdir(parents=True,exist_ok=True)
os.environ.setdefault('HF_HOME',str(root/'.hf'))
from huggingface_hub import HfApi,snapshot_download
from transformers import AutoTokenizer
models={}
if args.only=='prototype':models['nllb']='facebook/nllb-200-distilled-600M'
if args.only in ('all','whisper'):models['whisper-turbo' if args.whisper=='large-v3-turbo' else 'whisper']='mobiuslabsgmbh/faster-whisper-large-v3-turbo' if args.whisper=='large-v3-turbo' else f'Systran/faster-whisper-{args.whisper}'
if args.only in ('all','translation'):models.update(en_indic='ai4bharat/indictrans2-en-indic-dist-200M',indic_en='ai4bharat/indictrans2-indic-en-dist-200M')
if args.only in ('all','tts'):models['tts']='ai4bharat/indic-parler-tts'
manifest_path=root/'revisions.json';manifest=json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
failed=[]
for name,repo in models.items():
    try:
        revision=HfApi().model_info(repo).sha
        snapshot_download(repo,revision=revision,local_dir=root/name,ignore_patterns=['*.msgpack','*.h5','*.ot'])
        if name=='tts':
            config=json.loads((root/name/'config.json').read_text())
            desc=config['text_encoder']['_name_or_path']
            desc_revision=HfApi().model_info(desc).sha
            AutoTokenizer.from_pretrained(desc,revision=desc_revision).save_pretrained(root/'description_tokenizer')
            manifest['description_tokenizer']={'repo':desc,'revision':desc_revision}
        manifest[name]={'repo':repo,'revision':revision}
        manifest_path.write_text(json.dumps(manifest,indent=2));print(f'Installed {name} at {revision}')
    except Exception as error:
        failed.append(name)
        print(f'Could not install {name}: {type(error).__name__}. For gated AI4Bharat models, accept model access on Hugging Face and run hf auth login locally. Do not paste tokens into chat.')
if failed:raise SystemExit(1)
