const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const Module=require('node:module');
const ts=require('typescript');
const React=require('react');
const {renderToStaticMarkup}=require('react-dom/server');
const path=require('node:path');
const filename=path.resolve('components/i18n/localize.ts');
const compiled=ts.transpileModule(fs.readFileSync(filename,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}}).outputText;
const moduleInstance=new Module(filename,module);moduleInstance.filename=filename;moduleInstance.paths=Module._nodeModulePaths(path.dirname(filename));moduleInstance._compile(compiled,filename);
const {localizeTree}=moduleInstance.exports;
const h=React.createElement;
const messages={'Explore archive':'संग्रह शोधा','Search speeches…':'भाषणे शोधा…','Choose language':'भाषा निवडा','Public domain':'सार्वजनिक मालकी','Ask the archive':'संग्रहाला विचारा'};

test('navigation, placeholders and accessible names translate together',()=>{
 const missing=new Set();const original=h('div',null,h('button',null,'Explore archive'),h('input',{value:'my original query',placeholder:'Search speeches…','aria-label':'Choose language',onChange:()=>{}}));
 const result=renderToStaticMarkup(localizeTree(original,messages,missing));
 assert.match(result,/संग्रह शोधा/);assert.match(result,/placeholder="भाषणे शोधा…"/);assert.match(result,/aria-label="भाषा निवडा"/);assert.match(result,/value="my original query"/);assert.equal(missing.size,0);
});
test('switching back to English and rapid locale changes use the untouched original tree',()=>{
 const original=h('button',null,'Explore archive');
 assert.match(renderToStaticMarkup(localizeTree(original,messages,new Set())),/संग्रह शोधा/);
 assert.match(renderToStaticMarkup(localizeTree(original,{'Explore archive':'संग्रह देखें'},new Set())),/संग्रह देखें/);
 assert.equal(renderToStaticMarkup(original),'<button>Explore archive</button>');
});
test('button behavior and select submission values survive translation',()=>{
 const handler=()=>{};const button=localizeTree(h('button',{onClick:handler},'Explore archive'),messages,new Set());
 assert.equal(button.props.onClick,handler);
 const option=localizeTree(h('option',null,'Public domain'),messages,new Set());
 assert.equal(option.props.value,'Public domain');assert.equal(option.props.children,'सार्वजनिक मालकी');
 const explicit=localizeTree(h('option',{value:'museum'},'Public domain'),messages,new Set());assert.equal(explicit.props.value,'museum');
});
test('native answers, original quotes, identifiers and source links are preserved',()=>{
 const tree=h('div',null,h('p',{translate:'no'},'Ask the archive'),h('code',null,'SHA-256'),h('a',{href:'https://example.org/archive?q=English'},'Explore archive'),h('span',{className:'notranslate'},'मराठी · Marathi'));
 const result=renderToStaticMarkup(localizeTree(tree,messages,new Set()));
 assert.match(result,/>Ask the archive</);assert.match(result,/SHA-256/);assert.match(result,/href="https:\/\/example.org\/archive\?q=English"/);assert.match(result,/मराठी · Marathi/);
});
test('unknown text is queued once, with original whitespace retained',()=>{
 const missing=new Set();const tree=h(React.Fragment,null,' Unknown label ',h('b',null,'Unknown label'),'  Explore archive  ');
 assert.match(renderToStaticMarkup(localizeTree(tree,messages,missing)),/  संग्रह शोधा  /);assert.deepEqual([...missing],['Unknown label']);
});
test('every enabled UI language has a complete bundled pack, including the screenshot text',()=>{
 const catalog=JSON.parse(fs.readFileSync('components/i18n/catalog.json','utf8'));
 const supported=fs.readFileSync('components/i18n/languages.ts','utf8').match(/'([a-z]{2,3})'/g).map(value=>value.slice(1,-1)).filter(code=>code!=='en');
 assert.equal(supported.length,11);
 for(const language of supported){
  const pack=JSON.parse(fs.readFileSync(`public/locales/${language}.json`,'utf8'));
  assert.equal(catalog.filter(key=>!pack[key]?.trim()).length,0,`${language} has untranslated keys`);
  if(['mr','hi'].includes(language))for(const key of ['Explore archive','History map','Research assistant','Ideas that shaped','modern India.','Search speeches, ideas, dates…'])assert.match(pack[key],/\p{Script=Devanagari}/u);
 }
});

