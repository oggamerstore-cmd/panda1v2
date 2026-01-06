"""
PANDA.1 Voice Assistant
=======================
Voice assistant with wake phrase detection using Faster-Whisper.

Version: 0.2.11

States:
- SLEEPING: Waiting for wake phrase
- AWAKE_LISTENING: Wake phrase detected, listening for command
- PROCESSING: Processing command
- UNAVAILABLE: Microphone not available

Wake Phrases:
- "Hey Panda" or "Yo Panda" (case-insensitive)

Uses:
- Faster-Whisper for ALL speech recognition (wake and command)
- webrtcvad for Voice Activity Detection (reduces CPU)
- Kokoro TTS for speech output (v0.2.10)

v0.2.10 Changes:
- Switched from openai-whisper to faster-whisper (3-4x faster)
- Updated for Kokoro TTS support
- Korean language support improved
"""

import logging
import time
import threading
import queue
from enum import Enum, auto
from typing import Optional, Callable, Any, List, Dict
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class VoiceState(Enum):
    """Voice assistant states."""
    SLEEPING = auto()
    AWAKE_LISTENING = auto()
    PROCESSING = auto()
    SHUTDOWN = auto()
    UNAVAILABLE = auto()  # NEW: Microphone not available


@dataclass
class VoiceEvent:
    """Event from voice assistant."""
    type: str  # 'wake', 'command', 'timeout', 'error', 'state_change'
    data: Any = None
    transcript: Optional[str] = None


