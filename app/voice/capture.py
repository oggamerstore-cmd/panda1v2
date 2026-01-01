"""
PANDA.1 Audio Capture
=====================
Push-to-talk recording engine with real-time audio capture.

Version: 0.2.11

Features:
- Start/stop recording on demand (PTT)
- Real-time audio level monitoring
- WAV buffer management
- Device selection support
"""

import io
import wave
import time
import logging
import threading
from enum import Enum, auto
from pathlib import Path
from typing import Optional, Callable, List
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Try to import audio libraries
try:
    import numpy as np
    import sounddevice as sd
    AUDIO_AVAILABLE = True
except ImportError:
    AUDIO_AVAILABLE = False
    logger.warning("numpy/sounddevice not available, capture disabled")


class CaptureState(Enum):
    """Audio capture states."""
    IDLE = auto()
    RECORDING = auto()
    PROCESSING = auto()
    ERROR = auto()


@dataclass
class CaptureResult:
    """Result of an audio capture session."""
    success: bool
    audio_data: Optional[bytes] = None
    duration: float = 0.0
    rms: float = 0.0
    peak: float = 0.0
    sample_rate: int = 16000
    error: Optional[str] = None
    wav_path: Optional[str] = None


class AudioCapture:
    """
    Push-to-talk audio capture engine.
    
    Usage:
        capture = AudioCapture()
        capture.start()
        # ... user speaks ...
        result = capture.stop()
        if result.success:
            # result.audio_data contains WAV bytes
    """
    
    def __init__(
        self,
        sample_rate: int = 16000,
        channels: int = 1,
        device_index: Optional[int] = None,
        max_duration: float = 30.0,
        min_duration: float = 0.3,
        on_level_update: Optional[Callable[[float], None]] = None,
    ):
        """
        Initialize audio capture.
        
        Args:
            sample_rate: Audio sample rate (16000 for Whisper)
            channels: Number of channels (1 for mono)
            device_index: Input device index (None for default)
            max_duration: Maximum recording duration in seconds
            min_duration: Minimum recording duration in seconds
            on_level_update: Callback for real-time level updates
        """
        self.sample_rate = sample_rate
        self.channels = channels
        self.device_index = device_index
        self.max_duration = max_duration
        self.min_duration = min_duration
        self.on_level_update = on_level_update
        
        self._state = CaptureState.IDLE
        self._frames: List[np.ndarray] = []
        self._stream: Optional[sd.InputStream] = None
        self._start_time: float = 0.0
        self._lock = threading.Lock()
        self._level_callback_interval = 0.05  # 50ms
        self._last_level_callback = 0.0
        self._current_rms = 0.0
    
    @property
    def state(self) -> CaptureState:
        """Get current capture state."""
        return self._state
    
    @property
    def is_recording(self) -> bool:
        """Check if currently recording."""
        return self._state == CaptureState.RECORDING
    
    @property
    def duration(self) -> float:
        """Get current recording duration."""
        if self._start_time > 0:
            return time.time() - self._start_time
        return 0.0
    
    @property
    def current_level(self) -> float:
        """Get current audio level (RMS)."""
        return self._current_rms
    
    def _audio_callback(self, indata, frames, time_info, status):
        """Callback for audio stream."""
        if status:
            logger.warning(f"Audio capture status: {status}")
        
        if self._state != CaptureState.RECORDING:
            return
        
        # Store the frame
        with self._lock:
            self._frames.append(indata.copy())
        
        # Calculate RMS for level monitoring
        if AUDIO_AVAILABLE:
            rms = float(np.sqrt(np.mean(indata ** 2)))
            self._current_rms = rms
            
            # Call level update callback (rate-limited)
            now = time.time()
            if self.on_level_update and (now - self._last_level_callback) >= self._level_callback_interval:
                self._last_level_callback = now
                try:
                    self.on_level_update(rms)
                except Exception as e:
                    logger.debug(f"Level callback error: {e}")
        
        # Check max duration
        if self.duration >= self.max_duration:
            logger.info(f"Max recording duration ({self.max_duration}s) reached")
            # Don't stop here - let the caller handle it
    
    def start(self) -> bool:
        """
        Start recording.
        
        Returns:
            True if recording started successfully
        """
        if not AUDIO_AVAILABLE:
            logger.error("Audio capture not available (missing dependencies)")
            self._state = CaptureState.ERROR
            return False
        
        if self._state == CaptureState.RECORDING:
            logger.warning("Already recording")
            return True
        
        try:
            with self._lock:
                self._frames = []
                self._current_rms = 0.0
            
            self._stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype='float32',
                device=self.device_index,
                callback=self._audio_callback,
            )
            self._stream.start()
            self._start_time = time.time()
            self._state = CaptureState.RECORDING
            
            logger.info(f"Recording started (device={self.device_index or 'default'})")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start recording: {e}")
            self._state = CaptureState.ERROR
            return False
    
    def stop(self, save_path: Optional[Path] = None) -> CaptureResult:
        """
        Stop recording and return captured audio.
        
        Args:
            save_path: Optional path to save WAV file
        
        Returns:
            CaptureResult with audio data
        """
        if self._state != CaptureState.RECORDING:
            return CaptureResult(
                success=False,
                error="Not recording"
            )
        
        self._state = CaptureState.PROCESSING
        
        try:
            # Stop the stream
            if self._stream:
                self._stream.stop()
                self._stream.close()
                self._stream = None
            
            duration = time.time() - self._start_time
            
            # Check minimum duration
            if duration < self.min_duration:
                self._state = CaptureState.IDLE
                return CaptureResult(
                    success=False,
                    duration=duration,
                    error=f"Recording too short ({duration:.1f}s < {self.min_duration}s)"
                )
            
            # Combine frames
            with self._lock:
                if not self._frames:
                    self._state = CaptureState.IDLE
                    return CaptureResult(
                        success=False,
                        error="No audio captured"
                    )
                
                audio_data = np.concatenate(self._frames, axis=0)
                self._frames = []
            
            # Calculate stats
            rms = float(np.sqrt(np.mean(audio_data ** 2)))
            peak = float(np.max(np.abs(audio_data)))
            
            # Convert to WAV bytes
            wav_buffer = io.BytesIO()
            with wave.open(wav_buffer, 'wb') as wav_file:
                wav_file.setnchannels(self.channels)
                wav_file.setsampwidth(2)  # 16-bit
                wav_file.setframerate(self.sample_rate)
                
                # Convert float32 to int16
                audio_int16 = (audio_data * 32767).astype(np.int16)
                wav_file.writeframes(audio_int16.tobytes())
            
            wav_bytes = wav_buffer.getvalue()
            
            # Optionally save to file
            wav_path = None
            if save_path:
                save_path = Path(save_path)
                save_path.parent.mkdir(parents=True, exist_ok=True)
                with open(save_path, 'wb') as f:
                    f.write(wav_bytes)
                wav_path = str(save_path)
                logger.info(f"Audio saved to {wav_path}")
            
            self._state = CaptureState.IDLE
            
            return CaptureResult(
                success=True,
                audio_data=wav_bytes,
                duration=duration,
                rms=rms,
                peak=peak,
                sample_rate=self.sample_rate,
                wav_path=wav_path,
            )
            
        except Exception as e:
            logger.error(f"Error stopping capture: {e}")
            self._state = CaptureState.ERROR
            return CaptureResult(
                success=False,
                error=str(e)
            )
    
    def cancel(self) -> None:
        """Cancel recording without returning data."""
        if self._stream:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception as e:
                logger.debug(f"Error canceling stream: {e}")
            self._stream = None
        
        with self._lock:
            self._frames = []
        
        self._state = CaptureState.IDLE
        logger.info("Recording cancelled")
    
    def set_device(self, device_index: Optional[int]) -> bool:
        """
        Set the input device.
        
        Args:
            device_index: Device index (None for default)
        
        Returns:
            True if successful
        """
        if self._state == CaptureState.RECORDING:
            logger.warning("Cannot change device while recording")
            return False
        
        self.device_index = device_index
        logger.info(f"Input device set to {device_index or 'default'}")
        return True


def quick_record(
    duration: float = 3.0,
    device_index: Optional[int] = None,
    save_path: Optional[Path] = None,
) -> CaptureResult:
    """
    Quick recording helper for testing.
    
    Args:
        duration: Recording duration in seconds
        device_index: Input device (None for default)
        save_path: Optional path to save WAV
    
    Returns:
        CaptureResult
    """
    if not AUDIO_AVAILABLE:
        return CaptureResult(
            success=False,
            error="Audio not available"
        )
    
    logging.info(f"Recording for {duration} seconds...")
    
    capture = AudioCapture(
        device_index=device_index,
        on_level_update=lambda rms: logging.info(f"  Level: {'█' * int(rms * 100)} {rms:.3f}", end='\r')
    )
    
    if not capture.start():
        return CaptureResult(success=False, error="Failed to start recording")
    
    try:
        time.sleep(duration)
    except KeyboardInterrupt:
        logging.info("\nInterrupted!")
    
    result = capture.stop(save_path)
    logging.info()  # New line after level meter
    
    return result
