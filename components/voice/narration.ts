/** Keep names intact while buffering short native-language narration segments. */
export function narrationSegments(text:string,maxLength=260):string[] {
  const protectedText=text.replace(/\[\d+\]/g,'')
    .replace(/\b(?:Dr|Mr|Mrs|Ms|Prof|Sr|Jr)\./gi,value=>value.replace('.','\ue000'))
    .replace(/(?:डॉ|डा|ഡോ|ডা|ડૉ|ಡಾ|డా|ਡਾ|டா)\./g,value=>value.replace('.','\ue000'))
    .replace(/(?:बी|आर|পি|আর|பி|ஆர்|બી|આર|ಬಿ|ಆರ್|ബി|ആർ|బి|ఆర్|ਬੀ|ਆਰ|বি|আর)\./g,value=>value.replace('.','\ue000'))
    .replace(/\b[A-Z]\.(?=\s*[A-Z])/g,value=>value.replace('.','\ue000'));
  const segments:string[]=[];
  for(let sentence of protectedText.split(/(?<=[.!?।؟])\s+|\n+/)) {
    sentence=sentence.replace(/\ue000/g,'.').trim();
    while(sentence.length>maxLength) {
      const cut=sentence.lastIndexOf(' ',maxLength);
      if(cut<1)break;
      segments.push(sentence.slice(0,cut));sentence=sentence.slice(cut).trim();
    }
    if(sentence)segments.push(sentence);
  }
  return segments;
}
