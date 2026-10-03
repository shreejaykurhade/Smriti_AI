"""Prototype-only online narration and ungated translation. Production adapters remain available."""
import asyncio
import io
import json
from pathlib import Path
import soundfile as sf

EDGE_VOICES=json.loads(Path(__file__).with_name('edge_voices.json').read_text())
EDGE_LANGUAGES={voice['locale'].split('-')[0] for voice in EDGE_VOICES}-{'si'}
NLLB_CODES={'en':'eng_Latn','as':'asm_Beng','bn':'ben_Beng','gu':'guj_Gujr','hi':'hin_Deva','kn':'kan_Knda','ks':'kas_Arab','mai':'mai_Deva','mni':'mni_Beng','ml':'mal_Mlym','mr':'mar_Deva','ne':'npi_Deva','or':'ory_Orya','pa':'pan_Guru','sa':'san_Deva','sd':'snd_Arab','ta':'tam_Taml','te':'tel_Telu','ur':'urd_Arab'}

async def edge_audio(text,language,style,gender='female',voice_id=None):
    import edge_tts
    if language not in EDGE_LANGUAGES:raise ValueError('A neural prototype voice is unavailable for this language. Text answers remain available.')
    voices=[v for v in EDGE_VOICES if v['locale'].split('-')[0]==language and v['gender'].lower()==gender]
    if not voices:raise ValueError('Voice not available.')
    voices.sort(key=lambda v:not v['locale'].endswith('-IN'))
    preferred=next((v for v in voices if v['name']==voice_id or (voice_id is None and v['name']=='en-IN-NeerjaExpressiveNeural')),voices[0])
    rate={'museum':'-10%','conversation':'+0%','calm':'-14%'}[style]
    data=bytearray()
    async for chunk in edge_tts.Communicate(text,preferred['name'],rate=rate).stream():
        if chunk['type']=='audio':data.extend(chunk['data'])
    if not data:raise RuntimeError('The online voice service returned no audio.')
    samples,sample_rate=sf.read(io.BytesIO(data),dtype='float32')
    wav=io.BytesIO();sf.write(wav,samples,sample_rate,format='WAV',subtype='PCM_16')
    return wav.getvalue()

def nllb_translate(models,texts,source,target):
    if source not in NLLB_CODES or target not in NLLB_CODES:raise ValueError('This prototype translation model does not support the selected language. Try English, Hindi or Marathi.')
    import torch
    from transformers import AutoTokenizer,AutoModelForSeq2SeqLM
    if 'nllb' not in models.loaded:
        path=models.path('nllb')
        models.loaded['nllb']=(AutoModelForSeq2SeqLM.from_pretrained(path,local_files_only=True).to(models.device).eval(),AutoTokenizer.from_pretrained(path,local_files_only=True))
    model,tokenizer=models.loaded['nllb'];tokenizer.src_lang=NLLB_CODES[source]
    results=[]
    for text in texts:
        chunks=models.chunks(text,1000)
        inputs=tokenizer(chunks,return_tensors='pt',padding=True,truncation=False).to(models.device)
        if inputs.input_ids.shape[1]>512:raise ValueError('Translation passage is too long.')
        with torch.inference_mode():tokens=model.generate(**inputs,forced_bos_token_id=tokenizer.convert_tokens_to_ids(NLLB_CODES[target]),max_new_tokens=256,num_beams=4,no_repeat_ngram_size=4)
        if any(tokenizer.eos_token_id not in row[2:].tolist() for row in tokens):
            with torch.inference_mode():tokens=model.generate(**inputs,forced_bos_token_id=tokenizer.convert_tokens_to_ids(NLLB_CODES[target]),max_new_tokens=512,num_beams=4,no_repeat_ngram_size=4)
            if any(tokenizer.eos_token_id not in row[2:].tolist() for row in tokens):raise RuntimeError('Translation did not complete. Use shorter sentences.')
        results.append(' '.join(tokenizer.batch_decode(tokens,skip_special_tokens=True)))
    return results
