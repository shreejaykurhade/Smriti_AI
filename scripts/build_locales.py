"""Generate versioned, offline UI catalogues from the installed prototype model.
Machine translations are editable JSON, separate from authentic archival quotations.
"""
import argparse,json,time,os
from pathlib import Path
os.environ.setdefault('TOKENIZERS_PARALLELISM','false')
os.environ.setdefault('HF_HOME',str(Path(__file__).resolve().parents[1]/'models/.hf'))
import torch
from transformers import AutoTokenizer,AutoModelForSeq2SeqLM
from speech_service.prototype import NLLB_CODES
root=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser();parser.add_argument('languages',nargs='+');args=parser.parse_args()
torch.set_num_threads(4)
model=AutoModelForSeq2SeqLM.from_pretrained(root/'models/nllb',local_files_only=True).eval()
tokenizer=AutoTokenizer.from_pretrained(root/'models/nllb',local_files_only=True,src_lang='eng_Latn')
texts=json.loads((root/'components/i18n/catalog.json').read_text())
for language in args.languages:
    output=root/f'public/locales/{language}.json'
    checkpoint=root/f'.locale-progress-{language}.json'
    cached=checkpoint if checkpoint.exists() else output
    messages=json.loads(cached.read_text()) if cached.exists() else {}
    pending=sorted([text for text in texts if text not in messages],key=len)
    start=time.time()
    for offset in range(0,len(pending),8):
        batch=pending[offset:offset+8]
        inputs=tokenizer(batch,return_tensors='pt',padding=True,truncation=False)
        with torch.inference_mode():
            tokens=model.generate(**inputs,forced_bos_token_id=tokenizer.convert_tokens_to_ids(NLLB_CODES[language]),max_new_tokens=256,num_beams=2,no_repeat_ngram_size=4)
        for source,row,result in zip(batch,tokens,tokenizer.batch_decode(tokens,skip_special_tokens=True)):
            if tokenizer.eos_token_id not in row[2:].tolist():
                one=tokenizer([source],return_tensors='pt')
                with torch.inference_mode():row=model.generate(**one,forced_bos_token_id=tokenizer.convert_tokens_to_ids(NLLB_CODES[language]),max_new_tokens=512,num_beams=4,no_repeat_ngram_size=4)[0]
                if tokenizer.eos_token_id not in row[2:].tolist():raise RuntimeError(f'Incomplete translation: {source}')
                result=tokenizer.decode(row,skip_special_tokens=True)
            messages[source]=result
        checkpoint=root/f'.locale-progress-{language}.json'
        checkpoint.write_text(json.dumps(messages,ensure_ascii=False,indent=2)+'\n')
        if offset%40==0:print(f'{language}: {min(offset+8,len(pending))}/{len(pending)} · {time.time()-start:.0f}s',flush=True)
    output.write_text(json.dumps(messages,ensure_ascii=False,indent=2)+'\n')
    (root/f'.locale-progress-{language}.json').unlink(missing_ok=True)
    print(f'{language}: complete',flush=True)
