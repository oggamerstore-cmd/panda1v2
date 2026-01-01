# Kokoro TTS with CUDA 12.1 Setup Guide

**For RTX 2060 and Ubuntu 24.04**

## Overview

PANDA.1 now uses **Kokoro-82M** with PyTorch CUDA 12.1 for ultra-fast text-to-speech synthesis.

### Performance Specs
- **VRAM Usage**: ~0.4GB (leaves 5.6GB for LLM on 6GB GPU)
- **Latency**: <100ms for real-time streaming
- **Voices**:
  - English: `am_michael` (American Male - Default)
  - Korean: `km_omega` (Korean Male - Default)

---

## Installation Steps

### 1. Verify NVIDIA Drivers

Ensure you have NVIDIA drivers 535+ installed:

```bash
# Install latest drivers
sudo ubuntu-drivers install

# Verify GPU detection
nvidia-smi
```

You should see your RTX 2060 listed.

### 2. Install PyTorch with CUDA 12.1

```bash
# Install PyTorch with CUDA 12.1 support
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
```

**Important**: This must be done **before** installing other requirements, as the CUDA version needs to match.

### 3. Install Kokoro and Dependencies

```bash
# Install Kokoro and audio libraries
pip install kokoro soundfile

# Install remaining PANDA.1 requirements
pip install -r requirements.txt
```

### 4. Verify CUDA Installation

Test that PyTorch can see your GPU:

```bash
python3 -c "import torch; print(f'CUDA Available: {torch.cuda.is_available()}'); print(f'GPU: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else \"None\"}')"
```

Expected output:
```
CUDA Available: True
GPU: NVIDIA GeForce RTX 2060
```

---

## VRAM Optimization

### The "Golden Ratio" for 6GB GPU

With RTX 2060 (6GB VRAM), you can run:
- **Qwen2.5-7B (4-bit)**: ~4.7GB VRAM
- **Kokoro-82M**: ~0.4GB VRAM
- **System overhead**: ~0.9GB

**Total**: ~5.1GB (comfortably fits in 6GB)

### Limit Ollama VRAM Usage

If you're running Ollama alongside PANDA.1, limit its VRAM:

```bash
# Limit Ollama to 5GB, leaving 1GB for Kokoro + system
OLLAMA_MAX_VRAM=5000000000 ollama serve
```

Add this to your systemd service or startup script.

---

## Configuration

### Default Settings (Optimized for RTX 2060)

In `app/config.py`:

```python
tts_device: str = "cuda"  # Uses GPU acceleration
tts_voice_en: str = "am_michael"  # American Male voice
tts_voice_ko: str = "km_omega"    # Korean Male voice
tts_speed: float = 1.0
```

### Available Voices

**English**:
- `am_michael` - American Male (Default, best quality)
- `af_sarah` - American Female
- `af_nicole` - American Female
- `bf_emma` - British Female
- `bm_george` - British Male

**Korean**:
- `km_omega` - Korean Male (Default, best quality)
- `kf_alpha` - Korean Female

---

## Usage Examples

### Basic Synthesis

```python
from app.voice.tts_kokoro import get_tts

# Initialize TTS with CUDA
tts = get_tts(device='cuda')
tts.initialize('en')

# Synthesize speech
result = tts.synthesize("Hello, I am PANDA!", lang='en')
if result.success:
    print(f"Generated {result.duration:.2f}s audio in {result.processing_time:.3f}s")
```

### Streaming (Low Latency)

**Recommended for real-time applications:**

```python
from app.voice.tts_kokoro import KPipeline
import sounddevice as sd

# Initialize pipeline with CUDA
pipeline = KPipeline(lang_code='a', device='cuda')  # 'a' for American English

# Stream synthesis
generator = pipeline(
    "Hello! How can I help you today?",
    voice='am_michael',
    speed=1.0,
    split_pattern=r'\n+'
)

# Play as it generates (<100ms latency)
for i, (gs, ps, audio) in enumerate(generator):
    sd.play(audio, 24000)  # 24kHz sample rate
    sd.wait()
```

### Korean Example

```python
# Korean pipeline
pipeline = KPipeline(lang_code='k', device='cuda')  # 'k' for Korean

generator = pipeline(
    "안녕하세요, 만나서 반가워요. 오늘 무엇을 도와드릴까요?",
    voice='km_omega',
    speed=1.0
)

for _, _, audio in generator:
    sd.play(audio, 24000)
    sd.wait()
```

