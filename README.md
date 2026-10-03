# SMRITI AI — source-linked museum voice guide

A Next.js web app/PWA and touchscreen kiosk interface for exploring Dr. B. R. Ambedkar’s writings, speeches and ideas. Vercel hosts the website and authenticated API proxy. A separate Python service runs Whisper, translation, speech synthesis and Pipecat conversations.

## What is included

The catalogue has 13 featured works with direct original PDF links, collection links and page references. The reading library has 60 government-hosted PDF files: 20 English files and 40 Hindi files from the Ministry of External Affairs collection. The selected PDFs and passages were checked on 3 October 2026. These are official collected editions/reprints, not a claim of first-edition facsimiles. Original documents stay on their institutional hosts; downloaded verification copies are excluded from deployment and the source ZIP. `smriti_core/source-library.json` records the links and verification date.

Research is an eight-topic curated guide, with source-linked summaries and 88 enabled regional answer packets. It is **not full-text archival RAG** and does not browse the internet during a visitor’s question. Questions outside the covered evidence receive an insufficient-evidence response. Exact quotations are kept separate from summaries, with verified PDF page references. The scanned Hindu Code Bill volume is labelled as not OCR-verified. Timeline sources distinguish biographical chronology from original works and image credits.

Voice and text are available in English plus 11 Indian languages: Bengali, Gujarati, Hindi, Kannada, Malayalam, Marathi, Nepali, Punjabi, Tamil, Telugu and Urdu. The picker exposes only the configured intersection of input, narration and translation support. Unsupported and quota-dependent demo languages are hidden. Assamese is hidden because the short-question recognition smoke test did not meet the prototype’s quality bar. Female/male choices use distinct online neural speakers for English and ten Indian languages; Punjabi uses its installed single original MMS speaker. The prototype does not invent gender choices by changing pitch.

Voice preferences are saved on this device. Museum and calm delivery use slower narration. Sentence buffering starts playback before the entire answer has been synthesized; one following sentence is prefetched, and Stop or a language change cancels playback. Prepared guide answers avoid repeated output translation. New regional questions still require input translation. Microphone capture uses Whisper through a Pipecat push-to-talk session; tapping the microphone again submits the question. Generated narration is explicitly labelled as a guide, never an original recording or a clone of Dr. Ambedkar.

## Run locally

```sh
npm ci
python3.11 -m venv .venv
. .venv/bin/activate
sh scripts/install_voice.sh
HF_HOME="$PWD/models/.hf" python scripts/download_models.py --only whisper --whisper small
HF_HOME="$PWD/models/.hf" python scripts/download_models.py --only whisper --whisper large-v3-turbo
HF_HOME="$PWD/models/.hf" python scripts/download_models.py --only prototype
PYTHONPATH=. python scripts/download_regional_voices.py
SMRITI_BUILD_DIR=.next-preview LOCAL_ARCHIVE_URL=http://127.0.0.1:5003 npm run build
python scripts/run_local.py --port 3003 --voice-port 8002 --archive-port 5003
```

Open http://localhost:3003 and choose **Voice & research**. Select a language, narrator and delivery style; preview the voice or ask a ready question. **Ask with your voice** connects the live guide and requests microphone access. **Start live guide** also connects it without recording immediately. Use Chrome/Edge and allow the microphone; localhost is supported, and public deployments need HTTPS. A browser may require tapping **Play narration** once after audio becomes ready. The launcher creates a temporary local API key if no key is configured and launches all three services with consistent ports.

The prepared local stack uses `faster-whisper` large-v3-turbo (CPU int8), with the small checkpoint selected for Tamil after the short-question script comparison, NLLB-200 distilled 600M for prototype translation, Microsoft online neural narration through `edge-tts`, and local MMS/VITS for Punjabi. No paid API or Hugging Face login is required for these ungated prototype providers. They are not all open-source model services: Edge narration is an external online interface without a guaranteed production SLA. Spoken text is sent to Microsoft. Whisper, NLLB and MMS run on the model host; microphone input is not sent to Microsoft. Input recordings are discarded after transcription.

NLLB and MMS checkpoints are CC-BY-NC research models used here for a noncommercial prototype. Hindi/Marathi guide scripts and key interface labels have editorial overrides. Other translation packs are machine-generated and require native-speaker proofreading before institutional publication. Hearing quality, pronunciation and microphone performance on museum hardware also require a site test.

## Vercel + separate speech host

Import this project root into Vercel as a Next.js app. `vercel.json` routes the lightweight Flask archive API. The heavy speech process, models, virtual environment, caches and verification downloads are excluded by `.vercelignore`. Set these server-only variables:

