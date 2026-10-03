// Vercel hosts this lightweight proxy. Models and WebSockets run on the voice service.
import {serverlessVoice} from '../serverless';
export const runtime = 'nodejs';
export const maxDuration = 30;
type Context = { params: Promise<{ path: string[] }> };
async function proxy(request: Request, context: Context) {
  const { path } = await context.params;
  const endpoint = path.join('/');
  const allowed = request.method === 'GET'
    ? /^(capabilities|jobs\/[A-Za-z0-9_-]{20,40}(\/audio)?)$/.test(endpoint)
    : request.method === 'DELETE' ? /^jobs\/[A-Za-z0-9_-]{20,40}$/.test(endpoint) : /^(jobs|transcribe|session|narrate)$/.test(endpoint);
  if (!allowed) return Response.json({error:'Unknown voice endpoint.'},{status:404});
  const base = process.env.VOICE_BACKEND_URL;
  const key = process.env.VOICE_API_KEY;
  // Reject cross-site mutations before forwarding our server-side credential.
  const origin = request.headers.get('origin');
  if (request.method !== 'GET' && origin) {
    try {if(new URL(origin).origin !== new URL(request.url).origin) return Response.json({error:'Origin is not allowed.'},{status:403});}
    catch {return Response.json({error:'Origin is not allowed.'},{status:403});}
  }
  const limit = endpoint === 'transcribe' ? 1_000_000 : 60_000;
  if (Number(request.headers.get('content-length') || 0)>limit) return Response.json({error:'Request is too large.'},{status:413});
  try {
    let body: Uint8Array | undefined;
    if (request.method === 'POST') {
      const chunks: Uint8Array[] = []; let size=0;
      const reader=request.body?.getReader();
      if (reader) for (;;) { const item=await reader.read(); if(item.done)break; size+=item.value.length; if(size>limit){await reader.cancel();return Response.json({error:'Request is too large.'},{status:413});} chunks.push(item.value); }
      body = new Uint8Array(size); let offset=0; for(const chunk of chunks){body.set(chunk,offset);offset+=chunk.length;}
    }
    if (!base || !key) return serverlessVoice(request, endpoint, body);
    const parsed = new URL(base);
    if (!['https:','http:'].includes(parsed.protocol) || (process.env.VERCEL && parsed.protocol !== 'https:')) return Response.json({error:'Voice backend must use HTTPS.'},{status:503});
    const target=new URL(`${base.replace(/\/$/,'')}/${endpoint}`);
    const language=new URL(request.url).searchParams.get('language');
    if(endpoint==='transcribe' && language) target.searchParams.set('language',language);
    const upstream=await fetch(target,{method:request.method,headers:{'x-smriti-key':key,'content-type':request.headers.get('content-type') || 'application/json'},body:body as BodyInit | undefined,cache:'no-store',redirect:'error',signal:AbortSignal.timeout(25000)});
    const contentType=upstream.headers.get('content-type') || 'application/json';
    return new Response(upstream.body,{status:upstream.status,headers:{'Content-Type':contentType,'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'}});
  } catch {return Response.json({error:'The museum voice server is temporarily unavailable.'},{status:502});}
}
export { proxy as GET, proxy as POST, proxy as DELETE };