class VoiceAssistant:
    """
    Voice assistant with wake phrase detection.
    
    Features:
    - Whisper-based wake phrase detection
    - VAD to reduce unnecessary Whisper calls
    - Configurable wake phrases
    - Auto-sleep after timeout (5 minutes default)
    - Korean + English support
    - Kokoro TTS output
    - Audio input device selection (v0.2.10)
    - GUI integration callbacks (v0.2.10)
    """
    
    def __init__(
        self,
        wake_phrases: Optional[list] = None,
        sleep_timeout: int = 300,  # 5 minutes in seconds
        whisper_model_wake: str = "tiny",
        whisper_model_command: str = "base",
        audio_input_device: Optional[int] = None,
        on_wake: Optional[Callable] = None,
        on_command: Optional[Callable[[str], None]] = None,
        on_state_change: Optional[Callable[[VoiceState], None]] = None,
        on_transcript: Optional[Callable[[str], None]] = None,
    ):
        """
        Initialize voice assistant.
        
        Args:
            wake_phrases: List of wake phrases (default: ["hey panda", "yo panda"])
            sleep_timeout: Seconds before returning to sleep (5 minutes default)
            whisper_model_wake: Whisper model for wake detection (smaller = faster)
            whisper_model_command: Whisper model for command transcription
            audio_input_device: Microphone device index (None for default)
            on_wake: Callback when wake detected
            on_command: Callback when command received
            on_state_change: Callback when state changes
            on_transcript: Callback for live transcript updates
        """
        from .config import get_config
        config = get_config()
        
        self.wake_phrases = wake_phrases or config.wake_phrase_list
        self.sleep_timeout = sleep_timeout or (config.sleep_timeout_minutes * 60)
        self.whisper_model_wake = whisper_model_wake or config.whisper_model_wake
        self.whisper_model_command = whisper_model_command or config.whisper_model_command
        self.audio_input_device = audio_input_device if audio_input_device is not None else config.audio_input_device
        
        # Callbacks
        self.on_wake = on_wake
        self.on_command = on_command
        self.on_state_change = on_state_change
        self.on_transcript = on_transcript
        
        # State
        self._state = VoiceState.SLEEPING
        self._last_activity = time.time()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._event_queue: queue.Queue = queue.Queue()
        self._mic_available = False
        self._mic_info: Optional[Dict] = None
        self._sd = None
        
        # Audio components (initialized lazily)
        self._whisper_model = None
        self._whisper_model_small = None  # For wake detection
        self._vad = None
        self._audio_stream = None
        
        # Config
        self._sample_rate = 16000
        self._chunk_duration = 0.5  # seconds per chunk for VAD
        self._chunk_size = int(self._sample_rate * self._chunk_duration)
        
        logger.info(f"Voice assistant initialized with wake phrases: {self.wake_phrases}")
        logger.info(f"Sleep timeout: {self.sleep_timeout} seconds")
        logger.info(f"Audio input device: {self.audio_input_device or 'default'}")
    
    @property
    def state(self) -> VoiceState:
        """Current state."""
        return self._state
    
    @state.setter
    def state(self, new_state: VoiceState) -> None:
        """Set state and trigger callback."""
        if self._state != new_state:
            old_state = self._state
            self._state = new_state
            logger.info(f"Voice state: {old_state.name} -> {new_state.name}")
            
            # Queue state change event
            self._event_queue.put(VoiceEvent(type='state_change', data=new_state.name))
            
            if self.on_state_change:
                try:
                    self.on_state_change(new_state)
                except Exception as e:
                    logger.error(f"State change callback error: {e}")
    
    @property
    def state_name(self) -> str:
        """Get current state as string."""
        return self._state.name
    
    @property
    def mic_available(self) -> bool:
        """Check if microphone is available."""
        return self._mic_available
    
    @property
    def mic_info(self) -> Optional[Dict]:
        """Get microphone device info."""
        return self._mic_info
    
    def _init_whisper(self) -> bool:
        """Initialize Faster-Whisper models."""
        if self._whisper_model is not None:
            return True
        
        try:
            from faster_whisper import WhisperModel
            
            # Determine compute type based on available hardware
            import torch
            if torch.cuda.is_available():
                device = "cuda"
                compute_type = "float16"
            else:
                device = "cpu"
                compute_type = "int8"
            
            # Load model (faster-whisper uses single model for all sizes)
            model_size = self.whisper_model_command  # e.g., "base", "small"
            logger.info(f"Loading Faster-Whisper model: {model_size} on {device}")
            
            self._whisper_model = WhisperModel(
                model_size,
                device=device,
                compute_type=compute_type
            )
            self._whisper_model_small = self._whisper_model  # Same model for wake detection
            
            logger.info("Faster-Whisper model loaded")
            return True
            
        except ImportError:
            logger.error("faster-whisper not installed. Install: pip install faster-whisper")
            return False
        except Exception as e:
            logger.error(f"Failed to load Faster-Whisper: {e}")
            return False
    
    def _init_vad(self) -> bool:
        """Initialize Voice Activity Detection."""
        if self._vad is not None:
            return True
        
        try:
            import webrtcvad
            self._vad = webrtcvad.Vad(2)  # Aggressiveness 0-3
            logger.info("VAD initialized")
            return True
        except ImportError:
            logger.warning("webrtcvad not installed. VAD disabled. Install: pip install webrtcvad")
            return False
        except Exception as e:
            logger.warning(f"Failed to init VAD: {e}")
            return False
    
    def _init_audio(self) -> bool:
        """Initialize audio input stream."""
        try:
            import sounddevice as sd
            self._sd = sd
            
            # Get device info
            try:
                if self.audio_input_device is not None:
                    # Use specified device
                    device_info = sd.query_devices(self.audio_input_device, 'input')
                    logger.info(f"Using specified input device {self.audio_input_device}: {device_info['name']}")
                else:
                    # Use default input device
                    device_info = sd.query_devices(kind='input')
                    logger.info(f"Using default input device: {device_info['name']}")
                
                self._mic_info = {
                    'index': device_info.get('index', self.audio_input_device),
                    'name': device_info.get('name', 'Unknown'),
                    'channels': device_info.get('max_input_channels', 1),
                    'sample_rate': device_info.get('default_samplerate', 16000)
                }
                self._mic_available = True
                return True
                
            except sd.PortAudioError as e:
                logger.error(f"Audio device error: {e}")
                self._mic_available = False
                self._mic_info = None
                return False
            except ValueError as e:
                logger.error(f"Invalid audio device index {self.audio_input_device}: {e}")
                self._mic_available = False
                self._mic_info = None
                return False
                
        except ImportError:
            logger.error("sounddevice not installed. Install: pip install sounddevice")
            self._mic_available = False
            return False
        except Exception as e:
            logger.error(f"Failed to init audio: {e}")
            self._mic_available = False
            return False
    
    def _transcribe(self, audio_data, use_small_model: bool = False) -> Optional[str]:
        """Transcribe audio using Faster-Whisper."""
        model = self._whisper_model_small if use_small_model else self._whisper_model
        if model is None:
            return None
        
        try:
            import numpy as np
            import tempfile
            import soundfile as sf
            
            # Ensure audio is float32 and normalized
            if audio_data.dtype != np.float32:
                audio_data = audio_data.astype(np.float32) / 32768.0
            
            # Faster-whisper needs a file path or array
            # Write to temp file for reliability
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                temp_path = f.name
                sf.write(temp_path, audio_data, 16000)
            
            try:
                # Transcribe with faster-whisper
                segments, info = model.transcribe(
                    temp_path,
                    language=None,  # Auto-detect for Korean+English
                    vad_filter=True,
                    beam_size=5,
                )
                
                # Collect all segment text
                text_parts = []
                for segment in segments:
                    text_parts.append(segment.text)
                
                text = " ".join(text_parts).strip()
            finally:
                # Clean up temp file
                import os
                try:
                    os.unlink(temp_path)
                except Exception as e:
                    logging.error(f'Exception caught: {e}')
                    pass
            
            # Send live transcript callback
            if text and self.on_transcript:
                try:
                    self.on_transcript(text)
                except Exception as e:
                    logger.error(f"Transcript callback error: {e}")
            
            return text if text else None
            
        except Exception as e:
            logger.error(f"Transcription error: {e}")
            return None
    
    def _is_wake_phrase(self, text: str) -> bool:
        """Check if text contains wake phrase."""
        if not text:
            return False
        
        text_lower = text.lower().strip()
        
        for phrase in self.wake_phrases:
            if phrase in text_lower:
                return True
        
        return False
    
    def _check_speech(self, audio_chunk) -> bool:
        """Check if audio chunk contains speech using VAD."""
        if self._vad is None:
            return True  # If no VAD, assume always speech
        
        import numpy as np

        try:
            
            # Convert to 16-bit PCM if needed
            if audio_chunk.dtype == np.float32:
                audio_int16 = (audio_chunk * 32767).astype(np.int16)
            else:
                audio_int16 = audio_chunk
            
            # VAD expects 10, 20, or 30ms frames at 16kHz
            frame_length = int(self._sample_rate * 0.03)  # 30ms
            
            # Check multiple frames
            speech_frames = 0
            total_frames = 0
            
            for i in range(0, len(audio_int16) - frame_length, frame_length):
                frame = audio_int16[i:i + frame_length].tobytes()
                if self._vad.is_speech(frame, self._sample_rate):
                    speech_frames += 1
                total_frames += 1
            
            # Consider speech if >30% of frames contain speech
            if total_frames > 0:
                return (speech_frames / total_frames) > 0.3
            
            return False
            
        except Exception as e:
            logger.warning(f"VAD check error: {e}")
            return True  # Assume speech on error
    
    def _check_sleep_timeout(self) -> bool:
        """Check if we should return to sleep."""
        if self._state == VoiceState.AWAKE_LISTENING:
            if time.time() - self._last_activity > self.sleep_timeout:
                logger.info("Sleep timeout reached")
                self.state = VoiceState.SLEEPING
                self._event_queue.put(VoiceEvent(type='timeout'))
                return True
        return False
    
    def _listen_loop(self) -> None:
        """Main listening loop."""
        
        logger.info("Voice assistant listening loop started")
        import numpy as np

        try:
            # Recording parameters
            recording = False
            audio_buffer = []
            buffer_duration = 0.0
            max_buffer_duration = 10.0  # Max 10 seconds
            silence_count = 0
            max_silence = 4  # Number of silent chunks before processing
            
            # Build input stream kwargs
            stream_kwargs = {
                'samplerate': self._sample_rate,
                'channels': 1,
                'dtype': 'int16',
                'blocksize': self._chunk_size
            }
            
            # Add device if specified
            if self.audio_input_device is not None:
                stream_kwargs['device'] = self.audio_input_device
            
            sd = self._sd
            if sd is None:
                raise RuntimeError("sounddevice not available")

            with sd.InputStream(**stream_kwargs) as stream:
                
                while self._running:
                    # Check sleep timeout
                    self._check_sleep_timeout()
                    
                    # Read audio chunk
                    chunk, _ = stream.read(self._chunk_size)
                    chunk = chunk.flatten()
                    
                    # Check for speech
                    has_speech = self._check_speech(chunk)
                    
                    if has_speech:
                        silence_count = 0
                        if not recording:
                            recording = True
                            audio_buffer = []
                            buffer_duration = 0.0
                        
                        audio_buffer.append(chunk)
                        buffer_duration += self._chunk_duration
                        
                    elif recording:
                        silence_count += 1
                        audio_buffer.append(chunk)
                        buffer_duration += self._chunk_duration
                        
                        # Stop after silence
                        if silence_count >= max_silence or buffer_duration >= max_buffer_duration:
                            # Transcribe
                            if audio_buffer:
                                full_audio = np.concatenate(audio_buffer)
                                
                                # Use small model for wake detection when sleeping
                                use_small = (self._state == VoiceState.SLEEPING)
                                text = self._transcribe(full_audio, use_small_model=use_small)
                                
                                if text:
                                    self._handle_transcription(text)
                            
                            # Reset
                            audio_buffer = []
                            buffer_duration = 0.0
                            recording = False
                            silence_count = 0
                    
                    # Small delay to reduce CPU
                    time.sleep(0.01)
                    
        except Exception as e:
            logger.error(f"Listening loop error: {e}")
            self._event_queue.put(VoiceEvent(type='error', data=str(e)))
        
        logger.info("Voice assistant listening loop stopped")
    
    def _handle_transcription(self, text: str) -> None:
        """Handle transcribed text based on state."""
        logger.debug(f"Transcription: {text}")
        
        if self._state == VoiceState.SLEEPING:
            # Check for wake phrase
            if self._is_wake_phrase(text):
                logger.info(f"Wake phrase detected: {text}")
                self.state = VoiceState.AWAKE_LISTENING
                self._last_activity = time.time()
                self._event_queue.put(VoiceEvent(type='wake', transcript=text))
                
                if self.on_wake:
                    try:
                        self.on_wake()
                    except Exception as e:
                        logger.error(f"Wake callback error: {e}")
        
        elif self._state == VoiceState.AWAKE_LISTENING:
            # Check for another wake phrase (ignore)
            if self._is_wake_phrase(text):
                self._last_activity = time.time()
                return
            
            # This is a command
            if text.strip():
                self._last_activity = time.time()
                self.state = VoiceState.PROCESSING
                self._event_queue.put(VoiceEvent(type='command', transcript=text))
                
                if self.on_command:
                    try:
                        self.on_command(text)
                    except Exception as e:
                        logger.error(f"Command callback error: {e}")
                
                # Return to listening
                self.state = VoiceState.AWAKE_LISTENING
                self._last_activity = time.time()
    
    def start(self) -> bool:
        """
        Start the voice assistant.
        
        Returns:
            True if started successfully
        """
        if self._running:
            logger.warning("Voice assistant already running")
            return False
        
        # Initialize audio first to check mic availability
        if not self._init_audio():
            logger.warning("Microphone not available - voice assistant disabled")
            self.state = VoiceState.UNAVAILABLE
            return False
        
        # Initialize Whisper
        if not self._init_whisper():
            self.state = VoiceState.UNAVAILABLE
            return False
        
        self._init_vad()  # Optional
        
        # Start listening thread
        self._running = True
        self.state = VoiceState.SLEEPING
        self._thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._thread.start()
        
        logger.info("Voice assistant started")
        return True
    
    def stop(self) -> None:
        """Stop the voice assistant."""
        self._running = False
        self.state = VoiceState.SHUTDOWN
        
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        
        logger.info("Voice assistant stopped")
    
    def get_event(self, timeout: Optional[float] = None) -> Optional[VoiceEvent]:
        """
        Get next event from voice assistant.
        
        Args:
            timeout: Timeout in seconds (None for non-blocking)
        
        Returns:
            VoiceEvent or None
        """
        try:
            return self._event_queue.get(block=timeout is not None, timeout=timeout)
        except queue.Empty:
            return None
    
    def wake(self) -> None:
        """Manually wake the assistant."""
        if self._state == VoiceState.SLEEPING:
            self.state = VoiceState.AWAKE_LISTENING
            self._last_activity = time.time()
            self._event_queue.put(VoiceEvent(type='wake', data='manual'))
            logger.info("Manually woken")
    
    def sleep(self) -> None:
        """Manually put assistant to sleep."""
        if self._state != VoiceState.SLEEPING and self._state != VoiceState.UNAVAILABLE:
            self.state = VoiceState.SLEEPING
            logger.info("Manually slept")
    
    def get_status(self) -> dict:
        """Get voice assistant status."""
        return {
            "state": self._state.name,
            "running": self._running,
            "mic_available": self._mic_available,
            "mic_info": self._mic_info,
            "wake_phrases": self.wake_phrases,
            "audio_input_device": self.audio_input_device,
            "whisper_model_wake": self.whisper_model_wake,
            "whisper_model_command": self.whisper_model_command,
            "sleep_timeout": self.sleep_timeout,
            "last_activity": self._last_activity,
        }


