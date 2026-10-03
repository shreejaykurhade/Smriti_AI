// Collect stable English message keys; never rewrite component source or event values.
const ts = require('typescript');
const fs = require('fs');
const messages = new Set();
const add = value => {
  const text = value.replace(/\s+/g, ' ').trim();
  if (/[A-Za-z]/.test(text) && text.length < 3000 && !/^(https?:|\/|\.|smriti-|image\/)/.test(text)) messages.add(text);
};
for (const file of ['components/ArchiveApp.tsx', 'components/voice/useMuseumVoice.ts','components/voice/VoiceControls.tsx','components/archive/SourcePanel.tsx','components/archive/SourceLibrary.tsx']) {
  const tree = ts.createSourceFile(file, fs.readFileSync(file, 'utf8'), ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
  function visit(node) {
    if (ts.isJsxText(node)) add(node.text.replace(/&amp;/g,'&'));
    if (ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node)) {
      const parent = node.parent;
      if (ts.isJsxAttribute(parent) && ['placeholder','title','alt','aria-label'].includes(parent.name.text)) add(node.text);
      else if (ts.isPropertyAssignment(parent) && ['title','summary','detail','context','kicker','text','label','meaning','role','rights','place','collection','type','imageAlt','t','d'].includes(parent.name.getText(tree).replace(/['"]/g,''))) add(node.text);
      else if (!ts.isJsxAttribute(parent) && /[A-Z]/.test(node.text) && !/^(GET|POST|DELETE|OPEN|AbortError|Content-Type|SHA-256|UTC|WAVE|RIFF|PCM|SOURCE|Escape|Tab)$/i.test(node.text) && !node.text.includes('http') && !/^[A-Za-z]+[A-Z][A-Za-z]*$/.test(node.text)) add(node.text);
    }
    ts.forEachChild(node, visit);
  }
  visit(tree);
}
for (const file of ['smriti_core/records.json','smriti_core/guide-topics.json']) {
  for (const entry of JSON.parse(fs.readFileSync(file,'utf8'))) {
    for (const key of ['summary','sourceNote','question']) if(entry[key]) add(entry[key]);
  }
}
['pages','min','Entry','Listen in','Speak in','Remove','SMRITI AI home','Translation','Original quotation','Preparing this language…','Translation unavailable. Original text is shown.','Retry','Language names and original source references are preserved.'].forEach(add);
fs.writeFileSync('components/i18n/catalog.json', JSON.stringify([...messages].sort(), null, 2)+'\n');
console.log(`${messages.size} interface and catalogue messages`);
