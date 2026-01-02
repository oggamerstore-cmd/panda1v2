"""
PANDA.1 Chatterbox TTS Engine
=============================
Offline TTS using Chatterbox (resemble-ai/chatterbox).

Version: 0.2.11

Features:
- English TTS via ChatterboxTTS (single model handles all languages)
- GPU acceleration (CUDA) with automatic CPU fallback on OOM
- Optional voice cloning with reference audio
- Non-blocking playback via background thread
- PCM_16 WAV output for ALSA compatibility
"""

import os
import logging
import time
import threading
from pathlib import Path
from typing import Optional, Dict, Any, Literal

try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    torch = None
    TORCH_AVAILABLE = False

from .base import TTSEngine, chunk_text
from .playback import get_player

logger = logging.getLogger(__name__)


class ChatterboxEngine(TTSEngine):
    """
    Chatterbox TTS Engine (offline, GPU/CPU).
    
    Uses a single ChatterboxTTS model for all languages.
    Defaults to CPU to avoid VRAM conflicts with Ollama LLM.
    """
    
    name = "chatterbox"
    
    def __init__(
        self,
        device: Optional[str] = None,
        cache_dir: Optional[Path] = None,
        output_dir: Optional[Path] = None,
        reference_audio: Optional[Path] = None,
    ):
        """
        Initialize Chatterbox engine.
        
        Args:
            device: "cuda" or "cpu" (defaults to "cpu" for safety)
            cache_dir: Model cache directory
            output_dir: Audio output directory
            reference_audio: Optional voice cloning reference
        """
        super().__init__()
        
        # Default to CPU to avoid VRAM conflicts
        self._device = device or os.environ.get("PANDA_TTS_DEVICE", "cpu")
        self._cache_dir = cache_dir or Path.home() / ".panda1" / "cache" / "huggingface"
        self._output_dir = output_dir or Path.home() / ".panda1" / "audio_out"
        self._reference_audio = reference_audio
        
        # Single model for all languages
        self._model = None
        
        # Threading
        self._speak_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._speak_lock = threading.Lock()
        
        # Set HuggingFace cache
        os.environ["HF_HOME"] = str(self._cache_dir)
        os.environ["TRANSFORMERS_CACHE"] = str(self._cache_dir / "transformers")
        
        # Create output directory
        self._output_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"ChatterboxEngine initialized (device={self._device})")
    
    def _try_load_model(self, device: str) -> bool:
        """Try to load model on specified device."""
        try:
            from chatterbox.tts import ChatterboxTTS
            
            logger.info(f"Loading Chatterbox model on {device}...")
            self._model = ChatterboxTTS.from_pretrained(device=device)
            self._device = device
            logger.info(f"Chatterbox model loaded on {device}")
            return True
            
        except Exception as e:
            error_str = str(e).lower()
            if "cuda" in error_str and ("out of memory" in error_str or "oom" in error_str):
                logger.warning(f"GPU OOM on {device}, will try CPU fallback")
                return False
            raise
    
    def warmup(self) -> bool:
        """Load model (single model handles all languages)."""
        try:
            if not TORCH_AVAILABLE:
                logger.error("PyTorch not installed - Chatterbox requires torch")
                return False

            logger.info("Warming up Chatterbox TTS...")

            # Try loading on configured device
            if self._device == "cuda":
                try:
                    if torch.cuda.is_available():
                        if self._try_load_model("cuda"):
                            self._is_warmed_up = True
                            logger.info("Chatterbox warmup complete (GPU)")
                            return True
                except Exception as e:
                    logger.warning(f"GPU load failed: {e}")
                
                # Fallback to CPU
                logger.info("Falling back to CPU...")
                self._device = "cpu"
            
            # Load on CPU
            if self._try_load_model("cpu"):
                self._is_warmed_up = True
                logger.info("Chatterbox warmup complete (CPU)")
                return True
            
            return False
            
        except ImportError as e:
            logger.error(f"Chatterbox not installed: {e}")
            self._is_warmed_up = False
            return False
        except Exception as e:
            logger.error(f"Chatterbox warmup failed: {e}")
            self._is_warmed_up = False
            return False
    
    def synthesize(
        self, 
        text: str, 
        lang: Literal["en", "ko"] = "en",
        output_path: Optional[Path] = None
    ) -> Optional[Path]:
        """Synthesize text to audio file (PCM_16 WAV)."""
        if not text.strip():
            return None
        
        try:
            # Ensure model is loaded
            if not self._is_warmed_up:
                if not self.warmup():
                    return None
            
            if self._model is None:
                logger.error("No model loaded")
                return None
            
            # Generate output path
            if output_path is None:
                timestamp = int(time.time() * 1000)
                output_path = self._output_dir / f"tts_{timestamp}.wav"
            
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Generate audio
            logger.debug(f"Synthesizing ({lang}): {text[:50]}...")
            
            
            with torch.no_grad():
                try:
                    # Generate waveform
                    if self._reference_audio and Path(self._reference_audio).exists():
                        # Voice cloning mode
                        wav = self._model.generate(
                            text=text,
                            audio_prompt_path=str(self._reference_audio)
                        )
                    else:
                        # Default voice mode
                        wav = self._model.generate(text=text)
                    
                    # Get sample rate from model
                    sample_rate = getattr(self._model, 'sr', 24000)
                    
                    # Ensure tensor is on CPU and correct shape
                    wav = wav.cpu()
                    if wav.dim() == 1:
                        wav = wav.unsqueeze(0)
                    
                    # Convert to numpy and save as PCM_16 for ALSA compatibility
                    wav_np = wav.numpy()
                    
                    # Use soundfile for reliable PCM_16 output
                    try:
                        import soundfile as sf
                        # Transpose if needed (soundfile expects samples x channels)
                        if wav_np.shape[0] < wav_np.shape[1]:
                            wav_np = wav_np.T
                        elif wav_np.ndim == 2 and wav_np.shape[0] == 1:
                            wav_np = wav_np[0]  # Flatten single channel
                        
                        sf.write(str(output_path), wav_np, sample_rate, subtype='PCM_16')
                    except ImportError:
                        # Fallback to torchaudio
                        import torchaudio
                        torchaudio.save(str(output_path), wav, sample_rate)
                    
                except RuntimeError as e:
                    # Handle OOM during synthesis
                    if "out of memory" in str(e).lower():
                        logger.error("GPU OOM during synthesis, switching to CPU")
                        self._device = "cpu"
                        self._model = None
                        self._is_warmed_up = False
                        # Retry on CPU
                        return self.synthesize(text, lang, output_path)
                    raise
            
            logger.debug(f"Audio saved: {output_path}")
            return output_path
            
        except Exception as e:
            logger.error(f"Synthesis failed: {e}")
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
        """Synchronous speak."""
        chunks = chunk_text(text)
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
                chunks = chunk_text(text)
                player = get_player()
                player.start_worker()
                
                for chunk in chunks:
                    if self._stop_event.is_set():
                        break
                    
                    audio_path = self.synthesize(chunk, lang)
                    if audio_path:
                        player.play(audio_path, blocking=False)
                        
                        # Wait for playback to start before next chunk
                        time.sleep(0.1)
                
                # Wait for queue to empty
                while player.queue_size > 0 and not self._stop_event.is_set():
                    time.sleep(0.1)
                    
            except Exception as e:
                logger.error(f"Speech worker error: {e}")
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
            "models_loaded": False,
            "cache_dir": str(self._cache_dir),
            "error": None
        }

        try:
            # Check if chatterbox is importable
            import chatterbox
            result["chatterbox_version"] = getattr(chatterbox, "__version__", "unknown")

            # Check torch
            if TORCH_AVAILABLE and torch is not None:
                result["torch_version"] = torch.__version__
                result["cuda_available"] = torch.cuda.is_available()

                if torch.cuda.is_available():
                    result["cuda_device"] = torch.cuda.get_device_name(0)
            else:
                result["torch_version"] = "not installed"
                result["cuda_available"] = False

            # Check if model is loaded
            result["models_loaded"] = self._model is not None

            # Check audio player
            player = get_player()
            result["audio_player"] = player.get_player_name()

            result["healthy"] = True

        except ImportError as e:
            result["error"] = f"Import error: {e}"
        except Exception as e:
            result["error"] = str(e)

        return result
    
    def prefetch_models(self) -> bool:
        """Download and cache models for offline use."""
        try:
            logger.info("Prefetching Chatterbox models...")
            
            # This will download models if not cached
            if self.warmup():
                logger.info("Models prefetched successfully")
                return True
            return False
            
        except Exception as e:
            logger.error(f"Model prefetch failed: {e}")
            return False