def list_audio_devices() -> Dict[str, Any]:
    """
    List all audio input and output devices.
    
    Returns:
        Dict with 'input_devices', 'output_devices', 'default_input', 'default_output'
    """
    result = {
        "input_devices": [],
        "output_devices": [],
        "default_input": None,
        "default_output": None,
        "sounddevice_available": False,
        "error": None
    }
    
    try:
        result["sounddevice_available"] = True
        
        devices = sd.query_devices()
        
        for i, dev in enumerate(devices):
            device_info = {
                "index": i,
                "name": dev['name'],
                "hostapi": dev['hostapi'],
                "sample_rate": dev['default_samplerate']
            }
            
            if dev['max_input_channels'] > 0:
                device_info['input_channels'] = dev['max_input_channels']
                result["input_devices"].append(device_info.copy())
            
            if dev['max_output_channels'] > 0:
                device_info['output_channels'] = dev['max_output_channels']
                result["output_devices"].append(device_info.copy())
        
        # Get defaults
        try:
            default_input = sd.query_devices(kind='input')
            result["default_input"] = {
                "index": devices.index(default_input) if default_input in devices else None,
                "name": default_input['name']
            }
        except Exception:
            pass
        
        try:
            default_output = sd.query_devices(kind='output')
            result["default_output"] = {
                "index": devices.index(default_output) if default_output in devices else None,
                "name": default_output['name']
            }
        except Exception:
            pass
            
    except ImportError:
        result["error"] = "sounddevice not installed. Install: pip install sounddevice"
    except Exception as e:
        result["error"] = str(e)
    
    return result


