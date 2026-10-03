'use client';
import { useCallback, useEffect, useRef, useState } from 'react';
import { narrationSegments } from './narration';

export type MuseumSpeaker = {id:string;gender:string;name:string;provider:string;online:boolean;experimental?:boolean};
export type VoiceCapabilities = {voices?:Record<string,MuseumSpeaker[]>;tts:boolean;stt:boolean;translation:boolean;translation_languages?:string[];tts_languages:string[];stt_languages:string[];styles:string[];voice_label?:string;online_voice?:boolean};
export type ArchiveAnswer = {answer:string;citations:{number:number;id:string;title:string;source:string}[];language:string;spoken_text?:string};
async function api(path:string,options?:RequestInit){
  const response=await fetch(`/api/voice/${path}`,options);
  if(!response.ok){let message='Voice service is unavailable.';try{const data=await response.json();message=data.error||data.detail||message;}catch{}throw new Error(typeof message==='string'?message:'Invalid voice request.');}
  return response;
}
export async function voiceJob(payload:object,signal?:AbortSignal){
  const submitted=await (await api('jobs',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload),signal})).json();
  return pollJob(submitted.id,signal);
}
async function pollJob(id:string,signal?:AbortSignal){
  const cancel=()=>{void api(`jobs/${id}`,{method:'DELETE'}).catch(()=>{});};
  signal?.addEventListener('abort',cancel,{once:true});
  const deadline=Date.now()+300000;
  try {
  while(Date.now()<deadline){
    signal?.throwIfAborted();
    const state=await (await api(`jobs/${id}`,{signal})).json();
    if(state.state==='done')return {id,...state.result};
    if(state.state==='error')throw new Error(state.error||'Voice generation failed.');
    await new Promise<void>((resolve,reject)=>{const onAbort=()=>{clearTimeout(timer);reject(new DOMException('Cancelled','AbortError'));};const timer=setTimeout(()=>{signal?.removeEventListener('abort',onAbort);resolve();},250);signal?.addEventListener('abort',onAbort,{once:true});});
  }
  cancel();throw new Error('Voice generation took too long. Try a shorter passage.');
  } finally {signal?.removeEventListener('abort',cancel);}
}
const pcm=(samples:Float32Array)=>{const bytes=new Int16Array(samples.length);for(let i=0;i<samples.length;i++)bytes[i]=Math.round(Math.max(-1,Math.min(1,samples[i]))*32767);return bytes;};
function wavBlob(parts:Int16Array[]){
  const size=parts.reduce((n,p)=>n+p.byteLength,0);const data=new ArrayBuffer(44+size);const view=new DataView(data);
  const text=(offset:number,value:string)=>{for(let i=0;i<value.length;i++)view.setUint8(offset+i,value.charCodeAt(i));};
  text(0,'RIFF');view.setUint32(4,36+size,true);text(8,'WAVE');text(12,'fmt ');view.setUint32(16,16,true);view.setUint16(20,1,true);view.setUint16(22,1,true);view.setUint32(24,16000,true);view.setUint32(28,32000,true);view.setUint16(32,2,true);view.setUint16(34,16,true);text(36,'data');view.setUint32(40,size,true);
  let offset=44;for(const part of parts)for(const sample of part){view.setInt16(offset,sample,true);offset+=2;}
  return new Blob([data],{type:'audio/wav'});
}
function encoded(bytes:Int16Array){const raw=new Uint8Array(bytes.buffer,bytes.byteOffset,bytes.byteLength);let value='';for(const byte of raw)value+=String.fromCharCode(byte);return btoa(value);}

