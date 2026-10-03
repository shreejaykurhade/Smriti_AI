import { Check, Headphones, Mic2, RefreshCw, Square, UserRound, Volume2 } from 'lucide-react';
import type { useMuseumVoice } from './useMuseumVoice';
import { LocalizedInterface } from '../i18n/LocalizedInterface';

export function VoiceControls({voice,preview,language}:{voice:ReturnType<typeof useMuseumVoice>;preview:()=>void;language:string}) {
  return <LocalizedInterface language={language}><section className="guide-controls" aria-label="Choose your narrator">
    <div className="guide-heading"><Headphones/><div><strong>Your museum guide</strong><span>Choose a voice. Listen at your pace.</span></div></div>
    <div className="speaker-options" role="group" aria-label="Voice type">
      {voice.voices.map(speaker=><button key={speaker.id} type="button" aria-pressed={voice.selectedVoice?.id===speaker.id}
        className={voice.selectedVoice?.id===speaker.id?'selected':''} onClick={()=>voice.setGender(speaker.gender)}>
        <UserRound aria-hidden="true"/><span><b>{speaker.gender==='female'?'Female':speaker.gender==='male'?'Male':'Original speaker'}</b><small translate="no">{speaker.name}</small></span>
        {voice.selectedVoice?.id===speaker.id&&<Check className="speaker-selected" aria-hidden="true"/>}
      </button>)}
      {!voice.voices.length&&<p>Connect the voice service to choose a narrator.</p>}
    </div>
    <div className="guide-toolbar">
      <label>Delivery<select aria-label="Narration style" value={voice.style} onChange={e=>voice.setStyle(e.target.value)}>
        <option value="museum">Museum guide</option><option value="conversation">Conversation</option><option value="calm">Calm narration</option>
      </select></label>
      <button onClick={preview} disabled={voice.busy||!voice.selectedVoice}><Volume2/>Preview voice</button>
      <label className="voice-auto"><input type="checkbox" checked={voice.autoSpeak} onChange={e=>voice.setAutoSpeak(e.target.checked)}/>Read answers aloud</label>
    </div>
    <div className="guide-session"><button onClick={()=>voice.capabilities?.mode==='serverless'?void voice.toggleRecording():voice.live?voice.disconnect():void voice.startLive()} disabled={!voice.recording&&!voice.live&&(voice.busy||!voice.capabilities?.stt||!voice.capabilities.stt_languages.includes(language)||!voice.selectedVoice)}>
      {voice.recording||voice.live?<Square/>:<Mic2/>}{voice.capabilities?.mode==='serverless'?(voice.recording?'Send question':'Ask with your voice'):voice.live?'End live guide':'Start live guide'}</button>
      <button className="voice-refresh" aria-label="Refresh voices" onClick={()=>void voice.refreshCapabilities()}><RefreshCw/>Refresh voices</button>
      {voice.status.startsWith('Audio is ready')&&<button onClick={()=>void voice.resume()}>Play narration</button>}
    </div>
    {voice.selectedVoice?.gender==='original'&&<small className="single-speaker-note">This language has one original speaker. Male and female choices are available in other languages.</small>}
    <details className="voice-details"><summary>About this voice</summary><p>A generated museum guide, not a historical recording of Dr. Ambedkar.</p>
      {voice.selectedVoice?.online?<p>Online narration sends the spoken text to Microsoft’s speech service.</p>:<p>Voice generation runs on the connected model server.</p>}
      {voice.capabilities?.mode==='serverless'&&<p>Browser voice input uses your browser’s speech service.</p>}
    </details>
    {voice.capabilities?.mode==='serverless'&&!voice.capabilities.stt&&<small>Voice input is not supported in this browser. You can type your question.</small>}
  </section></LocalizedInterface>;
}