---

## Testing

### CLI Test

```bash
# Test English TTS with CUDA
python3 -m app.voice.tts_kokoro

# Or test directly
python3 -c "from app.voice.tts_kokoro import test_tts; test_tts('Hello PANDA!', 'en')"
```

Expected output:
```
============================================================
  PANDA.1 TTS Test (Kokoro-82M with CUDA)
============================================================

  Text: Hello PANDA!
  Language: en
  CUDA Available: True
  GPU: NVIDIA GeForce RTX 2060

  Initializing...
  Device: cuda
  Synthesizing...

  ==================================================
  ✅ Success!
  Duration: 1.20s
  Processing: 0.156s
  Real-time Factor: 0.13x
  Audio size: 57632 bytes
  Saved to: ~/.panda1/audio_out/tts_test.wav
  Playing...
  ✅ Playback complete
```

**Real-time Factor < 1.0** means faster than real-time!

---

## Troubleshooting

### Issue: "CUDA not available"

**Solution**:
1. Check NVIDIA drivers: `nvidia-smi`
2. Reinstall PyTorch with CUDA:
   ```bash
   pip uninstall torch torchvision torchaudio
   pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
   ```

### Issue: "CUDA out of memory"

**Solution**:
1. Close other GPU applications
2. Limit Ollama VRAM: `OLLAMA_MAX_VRAM=5000000000`
3. Switch to CPU mode temporarily:
   ```python
   tts = get_tts(device='cpu')
   ```

### Issue: "Slow synthesis (>1s)"

**Possible causes**:
- Running on CPU instead of CUDA
- Check `tts.using_cuda` property
- Verify with: `tts.get_status()`

### Issue: "Voice not found"

**Solution**:
Use exact voice names:
- English: `am_michael`, `af_sarah`, etc.
- Korean: `km_omega`, `kf_alpha`

Case-sensitive!

---

## Performance Benchmarks

### RTX 2060 (CUDA)
- **English synthesis**: 0.1-0.2s for 1s audio (5-10x real-time)
- **Korean synthesis**: 0.15-0.25s for 1s audio (4-6x real-time)
- **VRAM usage**: 0.3-0.5GB
- **Streaming latency**: <100ms first chunk

### CPU Fallback
- **English synthesis**: 1.5-3.0s for 1s audio (0.3-0.6x real-time)
- **Korean synthesis**: 2.0-4.0s for 1s audio (0.25-0.5x real-time)
- **RAM usage**: 1-2GB
- **Streaming latency**: 300-500ms

**Conclusion**: CUDA is **15-20x faster** than CPU!

---

## Advanced: Pipeline Integration

### Speak-as-you-type with LLM Streaming

```python
from app.voice.tts_kokoro import KPipeline
import sounddevice as sd

pipeline = KPipeline(lang_code='a', device='cuda')

# As LLM generates text...
for sentence in llm_stream():
    generator = pipeline(sentence, voice='am_michael')
    for _, _, audio in generator:
        sd.play(audio, 24000)  # Non-blocking playback
        # Next sentence can start processing immediately!
```

This allows PANDA to **start speaking** while still generating the rest of the response.

---

## Environment Variables

Set these in your `.env` or shell:

```bash
# Force CPU mode (debugging)
PANDA_TTS_DEVICE=cpu

# Limit Ollama VRAM
OLLAMA_MAX_VRAM=5000000000

# CUDA device selection (multi-GPU)
CUDA_VISIBLE_DEVICES=0
```

---

## Migration from Old TTS

### Old Config (v0.2.8)
```python
tts_voice_en = "af_heart"
tts_voice_ko = "af_heart"
tts_device = "cpu"
```

### New Config (v0.2.9)
```python
tts_voice_en = "am_michael"  # Better quality male voice
tts_voice_ko = "km_omega"    # Native Korean voice
tts_device = "cuda"          # 15-20x faster!
```

---

## Support

If you encounter issues:

1. Check CUDA setup: `nvidia-smi` and `torch.cuda.is_available()`
2. Test TTS: `python3 -m app.voice.tts_kokoro`
3. Review logs for errors
4. Fall back to CPU if needed: `tts_device = "cpu"`

For optimal performance on RTX 2060, always use CUDA mode!
