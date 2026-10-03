const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
function worker(overrides={}){
 const handlers={};const stored=new Map();const writes=[];
 const cache={put:async(key,response)=>{writes.push([typeof key==='string'?key:key.url,await response.text()]);}};
 const caches={open:async()=>cache,match:async key=>stored.get(typeof key==='string'?key:key.url)?.clone(),keys:async()=>[],delete:async()=>true,...overrides.caches};
 const self={location:{origin:'https://smriti.test'},addEventListener:(event,fn)=>handlers[event]=fn,skipWaiting:async()=>{},clients:{claim:async()=>{}},...overrides.self};
 vm.runInNewContext(fs.readFileSync('public/sw.js','utf8'),{URL,Request:class extends Request{constructor(url,options){super(new URL(url,'https://smriti.test'),options);}},Response,self,caches,fetch:overrides.fetch||(async()=>new Response('fresh content'))});
 const fetchEvent=(path,extra={})=>{
   const waits=[];let response;
   handlers.fetch({request:{url:'https://smriti.test'+path,method:'GET',mode:'cors',headers:new Headers(),...extra},waitUntil:p=>waits.push(p),respondWith:p=>response=p});
   return {waits,get response(){return response;}};
 };
 return {handlers,fetchEvent,writes,stored};
}
test('response is cloned before delayed cache opening, after browser consumption',async()=>{
 let release;const delayed=new Promise(resolve=>release=resolve);const written=[];
 const w=worker({caches:{open:()=>delayed}});
 const event=w.fetchEvent('/locales/mr.json');const response=await event.response;
 assert.equal(await response.text(),'fresh content');
 release({put:async(key,copy)=>written.push(await copy.text())});
 await Promise.all(event.waits);assert.deepEqual(written,['fresh content']);
});
test('quota failures do not break a successful network response or leak rejections',async()=>{
 const w=worker({caches:{open:async()=>{throw Error('storage disabled');}}});
 const event=w.fetchEvent('/',{mode:'navigate'});
 assert.equal(await (await event.response).text(),'fresh content');await Promise.all(event.waits);
});
test('offline navigation returns the cached page; cache miss is an explicit response',async()=>{
 const w=worker({fetch:async()=>{throw Error('offline');}});
 w.stored.set('/',new Response('offline archive'));
 assert.equal(await (await w.fetchEvent('/',{mode:'navigate'}).response).text(),'offline archive');
 const response=await w.fetchEvent('/locales/mr.json').response;assert.equal(response.status,503);
});
test('API, voice, Next.js chunks and RSC requests bypass the worker',()=>{
 const w=worker();
 for(const path of ['/api/voice/capabilities','/api/voice/narrate','/api/ask','/_next/static/chunks/main.js','/?_rsc=123','/unknown.js'])assert.equal(w.fetchEvent(path).response,undefined);
 assert.equal(w.fetchEvent('/',{headers:new Headers({RSC:'1'})}).response,undefined);
});
test('activation removes only old SMRITI caches',async()=>{
 const removed=[];const w=worker({caches:{keys:async()=>['smriti-ai-v25-voice-reviewed','unrelated-app','smriti-ai-v26-vercel-voice'],delete:async key=>removed.push(key)}});
 let task;w.handlers.activate({waitUntil:p=>task=p});await task;
 assert.deepEqual(removed,['smriti-ai-v25-voice-reviewed']);
});
test('one unavailable precache asset does not prevent the repaired worker installing',async()=>{
 let installed=false;let task;
 const w=worker({fetch:async request=>{if(request.url.endsWith('/locales/ur.json'))throw Error('temporary network failure');return new Response('asset');},self:{skipWaiting:async()=>{installed=true;}}});
 w.handlers.install({waitUntil:p=>task=p});await task;assert.equal(installed,true);
});
