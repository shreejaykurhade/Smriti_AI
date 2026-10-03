# SMRITI AI — source-linked museum voice guide

A Next.js web app/PWA and touchscreen kiosk interface for exploring Dr. B. R. Ambedkar’s writings, speeches and ideas. Vercel hosts the website, archive API and direct online neural narration. When no model backend is configured, microphone input uses the browser’s SpeechRecognition service. An optional separate Python service adds Whisper, translation, local speech synthesis and Pipecat conversations.

## What is included

The catalogue has 13 featured works with direct original PDF links, collection links and page references. The reading library has 60 government-hosted PDF files: 20 English files and 40 Hindi files from the Ministry of External Affairs collection. The selected PDFs and passages were checked on 3 October 2026. These are official collected editions/reprints, not a claim of first-edition facsimiles. Original documents stay on their institutional hosts; downloaded verification copies are excluded from deployment and the source ZIP. `smriti_core/source-library.json` records the links and verification date.

Research supports an optional server-only multilingual answer service. It answers the actual visitor question from 13 curated records, checked excerpts and eight guide notes. The server validates structured output and resolves source IDs to official PDF links; the model cannot supply new citation URLs. It is **not full-text archival RAG** and does not browse the internet during a visitor’s question. Questions outside the supplied evidence receive an insufficient-evidence response. Without credentials, or during provider outages, quota limits or malformed responses, the existing eight-topic guide and 88 regional answer packets remain available. Exact quotations are kept separate from summaries, with verified PDF page references. The scanned Hindu Code Bill volume is labelled as not OCR-verified. Timeline sources distinguish biographical chronology from original works and image credits.

With the model host connected, voice and text are available in English plus 11 Indian languages: Bengali, Gujarati, Hindi, Kannada, Malayalam, Marathi, Nepali, Punjabi, Tamil, Telugu and Urdu. The picker exposes only the configured intersection of input, narration and translation support. Unsupported and quota-dependent demo languages are hidden. Assamese is hidden because the short-question recognition smoke test did not meet the prototype’s quality bar. Female/male choices use distinct online neural speakers for English and ten Indian languages; Punjabi uses its installed single original MMS speaker. The prototype does not invent gender choices by changing pitch. Without a model host, Vercel exposes English and ten Indian narration languages from the reviewed online speaker list; Punjabi is hidden because its local MMS voice is not available on Vercel. Browser dictation is enabled only when the browser exposes SpeechRecognition, uses the selected locale, and disables a language if the browser rejects it. Remote recognition support varies by browser and provider; Firefox users can type and listen instead.

Voice preferences are saved on this device. Museum and calm delivery use slower narration. Sentence buffering starts playback before the entire answer has been synthesized; one following sentence is prefetched, and Stop or a language change cancels playback. Prepared guide answers avoid repeated output translation. New regional questions still require input translation. When a model host is configured, microphone capture uses Whisper through a Pipecat push-to-talk session; tapping the microphone again submits the question. Generated narration is explicitly labelled as a guide, never an original recording or a clone of Dr. Ambedkar.

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

## Deploy to Vercel

The app now works without voice environment variables. `/api/voice/capabilities` returns the lightweight narrator mode with HTTP 200. `/api/voice/narrate` returns MP3 audio directly in one bounded Node.js request using `edge-tts-universal`; it never relies on local job files persisting across function instances. Browser input uses SpeechRecognition when available and does not claim to be Whisper. Ready answers and a small native topic vocabulary use the bundled source-linked guide packets; unsupported questions get a localized insufficient-evidence reply. No arbitrary live translation is claimed in this mode. Online narration sends spoken text to Microsoft; browser dictation uses the browser provider’s speech service. There is no API key requirement, but these external free services have no production SLA.

The PWA worker clones responses before handing them to the browser, awaits optional cache writes, excludes APIs/RSC/Next.js chunks, and removes only old SMRITI caches. Updating the worker reloads already-controlled clients once. `/sw.js` has no-cache headers. The screenshot’s `contentscript.js` EventEmitter/ObjectMultiplex warnings come from an injected browser extension and are not emitted by this app.

