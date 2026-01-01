"""
PANDA.1 Kokoro TTS (CUDA Accelerated)
======================================
Text-to-speech using Kokoro-82M with PyTorch CUDA 12.1 for RTX 2060.

Version: 0.2.10

Features:
- Kokoro-82M model with CUDA acceleration
- English voice: am_michael (American Male - Default)
- Korean voice: km_omega (Korean Male - Default)
- Real-time streaming synthesis (<100ms latency)
- GPU-accelerated inference (~0.4GB VRAM)
- Direct sounddevice playback for minimal latency

Hardware Requirements:
- NVIDIA GPU with CUDA support (RTX 2060 or better)
- CUDA 12.1+ drivers
- ~0.4GB VRAM for Kokoro-82M model

Installation:
- pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
- pip install kokoro soundfile
"""

import io
import time
import wave
import logging
import threading
from pathlib import Path
from typing import Optional, Literal, Generator, Tuple
from dataclasses import dataclass
from queue import Queue

logger = logging.getLogger(__name__)

# Try to import Kokoro with CUDA support
try:
    from kokoro import KPipeline
    import torch
    KOKORO_AVAILABLE = True
    CUDA_AVAILABLE = torch.cuda.is_available()
    if CUDA_AVAILABLE:
        logger.info(f"CUDA available: {torch.cuda.get_device_name(0)}")
    else:
        logger.warning("CUDA not available, will use CPU (slower)")
except ImportError as e:
    KOKORO_AVAILABLE = False
    CUDA_AVAILABLE = False
    KPipeline = None
    logger.warning(f"kokoro not available, TTS disabled: {e}")


@dataclass
class TTSResult:
    """TTS synthesis result."""
    success: bool
    audio_data: Optional[bytes] = None
    duration: float = 0.0
    sample_rate: int = 24000
    processing_time: float = 0.0
    error: Optional[str] = None