def print_audio_devices():
    """Print audio devices to stdout (input and output)."""
    devices = list_audio_devices()
    
    logging.info()
    logging.info("=" * 70)
    logging.info("  PANDA.1 Audio Devices (v0.2.11)")
    logging.info("=" * 70)
    logging.info()
    
    if devices.get("error"):
        logging.error(f"Error: {devices['error']}")
        logging.info()
        return
    
    if not devices["sounddevice_available"]:
        logging.info("sounddevice not available")
        logging.info("Install: pip install sounddevice")
        logging.info()
        return
    
    # Input devices (microphones)
    logging.info("INPUT DEVICES (Microphones):")
    logging.info("-" * 40)
    if devices["input_devices"]:
        for dev in devices["input_devices"]:
            default_marker = " [DEFAULT]" if (
                devices.get("default_input") and 
                dev["index"] == devices["default_input"].get("index")
            ) else ""
            logging.info(f"  [{dev['index']:2d}] {dev['name']}{default_marker}")
            logging.info(f"       Channels: {dev.get('input_channels', '?')}, Rate: {dev.get('sample_rate', '?')} Hz")
    else:
        logging.info("  (No input devices found)")
    logging.info()
    
    # Output devices (speakers)
    logging.info("OUTPUT DEVICES (Speakers):")
    logging.info("-" * 40)
    if devices["output_devices"]:
        for dev in devices["output_devices"]:
            default_marker = " [DEFAULT]" if (
                devices.get("default_output") and 
                dev["index"] == devices["default_output"].get("index")
            ) else ""
            logging.info(f"  [{dev['index']:2d}] {dev['name']}{default_marker}")
            logging.info(f"       Channels: {dev.get('output_channels', '?')}, Rate: {dev.get('sample_rate', '?')} Hz")
    else:
        logging.info("  (No output devices found)")
    logging.info()
    
    # Current config
    config = get_config()
    logging.info("Current Configuration:")
    logging.info("-" * 40)
    logging.info(f"  PANDA_AUDIO_INPUT_DEVICE: {config.audio_input_device or 'default'}")
    logging.info(f"  PANDA_AUDIO_OUTPUT_DEVICE: {config.audio_output_device or 'default'}")
    logging.info(f"  PANDA_ALSA_DEVICE: {config.alsa_device}")
    logging.info()
    logging.info("To set input device, add to ~/.panda1/.env:")
    logging.info("  PANDA_AUDIO_INPUT_DEVICE=<index>")
    logging.info()


