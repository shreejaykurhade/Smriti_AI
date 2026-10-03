"""Build portable museum-guide packets. Runtime still translates novel questions."""
import os,json,time
from pathlib import Path
import torch
from transformers import AutoTokenizer,AutoModelForSeq2SeqLM
from speech_service.prototype import NLLB_CODES
root=Path(__file__).resolve().parents[1]
os.environ.setdefault('TOKENIZERS_PARALLELISM','false');torch.set_num_threads(4)
model=AutoModelForSeq2SeqLM.from_pretrained(root/'models/nllb',local_files_only=True).eval()
tokenizer=AutoTokenizer.from_pretrained(root/'models/nllb',local_files_only=True,src_lang='eng_Latn')
topics=json.loads((root/'smriti_core/guide-topics.json').read_text());dest=root/'smriti_core/guide-locales.json';data=json.loads(dest.read_text()) if dest.exists() else {}
for lang in ['as','bn','gu','hi','kn','ml','mr','ne','pa','ta','te','ur']:
 start=time.time();data.setdefault(lang,{})
 for topic in topics:
  if topic['id'] in data[lang]:continue
  original=[topic['question'],topic['answer']];inputs=tokenizer(original,return_tensors='pt',padding=True)
  with torch.inference_mode():tokens=model.generate(**inputs,forced_bos_token_id=tokenizer.convert_tokens_to_ids(NLLB_CODES[lang]),max_new_tokens=512,num_beams=2,no_repeat_ngram_size=4)
  assert all(tokenizer.eos_token_id in row[2:].tolist() for row in tokens),f'Incomplete {lang}/{topic["id"]}'
  q,a=tokenizer.batch_decode(tokens,skip_special_tokens=True);data[lang][topic['id']]={'question':q,'answer':a}
  dest.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
 print(lang,'prepared',round(time.time()-start,1),'seconds',flush=True)
