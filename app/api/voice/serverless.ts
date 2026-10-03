import speakers from './voices.json';
import { createHash } from 'node:crypto';

const voices = Object.fromEntries(Object.entries(speakers).map(([code, list]) => [code, list.map(speaker => ({
  id: speaker.name, name: speaker.name.split('-').slice(2).join('-').replace(/ExpressiveNeural$|Neural$/, ''),
  gender: speaker.gender.toLowerCase(), provider: 'edge-serverless', online: true,
}))]));
const languages = Object.keys(voices);
const cache = new Map<string, {audio: Uint8Array; expires: number}>();
const pending = new Map<string, Promise<Uint8Array>>();
const headers = {'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff'};

export function serverlessCapabilities() {
  return {mode: 'serverless', voices, tts: true, stt: false, translation: false,
    tts_languages: languages, stt_languages: [], browser_input_languages: languages,
    prepared_languages: languages, styles: ['museum', 'conversation', 'calm'],
    voice_label: 'Online neural narration', online_voice: true};
}

async function synthesize(text: string, voice: string, style: string) {
  const {Communicate} = await import('edge-tts-universal');
  const speaker = new Communicate(text, {voice, rate: style === 'calm' ? '-14%' : style === 'museum' ? '-10%' : '+0%', connectionTimeout: 7000});
  const chunks: Uint8Array[] = [];
  let size = 0;
  for await (const chunk of speaker.stream()) {
    if (chunk.type === 'audio' && chunk.data) {
      size += chunk.data.byteLength;
      if (size > 1_000_000) throw new Error('Narration exceeds audio limit.');
      chunks.push(chunk.data);
    }
  }
  if (!size) throw new Error('No narration received.');
  return new Uint8Array(Buffer.concat(chunks));
}

async function boundedNarration(text: string, voice: string, style: string) {
  let timer: ReturnType<typeof setTimeout> | undefined;
  try {
    return await Promise.race([synthesize(text, voice, style), new Promise<never>((_, reject) => {
      timer = setTimeout(() => reject(new Error('Narration timed out.')), 25000);
    })]);
  } finally {if (timer) clearTimeout(timer);}
}

// Audio returns in this request. No job IDs or local files are shared between
// Vercel instances. The bounded warm-instance cache is optional.
export async function serverlessVoice(request: Request, endpoint: string, body?: Uint8Array) {
  if (request.method === 'GET' && endpoint === 'capabilities') return Response.json(serverlessCapabilities(), {headers});
  if (request.method !== 'POST' || endpoint !== 'narrate') return Response.json({error: 'This voice mode uses browser input and direct narration.'}, {status: 404, headers});
  let payload;
  try {payload = JSON.parse(new TextDecoder().decode(body));} catch {return Response.json({error: 'Invalid narration request.'}, {status: 400, headers});}
  const {text, language, gender = 'female', style = 'museum'} = payload || {};
  const options = typeof language === 'string' && languages.includes(language) ? voices[language] : undefined;
  if (typeof text !== 'string' || !text.trim() || text.length > 600 || !options || !['female', 'male', 'auto'].includes(gender) || !['museum', 'conversation', 'calm'].includes(style)) {
    return Response.json({error: 'Choose an available narrator and a passage of up to 600 characters.'}, {status: 400, headers});
  }
  const voice = (options.find(speaker => speaker.gender === gender) || options[0]).id;
  const key = createHash('sha256').update(JSON.stringify([text, voice, style])).digest('hex');
  const found = cache.get(key);
  try {
    let audio = found && found.expires > Date.now() ? found.audio : undefined;
    if (!audio) {
      let task = pending.get(key);
      if (!task) {
        if (pending.size >= 4) return Response.json({error: 'Narrators are busy. Please try again shortly.'}, {status: 429, headers});
        task = boundedNarration(text, voice, style).finally(() => pending.delete(key));
        pending.set(key, task);
      }
      audio = await task;
      cache.delete(key);
      cache.set(key, {audio, expires: Date.now() + 600_000});
      while (cache.size > 24) cache.delete(cache.keys().next().value!);
    }
    return new Response(audio as BodyInit, {headers: {...headers, 'Content-Type': 'audio/mpeg'}});
  } catch {
    return Response.json({error: 'Online narration is temporarily unavailable. Your answer and original sources are still available.'}, {status: 502, headers});
  }
}
