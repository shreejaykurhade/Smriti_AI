'use client';
import { cloneElement, isValidElement, useEffect, useMemo, useState, type ReactNode } from 'react';
import { localizeTree, type Messages } from './localize';

const memory=new Map<string,Messages>();
const pendingLabels:Record<string,string>={mr:'भाषा बदलत आहे…',hi:'भाषा बदल रही है…',bn:'ভাষা পরিবর্তন হচ্ছে…',ta:'மொழி மாறுகிறது…',te:'భాష మారుతోంది…',gu:'ભાષા બદલાઈ રહી છે…',kn:'ಭಾಷೆ ಬದಲಾಗುತ್ತಿದೆ…',ml:'ഭാഷ മാറുന്നു…',pa:'ਭਾਸ਼ਾ ਬਦਲ ਰਹੀ ਹੈ…',ur:'زبان تبدیل ہو رہی ہے…'};

/** Static interface packs never depend on speech-model availability.
 * Dynamic research answers are translated separately by the research endpoint.
 */
export function LocalizedInterface({language,children,onMessages}:{language:string;children:ReactNode;onMessages?:(locale:{language:string;messages:Messages})=>void}) {
  const [locale,setLocale]=useState<{language:string;messages:Messages}>({language:'en',messages:{}});
  const [failure,setFailure]=useState(false);
  const [retry,setRetry]=useState(0);
  useEffect(()=>{
    const controller=new AbortController();setFailure(false);
    if(language==='en'){setLocale({language,messages:{}});return()=>controller.abort();}
    const cached=memory.get(language);
    if(cached){setLocale({language,messages:cached});return()=>controller.abort();}
    void (async()=>{
      try{
        const response=await fetch(`/locales/${language}.json`,{signal:controller.signal});
        if(!response.ok)throw new Error('Language pack unavailable');
        const messages:Messages=await response.json();
        if(!messages||typeof messages!=='object'||Object.values(messages).some(value=>typeof value!=='string'))throw new Error('Invalid language pack');
        if(controller.signal.aborted)return;
        memory.set(language,messages);setLocale({language,messages});
      }catch{if(!controller.signal.aborted)setFailure(true);}
    })();
    return()=>controller.abort();
  },[language,retry]);
  useEffect(()=>{if(locale.language===language)onMessages?.(locale);},[locale,language,onMessages]);
  const messages=locale.language===language?locale.messages:{};
  const {tree,missing}=useMemo(()=>{
    const missing=new Set<string>();
    return {tree:language==='en'?children:localizeTree(children,messages,missing),missing};
  },[children,language,messages]);
  return <>{language!=='en' && locale.language!==language && <div className="locale-status" role="status" aria-live="polite">
    {failure?<><span>Could not load this language. Check your connection.</span><button onClick={()=>setRetry(value=>value+1)}>Retry</button></>:<span>{pendingLabels[language]||'Changing language…'}</span>}
  </div>}{isValidElement<Record<string,unknown>>(tree)?cloneElement(tree,{"data-ui-language":language,"data-ui-missing":JSON.stringify([...missing])}):tree}</>;
}