test('variable page counts and native voice labels do not require new model jobs',()=>{
 const missing=new Set();const original=h('div',null,'32 pages',h('button',{'aria-label':'Speak in Marathi'},'Listen in मराठी'));
 const translated=renderToStaticMarkup(localizeTree(original,{pages:'पाने','Speak in':'या भाषेत बोला:','Listen in':'या भाषेत ऐका:','Marathi':'मराठी'},missing));
 assert.match(translated,/32 पाने/);assert.match(translated,/aria-label="या भाषेत बोला: मराठी"/);assert.match(translated,/या भाषेत ऐका: मराठी/);assert.equal(missing.size,0);
});

test('archive search matches both native displayed labels and canonical English',()=>{
 const {localizedSearchText}=moduleInstance.exports;
 const index=localizedSearchText(['Constitution','Social democracy'],{Constitution:'संविधान','Social democracy':'सामाजिक लोकशाही'});
 assert.ok(index.includes('संविधान'));assert.ok(index.includes('constitution'));assert.ok(index.includes('सामाजिक लोकशाही'));assert.ok(index.includes('social democracy'));
});

test('compound question labels translate for screen readers without a model job',()=>{
 const missing=new Set();const node=h('button',{'aria-label':'What is social democracy? — Marathi'},'What is social democracy?');
 const result=renderToStaticMarkup(localizeTree(node,{'What is social democracy?':'सामाजिक लोकशाही म्हणजे काय?','Marathi':'मराठी'},missing));
 assert.match(result,/aria-label="सामाजिक लोकशाही म्हणजे काय\? — मराठी"/);
 assert.equal(missing.size,0);
});

function loadTypescript(file){
 const source=ts.transpileModule(fs.readFileSync(file,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText;
 const loaded={exports:{}};new Function('require','module','exports',source)(require,loaded,loaded.exports);return loaded.exports;
}
test('language picker excludes text-only and quota-limited demo routes',()=>{
 const {interactionLanguages,INTERACTION_LANGUAGES}=loadTypescript('components/voice/interactionLanguages.ts');
 assert.equal(INTERACTION_LANGUAGES.length,12);
 for(const code of ['as','ks','sa','sd','mni','mai','or','brx','doi','kok','sat'])assert.ok(!INTERACTION_LANGUAGES.includes(code));
 const caps={stt:true,tts:true,translation:true,stt_languages:['en','mr','or'],tts_languages:['en','mr','or'],translation_languages:['en','mr','or']};
 assert.deepEqual(interactionLanguages(caps),['en','mr']);
 assert.deepEqual(interactionLanguages({...caps,stt:false}),[]);
 assert.deepEqual(interactionLanguages({...caps,translation:false}),['en']);
});
test('short narration buffers keep names and native sentence boundaries intact',()=>{
 const {narrationSegments}=loadTypescript('components/voice/narration.ts');
 assert.deepEqual(narrationSegments('Dr. B. R. Ambedkar studied caste. His work matters.'),['Dr. B. R. Ambedkar studied caste.','His work matters.']);
 assert.deepEqual(narrationSegments('डॉ. आंबेडकरांचे विचार. समानता महत्त्वाची आहे। पुढे वाचा.'),['डॉ. आंबेडकरांचे विचार.','समानता महत्त्वाची आहे।','पुढे वाचा.']);
 assert.ok(narrationSegments('An answer with enough words to split gently at a space.',25).every(part=>part.length<=25));
 assert.deepEqual(narrationSegments('டாக்டர் பி. ஆர். அம்பேத்கர். पुढे वाचा.'),['டாக்டர் பி. ஆர். அம்பேத்கர்.','पुढे वाचा.']);
 assert.deepEqual(narrationSegments(''),[]);
});

test('Vercel exposes only actual narrators and prepared languages even without browser dictation',()=>{
 const {interactionLanguages}=loadTypescript('components/voice/interactionLanguages.ts');
 const caps={mode:'serverless',stt:false,tts:true,translation:false,stt_languages:[],tts_languages:['en','mr','or'],prepared_languages:['en','mr','pa']};
 assert.deepEqual(interactionLanguages(caps),['en','mr']);
 assert.deepEqual(interactionLanguages({...caps,tts_languages:['en'],stt:true,stt_languages:['en','mr']}),['en']);
});