```text
VOICE_BACKEND_URL=https://voice.your-domain.in
VOICE_API_KEY=<same long random secret as the speech host>
```

Do not prefix these variables with `NEXT_PUBLIC_`. Vercel cannot run this long-lived model process or Pipecat WebSocket server. Run the Python service on a separate CPU/GPU machine with persistent storage and an HTTPS reverse proxy, using `voice.your-domain.in`. Attach the main website domain to Vercel. Set `PUBLIC_VOICE_URL` and exact `VOICE_ALLOWED_ORIGINS` on the speech host. Browser audio sessions use expiring, single-use tokens; API keys remain server-side.

```sh
cp speech_service/.env.example speech_service/.env
# Set the shared key, your exact website origins, and public speech URL.
docker compose -f compose.voice.yaml build
docker compose -f compose.voice.yaml run --rm voice python scripts/download_models.py --only whisper --whisper small
docker compose -f compose.voice.yaml run --rm voice python scripts/download_models.py --only whisper --whisper large-v3-turbo
docker compose -f compose.voice.yaml run --rm voice python scripts/download_models.py --only prototype
docker compose -f compose.voice.yaml run --rm voice python scripts/download_regional_voices.py
docker compose -f compose.voice.yaml up -d
```

The example chooses `SMRITI_TTS_PROVIDER=hybrid`, `SMRITI_TRANSLATION_PROVIDER=nllb`, and `SMRITI_REMOTE_PARLER=0`. Make the mounted `/models` and `/audio-cache` directories writable by container UID 10001. Docker is provided but has not been built on this local machine. The service uses one inference worker, a bounded queue, upload limits, short-lived jobs and a 256 MB / one-day narration cache. This is a single-instance prototype; scaling requires shared queues, sessions and distributed rate limits.

## Optional original AI4Bharat stack

The requested Indic Parler-TTS + Whisper + IndicTrans2 + Pipecat adapters remain available. The Hugging Face account owner must accept access conditions before downloading these gated models:

- https://huggingface.co/ai4bharat/indic-parler-tts
- https://huggingface.co/ai4bharat/indictrans2-en-indic-dist-200M
- https://huggingface.co/ai4bharat/indictrans2-indic-en-dist-200M

Authenticate on the speech host with `HF_HOME="$PWD/models/.hf" hf auth login`, then run `python scripts/download_models.py`. Set `SMRITI_TTS_PROVIDER=indic-parler` and `SMRITI_TRANSLATION_PROVIDER=indictrans2`; use `SMRITI_DEVICE=cuda` on an NVIDIA GPU host. Downloads record resolved revisions in `models/revisions.json`. No weights are downloaded during visitor requests. The public AI4Bharat demo is disabled by default and its voices are excluded from the website picker because shared free GPU quotas cannot guarantee availability. Punjabi/Kashmiri should not be advertised as official self-hosted Indic Parler voice coverage.

## Translation and checks

UI packs are static files in `public/locales/`, so website translation does not depend on a running model service. Original titles, quotations and source references are preserved. The PWA caches interface/archive assets, not microphone input or generated voice responses.

```sh
node scripts/extract_messages.cjs
HF_HOME="$PWD/models/.hf" PYTHONPATH="$PWD" .venv/bin/python scripts/build_locales.py bn gu hi kn ml mr ne pa ta te ur
.venv/bin/python scripts/refine_locales.py
npm run typecheck
npm run build
node --test tests/frontend/localization.test.cjs
.venv/bin/python -m pytest tests --timeout=20 -q
```

The automated suite covers multilingual interface behavior, supported-language filtering, native sentence boundaries, source provenance, prepared regional answers, unsupported-topic abstention, API authentication, upload limits, cancellation, token reuse and the Pipecat frame pipeline. Real provider/model smoke scripts are `scripts/check_prototype.py` and `scripts/check_live.py`; these use generated test audio rather than your microphone. Browser checks verify translated voice controls and direct source links. Deployment and production voice quality must be evaluated against the actual hosted backend and hardware.

Primary collection: https://www.mea.gov.in/books-writings-of-ambedkar.htm

Original debate: https://elibrary.sansad.in/items/aad33de6-ec92-47a9-a8b5-16bab1d210fc

Validated locally on 3 October 2026: both Vercel-style and isolated preview builds passed, along with 22 Python and 11 frontend checks. Real neural narration, native-script speech recognition checks, and the Whisper → source-linked guide → Pipecat speech path passed. Female/male English, Hindi and Marathi cold narration jobs became ready in roughly 2–4 seconds locally; this is a test result, not a hosted SLA. The launcher now prewarms 42 checksum-verified welcome sentence clips at the current pacing. Runtime model weights and private source verification downloads are not included in the source ZIP.
