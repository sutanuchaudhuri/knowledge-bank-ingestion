// Captures microphone audio at the context rate and emits mono PCM16 frames at the target rate (default 16 kHz).
class PcmCapture extends AudioWorkletProcessor {
  constructor(options) {
    super();
    this.target = options.processorOptions?.targetRate || 16000;
    this.frame = Math.round(this.target * 0.04); // 40 ms frames
    this.ratio = sampleRate / this.target;
    this.position = 0;
    this.last = 0;
    this.pending = [];
  }

  process(inputs) {
    const channel = inputs[0]?.[0];
    if (!channel) return true;
    let peak = 0;
    // Linear-interpolation resampling; index -1 is the previous block's last sample, so blocks join seamlessly.
    const at = (i) => (i < 0 ? this.last : channel[i]);
    while (this.position < channel.length - 1) {
      const index = Math.floor(this.position);
      const fraction = this.position - index;
      const value = at(index) + (at(index + 1) - at(index)) * fraction;
      this.pending.push(value);
      peak = Math.max(peak, Math.abs(value));
      this.position += this.ratio;
    }
    this.last = channel[channel.length - 1];
    this.position -= channel.length;
    while (this.pending.length >= this.frame) {
      const chunk = this.pending.splice(0, this.frame);
      const pcm = new Int16Array(chunk.length);
      for (let i = 0; i < chunk.length; i++) {
        const s = Math.max(-1, Math.min(1, chunk[i]));
        pcm[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
      }
      this.port.postMessage({ pcm: pcm.buffer, peak }, [pcm.buffer]);
    }
    return true;
  }
}

registerProcessor("pcm-capture", PcmCapture);