def mic_test(duration: float = 3.0, save_wav: bool = True) -> Dict[str, Any]:
    """
    Record audio from microphone and report levels.
    
    Args:
        duration: Recording duration in seconds
        save_wav: If True, save recording to file
    
    Returns:
        Dict with test results
    """
    result = {
        "success": False,
        "device_index": None,
        "device_name": None,
        "duration": duration,
        "rms": None,
        "peak": None,
        "wav_path": None,
        "error": None
    }
    
    try:
        
        config = get_config()
        
        device_index = config.audio_input_device
        
        # Get device info
        if device_index is not None:
            device_info = sd.query_devices(device_index, 'input')
        else:
            device_info = sd.query_devices(kind='input')
            device_index = None
        
        result["device_index"] = device_index
        result["device_name"] = device_info['name']
        
        logging.info(f"Recording {duration}s from: {device_info['name']}")
        logging.info("Speak now...")
        
        # Record
        sample_rate = 16000
        recording = sd.rec(
            int(duration * sample_rate),
            samplerate=sample_rate,
            channels=1,
            dtype='float32',
            device=device_index
        )
        sd.wait()
        
        logging.info("Recording complete.")
        
        # Calculate levels
        audio = recording.flatten()
        rms = np.sqrt(np.mean(audio ** 2))
        peak = np.max(np.abs(audio))
        
        result["rms"] = float(rms)
        result["peak"] = float(peak)
        result["success"] = True
        
        logging.info(f"RMS Level: {rms:.4f}")
        logging.info(f"Peak Level: {peak:.4f}")
        
        # Interpret levels
        if rms < 0.001:
            logging.info("⚠ Very low audio level - check microphone connection")
        elif rms < 0.01:
            logging.info("○ Low audio level - try speaking louder")
        elif rms < 0.1:
            logging.info("✓ Good audio level")
        else:
            logging.info("⚠ High audio level - may cause clipping")
        
        # Save WAV if requested
        if save_wav:
            import struct
            
            wav_dir = config.audio_in_test_dir
            wav_dir.mkdir(parents=True, exist_ok=True)
            
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            wav_path = wav_dir / f"mic_test_{timestamp}.wav"
            
            # Convert to int16
            audio_int16 = (audio * 32767).astype(np.int16)
            audio_bytes = audio_int16.tobytes()
            
            with open(wav_path, 'wb') as f:
                # WAV header
                f.write(b'RIFF')
                f.write(struct.pack('<I', 36 + len(audio_bytes)))
                f.write(b'WAVE')
                f.write(b'fmt ')
                f.write(struct.pack('<I', 16))  # Subchunk1Size
                f.write(struct.pack('<H', 1))   # AudioFormat (PCM)
                f.write(struct.pack('<H', 1))   # NumChannels
                f.write(struct.pack('<I', sample_rate))
                f.write(struct.pack('<I', sample_rate * 2))  # ByteRate
                f.write(struct.pack('<H', 2))   # BlockAlign
                f.write(struct.pack('<H', 16))  # BitsPerSample
                f.write(b'data')
                f.write(struct.pack('<I', len(audio_bytes)))
                f.write(audio_bytes)
            
            result["wav_path"] = str(wav_path)
            logging.info(f"Saved: {wav_path}")
        
    except ImportError:
        result["error"] = "sounddevice not installed"
        logging.error("Error: sounddevice not installed")
        logging.info("Install: pip install sounddevice")
    except Exception as e:
        result["error"] = str(e)
        logging.error(f"Error: {e}")
    
    return result


