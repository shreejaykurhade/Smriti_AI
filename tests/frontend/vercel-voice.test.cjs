const {test}=require('node:test');const assert=require('node:assert/strict');
const fs=require('node:fs');const path=require('node:path');const ts=require('typescript');
const calls=[];const modules=new Map();
class Communicate{
 constructor(text,options){calls.push({text,...options});}
 async *stream(){yield {type:'audio',data:Buffer.from([255,251,144,0,1,2,3])};}
}
function load(file){
 file=path.resolve(file);if(modules.has(file))return modules.get(file).exports;
 if(file.endsWith('.json'))return JSON.parse(fs.readFileSync(file,'utf8'));
 const module={exports:{}};modules.set(file,module);
 const source=ts.transpileModule(fs.readFileSync(file,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,esModuleInterop:true}}).outputText;
 const localRequire=id=>id==='edge-tts-universal'?{Communicate}:id.startsWith('.')?load(path.resolve(path.dirname(file),id)+(id.endsWith('.json')?'':'.ts')):require(id);
 new Function('require','module','exports',source)(localRequire,module,module.exports);return module.exports;
}
const route=load('app/api/voice/[...path]/route.ts');
const context=endpoint=>({params:Promise.resolve({path:endpoint.split('/')})});
const post=(endpoint,payload,extra={})=>route.POST(new Request('https://smriti.test/api/voice/'+endpoint,{method:'POST',headers:{'Content-Type':'application/json',...extra},body:JSON.stringify(payload)}),context(endpoint));
const saved={url:process.env.VOICE_BACKEND_URL,key:process.env.VOICE_API_KEY};
test.before(()=>{delete process.env.VOICE_BACKEND_URL;delete process.env.VOICE_API_KEY;});
test.after(()=>{if(saved.url!==undefined)process.env.VOICE_BACKEND_URL=saved.url;if(saved.key!==undefined)process.env.VOICE_API_KEY=saved.key;});
test('missing model-host variables return honest usable Vercel capabilities with no 503',async()=>{
 const response=await route.GET(new Request('https://smriti.test/api/voice/capabilities'),context('capabilities'));
 assert.equal(response.status,200);const data=await response.json();assert.equal(data.mode,'serverless');assert.equal(data.stt,false);assert.equal(data.translation,false);
 assert.equal(data.tts_languages.length,11);assert.equal(data.voices.mr[0].id,'mr-IN-AarohiNeural');assert.equal(data.voices.mr[1].id,'mr-IN-ManoharNeural');assert.ok(!data.tts_languages.includes('pa'));
});
test('narration returns actual audio directly and repeats reuse the optional cache',async()=>{
 const payload={text:'Deployment narration check.',language:'mr',gender:'male',style:'calm'};
 const first=await post('narrate',payload);assert.equal(first.status,200);assert.equal(first.headers.get('Content-Type'),'audio/mpeg');assert.equal((await first.arrayBuffer()).byteLength,7);
 const count=calls.length;const second=await post('narrate',payload);await second.arrayBuffer();assert.equal(calls.length,count);
 assert.equal(calls.at(-1).voice,'mr-IN-ManoharNeural');assert.equal(calls.at(-1).rate,'-14%');
});
test('invalid voices, malicious language property names, oversize and malformed bodies fail safely',async()=>{
 for(const payload of [{text:'hi',language:'constructor'},{text:'hi',language:'mr',gender:'invented'},{text:'x'.repeat(601),language:'en'},null])assert.equal((await post('narrate',payload)).status,400);
 const response=await route.POST(new Request('https://smriti.test/api/voice/narrate',{method:'POST',body:'not JSON'}),context('narrate'));assert.equal(response.status,400);
});
test('cross-site narration is blocked even without a private backend key',async()=>{
 for(const origin of ['https://other.test','http://smriti.test','null'])assert.equal((await post('narrate',{text:'hi',language:'en'},{Origin:origin})).status,403);
});
test('browser dictation submits once, keeps native text, and cancel ignores late events',()=>{
 const {startBrowserDictation}=load('components/voice/browserRecognition.ts');let recognition;const texts=[];const errors=[];
 class MockRecognition{constructor(){recognition=this;}start(){this.onstart?.();}stop(){this.onend?.();}abort(){this.aborted=true;}}
 const handle=startBrowserDictation(MockRecognition,'mr',{start:()=>{},complete:t=>texts.push(t),error:e=>errors.push(e)});
 assert.equal(recognition.lang,'mr-IN');recognition.onresult({resultIndex:0,results:[{isFinal:true,0:{transcript:'सामाजिक लोकशाही म्हणजे काय'}}]});
 const oldEnd=recognition.onend;handle.stop();oldEnd();assert.deepEqual(texts,['सामाजिक लोकशाही म्हणजे काय']);
 const cancelled=startBrowserDictation(MockRecognition,'hi',{start:()=>{},complete:t=>texts.push(t),error:e=>errors.push(e)});
 const oldResult=recognition.onresult;const laterEnd=recognition.onend;cancelled.cancel();oldResult({resultIndex:0,results:[{isFinal:true,0:{transcript:'stale question'}}]});laterEnd();assert.equal(texts.length,1);assert.equal(recognition.aborted,true);
});
test('unsupported dictation is reported once and does not submit an empty or stale query',()=>{
 const {startBrowserDictation}=load('components/voice/browserRecognition.ts');let recognition;const events=[];
 class MockRecognition{constructor(){recognition=this;}start(){}stop(){}abort(){}}
 startBrowserDictation(MockRecognition,'ta',{start:()=>{},complete:t=>events.push(t),error:e=>events.push(e)});
 const oldEnd=recognition.onend;recognition.onerror({error:'language-not-supported'});oldEnd();assert.deepEqual(events,['language-not-supported']);
});
test('bundled preview audio matches its checksum, real narrator and current pacing',()=>{
 const crypto=require('node:crypto');
 const manifest=JSON.parse(fs.readFileSync('components/voice/preview-manifest.json','utf8'));
 const voices=JSON.parse(fs.readFileSync('app/api/voice/voices.json','utf8'));
 const ids=new Set(Object.values(voices).flat().map(voice=>voice.name));
 assert.equal(manifest.length,40);
 for(const clip of manifest){
  assert.ok(ids.has(clip.voice_id));assert.equal(clip.preset_version,'calm-guide-v2');
  assert.equal(crypto.createHash('sha256').update(fs.readFileSync('public/voice/'+clip.file)).digest('hex'),clip.sha256);
 }
});
