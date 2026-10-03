"""Only advertise installed voices. Gender describes a speaker, never a pitch effect."""
import os
from .prototype import EDGE_LANGUAGES, EDGE_VOICES
from .languages import TTS_LANGUAGES

MMS_REPOS = {'as':'facebook/mms-tts-asm','mai':'facebook/mms-tts-mai','or':'facebook/mms-tts-ory','pa':'facebook/mms-tts-pan'}

def installed(path):
    return (path/'config.json').exists() and (any(path.glob('*.safetensors')) or any(path.glob('*.bin')))

def voice_catalog(models):
    catalog={}
    if models.tts_provider in ('edge','hybrid'):
        for language in sorted(EDGE_LANGUAGES):
            candidates=[v for v in EDGE_VOICES if v['locale'].split('-')[0]==language]
            candidates.sort(key=lambda v:(not v['locale'].endswith('-IN'),v['name']!='en-IN-NeerjaExpressiveNeural'))
            options=[]
            for gender in ('female','male'):
                voice=next((v for v in candidates if v['gender'].lower()==gender),None)
                if voice:options.append({'id':voice['name'],'gender':gender,'name':voice['name'].split('-')[-1].replace('Neural',''),'provider':'edge','online':True})
            catalog[language]=options
    if models.tts_provider=='hybrid':
        for language,repo in MMS_REPOS.items():
            if installed(models.root/'mms'/language):
                catalog.setdefault(language,[{'id':repo,'gender':'original','name':'Original speaker','provider':'mms','online':False}])
    if models.tts_provider in ('indic-parler','hybrid') and installed(models.root/'tts') and (models.root/'description_tokenizer'/'tokenizer_config.json').exists():
        for language in TTS_LANGUAGES:
            catalog.setdefault(language,[{'id':f'parler-{gender}','gender':gender,'name':gender.title(),'provider':'indic-parler','online':False} for gender in ('female','male')])
    if models.tts_provider=='hybrid' and os.getenv('SMRITI_REMOTE_PARLER','0')=='1':
        from .remote_parler import LANGUAGES
        for language in LANGUAGES:
            options=catalog.setdefault(language,[])
            if not any(v['provider']=='indic-parler' for v in options):
                options.extend({'id':f'remote-parler-{gender}','gender':gender,'name':gender.title(),'provider':'parler-demo','online':True,'experimental':language in ('ks','pa')} for gender in ('female','male'))
    return catalog

def select_voice(models,language,gender='auto'):
    options=voice_catalog(models).get(language,[])
    if not options:raise ValueError('No installed voice for this language. You can still read the translated answer.')
    if gender=='auto':return options[0]
    voice=next((option for option in options if option['gender']==gender),None)
    if not voice:raise ValueError('This speaker type is not available in the selected language. Choose the original speaker.')
    return voice
