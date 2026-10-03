"""Curated guide answers with verified primary-edition links. No invented quotations."""
import json
import re
from pathlib import Path
from functools import lru_cache

ROOT=Path(__file__).parent
RECORDS=json.loads((ROOT/'records.json').read_text())
TOPICS=json.loads((ROOT/'guide-topics.json').read_text())
PACKS=ROOT/'guide-locales.json'
GUIDE_LOCALES=json.loads(PACKS.read_text()) if PACKS.exists() else {}

def normalize(text):return re.sub(r'[\s?？।.!]+',' ',text.casefold()).strip()

def topic_for(question,language):
    value=normalize(question)
    # Exact prepared question labels are reviewed/generated in advance. This fast
    # path never treats an arbitrary recording as an unrelated canned question.
    for topic in TOPICS:
        native=GUIDE_LOCALES.get(language,{}).get(topic['id'],{}).get('question','')
        if value in {normalize(topic['question']),normalize(native)}-{''}:return topic
    # A small, explicit native topic vocabulary handles common Whisper spacing
    # errors without another model pass. This selects a labelled curated topic;
    # it never invents a detailed response to an arbitrary historical claim.
    native_democracy={
        'bn':['গণতন্ত্র','গনতন্ত্র'], 'gu':['લોકશાહી','લોક્શાહી'],
        'hi':['लोकतंत्र','लोकतन्त्र','लोगतंत्र'], 'kn':['ಪ್ರಜಾಪ್ರಭುತ್ವ','ಪ್ರಜಾಪ್ರಬುತ್ವ'],
        'ml':['ജനാധിപ'], 'mr':['लोकशाही','लोक्षाही','लोक्षाहि'],
        'ne':['लोकतंत्र','लोकतन्त्र'], 'pa':['ਲੋਕਤੰਤਰ','ਲੋਕਤਂਤਰ','ਲੋਕਤਨਤਰ'],
        'ta':['ஜனநாயக','ஜனனாயக'], 'te':['ప్రజాస్వామ'], 'ur':['جمہوریت'],
    }
    compact=re.sub(r'\s+','',value)
    if any(term in compact for term in native_democracy.get(language,[])):
        return next(topic for topic in TOPICS if topic['id']=='democracy')
    tokens=set(re.findall(r'[a-z]+',value))
    scored=[]
    for topic in TOPICS:
        score=sum(3 if ' ' in key else 1 for key in topic['keywords'] if (key in value if ' ' in key else key in tokens))
        if score:scored.append((score,topic))
    return max(scored,key=lambda entry:entry[0])[1] if scored else None

@lru_cache(maxsize=1024)
def translated_answer(text,language,translator):
    return translator([text],'en',language)[0]

def citation(record,number):
    fields=['id','title','source','sourceUrl','pdfUrl','pdfPage','excerptPage','pageLabel','sourceHost','verifiedAt','sourceKind']
    return {'number':number,**{key:record[key] for key in fields if key in record}}

def answer_question(question,language='en',question_language='en',translator=None):
    if not isinstance(question,str) or not question.strip() or len(question)>1200:
        raise ValueError('Please enter a question of up to 1,200 characters.')
    normalized=question.strip();topic=topic_for(normalized,question_language)
    if question_language!='en' and not topic:
        if translator is None:raise RuntimeError('Regional-language research needs the connected translation service.')
        normalized=translator([normalized],question_language,'en')[0];topic=topic_for(normalized,'en')
    if topic:
        ids=topic['records'];text=topic['answer'];packet=GUIDE_LOCALES.get(language,{}).get(topic['id'],{})
    else:
        matches=[r for r in RECORDS if normalize(r['title']) in normalize(normalized)]
        ids=[r['id'] for r in matches[:3]];packet={}
        text=' '.join(r['summary'] for r in matches[:3]) if matches else 'I do not have enough evidence in this curated archive to answer that. You can ask about caste, democracy, constitutional safeguards, economics, women’s rights or Buddhism, or open an original source to read further.'
    if language!='en':
        if packet.get('answer'):text=packet['answer']
        elif translator is not None:text=translated_answer(text,language,translator)
        else:raise RuntimeError('Translation is unavailable. Select English or connect the translation service.')
    selected=[r for rid in ids for r in RECORDS if r['id']==rid]
    return dict(answer=text,citations=[citation(r,i+1) for i,r in enumerate(selected)],mode='curated-source-guide',language=language,evidence_scope='curated summaries linked to verified primary editions',spoken_text=re.sub(r'\[\d+\]','',text),topic=topic['id'] if topic else None,prepared_translation=bool(language!='en' and packet.get('answer')))
