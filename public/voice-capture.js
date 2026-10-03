/* Local microphone capture; no external recognition SDK or recording storage. */
class SmritiCapture extends AudioWorkletProcessor {
  constructor() {
    super(); this.samples=[]; this.sum=0; this.count=0; this.phase=0;
    this.port.onmessage=event=>{if(event.data==='flush'){this.flush();this.port.postMessage({flushed:true});}};
  }
  flush(){if(this.samples.length){this.port.postMessage({samples:new Float32Array(this.samples)});this.samples=[];}}
  process(inputs) {
    const input=inputs[0]?.[0];
    if(input) for(const sample of input){
      this.sum+=sample; this.count++; this.phase+=16000;
      if(this.phase>=sampleRate){this.samples.push(this.sum/this.count);this.phase-=sampleRate;this.sum=0;this.count=0;}
      if(this.samples.length>=1280)this.flush();
    }
    return true;
  }
}
registerProcessor('smriti-capture',SmritiCapture);
