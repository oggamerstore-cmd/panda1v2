"""
PANDA.1 Audio Playback Utilities
================================
Robust non-blocking audio playback for TTS output.

Version: 0.2.11

Features:
- ALSA device selection via PANDA_ALSA_DEVICE
- Custom player override via PANDA_AUDIO_PLAYER
- Fallback chain: aplay -> paplay -> ffplay -> mpv
- Proper error logging with stderr capture
- PCM_16 WAV format support
"""

import os
import logging
import shutil
import subprocess
import threading
import queue
from pathlib import Path
from typing import Optional, Callable, Tuple, List, Dict, Any

logger = logging.getLogger(__name__)


def get_alsa_device() -> str:
    """Get ALSA device from environment."""
    return os.environ.get("PANDA_ALSA_DEVICE", "default")


def get_custom_player() -> Optional[str]:
    """Get custom audio player from environment."""
    return os.environ.get("PANDA_AUDIO_PLAYER")


def list_audio_devices() -> Dict[str, Any]:
    """
    List available audio devices.
    
    Returns:
        Dict with 'alsa_devices', 'pulse_sinks', 'default_alsa'
    """
    result = {
        "alsa_devices": [],
        "pulse_sinks": [],
        "default_alsa": get_alsa_device(),
        "custom_player": get_custom_player()
    }
    
    # Get ALSA devices
    if shutil.which("aplay"):
        try:
            proc = subprocess.run(
                ["aplay", "-l"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if proc.returncode == 0:
                result["alsa_devices"] = proc.stdout.strip().split("\n")
        except Exception as e:
            logger.debug(f"aplay -l failed: {e}")
    
    # Get PulseAudio sinks
    if shutil.which("pactl"):
        try:
            proc = subprocess.run(
                ["pactl", "list", "short", "sinks"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if proc.returncode == 0:
                result["pulse_sinks"] = proc.stdout.strip().split("\n")
        except Exception as e:
            logger.debug(f"pactl failed: {e}")
    
    return result


def print_audio_devices():
    """Print audio devices to stdout."""
    devices = list_audio_devices()
    
    logging.info("=" * 60)
    logging.info("  PANDA.1 Audio Devices")
    logging.info("=" * 60)
    logging.info()
    
    logging.info("Current Settings:")
    logging.info(f"  PANDA_ALSA_DEVICE: {devices['default_alsa']}")
    if devices['custom_player']:
        logging.info(f"  PANDA_AUDIO_PLAYER: {devices['custom_player']}")
    logging.info()
    
    logging.info("ALSA Devices (aplay -l):")
    if devices['alsa_devices']:
        for line in devices['alsa_devices']:
            logging.info(f"  {line}")
    else:
        logging.info("  (none found or aplay not installed)")
    logging.info()
    
    logging.info("PulseAudio Sinks (pactl):")
    if devices['pulse_sinks']:
        for line in devices['pulse_sinks']:
            logging.info(f"  {line}")
    else:
        logging.info("  (none found or pactl not installed)")
    logging.info()
    
    logging.info("To change ALSA device, set PANDA_ALSA_DEVICE in ~/.panda1/.env")
    logging.info("Example: PANDA_ALSA_DEVICE=hw:0,0")


def test_audio_playback() -> bool:
    """
    Test audio playback with a beep.
    
    Returns:
        True if audio played successfully
    """
    import struct
    import math
    
    logging.info("=" * 60)
    logging.info("  PANDA.1 Audio Test")
    logging.info("=" * 60)
    logging.info()
    
    player = get_player()
    logging.info(f"Audio Player: {player.get_player_info()}")
    logging.info(f"ALSA Device: {get_alsa_device()}")
    logging.info()
    
    # Generate a simple beep WAV
    test_wav = Path.home() / ".panda1" / "audio_out" / "test_beep.wav"
    test_wav.parent.mkdir(parents=True, exist_ok=True)
    
    # Generate 440Hz beep for 0.5 seconds
    sample_rate = 44100
    duration = 0.5
    frequency = 440
    num_samples = int(sample_rate * duration)
    
    # Generate samples
    samples = []
    for i in range(num_samples):
        t = i / sample_rate
        value = int(32767 * 0.5 * math.sin(2 * math.pi * frequency * t))
        samples.append(struct.pack('<h', value))
    
    audio_data = b''.join(samples)
    
    # Write WAV file (PCM_16)
    with open(test_wav, 'wb') as f:
        # WAV header
        f.write(b'RIFF')
        f.write(struct.pack('<I', 36 + len(audio_data)))
        f.write(b'WAVE')
        f.write(b'fmt ')
        f.write(struct.pack('<I', 16))  # Subchunk1Size
        f.write(struct.pack('<H', 1))   # AudioFormat (PCM)
        f.write(struct.pack('<H', 1))   # NumChannels
        f.write(struct.pack('<I', sample_rate))  # SampleRate
        f.write(struct.pack('<I', sample_rate * 2))  # ByteRate
        f.write(struct.pack('<H', 2))   # BlockAlign
        f.write(struct.pack('<H', 16))  # BitsPerSample
        f.write(b'data')
        f.write(struct.pack('<I', len(audio_data)))
        f.write(audio_data)
    
    logging.info(f"Generated test beep: {test_wav}")
    logging.info("Playing...")
    logging.info()
    
    success, error = player.play_with_result(test_wav, blocking=True)
    
    if success:
        logging.info("✓ Audio test PASSED")
        logging.info()
        logging.info("If you didn't hear sound, check:")
        logging.info("  1. System volume is up")
        logging.info("  2. Correct audio device selected")
        logging.info("  3. Run: panda --audio-devices")
        return True
    else:
        logging.error(f"✗ Audio test FAILED: {error}")
        logging.info()
        logging.info("Troubleshooting:")
        logging.info("  1. Check ALSA device: panda --audio-devices")
        logging.info("  2. Test with: speaker-test -t sine -f 440 -l 1")
        logging.info("  3. Install audio tools: sudo apt install alsa-utils")
        return False


class AudioPlayer:
    """
    Robust non-blocking audio player.
    
    Features:
    - ALSA device selection
    - Fallback chain: aplay -> paplay -> ffplay -> mpv
    - Error capture and logging
    - Non-blocking queue-based playback
    """
    
    def __init__(self):
        self._playback_thread: Optional[threading.Thread] = None
        self._playback_process: Optional[subprocess.Popen] = None
        self._stop_event = threading.Event()
        self._queue: queue.Queue = queue.Queue()
        self._worker_thread: Optional[threading.Thread] = None
        self._running = False
        self._on_start_callback: Optional[Callable] = None
        self._on_finish_callback: Optional[Callable] = None
        self._last_error: Optional[str] = None
        
        # Find available player
        self._player_cmd, self._player_name = self._find_player()
        
    def _find_player(self) -> Tuple[Optional[List[str]], str]:
        """Find available audio player with ALSA device support."""
        alsa_device = get_alsa_device()
        custom_player = get_custom_player()
        
        # If custom player specified, use it
        if custom_player:
            if shutil.which(custom_player.split()[0]):
                logger.info(f"Using custom player: {custom_player}")
                return custom_player.split(), f"custom ({custom_player.split()[0]})"
            else:
                logger.warning(f"Custom player not found: {custom_player}")
        
        # Build player list with ALSA device support
        players = [
            # aplay with ALSA device
            (["aplay", "-D", alsa_device, "-q"], "aplay"),
            # paplay (PulseAudio)
            (["paplay"], "paplay"),
            # ffplay
            (["ffplay", "-nodisp", "-autoexit", "-loglevel", "error"], "ffplay"),
            # mpv
            (["mpv", "--no-video", "--really-quiet"], "mpv"),
            # sox play
            (["play", "-q"], "sox"),
        ]
        
        for cmd, name in players:
            if shutil.which(cmd[0]):
                logger.info(f"Using audio player: {name}")
                return cmd, name
        
        logger.warning("No audio player found! Install: sudo apt install alsa-utils")
        return None, "none"
    
    def get_player_name(self) -> str:
        """Get name of active player."""
        return self._player_name
    
    def get_player_info(self) -> str:
        """Get detailed player info."""
        if self._player_cmd:
            return f"{self._player_name} ({' '.join(self._player_cmd[:2])})"
        return "none"
    
    def get_last_error(self) -> Optional[str]:
        """Get last playback error."""
        return self._last_error
    
    def start_worker(self):
        """Start background playback worker."""
        if self._running:
            return
        
        self._running = True
        self._stop_event.clear()
        self._worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self._worker_thread.start()
        logger.debug("Audio playback worker started")
    
    def stop_worker(self):
        """Stop background playback worker."""
        self._running = False
        self._stop_event.set()
        
        # Clear queue
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break
        
        # Stop current playback
        self._stop_current()
        
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=2.0)
        
        logger.debug("Audio playback worker stopped")
    
    def _worker_loop(self):
        """Background worker loop."""
        while self._running and not self._stop_event.is_set():
            try:
                # Get next audio file from queue
                audio_path = self._queue.get(timeout=0.5)
                
                if audio_path is None:
                    continue
                
                if self._stop_event.is_set():
                    break
                
                # Play the audio
                self._play_file(audio_path)
                
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Playback worker error: {e}")
                self._last_error = str(e)
    
    def _play_file(self, audio_path: Path) -> bool:
        """Play audio file synchronously with error capture."""
        if not self._player_cmd:
            self._last_error = "No audio player available"
            logger.warning(f"No player available, cannot play: {audio_path}")
            return False
        
        audio_path = Path(audio_path)
        if not audio_path.exists():
            self._last_error = f"Audio file not found: {audio_path}"
            logger.error(self._last_error)
            return False
        
        try:
            # Notify start
            if self._on_start_callback:
                try:
                    self._on_start_callback()
                except Exception as e:
                    logger.error(f"Start callback error: {e}")
            
            cmd = self._player_cmd + [str(audio_path)]
            logger.info(f"Playing: {' '.join(cmd)}")
            
            self._playback_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            # Wait for playback to complete
            while self._playback_process.poll() is None:
                if self._stop_event.is_set():
                    self._playback_process.terminate()
                    self._last_error = "Playback stopped by user"
                    break
                self._stop_event.wait(0.1)
            
            # Capture output
            stdout, stderr = self._playback_process.communicate(timeout=1)
            return_code = self._playback_process.returncode
            
            if return_code != 0 and not self._stop_event.is_set():
                error_msg = stderr.decode('utf-8', errors='ignore').strip()
                self._last_error = f"Player exit code {return_code}: {error_msg}"
                logger.error(f"Playback failed: {self._last_error}")
                return False
            
            self._playback_process = None
            self._last_error = None
            
            # Notify finish
            if self._on_finish_callback:
                try:
                    self._on_finish_callback()
                except Exception as e:
                    logger.error(f"Finish callback error: {e}")
            
            return True
            
        except subprocess.TimeoutExpired:
            self._last_error = "Playback timed out"
            logger.error(self._last_error)
            return False
        except Exception as e:
            self._last_error = str(e)
            logger.error(f"Playback error: {e}")
            return False
    
    def _stop_current(self):
        """Stop current playback."""
        if self._playback_process:
            try:
                self._playback_process.terminate()
                self._playback_process.wait(timeout=1.0)
            except Exception:
                try:
                    self._playback_process.kill()
                except Exception:
                    pass
            self._playback_process = None
    
    def play(self, audio_path: Path, blocking: bool = False) -> bool:
        """
        Queue audio file for playback.
        
        Args:
            audio_path: Path to audio file
            blocking: If True, wait for playback to complete
        
        Returns:
            True if queued/played successfully
        """
        if not self._player_cmd:
            self._last_error = "No audio player available"
            return False
        
        if blocking:
            return self._play_file(audio_path)
        else:
            # Ensure worker is running
            if not self._running:
                self.start_worker()
            
            self._queue.put(audio_path)
            return True
    
    def play_with_result(self, audio_path: Path, blocking: bool = True) -> Tuple[bool, Optional[str]]:
        """
        Play audio and return result with error message.
        
        Returns:
            Tuple of (success, error_message)
        """
        self._last_error = None
        success = self.play(audio_path, blocking=blocking)
        return success, self._last_error
    
    def stop(self):
        """Stop current playback and clear queue."""
        self._stop_event.set()
        
        # Clear queue
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break
        
        self._stop_current()
        
        # Reset stop event for future playback
        self._stop_event.clear()
    
    def set_callbacks(
        self, 
        on_start: Optional[Callable] = None,
        on_finish: Optional[Callable] = None
    ):
        """Set playback callbacks."""
        self._on_start_callback = on_start
        self._on_finish_callback = on_finish
    
    @property
    def is_playing(self) -> bool:
        """Check if currently playing."""
        return self._playback_process is not None
    
    @property
    def queue_size(self) -> int:
        """Get number of items in playback queue."""
        return self._queue.qsize()


# Global player instance
_player: Optional[AudioPlayer] = None


def get_player() -> AudioPlayer:
    """Get global audio player instance."""
    global _player
    if _player is None:
        _player = AudioPlayer()
    return _player


def reset_player():
    """Reset global player (for config changes)."""
    global _player
    if _player:
        _player.stop_worker()
    _player = None