### Optional model host

Import this project root into Vercel as a Next.js app. `vercel.json` routes the lightweight Flask archive API. The heavy speech process, models, virtual environment, caches and verification downloads are excluded by `.vercelignore`. Set these server-only variables:

For generated multilingual answers, add `GROQ_API_KEY` as a sensitive environment variable in Vercel for Production and Preview, then redeploy. The default answer model is `openai/gpt-oss-120b`, verified against the account's live model catalogue. Optional `SMRITI_ANSWER_MODEL` can select a compatible structured-output model. No provider branding is added to the public interface. The key grants model access; the curated archive is the knowledge source. Never put credentials in source files, client components, logs or `NEXT_PUBLIC_*` variables. Visitor questions and the public archive context are sent to the online answer service.

One request has an 18-second provider deadline and a bounded output. Warm instances cache up to 128 validated answers for five minutes and permit at most three concurrent model calls; these are per-instance protections, not distributed rate limits. Use the provider account's spending limits and Vercel firewall/rate-limit controls for public traffic. Expired/invalid keys, 429s and timeouts keep the existing guide available. Model-grounded responses are not a guarantee of historical accuracy; verify interpretation against the linked original sources.

```text
VOICE_BACKEND_URL=https://voice.your-domain.in
VOICE_API_KEY=<same long random secret as the speech host>
```

Do not prefix these variables with `NEXT_PUBLIC_`. The Whisper/NLLB/MMS model stack requires a persistent model host. Run the Python service on a separate CPU/GPU machine with persistent storage and an HTTPS reverse proxy, using `voice.your-domain.in`. Attach the main website domain to Vercel. Set `PUBLIC_VOICE_URL` and exact `VOICE_ALLOWED_ORIGINS` on the speech host. Browser audio sessions use expiring, single-use tokens; API keys remain server-side.

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
node --test tests/frontend/*.test.cjs
.venv/bin/python -m pytest tests --timeout=20 -q
```

The automated suite covers multilingual interface behavior, supported-language filtering, native sentence boundaries, source provenance, prepared regional answers, unsupported-topic abstention, API authentication, upload limits, cancellation, token reuse and the Pipecat frame pipeline. Real provider/model smoke scripts are `scripts/check_prototype.py` and `scripts/check_live.py`; these use generated test audio rather than your microphone. Browser checks verify translated voice controls and direct source links. Deployment and production voice quality must be evaluated against the actual hosted backend and hardware.

Primary collection: https://www.mea.gov.in/books-writings-of-ambedkar.htm

Original debate: https://elibrary.sansad.in/items/aad33de6-ec92-47a9-a8b5-16bab1d210fc

Validated locally on 3 October 2026: both Vercel-style and isolated preview builds passed, along with 22 Python and 11 frontend checks. Real neural narration, native-script speech recognition checks, and the Whisper → source-linked guide → Pipecat speech path passed. Female/male English, Hindi and Marathi cold narration jobs became ready in roughly 2–4 seconds locally; this is a test result, not a hosted SLA. The launcher now prewarms 42 checksum-verified welcome sentence clips at the current pacing. Runtime model weights and private source verification downloads are not included in the source ZIP.

Deployment repair checked on 3 October 2026: 25 frontend and 25 Python checks passed; production build and type checking passed. Service-worker tests reproduce consuming the original response before the cache opens, offline misses, quota failures and cache upgrades. Vercel voice tests cover missing backend variables, direct audio responses, narrator selection, request limits, cross-site protection, browser cancellation and unsupported languages. Live-provider and deployed-site results are verified separately.

Forty genuine welcome sentence clips are bundled as MP3 previews with checksums, speaker IDs and the current museum pacing. The frontend uses them only for an exact text/speaker/style match; other answers are synthesized from their actual text. Both speakers across all 11 Vercel narration languages produced decodable audio in the real provider check. Cold provider requests can take longer; prerecorded previews do not imply that every answer is prerecorded.