class KokoroTTS:
    """
    Kokoro-82M text-to-speech engine with CUDA acceleration.

    Optimized for RTX 2060 with CUDA 12.1 support.
    Uses ~0.4GB VRAM, leaving room for LLM inference.

    Usage:
        tts = KokoroTTS()
        tts.initialize()

        # Full synthesis
        result = tts.synthesize("Hello, I am PANDA!")

        # Streaming synthesis (recommended)
        for chunk in tts.synthesize_streaming("Long text..."):
            play_audio(chunk)
    """

    # Available voices (Kokoro-82M)
    VOICES = {
        "en": {
            "am_michael": "American Male (Michael) - Default",
            "af_sarah": "American Female (Sarah)",
            "af_nicole": "American Female (Nicole)",
            "af_bella": "American Female (Bella)",
            "af_sky": "American Female (Sky)",
            "bf_emma": "British Female (Emma)",
            "bf_isabella": "British Female (Isabella)",
            "bm_george": "British Male (George)",
            "bm_lewis": "British Male (Lewis)",
        },
        "ko": {
            "km_omega": "Korean Male (Omega) - Default",
            "kf_alpha": "Korean Female (Alpha)",
        }
    }

    def __init__(
        self,
        voice_en: str = "am_michael",
        voice_ko: str = "km_omega",
        speed: float = 1.0,
        device: str = "cuda",
        cache_dir: Optional[Path] = None,
    ):
        """
        Initialize Kokoro TTS with CUDA acceleration.

        Args:
            voice_en: English voice ID (default: am_michael)
            voice_ko: Korean voice ID (default: km_omega)
            speed: Speech speed multiplier (0.5 - 2.0)
            device: Device for inference (cuda, cpu)
            cache_dir: Model cache directory
        """
        self.voice_en = voice_en
        self.voice_ko = voice_ko
        self.speed = max(0.5, min(2.0, speed))

        # Auto-select device
        if device == "cuda" and not CUDA_AVAILABLE:
            logger.warning("CUDA requested but not available, falling back to CPU")
            device = "cpu"
        self.device = device

        self.cache_dir = cache_dir or Path.home() / ".panda1" / "cache" / "kokoro"

        self._pipeline_en: Optional[KPipeline] = None
        self._pipeline_ko: Optional[KPipeline] = None
        self._initialized = False
        self._lock = threading.Lock()

        # Audio settings (Kokoro-82M outputs at 24kHz)
        self.sample_rate = 24000

    @property
    def is_available(self) -> bool:
        """Check if Kokoro is available."""
        return KOKORO_AVAILABLE

    @property
    def is_initialized(self) -> bool:
        """Check if TTS is initialized."""
        return self._initialized

    @property
    def using_cuda(self) -> bool:
        """Check if using CUDA acceleration."""
        return self.device == "cuda" and CUDA_AVAILABLE

    def initialize(self, lang: str = "en") -> bool:
        """
        Initialize the TTS engine with CUDA support.

        Args:
            lang: Language to initialize (en, ko, both)

        Returns:
            True if initialized successfully
        """
        if not KOKORO_AVAILABLE:
            logger.error("kokoro not installed")
            logger.error("Install: pip install kokoro soundfile")
            logger.error("For CUDA: pip install torch --index-url https://download.pytorch.org/whl/cu121")
            return False

        try:
            start_time = time.time()
            self.cache_dir.mkdir(parents=True, exist_ok=True)

            # Initialize English pipeline
            if lang in ("en", "both") and self._pipeline_en is None:
                logger.info(f"Initializing Kokoro English pipeline (device={self.device})...")
                # 'a' for American English
                self._pipeline_en = KPipeline(lang_code='a', device=self.device)
                logger.info("English pipeline ready")

            # Initialize Korean pipeline
            if lang in ("ko", "both") and self._pipeline_ko is None:
                logger.info(f"Initializing Kokoro Korean pipeline (device={self.device})...")
                try:
                    # 'k' for Korean
                    self._pipeline_ko = KPipeline(lang_code='k', device=self.device)
                    logger.info("Korean pipeline ready")
                except Exception as e:
                    logger.warning(f"Korean pipeline failed: {e}")
                    logger.info("Falling back to English pipeline for Korean")
                    self._pipeline_ko = self._pipeline_en or KPipeline(lang_code='a', device=self.device)

            load_time = time.time() - start_time

            device_info = f"CUDA ({torch.cuda.get_device_name(0)})" if self.using_cuda else "CPU"
            logger.info(f"Kokoro TTS initialized on {device_info} in {load_time:.2f}s")

            if self.using_cuda:
                vram_allocated = torch.cuda.memory_allocated(0) / 1024**3
                logger.info(f"VRAM allocated: {vram_allocated:.2f} GB")

            self._initialized = True
            return True

        except Exception as e:
            logger.error(f"Failed to initialize Kokoro: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _get_pipeline(self, lang: str) -> Optional[KPipeline]:
        """Get the appropriate pipeline for language."""
        if lang == "ko":
            if self._pipeline_ko is None:
                self.initialize("ko")
            return self._pipeline_ko
        else:
            if self._pipeline_en is None:
                self.initialize("en")
            return self._pipeline_en

    def _get_voice(self, lang: str) -> str:
        """Get voice ID for language."""
        return self.voice_ko if lang == "ko" else self.voice_en

    def synthesize(
        self,
        text: str,
        lang: str = "en",
    ) -> TTSResult:
        """
        Synthesize text to speech with CUDA acceleration.

        Args:
            text: Text to synthesize
            lang: Language (en, ko)

        Returns:
            TTSResult with audio data
        """
        if not text.strip():
            return TTSResult(success=False, error="Empty text")

        start_time = time.time()

        try:
            with self._lock:
                pipeline = self._get_pipeline(lang)
                if not pipeline:
                    return TTSResult(success=False, error="Pipeline not initialized")

                voice = self._get_voice(lang)

                logger.debug(f"Synthesizing: '{text[:50]}...' (lang={lang}, voice={voice}, device={self.device})")

                # Generate audio with streaming
                generator = pipeline(
                    text,
                    voice=voice,
                    speed=self.speed,
                    split_pattern=r'\n+'
                )

                # Collect all audio chunks
                audio_chunks = []
                for _, _, audio in generator:
                    if audio is not None and len(audio) > 0:
                        audio_chunks.append(audio)

                if not audio_chunks:
                    return TTSResult(success=False, error="No audio generated")

                # Concatenate audio
                import numpy as np
                full_audio = np.concatenate(audio_chunks)

                # Convert to WAV bytes
                wav_bytes = self._to_wav_bytes(full_audio)

                duration = len(full_audio) / self.sample_rate
                processing_time = time.time() - start_time

                logger.debug(
                    f"Synthesized in {processing_time:.3f}s "
                    f"(dur={duration:.2f}s, RTF={processing_time/duration:.2f}x)"
                )

                return TTSResult(
                    success=True,
                    audio_data=wav_bytes,
                    duration=duration,
                    sample_rate=self.sample_rate,
                    processing_time=processing_time,
                )

        except Exception as e:
            logger.error(f"Synthesis failed: {e}")
            traceback.print_exc()
            return TTSResult(
                success=False,
                error=str(e),
                processing_time=time.time() - start_time,
            )

    def synthesize_streaming(
        self,
        text: str,
        lang: str = "en",
    ) -> Generator[bytes, None, None]:
        """
        Synthesize text to speech with streaming output for low latency.

        This is the recommended method for real-time applications.
        Yields audio chunks as they're generated (<100ms latency).

        Args:
            text: Text to synthesize
            lang: Language (en, ko)

        Yields:
            WAV audio chunks (can be played directly with sounddevice)
        """
        if not text.strip():
            return

        try:
            with self._lock:
                pipeline = self._get_pipeline(lang)
                if not pipeline:
                    logger.error("Pipeline not initialized")
                    return

                voice = self._get_voice(lang)

                logger.debug(f"Streaming synthesis: '{text[:50]}...' (voice={voice})")

                # Generate audio with streaming for low latency
                generator = pipeline(
                    text,
                    voice=voice,
                    speed=self.speed,
                    split_pattern=r'\n+'
                )

                for i, (_, _, audio) in enumerate(generator):
                    if audio is not None and len(audio) > 0:
                        wav_bytes = self._to_wav_bytes(audio)
                        yield wav_bytes

        except Exception as e:
            logger.error(f"Streaming synthesis failed: {e}")
            traceback.print_exc()

    def _to_wav_bytes(self, audio_data) -> bytes:
        """Convert numpy audio to WAV bytes."""

        # Ensure audio is float32 and in range [-1, 1]
        audio = np.clip(audio_data, -1.0, 1.0)

        # Convert to int16
        audio_int16 = (audio * 32767).astype(np.int16)

        # Create WAV file in memory
        buffer = io.BytesIO()
        with wave.open(buffer, 'wb') as wav:
            wav.setnchannels(1)  # Mono
            wav.setsampwidth(2)  # 16-bit
            wav.setframerate(self.sample_rate)
            wav.writeframes(audio_int16.tobytes())

        return buffer.getvalue()

    def get_status(self) -> dict:
        """Get TTS engine status."""
        status = {
            "available": KOKORO_AVAILABLE,
            "initialized": self._initialized,
            "voice_en": self.voice_en,
            "voice_ko": self.voice_ko,
            "speed": self.speed,
            "sample_rate": self.sample_rate,
            "device": self.device,
            "cuda_available": CUDA_AVAILABLE,
            "using_cuda": self.using_cuda,
            "pipeline_en_ready": self._pipeline_en is not None,
            "pipeline_ko_ready": self._pipeline_ko is not None,
        }

        if self.using_cuda:
            try:
                status["cuda_device"] = torch.cuda.get_device_name(0)
                status["vram_allocated_gb"] = torch.cuda.memory_allocated(0) / 1024**3
                status["vram_reserved_gb"] = torch.cuda.memory_reserved(0) / 1024**3
            except Exception as e:
                logging.error(f'Exception caught: {e}')
                pass

        return status


# Global TTS instance
_tts_instance: Optional[KokoroTTS] = None


def get_tts(
    voice_en: str = "am_michael",
    voice_ko: str = "km_omega",
    speed: float = 1.0,
    device: str = "cuda",
) -> KokoroTTS:
    """
    Get or create the global TTS instance.

    Args:
        voice_en: English voice (default: am_michael)
        voice_ko: Korean voice (default: km_omega)
        speed: Speech speed
        device: Device for inference (cuda, cpu)

    Returns:
        KokoroTTS instance
    """
    global _tts_instance

    if _tts_instance is None:
        _tts_instance = KokoroTTS(
            voice_en=voice_en,
            voice_ko=voice_ko,
            speed=speed,
            device=device,
        )

    return _tts_instance


def speak(text: str, lang: str = "en") -> TTSResult:
    """
    Quick synthesis helper.

    Args:
        text: Text to speak
        lang: Language (en, ko)

    Returns:
        TTSResult
    """
    tts = get_tts()
    if not tts.is_initialized:
        tts.initialize(lang)
    return tts.synthesize(text, lang)


def detect_language(text: str) -> str:
    """
    Detect language from text (simple heuristic).

    Args:
        text: Text to analyze

    Returns:
        Language code (en, ko)
    """
    # Count Korean characters (Hangul syllables and Jamo)
    korean_chars = sum(1 for c in text if '\uac00' <= c <= '\ud7a3' or '\u1100' <= c <= '\u11ff')
    total_chars = len([c for c in text if c.isalpha()])

    if total_chars == 0:
        return "en"

    korean_ratio = korean_chars / total_chars
    return "ko" if korean_ratio > 0.3 else "en"


def test_tts(text: str = "Hello, I am PANDA!", lang: str = "en") -> None:
    """
    Test TTS synthesis with CUDA acceleration (CLI helper).

    Args:
        text: Text to synthesize
        lang: Language (en, ko)
    """
    logging.info(f"\n{'='*60}")
    logging.info("  PANDA.1 TTS Test (Kokoro-82M with CUDA)")
    logging.info(f"{'='*60}")

    if not KOKORO_AVAILABLE:
        logging.info("\n  ❌ kokoro not installed!")
        logging.info("  Run: pip install kokoro soundfile")
        logging.info("  CUDA: pip install torch --index-url https://download.pytorch.org/whl/cu121")
        return

    logging.info(f"\n  Text: {text}")
    logging.info(f"  Language: {lang}")
    logging.info(f"  CUDA Available: {CUDA_AVAILABLE}")

    if CUDA_AVAILABLE:
        logging.info(f"  GPU: {torch.cuda.get_device_name(0)}")

    tts = get_tts()

    logging.info("\n  Initializing...")
    if not tts.initialize(lang):
        logging.error("  ❌ Failed to initialize")
        return

    logging.info(f"  Device: {tts.device}")
    logging.info("  Synthesizing...")

    start = time.time()
    result = tts.synthesize(text, lang)
    total_time = time.time() - start

    logging.info(f"\n  {'='*50}")
    if result.success:
        logging.info(f"  ✅ Success!")
        logging.info(f"  Duration: {result.duration:.2f}s")
        logging.info(f"  Processing: {result.processing_time:.3f}s")
        logging.info(f"  Real-time Factor: {result.processing_time/result.duration:.2f}x")
        logging.info(f"  Audio size: {len(result.audio_data)} bytes")

        # Save test audio
        test_path = Path.home() / ".panda1" / "audio_out" / "tts_test.wav"
        test_path.parent.mkdir(parents=True, exist_ok=True)
        with open(test_path, 'wb') as f:
            f.write(result.audio_data)
        logging.info(f"  Saved to: {test_path}")

        # Try to play with sounddevice
        try:
            import sounddevice as sd

            # Read WAV data
            wav_io = io.BytesIO(result.audio_data)
            with wave.open(wav_io, 'rb') as wav:
                frames = wav.readframes(wav.getnframes())
                audio = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32767

            logging.info("  Playing...")
            sd.play(audio, result.sample_rate)
            sd.wait()
            logging.info("  ✅ Playback complete")

        except Exception as e:
            logging.error(f"  ⚠ Playback failed: {e}")
            logging.info(f"  You can manually play: {test_path}")
    else:
        logging.error(f"  ❌ Failed: {result.error}")

    logging.info()


if __name__ == "__main__":
    # Test with English
    test_tts("Hello! I am PANDA, your AI assistant.", "en")

    # Test with Korean
    test_tts("안녕하세요! 저는 PANDA입니다.", "ko")
