# SMRITI AI

An end-to-end, evidence-led digital heritage archive prototype for SIH problem statement 26096. It combines a responsive Next.js exhibition and research interface with a Flask API deployable as a Vercel Python Function.

## Included

- Curated archive search and record viewer
- Source-labelled sample catalogue records
- Interactive life timeline and exhibition journeys
- Evidence-grounded research assistant with linked citations
- Responsive kiosk-friendly design
- Flask endpoints for health, records, record detail and research answers
- Installable Progressive Web App with offline shell caching
- Custom SMRITI AI logo and matching PWA icon set
- Black-and-white historical photo archive mapped to dated events, places, documents and source records
- All 22 scheduled Indian languages plus English, with native-script selection, multilingual LLM answers, speech input and spoken answers

## Multilingual AI configuration

The archive ships with multilingual evidence-grounded fallback content. For open-ended LLM conversations in every supported language, configure `OPENAI_API_KEY` in Vercel. You can optionally set `OPENAI_MODEL`; the default is `gpt-4.1-mini`. The key remains server-side in the Flask function.
- One-project Vercel deployment configuration

## Local development

Install dependencies and use Vercel's local runtime so both Next.js and Python routes are available:

```bash
npm install
npx vercel dev
```

Open `http://localhost:3000`. `npm run dev` runs the interface with its built-in catalogue fallback, but does not start the Python function.

## Deploy

```bash
npx vercel
npx vercel --prod
```

The prototype uses curated demonstration content. Before institutional publication, attach verified scans, rights statements, IIIF manifests and curator-approved transcripts to each catalogue entry. Persistent PostgreSQL/Qdrant storage, OCR workers, local language models, Keycloak and OCFL preservation should run on the institutional server and connect through authenticated service APIs; these workloads are not suitable for Vercel serverless functions.

## API

- `GET /api/health`
- `GET /api/records?q=democracy`
- `GET /api/records/<id>`
- `POST /api/ask` with `{ "question": "...", "language": "EN" }`
