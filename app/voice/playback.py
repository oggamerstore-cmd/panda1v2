"""
PANDA.1 Audio Playback
======================
Reliable audio output with multiple backend support.

Version: 0.2.11

Features:
- Primary: sounddevice for cross-platform playback
- Fallback: aplay for Linux ALSA
- Queue-based async playback
- Volume control and muting
"""

import io
import os
import wave
import time
import logging
import subprocess
import threading
from pathlib import Path
from queue import Queue, Empty
from typing import Optional, Callable
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Try to import audio libraries
try:
    import numpy as np
    import sounddevice as sd
    SOUNDDEVICE_AVAILABLE = True
except ImportError:
    SOUNDDEVICE_AVAILABLE = False
    logger.warning("sounddevice not available")


@dataclass
class PlaybackResult:
    """Result of audio playback."""
    success: bool
    duration: float = 0.0
    error: Optional[str] = None


class AudioPlayer:
    """
    Audio playback manager with queue support.
    
    Usage:
        player = AudioPlayer()
        player.play(wav_bytes)
        player.wait()
    """
    
    def __init__(
        self,
        device_index: Optional[int] = None,
        volume: float = 1.0,
        use_queue: bool = True,
    ):
        """
        Initialize audio player.
        
        Args:
            device_index: Output device index (None for default)
            volume: Volume level (0.0 - 1.0)
            use_queue: Use async queue-based playback
        """
        self.device_index = device_index
        self.volume = max(0.0, min(1.0, volume))
        self.use_queue = use_queue
        
        self._muted = False
        self._playing = False
        self._queue: Queue = Queue()
        self._playback_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        
        # Start playback thread if using queue
        if use_queue:
            self._start_playback_thread()
    
    @property
    def is_muted(self) -> bool:
        """Check if muted."""
        return self._muted
    
    @property
    def is_playing(self) -> bool:
        """Check if currently playing."""
        return self._playing
    
    def mute(self, muted: bool = True) -> None:
        """Set mute state."""
        self._muted = muted
        logger.debug(f"Audio {'muted' if muted else 'unmuted'}")
    
    def set_volume(self, volume: float) -> None:
        """Set volume level (0.0 - 1.0)."""
        self.volume = max(0.0, min(1.0, volume))
        logger.debug(f"Volume set to {self.volume:.0%}")
    
    def set_device(self, device_index: Optional[int]) -> None:
        """Set output device."""
        self.device_index = device_index
        logger.debug(f"Output device set to {device_index or 'default'}")
    
    def play(self, audio: bytes, blocking: bool = False) -> PlaybackResult:
        """
        Play audio.
        
        Args:
            audio: WAV audio bytes
            blocking: Wait for playback to complete
        
        Returns:
            PlaybackResult
        """
        if self._muted:
            return PlaybackResult(success=True, duration=0.0)
        
        if self.use_queue and not blocking:
            self._queue.put(audio)
            return PlaybackResult(success=True)
        
        return self._play_audio(audio)
    
    def play_file(self, file_path: Path, blocking: bool = False) -> PlaybackResult:
        """
        Play audio from file.
        
        Args:
            file_path: Path to WAV file
            blocking: Wait for playback to complete
        
        Returns:
            PlaybackResult
        """
        try:
            with open(file_path, 'rb') as f:
                audio = f.read()
            return self.play(audio, blocking)
        except Exception as e:
            return PlaybackResult(success=False, error=str(e))
    
    def stop(self) -> None:
        """Stop current playback and clear queue."""
        self._stop_event.set()
        
        # Clear queue
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except Empty:
                break
        
        # Try to stop sounddevice
        if SOUNDDEVICE_AVAILABLE:
            try:
                sd.stop()
            except Exception:
                pass
        
        self._stop_event.clear()
        logger.debug("Playback stopped")
    
    def wait(self, timeout: Optional[float] = None) -> None:
        """Wait for all queued audio to play."""
        if self.use_queue and self._playback_thread:
            # Put sentinel to signal completion check
            start = time.time()
            while not self._queue.empty():
                if timeout and (time.time() - start) > timeout:
                    break
                time.sleep(0.1)
    
    def shutdown(self) -> None:
        """Shutdown the player."""
        self._stop_event.set()
        self._queue.put(None)  # Signal thread to exit
        
        if self._playback_thread and self._playback_thread.is_alive():
            self._playback_thread.join(timeout=2.0)
    
    def _start_playback_thread(self) -> None:
        """Start the background playback thread."""
        self._playback_thread = threading.Thread(
            target=self._playback_worker,
            daemon=True
        )
        self._playback_thread.start()
    
    def _playback_worker(self) -> None:
        """Background thread for queue-based playback."""
        while True:
            try:
                audio = self._queue.get(timeout=0.5)
                
                if audio is None:
                    break
                
                if self._muted:
                    continue
                
                self._play_audio(audio)
                
            except Empty:
                continue
            except Exception as e:
                logger.error(f"Playback worker error: {e}")
    
    def _play_audio(self, audio: bytes) -> PlaybackResult:
        """Play audio bytes."""
        if SOUNDDEVICE_AVAILABLE:
            return self._play_sounddevice(audio)
        else:
            return self._play_aplay(audio)
    
    def _play_sounddevice(self, audio: bytes) -> PlaybackResult:
        """Play using sounddevice."""
        try:
            # Parse WAV
            wav_io = io.BytesIO(audio)
            with wave.open(wav_io, 'rb') as wav:
                sample_rate = wav.getframerate()
                channels = wav.getnchannels()
                sample_width = wav.getsampwidth()
                frames = wav.readframes(wav.getnframes())
            
            # Convert to numpy
            if sample_width == 2:
                audio_data = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32767
            elif sample_width == 4:
                audio_data = np.frombuffer(frames, dtype=np.int32).astype(np.float32) / 2147483647
            else:
                audio_data = np.frombuffer(frames, dtype=np.uint8).astype(np.float32) / 128 - 1.0
            
            # Apply volume
            audio_data = audio_data * self.volume
            
            # Reshape for channels
            if channels > 1:
                audio_data = audio_data.reshape(-1, channels)
            
            duration = len(frames) / (sample_rate * channels * sample_width)
            
            self._playing = True
            sd.play(audio_data, sample_rate, device=self.device_index)
            sd.wait()
            self._playing = False
            
            return PlaybackResult(success=True, duration=duration)
            
        except Exception as e:
            self._playing = False
            logger.error(f"sounddevice playback failed: {e}")
            return PlaybackResult(success=False, error=str(e))
    
    def _play_aplay(self, audio: bytes) -> PlaybackResult:
        """Play using aplay (Linux fallback)."""
        try:
            # Save to temp file
            temp_path = Path.home() / ".panda1" / "cache" / "temp_playback.wav"
            temp_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(temp_path, 'wb') as f:
                f.write(audio)
            
            # Get duration from WAV
            wav_io = io.BytesIO(audio)
            with wave.open(wav_io, 'rb') as wav:
                duration = wav.getnframes() / wav.getframerate()
            
            # Build aplay command
            cmd = ["aplay"]
            
            # Check for ALSA device setting
            alsa_device = os.environ.get("PANDA_ALSA_DEVICE")
            if alsa_device:
                cmd.extend(["-D", alsa_device])
            
            cmd.append(str(temp_path))
            
            self._playing = True
            result = subprocess.run(
                cmd,
                capture_output=True,
                timeout=duration + 5
            )
            self._playing = False
            
            if result.returncode != 0:
                return PlaybackResult(
                    success=False,
                    error=result.stderr.decode()
                )
            
            return PlaybackResult(success=True, duration=duration)
            
        except subprocess.TimeoutExpired:
            self._playing = False
            return PlaybackResult(success=False, error="Playback timeout")
        except FileNotFoundError:
            self._playing = False
            return PlaybackResult(success=False, error="aplay not found")
        except Exception as e:
            self._playing = False
            return PlaybackResult(success=False, error=str(e))


