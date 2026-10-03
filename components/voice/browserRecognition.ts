export const BROWSER_LOCALES: Record<string, string> = {en:'en-IN',bn:'bn-IN',gu:'gu-IN',hi:'hi-IN',kn:'kn-IN',ml:'ml-IN',mr:'mr-IN',ne:'ne-NP',ta:'ta-IN',te:'te-IN',ur:'ur-IN'};
type RecognitionEvent = {resultIndex:number;results:ArrayLike<{isFinal:boolean;0:{transcript:string}}>};
type Recognition = {
  lang:string;continuous:boolean;interimResults:boolean;maxAlternatives:number;
  onresult:((event:RecognitionEvent)=>void)|null;onend:(()=>void)|null;
  onerror:((event:{error:string})=>void)|null;onstart:(()=>void)|null;
  start:()=>void;stop:()=>void;abort:()=>void;
};
export type RecognitionConstructor = new()=>Recognition;
export function browserRecognitionConstructor():RecognitionConstructor|undefined {
  if(typeof window==='undefined')return;
  const browser=window as unknown as {SpeechRecognition?:RecognitionConstructor;webkitSpeechRecognition?:RecognitionConstructor};
  return browser.SpeechRecognition||browser.webkitSpeechRecognition;
}

/** Exactly one transcript is submitted. Stop finishes; cancel discards all late
 * results. The caller must start this only from an explicit microphone gesture. */
export function startBrowserDictation(Constructor:RecognitionConstructor,language:string,callbacks:{start:()=>void;complete:(text:string)=>void;error:(reason:string)=>void}) {
  if(!BROWSER_LOCALES[language])throw new Error('Unsupported input language');
  const recognition=new Constructor();let active=true;let finalText='';let interim='';
  recognition.lang=BROWSER_LOCALES[language];recognition.continuous=false;recognition.interimResults=true;recognition.maxAlternatives=1;
  const cleanup=()=>{clearTimeout(timer);recognition.onstart=null;recognition.onresult=null;recognition.onerror=null;recognition.onend=null;};
  const finish=()=>{if(!active)return;active=false;cleanup();callbacks.complete((finalText||interim).trim());};
  const timer=setTimeout(()=>{if(active)try{recognition.stop();}catch{finish();}},29500);
  recognition.onstart=()=>{if(active)callbacks.start();};
  recognition.onresult=event=>{
    if(!active)return;interim='';
    for(let index=event.resultIndex;index<event.results.length;index++){
      const result=event.results[index];if(result.isFinal)finalText+=result[0].transcript+' ';else interim+=result[0].transcript+' ';
    }
  };
  recognition.onend=finish;
  recognition.onerror=event=>{if(!active)return;active=false;cleanup();callbacks.error(event.error);};
  try{recognition.start();}catch(error){active=false;cleanup();throw error;}
  return {stop:()=>{if(active)recognition.stop();},cancel:()=>{active=false;cleanup();try{recognition.abort();}catch{}}};
}
