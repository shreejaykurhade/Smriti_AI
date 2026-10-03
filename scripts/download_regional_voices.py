#!/usr/bin/env python3
"""Install verified ungated MMS checkpoints with pinned revisions."""
import json,os,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
root=Path(os.getenv('SMRITI_MODEL_DIR','./models')).resolve();root.mkdir(parents=True,exist_ok=True)
os.environ.setdefault('HF_HOME',str(root/'.hf'))
from huggingface_hub import HfApi,snapshot_download
from speech_service.voices import MMS_REPOS
manifest_file=root/'revisions.json';manifest=json.loads(manifest_file.read_text()) if manifest_file.exists() else {}
for code,repo in MMS_REPOS.items():
    revision=HfApi().model_info(repo).sha
    snapshot_download(repo,revision=revision,local_dir=root/'mms'/code,allow_patterns=['*.json','*.safetensors','README.md'])
    manifest['mms-'+code]={'repo':repo,'revision':revision}
    manifest_file.write_text(json.dumps(manifest,indent=2))
    print(f'Installed {code}: {repo} at {revision}',flush=True)
