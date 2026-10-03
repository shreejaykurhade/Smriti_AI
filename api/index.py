"""Lightweight Vercel archive API. GPU models live in speech_service, never here."""
import json
import os
import time
import urllib.request
import urllib.error
from functools import lru_cache
from flask import Flask, jsonify, request
from smriti_core.research import RECORDS
from smriti_core.answer_service import museum_answer, configured as answers_configured

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 60000
LANGUAGES = {'as':'Assamese','bn':'Bengali','brx':'Bodo','doi':'Dogri','gu':'Gujarati','hi':'Hindi','kn':'Kannada','ks':'Kashmiri','kok':'Konkani','mai':'Maithili','ml':'Malayalam','mni':'Manipuri','mr':'Marathi','ne':'Nepali','or':'Odia','pa':'Punjabi','sa':'Sanskrit','sat':'Santali','sd':'Sindhi','ta':'Tamil','te':'Telugu','ur':'Urdu','en':'English'}

def voice_request(path,payload=None):
    base=os.getenv('VOICE_BACKEND_URL','').rstrip('/')
    key=os.getenv('VOICE_API_KEY','')
    if not base or not key: raise RuntimeError('Regional-language translation needs the connected IndicTrans2 service. English research remains available.')
    if os.getenv('VERCEL') and not base.startswith('https://'): raise RuntimeError('The voice backend must use HTTPS.')
    req=urllib.request.Request(base+'/'+path,data=json.dumps(payload).encode() if payload is not None else None,headers={'Content-Type':'application/json','x-smriti-key':key})
    try:
        with urllib.request.urlopen(req,timeout=8) as response: return json.load(response)
    except (urllib.error.URLError,TimeoutError): raise RuntimeError('The translation service is temporarily unavailable.')

@lru_cache(maxsize=1024)
def translate_cached(texts,source,target):
    if source==target:return texts
    job=voice_request('jobs',{'kind':'translate','texts':list(texts),'source_language':source,'language':target})
    deadline=time.monotonic()+20
    while time.monotonic()<deadline:
        state=voice_request('jobs/'+job['id'])
        if state['state']=='done':return tuple(state['result']['translations'])
        if state['state']=='error':raise RuntimeError(state['error'])
        time.sleep(.5)
    raise RuntimeError('Translation is warming up. Try again shortly.')

def translator(texts,source,target):return list(translate_cached(tuple(texts),source,target))

@app.get('/api/health')
def health():
    configured=bool(os.getenv('VOICE_BACKEND_URL') and os.getenv('VOICE_API_KEY'))
    return jsonify(status='ok',service='SMRITI AI archive',voice_configured=configured,voice_mode='model-host' if configured else 'serverless',answer_configured=answers_configured(),release='vercel-answers-v27')
@app.get('/api/records')
def records():
    query=request.args.get('q','').lower().strip()
    found=RECORDS if not query else [r for r in RECORDS if query in (r['title']+r['summary']+' '.join(r['themes'])).lower()]
    return jsonify(records=found,total=len(found))
@app.get('/api/records/<record_id>')
def record(record_id):
    item=next((r for r in RECORDS if r['id']==record_id),None)
    return (jsonify(item),200) if item else (jsonify(error='Record not found'),404)
@app.post('/api/translate')
def translate():
    p=request.get_json(silent=True) or {}
    lang=p.get('language','en');texts=p.get('texts',[])
    if lang not in LANGUAGES or not isinstance(texts,list) or len(texts)>40 or any(not isinstance(t,str) or len(t)>1800 for t in texts) or sum(map(len,texts))>15000:
        return jsonify(error='Invalid translation request'),400
    try:return jsonify(language=lang,translations=translator(texts,'en',lang))
    except RuntimeError as e:return jsonify(error=str(e)),503
@app.post('/api/ask')
def ask():
    p=request.get_json(silent=True) or {}
    if not isinstance(p,dict):return jsonify(error='Invalid question request'),400
    language=p.get('language','en');source=p.get('question_language','en')
    if not isinstance(language,str) or not isinstance(source,str):return jsonify(error='Invalid language'),400
    if language not in LANGUAGES or source not in LANGUAGES:return jsonify(error='Invalid language'),400
    try:
        connected=bool(os.getenv('VOICE_BACKEND_URL') and os.getenv('VOICE_API_KEY'))
        result=museum_answer(p.get('question',''),language,source,translator if connected else None)
        response=jsonify(**result,language_name=LANGUAGES[language])
        response.headers['Cache-Control']='no-store'
        return response
    except ValueError as e:return jsonify(error=str(e)),400
    except RuntimeError as e:return jsonify(error=str(e)),503