# Global player instance
_player: Optional[AudioPlayer] = None


def get_player(device_index: Optional[int] = None) -> AudioPlayer:
    """
    Get or create the global audio player.
    
    Args:
        device_index: Output device index
    
    Returns:
        AudioPlayer instance
    """
    global _player
    
    if _player is None:
        _player = AudioPlayer(device_index=device_index)
    
    return _player


def play_audio(audio: bytes, blocking: bool = True) -> PlaybackResult:
    """
    Quick playback helper.
    
    Args:
        audio: WAV audio bytes
        blocking: Wait for completion
    
    Returns:
        PlaybackResult
    """
    player = get_player()
    return player.play(audio, blocking)


def play_file(file_path: Path, blocking: bool = True) -> PlaybackResult:
    """
    Quick file playback helper.
    
    Args:
        file_path: Path to WAV file
        blocking: Wait for completion
    
    Returns:
        PlaybackResult
    """
    player = get_player()
    return player.play_file(file_path, blocking)


def play_test_tone(
    frequency: float = 440.0,
    duration: float = 0.5,
    device_index: Optional[int] = None,
) -> PlaybackResult:
    """
    Play a test tone.
    
    Args:
        frequency: Tone frequency in Hz
        duration: Duration in seconds
        device_index: Output device
    
    Returns:
        PlaybackResult
    """
    if not SOUNDDEVICE_AVAILABLE:
        return PlaybackResult(success=False, error="sounddevice not available")
    
    try:
        sample_rate = 44100
        t = np.linspace(0, duration, int(sample_rate * duration), False)
        tone = 0.3 * np.sin(2 * np.pi * frequency * t)
        
        # Fade in/out
        fade_samples = int(0.02 * sample_rate)
        tone[:fade_samples] *= np.linspace(0, 1, fade_samples)
        tone[-fade_samples:] *= np.linspace(1, 0, fade_samples)
        
        sd.play(tone.astype('float32'), sample_rate, device=device_index)
        sd.wait()
        
        return PlaybackResult(success=True, duration=duration)
        
    except Exception as e:
        return PlaybackResult(success=False, error=str(e))


def test_playback(device_index: Optional[int] = None) -> None:
    """
    Test audio playback (CLI helper).
    
    Args:
        device_index: Output device to test
    """
    logging.info(f"\n{'='*60}")
    logging.info("  PANDA.1 Playback Test")
    logging.info(f"{'='*60}")
    
    logging.info(f"\n  Device: {device_index or 'default'}")
    logging.info(f"  sounddevice available: {SOUNDDEVICE_AVAILABLE}")
    
    if not SOUNDDEVICE_AVAILABLE:
        logging.info("\n  ❌ sounddevice not available!")
        logging.info("  Run: pip install sounddevice")
        return
    
    logging.info("\n  Playing test tone (440 Hz, 0.5s)...")
    result = play_test_tone(device_index=device_index)
    
    if result.success:
        logging.info("  ✅ Playback successful!")
    else:
        logging.error(f"  ❌ Playback failed: {result.error}")
    
    logging.info()