export function useMuseumVoice(language:string,onTranscript:(text:string,submit?:boolean)=>void,onAnswer:(answer:ArchiveAnswer)=>void,onVoiceError:()=>void=()=>{}){
  const [capabilities,setCapabilities]=useState<VoiceCapabilities|null>(null);
  const [status,setStatus]=useState('');const [speaking,setSpeaking]=useState(false);const [busy,setBusy]=useState(false);const [recording,setRecording]=useState(false);const [live,setLive]=useState(false);
  const [style,setStyle]=useState('museum');const [autoSpeak,setAutoSpeak]=useState(true);
  const [gender,setGender]=useState('auto');const [preferencesReady,setPreferencesReady]=useState(false);
  const voices=(capabilities?.voices?.[language]||[]).filter(voice=>voice.provider!=='parler-demo'&&!voice.experimental);
  const selectedVoice=voices.find(voice=>voice.gender===gender)||voices[0];
  const effectiveGender=selectedVoice?.gender||'auto';
  const callbacks=useRef({onTranscript,onAnswer,onVoiceError});callbacks.current={onTranscript,onAnswer,onVoiceError};
  const controller=useRef<AbortController|null>(null);const generation=useRef(0);
  const audio=useRef<HTMLAudioElement|null>(null);const audioUrl=useRef('');const socket=useRef<WebSocket|null>(null);
  const playback=useRef<AudioContext|null>(null);const sources=useRef<AudioBufferSourceNode[]>([]);const schedule=useRef(0);const accepting=useRef(true);
  const capture=useRef<{stream:MediaStream;context:AudioContext;node:AudioWorkletNode;parts:Int16Array[];timer:ReturnType<typeof setTimeout>}|null>(null);
  const stopSound=useCallback(()=>{
    controller.current?.abort();controller.current=null;generation.current++;
    audio.current?.pause();audio.current=null;if(audioUrl.current)URL.revokeObjectURL(audioUrl.current);audioUrl.current='';
    for(const source of sources.current){try{source.stop();}catch{}}sources.current=[];schedule.current=0;accepting.current=false;
    setSpeaking(false);setBusy(false);
  },[]);
  const releaseMic=useCallback(()=>{const mic=capture.current;if(!mic)return;capture.current=null;clearTimeout(mic.timer);mic.stream.getTracks().forEach(track=>track.stop());mic.node.disconnect();void mic.context.close();setRecording(false);},[]);
  const disconnect=useCallback(()=>{stopSound();releaseMic();socket.current?.close();socket.current=null;void playback.current?.close();playback.current=null;setLive(false);callbacks.current.onVoiceError();},[stopSound,releaseMic]);
  useEffect(()=>{try{const saved=JSON.parse(localStorage.getItem('smriti-voice-preferences')||'{}');if(['auto','female','male','original'].includes(saved.gender))setGender(saved.gender);if(['museum','conversation','calm'].includes(saved.style))setStyle(saved.style);if(typeof saved.autoSpeak==='boolean')setAutoSpeak(saved.autoSpeak);}catch{}setPreferencesReady(true);},[]);
  useEffect(()=>{if(preferencesReady)try{localStorage.setItem('smriti-voice-preferences',JSON.stringify({gender,style,autoSpeak}));}catch{}},[gender,style,autoSpeak,preferencesReady]);
  const refreshCapabilities=useCallback(async()=>{try{const data=await (await api('capabilities')).json();setCapabilities(data);setStatus('Voice availability updated.');}catch{setStatus('The voice service could not be reached. The website translation still works.');}},[]);
  useEffect(()=>{let active=true;api('capabilities').then(r=>r.json()).then(data=>{if(active)setCapabilities(data);}).catch(error=>{if(active)setStatus(error.message);});return()=>{active=false;};},[]);
  useEffect(()=>{disconnect();setStatus('');return disconnect;},[language,style,gender,effectiveGender,selectedVoice?.id,disconnect]);
  const narrate=useCallback(async(text:string,sourceLanguage=language)=>{
    if(!capabilities?.tts_languages.includes(language)){setStatus('No installed voice for this language. You can still read the translated answer.');return;}
    stopSound();const ticket=generation.current;const abort=new AbortController();controller.current=abort;
    setBusy(true);setStatus('Preparing museum narration…');
    try{
      // Translate before splitting: otherwise translated clause boundaries change
      // between individual model calls. Research answers already arrive translated.
      let nativeText=text;
      if(sourceLanguage!==language){const result=await voiceJob({kind:'translate',texts:[text],source_language:sourceLanguage,language},abort.signal);nativeText=result.translations[0];}
      const segments=narrationSegments(nativeText);
      if(!segments.length)throw new Error('No text to narrate.');
      const prepare=async(passage:string)=>{
        const result=await voiceJob({kind:'narrate',text:passage,language,source_language:language,style,gender:effectiveGender},abort.signal);
        return (await api(`jobs/${result.id}/audio`,{signal:abort.signal})).blob();
      };
      // At most one sentence is prefetched. The first starts playing while the next
      // is generated; cancellation aborts polling and prevents old-language audio.
      let pending=prepare(segments[0]);
      const element=new Audio();audio.current=element;
      for(let index=0;index<segments.length;index++){
        const blob=await pending;abort.signal.throwIfAborted();if(ticket!==generation.current)return;
        const next=index+1<segments.length?prepare(segments[index+1]):null;
        next?.catch(()=>{}); // Keep prefetched failures handled until they are awaited.
        if(audioUrl.current)URL.revokeObjectURL(audioUrl.current);
        audioUrl.current=URL.createObjectURL(blob);element.src=audioUrl.current;
        await new Promise<void>((resolve,reject)=>{
          const cleanup=()=>{abort.signal.removeEventListener('abort',cancel);element.onended=null;element.onerror=null;};
          const cancel=()=>{cleanup();reject(new DOMException('Cancelled','AbortError'));};
          abort.signal.addEventListener('abort',cancel,{once:true});
          element.onended=()=>{cleanup();resolve();};
          element.onerror=()=>{cleanup();reject(new Error('Audio playback failed. Try Listen again.'));};
          void element.play().then(()=>{if(ticket===generation.current){setSpeaking(true);setBusy(false);setStatus('Museum guide is speaking.');}})
            .catch(()=>{if(!abort.signal.aborted)setStatus('Audio is ready. Tap Play narration to listen.');});
        });
        if(next)pending=next;
      }
      if(ticket===generation.current){setSpeaking(false);setStatus('Narration finished.');}
    }catch(error){if(!abort.signal.aborted)setStatus(error instanceof Error?error.message:'Narration failed.');}
    finally{if(ticket===generation.current)setBusy(false);}
  },[language,style,effectiveGender,stopSound,capabilities]);
  const resume=async()=>{try{await audio.current?.play();setSpeaking(true);setStatus('Museum guide is speaking.');}catch{setStatus('Tap Listen to try playback again.');}};
  const startLive=async()=>{
    disconnect();setBusy(true);setStatus('Connecting museum guide…');const ticket=generation.current;
    try{
      // Create the audio context during the button gesture to satisfy mobile autoplay rules.
      playback.current=new AudioContext();await playback.current.resume();
      const session=await (await api('session',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({kind:'transcribe',language,style,gender:effectiveGender})})).json();
      if(ticket!==generation.current)return;
      const ws=new WebSocket(session.url);socket.current=ws;
      ws.onopen=()=>ws.send(JSON.stringify({token:session.token}));
      let readyResolve:(value:boolean)=>void=()=>{};
      const ready=new Promise<boolean>(resolve=>{readyResolve=resolve;});
      const readyTimeout=setTimeout(()=>readyResolve(false),12000);
      ws.onmessage=event=>{
        if(socket.current!==ws)return;
        const message=JSON.parse(event.data);
        if(message.type==='ready'){clearTimeout(readyTimeout);readyResolve(true);setLive(true);setBusy(false);setStatus('Live guide connected. Tap the microphone to ask; tap again to send.');}
        if(message.type==='transcript'){callbacks.current.onTranscript(message.text,false);setBusy(true);setStatus('Reading the archive…');}
        if(message.type==='answer'){callbacks.current.onAnswer(message);accepting.current=true;setBusy(false);setStatus('Your source-linked answer is ready.');}
        if(message.type==='error'){setBusy(false);callbacks.current.onVoiceError();setStatus(message.message);}
        if(message.type==='audio' && accepting.current && playback.current){
          const raw=Uint8Array.from(atob(message.audio),(v:string)=>v.charCodeAt(0));const samples=new DataView(raw.buffer);const ctx=playback.current;
          const buffer=ctx.createBuffer(1,raw.length/2,message.sample_rate);const output=buffer.getChannelData(0);for(let i=0;i<output.length;i++)output[i]=samples.getInt16(i*2,true)/32768;
          const node=ctx.createBufferSource();node.buffer=buffer;node.connect(ctx.destination);const begin=Math.max(ctx.currentTime+.025,schedule.current);schedule.current=begin+buffer.duration;node.start(begin);sources.current.push(node);setSpeaking(true);
          node.onended=()=>{sources.current=sources.current.filter(item=>item!==node);if(!sources.current.length)setSpeaking(false);};
        }
      };
      ws.onerror=()=>{clearTimeout(readyTimeout);readyResolve(false);setBusy(false);callbacks.current.onVoiceError();setStatus('Could not connect to live voice. Check the server URL and allowed website origin.');};
      ws.onclose=()=>{clearTimeout(readyTimeout);readyResolve(false);if(socket.current===ws){releaseMic();socket.current=null;setLive(false);setBusy(false);callbacks.current.onVoiceError();stopSound();setStatus('Live guide disconnected. You can reconnect or type a question.');}};
      const connected=await ready;
      if(!connected&&ticket===generation.current){disconnect();setStatus('Could not connect to live voice. Please try again.');}
      return connected&&ticket===generation.current;
    }catch(error){disconnect();setStatus(error instanceof Error?error.message:'Live voice failed.');return false;}finally{if(ticket===generation.current)setBusy(false);}
  };
  const finishRecording=async()=>{
    const mic=capture.current;if(!mic)return;
    const recordingTicket=generation.current;
    await new Promise<void>(resolve=>{const timer=setTimeout(resolve,120);const previous=mic.node.port.onmessage;mic.node.port.onmessage=event=>{if(event.data.flushed){clearTimeout(timer);resolve();}else previous?.call(mic.node.port,event);};mic.node.port.postMessage('flush');});
    if(capture.current!==mic||recordingTicket!==generation.current)return;
    const blob=wavBlob(mic.parts);releaseMic();
    if(socket.current?.readyState===WebSocket.OPEN){socket.current.send(JSON.stringify({type:'end'}));setBusy(true);setStatus('Transcribing your question…');return;}
    const ticket=generation.current;const abort=new AbortController();controller.current=abort;setBusy(true);setStatus('Transcribing your question…');
    try{
      const job=await (await api(`transcribe?language=${encodeURIComponent(language)}`,{method:'POST',headers:{'Content-Type':'audio/wav'},body:blob,signal:abort.signal})).json();
      const result=await pollJob(job.id,abort.signal);if(ticket===generation.current){setBusy(false);setStatus('Question transcribed.');callbacks.current.onTranscript(result.transcript);}
    }catch(error){if(!abort.signal.aborted)setStatus(error instanceof Error?error.message:'Transcription failed.');}finally{if(ticket===generation.current)setBusy(false);}
  };
  const toggleRecording=async()=>{
    if(capture.current){await finishRecording();return;}
    stopSound();setStatus('Allow microphone access, then ask your question.');
    const ticket=generation.current;
    try{
      const stream=await navigator.mediaDevices.getUserMedia({audio:{channelCount:1,echoCancellation:true,noiseSuppression:true,autoGainControl:true}});
      if(ticket!==generation.current){stream.getTracks().forEach(t=>t.stop());return;}
      const context=new AudioContext();await context.audioWorklet.addModule('/voice-capture.js');await context.resume();
      const node=new AudioWorkletNode(context,'smriti-capture');const source=context.createMediaStreamSource(stream);const mute=context.createGain();mute.gain.value=0;source.connect(node);node.connect(mute);mute.connect(context.destination);
      const parts:Int16Array[]=[];capture.current={stream,context,node,parts,timer:setTimeout(()=>void finishRecording(),29500)};
      node.port.onmessage=event=>{if(event.data.samples){const bytes=pcm(event.data.samples);parts.push(bytes);if(socket.current?.readyState===WebSocket.OPEN)socket.current.send(JSON.stringify({type:'audio',audio:encoded(bytes)}));}};
      if(socket.current?.readyState===WebSocket.OPEN)socket.current.send(JSON.stringify({type:'start'}));
      setRecording(true);setStatus('Listening… Tap the microphone again to send. Maximum 30 seconds.');
    }catch{releaseMic();setStatus('Microphone access was not available. Use HTTPS and allow the microphone, or type your question.');}
  };
  return {capabilities,status,setStatus,speaking,busy,recording,live,style,setStyle,gender,setGender,voices,selectedVoice,effectiveGender,refreshCapabilities,autoSpeak,setAutoSpeak,narrate,stop:()=>socket.current?disconnect():stopSound(),disconnect,toggleRecording,startLive,resume};
}
