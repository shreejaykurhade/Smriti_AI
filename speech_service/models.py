"""Lazy, shared model instances. All inference runs inside a single bounded job worker."""
import io
import os
import re
from pathlib import Path
import numpy as np
from .languages import FLORES, TTS_LANGUAGES, WHISPER_LANGUAGES, STYLES

MODEL_IDS = {'tts':'ai4bharat/indic-parler-tts', 'en_indic':'ai4bharat/indictrans2-en-indic-dist-200M', 'indic_en':'ai4bharat/indictrans2-indic-en-dist-200M'}

class Models:
    def __init__(self):
        self.root = Path(os.getenv('SMRITI_MODEL_DIR', './models')).resolve()
        self.loaded = {}
        self.tts_provider=os.getenv('SMRITI_TTS_PROVIDER','indic-parler')
        self.translation_provider=os.getenv('SMRITI_TRANSLATION_PROVIDER','indictrans2')
        import torch
        torch.set_num_threads(int(os.getenv('SMRITI_CPU_THREADS','4')))
        self.device = os.getenv('SMRITI_DEVICE','cpu')  # CPU by default; set cuda on an NVIDIA host.

    def path(self, name):
        path = self.root / name
        if not (path / 'config.json').exists() or not any(path.glob('*.safetensors')) and not any(path.glob('*.bin')):
            raise RuntimeError(f'{name} model is not installed. Run scripts/download_models.py after Hugging Face login.')
        return str(path)

    def capabilities(self):
        from .prototype import NLLB_CODES
        from .voices import voice_catalog,installed
        voices=voice_catalog(self)
        translation_ready=installed(self.root/'nllb') if self.translation_provider=='nllb' else all(installed(self.root/n) for n in ('en_indic','indic_en'))
        return {
            'tts':bool(voices),'stt':((self.root/'whisper-turbo'/'model.bin').exists() or (self.root/'whisper'/'model.bin').exists()),'translation':translation_ready,
            'tts_languages':sorted(voices),'voices':voices,
            'stt_languages':sorted(WHISPER_LANGUAGES),'translation_languages':sorted(NLLB_CODES if self.translation_provider=='nllb' else FLORES) if translation_ready else [],
            'styles':list(STYLES),'loaded':list(self.loaded),'device':self.device,
            'tts_provider':self.tts_provider,'translation_provider':self.translation_provider,
            'voice_label':'Museum narration','online_voice':any(v['online'] for options in voices.values() for v in options),
        }

    def transcribe(self, audio, language):
        if language not in WHISPER_LANGUAGES:
            raise ValueError('Whisper does not support this selected language. Please type your question.')
        # Short Tamil questions decoded in the wrong script with turbo in our
        # real-audio check; the small multilingual checkpoint performed better.
        name='whisper' if language=='ta' and (self.root/'whisper'/'model.bin').exists() else ('whisper-turbo' if (self.root/'whisper-turbo'/'model.bin').exists() else 'whisper')
        cache_key='stt:'+name
        if cache_key not in self.loaded:
            from faster_whisper import WhisperModel
            path=self.root/name
            if not (path/'model.bin').exists():
                raise RuntimeError('Whisper is not installed. Run scripts/download_models.py --only whisper.')
            self.loaded[cache_key]=WhisperModel(str(path),device=self.device,compute_type='float16' if self.device=='cuda' else 'int8',local_files_only=True)
        # English vocabulary prompts leaked into regional transcripts. Let the
        # selected language and the visitor’s actual audio guide recognition.
        segments,_=self.loaded[cache_key].transcribe(io.BytesIO(audio),language=language,beam_size=5,vad_filter=True,condition_on_previous_text=False)
        text = ' '.join(segment.text.strip() for segment in segments).strip()
        if not text:
            raise ValueError('No speech was detected. Please speak closer to the microphone.')
        return text

    def translate(self, texts, source, target):
        if source not in FLORES or target not in FLORES:
            raise ValueError('Unsupported translation language.')
        if source == target:
            return list(texts)
        if self.translation_provider=='nllb':
            from .prototype import nllb_translate
            return nllb_translate(self,texts,source,target)
        if source != 'en' and target != 'en':
            return self.translate(self.translate(texts,source,'en'),'en',target)
        import torch
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
        from IndicTransToolkit import IndicProcessor
        name = 'en_indic' if source=='en' else 'indic_en'
        if name not in self.loaded:
            path = self.path(name)
            self.loaded[name] = (AutoModelForSeq2SeqLM.from_pretrained(path,trust_remote_code=True,local_files_only=True,attn_implementation='eager').to(self.device).eval(), AutoTokenizer.from_pretrained(path,trust_remote_code=True,local_files_only=True), IndicProcessor(inference=True))
        model,tokenizer,processor = self.loaded[name]
        result = []
        for text in texts:
            parts = self.chunks(text, 350)
            batch = processor.preprocess_batch(parts,src_lang=FLORES[source],tgt_lang=FLORES[target])
            inputs = tokenizer(batch,return_tensors='pt',padding=True,truncation=False).to(self.device)
            if inputs.input_ids.shape[1] > 256:
                raise ValueError('A translation segment exceeds the model limit. Please use shorter sentences.')
            with torch.inference_mode():
                tokens = model.generate(**inputs,max_new_tokens=256,num_beams=5)
            outputs = tokenizer.batch_decode(tokens,skip_special_tokens=True)
            result.append(' '.join(processor.postprocess_batch(outputs,lang=FLORES[target])))
        return result

    @staticmethod
    def chunks(text, limit=230):
        text = re.sub(r'\[\d+\]', '', text).strip()
        protected=re.sub(r'\b(?:Dr|Mr|Mrs|Ms|Prof|Sr|Jr)\.',lambda m:m.group().replace('.', '\ue000'),text,flags=re.I)
        protected=re.sub(r'(?:डॉ|डा|ഡോ|ডা|ડૉ|ಡಾ|డా|ਡਾ|டா)\.',lambda m:m.group().replace('.', '\ue000'),protected)
        protected=re.sub(r'(?:बी|आर|পি|আর|பி|ஆர்|બી|આર|ಬಿ|ಆರ್|ബി|ആർ|బి|ఆర్|ਬੀ|ਆਰ|বি|আর)\.',lambda m:m.group().replace('.', '\ue000'),protected)
        protected=re.sub(r'\b[A-Z]\.(?=\s*[A-Z])',lambda m:m.group().replace('.', '\ue000'),protected)
        sentences = [part.replace('\ue000','.') for part in re.split(r'(?<=[.!?।؟])\s+|\n+',protected)]
        result=[]
        for sentence in sentences:
            if not sentence.strip(): continue
            while len(sentence)>limit:
                cut=sentence.rfind(' ',0,limit)
                if cut<1: raise ValueError('A text segment is too long; add spaces or punctuation.')
                result.append(sentence[:cut]); sentence=sentence[cut:].strip()
            result.append(sentence)
        if not result: raise ValueError('No text to narrate.')
        return result

    def synthesize(self, text, language, style='museum', gender='auto'):
        from .voices import select_voice
        voice=select_voice(self,language,gender)
        if style not in STYLES: raise ValueError('Unknown narrator style.')
        if voice['provider']=='edge':
            import asyncio
            from .prototype import edge_audio
            return asyncio.run(edge_audio(text,language,style,voice['gender'],voice['id']))
        if voice['provider']=='mms':return self.mms_audio(text,language,style)
        if voice['provider']=='parler-demo':
            from .remote_parler import remote_audio
            return remote_audio(self,text,language,voice['gender'],style)
        import torch
        import soundfile as sf
        from parler_tts import ParlerTTSForConditionalGeneration
        from transformers import AutoTokenizer
        if 'tts' not in self.loaded:
            path=self.path('tts')
            model=ParlerTTSForConditionalGeneration.from_pretrained(path,local_files_only=True).to(self.device).eval()
            # Description encoder tokenizer is downloaded explicitly, not silently at request time.
            desc_path=self.root/'description_tokenizer'
            if not desc_path.exists(): raise RuntimeError('TTS description tokenizer is missing. Re-run the model downloader.')
            self.loaded['tts']=(model,AutoTokenizer.from_pretrained(path,local_files_only=True),AutoTokenizer.from_pretrained(str(desc_path),local_files_only=True))
        model,tokenizer,desc_tokenizer=self.loaded['tts']
        description=desc_tokenizer(STYLES[style].replace('speaker',voice['gender']+' speaker',1),return_tensors='pt').to(self.device)
        pieces=[]
        for chunk in self.chunks(text):
            prompt=tokenizer(chunk,return_tensors='pt').to(self.device)
            if prompt.input_ids.shape[1]>256: raise ValueError('Narration segment is too long.')
            with torch.inference_mode():
                generated=model.generate(input_ids=description.input_ids,attention_mask=description.attention_mask,prompt_input_ids=prompt.input_ids,prompt_attention_mask=prompt.attention_mask,do_sample=True,temperature=1.0)
            samples=generated.float().cpu().numpy().squeeze()
            pieces.extend([samples,np.zeros(int(model.config.sampling_rate*.16),dtype=np.float32)])
        out=io.BytesIO()
        sf.write(out,np.concatenate(pieces),model.config.sampling_rate,format='WAV',subtype='PCM_16')
        return out.getvalue()

    def mms_audio(self,text,language,style):
        import torch
        import soundfile as sf
        from transformers import VitsModel,AutoTokenizer
        key='mms-'+language
        if key not in self.loaded:
            # Bound memory on small prototype servers; keep only one regional model.
            for name in list(self.loaded):
                if name.startswith('mms-'):del self.loaded[name]
            path=self.root/'mms'/language
            self.loaded[key]=(VitsModel.from_pretrained(path,local_files_only=True).to(self.device).eval(),AutoTokenizer.from_pretrained(path,local_files_only=True))
        model,tokenizer=self.loaded[key]
        model.speaking_rate={'museum':.92,'conversation':1.0,'calm':.84}[style]
        pieces=[]
        for chunk in self.chunks(text,200):
            inputs=tokenizer(chunk,return_tensors='pt').to(self.device)
            if inputs.input_ids.numel()<2:raise ValueError('The selected voice cannot read this script.')
            with torch.inference_mode():samples=model(**inputs).waveform.squeeze().float().cpu().numpy()
            pieces.extend([samples,np.zeros(int(model.config.sampling_rate*.16),dtype=np.float32)])
        out=io.BytesIO();sf.write(out,np.concatenate(pieces),model.config.sampling_rate,format='WAV',subtype='PCM_16')
        return out.getvalue()
