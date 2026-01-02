"""
PANDA.1 Piper TTS Engine (Fallback)
===================================
Offline TTS using Piper (rhasspy/piper).

Version: 0.2.6

This is a fallback engine if Chatterbox is unavailable.
Piper is lighter weight but lower quality.
"""

import os
import logging
import shutil
import subprocess
import time
import threading
from pathlib import Path
from typing import Optional, Dict, Any, Literal

from .base import TTSEngine, chunk_text
from .playback import get_player

logger = logging.getLogger(__name__)


class PiperEngine(TTSEngine):
    """
    Piper TTS Engine (offline, CPU-based fallback).
    
    Uses piper-tts command-line tool.
    """
    
    name = "piper"
    
    def __init__(
        self,
        model_path: Optional[Path] = None,
        model_name: Optional[str] = None,
        output_dir: Optional[Path] = None,
    ):
        """
        Initialize Piper engine.
        
        Args:
            model_path: Path to Piper model (.onnx)
            output_dir: Audio output directory
        """
        super().__init__()
        
        self._model_path = model_path
        self._model_name = model_name
        self._output_dir = output_dir or Path.home() / ".panda1" / "audio_out"
        
        # Find piper binary
        self._piper_bin = self._find_piper()
        
        # Threading
        self._speak_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._speak_lock = threading.Lock()
        
        # Create output directory
        self._output_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"PiperEngine initialized (binary={self._piper_bin})")
    
    def _find_piper(self) -> Optional[str]:
        """Find piper binary."""
        # Check common locations
        locations = [
            shutil.which("piper"),
            shutil.which("piper-tts"),
            str(Path.home() / ".local" / "bin" / "piper"),
            "/usr/local/bin/piper",
            "/usr/bin/piper",
        ]
        
        for loc in locations:
            if loc and Path(loc).exists():
                return loc
        
        return None
    
    def _find_model(self) -> Optional[Path]:
        """Find a Piper model."""
        if self._model_path and self._model_path.exists():
            return self._model_path
        
        # Search common locations
        model_dirs = [
            Path.home() / ".panda1" / "models" / "piper",
            Path.home() / ".local" / "share" / "piper" / "models",
            Path("/usr/share/piper/models"),
        ]
        
        model_name = self._model_name.lower() if self._model_name else None
        candidates = []

        for model_dir in model_dirs:
            if not model_dir.exists():
                continue
            for onnx in model_dir.rglob("*.onnx"):
                candidates.append(onnx)

        if model_name:
            preferred = [
                model for model in candidates
                if model_name in model.stem.lower() or model_name in model.name.lower()
            ]
            if preferred:
                preferred.sort(key=lambda path: path.name.lower())
                logger.info(f"Found Piper model matching '{self._model_name}': {preferred[0]}")
                return preferred[0]
            else:
                logger.warning(f"No Piper model matching '{self._model_name}' found; using first available model.")

        if candidates:
            candidates.sort(key=lambda path: path.name.lower())
            logger.info(f"Found Piper model: {candidates[0]}")
            return candidates[0]

        return None
    
    def warmup(self) -> bool:
        """Check Piper is available."""
        try:
            if not self._piper_bin:
                logger.error("Piper binary not found")
                return False
            
            self._model_path = self._find_model()
            if not self._model_path:
                logger.error("No Piper model found")
                return False
            
            self._is_warmed_up = True
            logger.info("Piper warmup complete")
            return True
            
        except Exception as e:
            logger.error(f"Piper warmup failed: {e}")
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
        
        if not self._piper_bin or not self._model_path:
            logger.error("Piper not configured")
            return None
        
        try:
            # Generate output path
            if output_path is None:
                timestamp = int(time.time() * 1000)
                output_path = self._output_dir / f"piper_{timestamp}.wav"
            
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Run piper
            cmd = [
                self._piper_bin,
                "--model", str(self._model_path),
                "--output_file", str(output_path)
            ]
            
            logger.debug(f"Running: {' '.join(cmd)}")
            
            result = subprocess.run(
                cmd,
                input=text,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode != 0:
                logger.error(f"Piper failed: {result.stderr}")
                return None
            
            if output_path.exists():
                return output_path
            else:
                logger.error("Piper did not create output file")
                return None
            
        except subprocess.TimeoutExpired:
            logger.error("Piper timed out")
            return None
        except Exception as e:
            logger.error(f"Piper synthesis failed: {e}")
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
        """Asynchronous speak."""
        self.stop()
        
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
                        time.sleep(0.1)
                
                while player.queue_size > 0 and not self._stop_event.is_set():
                    time.sleep(0.1)
                    
            except Exception as e:
                logger.error(f"Piper speech error: {e}")
            finally:
                self._is_speaking = False
    
    def stop(self) -> None:
        """Stop current speech."""
        self._stop_event.set()
        
        player = get_player()
        player.stop()
        
        if self._speak_thread and self._speak_thread.is_alive():
            self._speak_thread.join(timeout=2.0)
        
        self._is_speaking = False
        self._stop_event.clear()
    
    def healthcheck(self) -> Dict[str, Any]:
        """Check engine health."""
        result = {
            "healthy": False,
            "engine": self.name,
            "device": "cpu",
            "models_loaded": False,
            "error": None
        }
        
        try:
            if not self._piper_bin:
                result["error"] = "Piper binary not found"
                return result
            
            result["piper_binary"] = self._piper_bin
            
            model = self._find_model()
            if model:
                result["model_path"] = str(model)
                result["models_loaded"] = True
            else:
                result["error"] = "No Piper model found"
                return result
            
            player = get_player()
            result["audio_player"] = player.get_player_name()
            
            result["healthy"] = True
            
        except Exception as e:
            result["error"] = str(e)
        
        return result
