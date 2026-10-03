"""Generate genuine sentence previews at the current pacing; no canned research replies."""
import hashlib,json,os,sys,wave,io
from pathlib import Path
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
os.environ.setdefault('SMRITI_TTS_PROVIDER','hybrid');os.environ.setdefault('SMRITI_TRANSLATION_PROVIDER','nllb');os.environ['SMRITI_REMOTE_PARLER']='0'
from speech_service.models import Models
from speech_service.voices import voice_catalog
models=Models();catalog=voice_catalog(models);cache=root/'.audio-cache';cache.mkdir(exist_ok=True)
phrase='Welcome to SMRITI AI. Let us explore Dr. B. R. Ambedkar’s ideas together.'
manifest=[]
for lang in ['en','bn','gu','hi','kn','ml','mr','ne','pa','ta','te','ur']:
 pack=json.loads((root/f'public/locales/{lang}.json').read_text()) if lang!='en' else {}
 text=pack.get(phrase,phrase)
 for speaker in catalog.get(lang,[]):
  if speaker['provider']=='parler-demo' or speaker.get('experimental'):continue
  for index,passage in enumerate(models.chunks(text,260)):
   key=hashlib.sha256(f"v5|{speaker['id']}|{lang}|museum|{speaker['gender']}|{passage}".encode()).hexdigest();cached=cache/f'{key}.wav'
   audio=cached.read_bytes() if cached.exists() else models.synthesize(passage,lang,'museum',speaker['gender'])
   with wave.open(io.BytesIO(audio)) as wav:assert wav.getnframes()>wav.getframerate()*.15
   filename=f"preview-v2-{lang}-{speaker['gender']}-{index}.wav";(root/'tests/fixtures'/filename).write_bytes(audio);cached.write_bytes(audio)
   manifest.append(dict(file=filename,language=lang,gender=speaker['gender'],voice_id=speaker['id'],text=passage,sha256=hashlib.sha256(audio).hexdigest(),preset_version='calm-guide-v2'))
 (root/'tests/fixtures/voice-preview-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
 print(lang,'ready',len(manifest),'genuine sentence previews',flush=True)
