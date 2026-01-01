"""
PANDA.1 Faster-Whisper STT
==========================
Speech-to-text using Faster-Whisper for fast, accurate transcription.

Version: 0.2.10

Features:
- Multi-language support (EN, KO, auto-detect)
- VAD filtering for better accuracy
- Configurable model sizes
- GPU acceleration support
"""

import io
import time
import logging
from pathlib import Path
from typing import Optional, Literal, Tuple, List
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

# Try to import faster-whisper
try:
    from faster_whisper import WhisperModel
    FASTER_WHISPER_AVAILABLE = True
except ImportError:
    FASTER_WHISPER_AVAILABLE = False
    WhisperModel = None
    logger.warning("faster-whisper not available, STT disabled")


class STTLanguage(str, Enum):
    """Supported STT languages."""
    AUTO = "auto"
    ENGLISH = "en"
    KOREAN = "ko"


@dataclass
class STTResult:
    """Speech-to-text result."""
    success: bool
    text: str = ""
    language: str = ""
    confidence: float = 0.0
    duration: float = 0.0
    processing_time: float = 0.0
    segments: List[dict] = None
    error: Optional[str] = None
    
    def __post_init__(self):
        if self.segments is None:
            self.segments = []


class FasterWhisperSTT:
    """
    Faster-Whisper speech-to-text engine.
    
    Usage:
        stt = FasterWhisperSTT()
        stt.load_model()
        result = stt.transcribe(audio_bytes)
        logging.info(result.text)
    """
    
    # Model size to approximate VRAM usage
    MODEL_SIZES = {
        "tiny": "~1GB",
        "base": "~1GB",
        "small": "~2GB",
        "medium": "~5GB",
        "large-v3": "~10GB",
    }
    
    def __init__(
        self,
        model_size: str = "small",
        device: str = "auto",
        compute_type: str = "int8",
        cache_dir: Optional[Path] = None,
    ):
        """
        Initialize Faster-Whisper STT.
        
        Args:
            model_size: Model size (tiny, base, small, medium, large-v3)
            device: Device to use (auto, cuda, cpu)
            compute_type: Compute type (int8, float16, float32)
            cache_dir: Model cache directory
        """
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self.cache_dir = cache_dir or Path.home() / ".panda1" / "cache" / "whisper"
        
        self._model: Optional[WhisperModel] = None
        self._model_loaded = False
    
    @property
    def is_available(self) -> bool:
        """Check if Faster-Whisper is available."""
        return FASTER_WHISPER_AVAILABLE
    
    @property
    def is_loaded(self) -> bool:
        """Check if model is loaded."""
        return self._model_loaded and self._model is not None
    
    def load_model(self) -> bool:
        """
        Load the Whisper model.
        
        Returns:
            True if model loaded successfully
        """
        if not FASTER_WHISPER_AVAILABLE:
            logger.error("faster-whisper not installed")
            return False
        
        if self._model_loaded:
            logger.debug("Model already loaded")
            return True
        
        try:
            logger.info(f"Loading Faster-Whisper model: {self.model_size}")
            start_time = time.time()
            
            # Determine device
            device = self.device
            if device == "auto":
                try:
                    import torch
                    device = "cuda" if torch.cuda.is_available() else "cpu"
                except ImportError:
                    device = "cpu"
            
            # Adjust compute type for CPU
            compute_type = self.compute_type
            if device == "cpu" and compute_type == "float16":
                compute_type = "int8"
                logger.info("Using int8 compute type for CPU")
            
            # Ensure cache directory exists
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            
            self._model = WhisperModel(
                self.model_size,
                device=device,
                compute_type=compute_type,
                download_root=str(self.cache_dir),
            )
            
            load_time = time.time() - start_time
            logger.info(f"Model loaded in {load_time:.2f}s (device={device}, compute={compute_type})")
            
            self._model_loaded = True
            return True
            
        except Exception as e:
            logger.error(f"Failed to load Whisper model: {e}")
            return False
    
    def unload_model(self) -> None:
        """Unload the model to free memory."""
        if self._model:
            del self._model
            self._model = None
        self._model_loaded = False
        logger.info("Model unloaded")
    
    def transcribe(
        self,
        audio: bytes,
        language: STTLanguage = STTLanguage.AUTO,
        beam_size: int = 5,
        vad_filter: bool = True,
    ) -> STTResult:
        """
        Transcribe audio to text.
        
        Args:
            audio: WAV audio bytes
            language: Language mode (auto, en, ko)
            beam_size: Beam size for decoding
            vad_filter: Use VAD filtering
        
        Returns:
            STTResult with transcription
        """
        if not self.is_loaded:
            if not self.load_model():
                return STTResult(
                    success=False,
                    error="Failed to load model"
                )
        
        start_time = time.time()
        
        try:
            # Prepare audio file-like object
            audio_io = io.BytesIO(audio)
            
            # Set language parameter
            lang_param = None if language == STTLanguage.AUTO else language.value
            
            # Transcribe
            segments, info = self._model.transcribe(
                audio_io,
                language=lang_param,
                beam_size=beam_size,
                vad_filter=vad_filter,
                vad_parameters=dict(
                    min_silence_duration_ms=500,
                    speech_pad_ms=200,
                ),
            )
            
            # Collect segments
            segment_list = []
            text_parts = []
            total_confidence = 0.0
            
            for segment in segments:
                segment_list.append({
                    "start": segment.start,
                    "end": segment.end,
                    "text": segment.text.strip(),
                    "avg_logprob": segment.avg_logprob,
                })
                text_parts.append(segment.text.strip())
                # Convert log probability to confidence
                total_confidence += 2 ** segment.avg_logprob
            
            full_text = " ".join(text_parts).strip()
            avg_confidence = total_confidence / len(segment_list) if segment_list else 0.0
            
            processing_time = time.time() - start_time
            
            logger.info(
                f"Transcribed: '{full_text[:50]}...' "
                f"(lang={info.language}, conf={avg_confidence:.2f}, time={processing_time:.2f}s)"
            )
            
            return STTResult(
                success=True,
                text=full_text,
                language=info.language,
                confidence=min(avg_confidence, 1.0),
                duration=info.duration,
                processing_time=processing_time,
                segments=segment_list,
            )
            
        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            return STTResult(
                success=False,
                error=str(e),
                processing_time=time.time() - start_time,
            )
    
    def transcribe_file(
        self,
        file_path: Path,
        language: STTLanguage = STTLanguage.AUTO,
        beam_size: int = 5,
        vad_filter: bool = True,
    ) -> STTResult:
        """
        Transcribe audio from file.
        
        Args:
            file_path: Path to audio file
            language: Language mode
            beam_size: Beam size for decoding
            vad_filter: Use VAD filtering
        
        Returns:
            STTResult with transcription
        """
        try:
            with open(file_path, 'rb') as f:
                audio = f.read()
            return self.transcribe(audio, language, beam_size, vad_filter)
        except Exception as e:
            return STTResult(
                success=False,
                error=f"Failed to read file: {e}"
            )
    
    def get_status(self) -> dict:
        """Get STT engine status."""
        return {
            "available": FASTER_WHISPER_AVAILABLE,
            "loaded": self.is_loaded,
            "model_size": self.model_size,
            "device": self.device,
            "compute_type": self.compute_type,
            "cache_dir": str(self.cache_dir),
            "estimated_vram": self.MODEL_SIZES.get(self.model_size, "unknown"),
        }