def run_voice_assistant() -> int:
    """Run voice assistant as main mode."""
    from panda_core import PandaCore
    from tts import speak, is_tts_available
    from language_mode import process_language_command, get_language_mode
    
    config = get_config()
    panda = PandaCore()
    tts_available = is_tts_available()
    
    def on_wake():
        """Called when wake phrase detected."""
        if tts_available and config.voice_ack_enabled:
            speak("Yes BOS.", block=True)
    
    def on_command(text: str):
        """Called when command received."""
        logging.info(f"\n[You]: {text}")
        
        # Check for language switch
        is_switch, ack = process_language_command(text)
        if is_switch and ack:
            logging.info(f"[PANDA.1]: {ack}")
            if tts_available:
                speak(ack, block=True)
            return
        
        # Process command
        response = panda.process(text)
        logging.info(f"[PANDA.1]: {response}")
        
        if tts_available:
            speak(response, block=True)
    
    def on_state_change(state: VoiceState):
        """Called when state changes."""
        if state == VoiceState.SLEEPING:
            logging.info("[Status: Sleeping - say 'Hey Panda' or 'Yo Panda' to wake]")
        elif state == VoiceState.AWAKE_LISTENING:
            logging.info("[Status: Listening for command...]")
        elif state == VoiceState.PROCESSING:
            logging.info("[Status: Processing...]")
        elif state == VoiceState.UNAVAILABLE:
            logging.info("[Status: Microphone unavailable]")
    
    # Create and start assistant
    assistant = VoiceAssistant(
        wake_phrases=config.wake_phrase_list,
        sleep_timeout=config.sleep_timeout_minutes * 60,
        whisper_model_wake=config.whisper_model_wake,
        whisper_model_command=config.whisper_model_command,
        audio_input_device=config.audio_input_device,
        on_wake=on_wake,
        on_command=on_command,
        on_state_change=on_state_change,
    )
    
    logging.info()
    logging.info("=" * 50)
    logging.info("PANDA.1 Voice Assistant v0.2.11")
    logging.info("=" * 50)
    logging.info()
    logging.info(f"Wake phrases: {', '.join(config.wake_phrase_list)}")
    logging.info(f"Timeout: {config.sleep_timeout_minutes} minutes")
    logging.info(f"Audio input device: {config.audio_input_device or 'default'}")
    logging.info(f"Whisper wake model: {config.whisper_model_wake}")
    logging.info(f"Whisper command model: {config.whisper_model_command}")
    logging.info(f"TTS: {'Chatterbox (offline)' if tts_available else 'Not available'}")
    logging.info()
    logging.info("Press Ctrl+C to exit")
    logging.info()
    
    if not assistant.start():
        logging.error("Failed to start voice assistant")
        if not assistant.mic_available:
            logging.info("Microphone not available. Check:")
            logging.info("  1. Run: panda --audio-devices")
            logging.info("  2. Set PANDA_AUDIO_INPUT_DEVICE in ~/.panda1/.env")
        return 1
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logging.info("\nShutting down...")
    finally:
        assistant.stop()
    
    return 0
