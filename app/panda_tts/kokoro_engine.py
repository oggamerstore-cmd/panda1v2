"""
PANDA.1 Kokoro TTS Engine
=========================
Lightweight TTS using Kokoro-82M (hexgrad/Kokoro-82M).

Version: 2.0

Features:
- 82M parameter model (~80MB) - very lightweight
- CPU-optimized to preserve GPU VRAM for LLM
- Michael male voice (am_michael)
- Fast synthesis for quick response
- Supports up to 90 seconds of continuous speech
- 24kHz sample rate output
"""

import os
import inspect
import logging
import time
import threading
from pathlib import Path
from typing import Optional, Dict, Any, Literal

from .base import TTSEngine, chunk_text
from .playback import get_player

logger = logging.getLogger(__name__)

# Kokoro voice mappings
KOKORO_VOICES = {
    "en": "am_michael",    # American English - Michael (male)
    "ko": "am_michael",    # Use English voice for Korean (Kokoro doesn't support Korean natively)
}

# Maximum text length per synthesis chunk (roughly 90 seconds of speech)
# Kokoro: ~1000 chars = ~1 minute, so 1500 chars ≈ 90 seconds
MAX_CHUNK_CHARS = 1500


class KokoroEngine(TTSEngine):
    """
    Kokoro TTS Engine (lightweight, CPU-optimized).

    Uses Kokoro-82M model with Michael voice for natural speech.
    Optimized for quick response and smooth playback.
    """

    name = "kokoro"

    def __init__(
        self,
        voice: str = "michael",
        speed: float = 1.0,
        output_dir: Optional[Path] = None,
        device: str = "cpu",
    ):
        """
        Initialize Kokoro engine.

        Args:
            voice: Voice ID (default: michael for Michael)
            speed: Speech speed multiplier (0.5-2.0)
            output_dir: Audio output directory
            device: Device for inference (cpu recommended to save GPU for LLM)
        """
        super().__init__()

        self._voice = "am_michael" if voice == "michael" else voice
        self._speed = max(0.5, min(2.0, speed))
        self._device = device
        self._output_dir = output_dir or Path.home() / ".panda1" / "audio_out"

        # Pipeline reference
        self._pipeline = None

        # Threading for non-blocking playback
        self._speak_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._speak_lock = threading.Lock()

        # Create output directory
        self._output_dir.mkdir(parents=True, exist_ok=True)

        logger.info(
            "KokoroEngine initialized (voice=%s, speed=%s, device=%s)",
            self._voice,
            self._speed,
            self._device,
        )

    def warmup(self) -> bool:
        """Load Kokoro pipeline."""
        try:
            logger.info("Warming up Kokoro TTS...")

            # Initialize pipeline for American English
            # 'a' = American English
            self._pipeline = self._create_pipeline(lang_code='a')

            # Verify voice is available by doing a quick test synthesis
            logger.info(f"Testing voice: {self._voice}")
            test_gen = self._pipeline("test", voice=self._voice, speed=self._speed)
            for _, _, audio in test_gen:
                if audio is not None and len(audio) > 0:
                    self._is_warmed_up = True
                    logger.info("Kokoro warmup complete")
                    return True
                break

            logger.error("Kokoro warmup failed - no audio generated")
            return False

        except RuntimeError as e:
            if self._should_retry_on_cpu(e):
                return self._retry_on_cpu("warmup")
            logger.error(f"Kokoro warmup failed: {e}")
            self._is_warmed_up = False
            return False
        except Exception as e:
            if isinstance(e, ModuleNotFoundError) and e.name == "kokoro":
                logger.error(f"Kokoro not installed: {e}")
                logger.info("Install with: pip install kokoro soundfile")
            else:
                logger.error(f"Kokoro warmup failed: {e}")
            self._is_warmed_up = False
            return False

    def synthesize(
        self,
        text: str,
        lang: Literal["en", "ko"] = "en",
        output_path: Optional[Path] = None
    ) -> Optional[Path]:
        """Synthesize text to audio file."""
        if not text.strip():
            return None

        try:
            # Ensure pipeline is loaded
            if not self._is_warmed_up or self._pipeline is None:
                if not self.warmup():
                    return None

            # Generate output path
            if output_path is None:
                timestamp = int(time.time() * 1000)
                output_path = self._output_dir / f"kokoro_{timestamp}.wav"

            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # Get voice for language
            voice = KOKORO_VOICES.get(lang, self._voice)

            # Synthesize
            logger.debug(f"Synthesizing ({lang}): {text[:50]}...")

            # Collect all audio chunks
            audio_chunks = []
            generator = self._pipeline(text, voice=voice, speed=self._speed)

            for graphemes, phonemes, audio in generator:
                if audio is not None:
                    audio_chunks.append(audio)

            if not audio_chunks:
                logger.error("No audio generated")
                return None

            # Concatenate audio chunks
            import numpy as np
            full_audio = np.concatenate(audio_chunks) if len(audio_chunks) > 1 else audio_chunks[0]

            # Save as WAV (24kHz sample rate)
            try:
                import soundfile as sf
                sf.write(str(output_path), full_audio, 24000, subtype='PCM_16')
            except ImportError:
                # Fallback to scipy
                from scipy.io import wavfile
                # Normalize to int16
                audio_int16 = (full_audio * 32767).astype(np.int16)
                wavfile.write(str(output_path), 24000, audio_int16)

            logger.debug(f"Audio saved: {output_path}")
            return output_path

        except RuntimeError as e:
            if self._should_retry_on_cpu(e):
                if self._retry_on_cpu("synthesis"):
                    return self.synthesize(text, lang, output_path)
            logger.error(f"Kokoro synthesis failed: {e}")
            return None
        except Exception as e:
            logger.error(f"Kokoro synthesis failed: {e}")
            return None

    def speak(
        self,
        text: str,
        lang: Literal["en", "ko"] = "en",
        blocking: bool = False
    ) -> bool:
        """Synthesize and play text."""
        if not text.strip():
            return False

        if blocking:
            return self._speak_sync(text, lang)
        else:
            return self._speak_async(text, lang)

    def _speak_sync(self, text: str, lang: str) -> bool:
        """Synchronous speak with chunking for long text."""
        # Use larger chunks for Kokoro (supports up to ~90s)
        chunks = chunk_text(text, max_chars=MAX_CHUNK_CHARS)
        player = get_player()
        success = True

        for chunk in chunks:
            if self._stop_event.is_set():
                break

            audio_path = self.synthesize(chunk, lang)
            if audio_path:
                player.play(audio_path, blocking=True)
            else:
                success = False

        return success

    def _create_pipeline(self, lang_code: str):
        """Initialize Kokoro pipeline with device handling."""
        from kokoro import KPipeline

        try:
            params = inspect.signature(KPipeline).parameters
        except (TypeError, ValueError):
            params = {}

        if "device" in params:
            return KPipeline(lang_code=lang_code, device=self._device)

        return KPipeline(lang_code=lang_code)

    def _should_retry_on_cpu(self, error: Exception) -> bool:
        if self._device == "cpu":
            return False
        return "cuda out of memory" in str(error).lower()

    def _retry_on_cpu(self, phase: str) -> bool:
        logger.warning("Kokoro %s hit CUDA OOM; retrying on CPU", phase)
        self._device = "cpu"
        self._pipeline = None
        return self.warmup()

    def _speak_async(self, text: str, lang: str) -> bool:
        """Asynchronous speak in background thread."""
        # Stop any current speech
        self.stop()

        # Start new speech thread
        self._stop_event.clear()
        self._speak_thread = threading.Thread(
            target=self._speak_worker,
            args=(text, lang),
            daemon=True
        )
        self._speak_thread.start()
        return True

    def _speak_worker(self, text: str, lang: str):
        """Background speech worker."""
        with self._speak_lock:
            self._is_speaking = True

            try:
                # Use larger chunks for Kokoro
                chunks = chunk_text(text, max_chars=MAX_CHUNK_CHARS)
                player = get_player()
                player.start_worker()

                for chunk in chunks:
                    if self._stop_event.is_set():
                        break

                    audio_path = self.synthesize(chunk, lang)
                    if audio_path:
                        player.play(audio_path, blocking=False)
                        # Small delay between chunks
                        time.sleep(0.05)

                # Wait for queue to empty
                while player.queue_size > 0 and not self._stop_event.is_set():
                    time.sleep(0.1)

            except Exception as e:
                logger.error(f"Kokoro speech error: {e}")
            finally:
                self._is_speaking = False

    def stop(self) -> None:
        """Stop current speech and clear queue."""
        self._stop_event.set()

        # Stop audio player
        player = get_player()
        player.stop()

        # Wait for thread
        if self._speak_thread and self._speak_thread.is_alive():
            self._speak_thread.join(timeout=2.0)

        self._is_speaking = False
        self._stop_event.clear()

    def healthcheck(self) -> Dict[str, Any]:
        """Check engine health."""
        result = {
            "healthy": False,
            "engine": self.name,
            "device": self._device,
            "voice": self._voice,
            "speed": self._speed,
            "models_loaded": False,
            "error": None
        }

        try:
            # Check if kokoro is importable
            import kokoro
            result["kokoro_available"] = True

            # Check if pipeline is loaded
            result["models_loaded"] = self._pipeline is not None

            # Check soundfile
            try:
                import soundfile
                result["soundfile_available"] = True
            except ImportError:
                result["soundfile_available"] = False

            # Check audio player
            player = get_player()
            result["audio_player"] = player.get_player_name()

            result["healthy"] = self._is_warmed_up

        except ImportError:
            result["kokoro_available"] = False
            result["error"] = "Kokoro not installed. Run: pip install kokoro soundfile"
        except Exception as e:
            result["error"] = str(e)

        return result

    def prefetch_models(self) -> bool:
        """Download and cache Kokoro models for offline use."""
        try:
            logger.info("Prefetching Kokoro models...")

            # Warmup will download models if needed
            if self.warmup():
                logger.info("Kokoro models prefetched successfully")
                return True
            return False

        except Exception as e:
            logger.error(f"Kokoro model prefetch failed: {e}")
            return False