# Global STT instance
_stt_instance: Optional[FasterWhisperSTT] = None


def get_stt(
    model_size: str = "small",
    device: str = "auto",
    compute_type: str = "int8",
) -> FasterWhisperSTT:
    """
    Get or create the global STT instance.
    
    Args:
        model_size: Model size
        device: Device (auto, cuda, cpu)
        compute_type: Compute type
    
    Returns:
        FasterWhisperSTT instance
    """
    global _stt_instance
    
    if _stt_instance is None:
        _stt_instance = FasterWhisperSTT(
            model_size=model_size,
            device=device,
            compute_type=compute_type,
        )
    
    return _stt_instance


def transcribe_audio(
    audio: bytes,
    language: str = "auto",
) -> STTResult:
    """
    Quick transcription helper.
    
    Args:
        audio: WAV audio bytes
        language: Language (auto, en, ko)
    
    Returns:
        STTResult
    """
    stt = get_stt()
    lang = STTLanguage(language) if language in ["auto", "en", "ko"] else STTLanguage.AUTO
    return stt.transcribe(audio, language=lang)


def test_stt(
    audio_path: Path,
    language: str = "auto",
) -> None:
    """
    Test STT with an audio file (CLI helper).
    
    Args:
        audio_path: Path to WAV file
        language: Language mode
    """
    logging.info(f"\n{'='*60}")
    logging.info("  PANDA.1 STT Test (Faster-Whisper)")
    logging.info(f"{'='*60}")
    
    if not FASTER_WHISPER_AVAILABLE:
        logging.info("\n  ❌ faster-whisper not installed!")
        logging.info("  Run: pip install faster-whisper")
        return
    
    audio_path = Path(audio_path)
    if not audio_path.exists():
        logging.info(f"\n  ❌ File not found: {audio_path}")
        return
    
    logging.info(f"\n  File: {audio_path}")
    logging.info(f"  Language: {language}")
    
    stt = get_stt()
    
    logging.info("\n  Loading model...")
    if not stt.load_model():
        logging.error("  ❌ Failed to load model")
        return
    
    logging.info("  Transcribing...")
    result = stt.transcribe_file(
        audio_path,
        language=STTLanguage(language) if language in ["auto", "en", "ko"] else STTLanguage.AUTO
    )
    
    logging.info(f"\n  {'='*50}")
    if result.success:
        logging.info(f"  ✅ Success!")
        logging.info(f"  Text: {result.text}")
        logging.info(f"  Language: {result.language}")
        logging.info(f"  Confidence: {result.confidence:.2%}")
        logging.info(f"  Duration: {result.duration:.2f}s")
        logging.info(f"  Processing: {result.processing_time:.2f}s")
        if result.segments:
            logging.info(f"\n  Segments:")
            for seg in result.segments[:5]:  # Show first 5
                logging.info(f"    [{seg['start']:.1f}s - {seg['end']:.1f}s] {seg['text']}")
    else:
        logging.error(f"  ❌ Failed: {result.error}")
    
    logging.info()
