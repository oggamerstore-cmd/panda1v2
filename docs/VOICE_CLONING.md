# PANDA.1 Voice Cloning Guide

## Overview

PANDA.1 uses Chatterbox TTS which supports voice cloning from a reference audio file. This allows you to customize PANDA.1's voice to sound like a specific person or character.

## Setting Up a Custom Voice

### Requirements

- A clear reference audio file (WAV format recommended)
- 5-30 seconds of speech
- Single speaker, minimal background noise
- Clear articulation

### Configuration

1. **Place your reference audio file:**
   ```bash
   # Create voices directory
   mkdir -p ~/.panda1/voices
   
   # Copy your reference audio
   cp your_reference.wav ~/.panda1/voices/panda_voice.wav
   ```

2. **Update configuration:**
   ```bash
   # Edit ~/.panda1/.env
   PANDA_TTS_REFERENCE_AUDIO=/home/bos/.panda1/voices/panda_voice.wav
   ```

3. **Restart PANDA.1:**
   ```bash
   panda --doctor  # Verify TTS is working
   panda --tts-test "Hello, I am PANDA speaking with my new voice."
   ```

## Finding Reference Audio

For an "old gentleman" voice similar to Charles Darwin or a Victorian scholar:

### Option 1: Audiobook Excerpts
- Look for public domain audiobook recordings of Victorian-era literature
- Sources like LibriVox have free audiobooks with various reader styles
- Extract a clean 10-20 second clip

### Option 2: Voice Actor Samples
- Many voice actors provide samples online
- Search for "British narrator voice samples" or "documentary narrator voice"
- Ensure you have rights to use the audio

### Option 3: AI-Generated Reference
- Use another TTS service to generate a reference in your desired style
- Save as WAV file and use as reference

## Audio Quality Tips

1. **Sample Rate:** 22050 Hz or higher
2. **Format:** WAV (PCM 16-bit) preferred
3. **Duration:** 10-30 seconds works best
4. **Content:** Complete sentences, varied intonation
5. **Noise:** Minimal background noise, no music

## Extracting Audio Clips

```bash
# Using ffmpeg to extract a clip from a longer file
ffmpeg -i source.mp3 -ss 00:01:30 -t 00:00:20 -ar 22050 -ac 1 reference.wav

# Convert to proper format
ffmpeg -i input.mp3 -ar 22050 -ac 1 -acodec pcm_s16le output.wav
```

## Troubleshooting

### Voice sounds different from reference
- Try a longer reference clip (20+ seconds)
- Ensure reference has varied intonation
- Check audio quality of reference

### TTS is slow
- Voice cloning adds processing overhead
- Consider using CPU if GPU VRAM is limited
- Shorter reference files process faster

### No voice cloning effect
- Verify the path in PANDA_TTS_REFERENCE_AUDIO is correct
- Check file permissions
- Run `panda --doctor` to verify configuration

## Voice Presets (Future)

We plan to add preset voices in future versions:
- Scholarly Gentleman (British male)
- Warm Assistant (Neutral)
- Professional (News anchor style)

For now, use reference audio for custom voices.

## Legal Note

When using voice cloning:
- Only use audio you have rights to
- Don't clone real people's voices without consent
- Voice cloning is intended for personal/private use
