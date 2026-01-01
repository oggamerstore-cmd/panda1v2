"""
PANDA.1 Audio Device Management
================================
Enumerate and select audio input/output devices.

Version: 0.2.11

Supports:
- sounddevice for cross-platform device enumeration
- ALSA device listing as fallback on Linux
"""

import logging
import subprocess
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Try to import sounddevice
try:
    import sounddevice as sd
    SOUNDDEVICE_AVAILABLE = True
except ImportError:
    SOUNDDEVICE_AVAILABLE = False
    logger.warning("sounddevice not available, audio features limited")


@dataclass
class AudioDevice:
    """Audio device information."""
    index: int
    name: str
    hostapi: str
    max_input_channels: int
    max_output_channels: int
    default_samplerate: float
    is_default_input: bool = False
    is_default_output: bool = False
    
    @property
    def is_input(self) -> bool:
        return self.max_input_channels > 0
    
    @property
    def is_output(self) -> bool:
        return self.max_output_channels > 0
    
    def to_dict(self) -> dict:
        return {
            "index": self.index,
            "name": self.name,
            "hostapi": self.hostapi,
            "max_input_channels": self.max_input_channels,
            "max_output_channels": self.max_output_channels,
            "default_samplerate": self.default_samplerate,
            "is_input": self.is_input,
            "is_output": self.is_output,
            "is_default_input": self.is_default_input,
            "is_default_output": self.is_default_output,
        }


def _get_sounddevice_devices() -> List[AudioDevice]:
    """Get devices using sounddevice."""
    if not SOUNDDEVICE_AVAILABLE:
        return []
    
    devices = []
    try:
        device_list = sd.query_devices()
        hostapis = sd.query_hostapis()
        default_input = sd.default.device[0]
        default_output = sd.default.device[1]
        
        for i, dev in enumerate(device_list):
            hostapi_name = hostapis[dev['hostapi']]['name'] if dev['hostapi'] < len(hostapis) else "Unknown"
            
            device = AudioDevice(
                index=i,
                name=dev['name'],
                hostapi=hostapi_name,
                max_input_channels=dev['max_input_channels'],
                max_output_channels=dev['max_output_channels'],
                default_samplerate=dev['default_samplerate'],
                is_default_input=(i == default_input),
                is_default_output=(i == default_output),
            )
            devices.append(device)
            
    except Exception as e:
        logger.error(f"Error querying sounddevice: {e}")
    
    return devices


def _get_alsa_devices() -> Tuple[List[Dict], List[Dict]]:
    """Get ALSA devices using arecord/aplay (Linux fallback)."""
    input_devices = []
    output_devices = []
    
    # Get recording devices
    try:
        result = subprocess.run(
            ["arecord", "-l"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            for line in result.stdout.split("\n"):
                if line.startswith("card"):
                    # Parse: card 0: Device [Device Name], device 0: ...
                    parts = line.split(":")
                    if len(parts) >= 2:
                        card_info = parts[0].strip()
                        name = parts[1].split(",")[0].strip() if "," in parts[1] else parts[1].strip()
                        input_devices.append({
                            "alsa_id": card_info,
                            "name": name,
                            "type": "input"
                        })
    except Exception as e:
        logger.debug(f"arecord not available: {e}")
    
    # Get playback devices
    try:
        result = subprocess.run(
            ["aplay", "-l"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            for line in result.stdout.split("\n"):
                if line.startswith("card"):
                    parts = line.split(":")
                    if len(parts) >= 2:
                        card_info = parts[0].strip()
                        name = parts[1].split(",")[0].strip() if "," in parts[1] else parts[1].strip()
                        output_devices.append({
                            "alsa_id": card_info,
                            "name": name,
                            "type": "output"
                        })
    except Exception as e:
        logger.debug(f"aplay not available: {e}")
    
    return input_devices, output_devices


def list_all_devices() -> List[AudioDevice]:
    """
    List all audio devices.
    
    Returns:
        List of AudioDevice objects
    """
    return _get_sounddevice_devices()


def list_input_devices() -> List[AudioDevice]:
    """
    List audio input (recording) devices.
    
    Returns:
        List of AudioDevice objects that support input
    """
    return [d for d in list_all_devices() if d.is_input]


def list_output_devices() -> List[AudioDevice]:
    """
    List audio output (playback) devices.
    
    Returns:
        List of AudioDevice objects that support output
    """
    return [d for d in list_all_devices() if d.is_output]


def get_default_input_device() -> Optional[AudioDevice]:
    """Get the default input device."""
    for device in list_input_devices():
        if device.is_default_input:
            return device
    
    # Fallback to first input device
    inputs = list_input_devices()
    return inputs[0] if inputs else None


def get_default_output_device() -> Optional[AudioDevice]:
    """Get the default output device."""
    for device in list_output_devices():
        if device.is_default_output:
            return device
    
    # Fallback to first output device
    outputs = list_output_devices()
    return outputs[0] if outputs else None


def get_device_by_index(index: int) -> Optional[AudioDevice]:
    """Get a device by its index."""
    devices = list_all_devices()
    for device in devices:
        if device.index == index:
            return device
    return None


def validate_device(index: Optional[int], is_input: bool = True) -> Tuple[bool, str]:
    """
    Validate that a device index is valid and usable.
    
    Args:
        index: Device index (None for default)
        is_input: True for input device, False for output
    
    Returns:
        Tuple of (is_valid, message)
    """
    if not SOUNDDEVICE_AVAILABLE:
        return False, "sounddevice not installed"
    
    if index is None:
        # Using default device
        default = get_default_input_device() if is_input else get_default_output_device()
        if default:
            return True, f"Using default: {default.name}"
        return False, "No default device available"
    
    device = get_device_by_index(index)
    if not device:
        return False, f"Device index {index} not found"
    
    if is_input and not device.is_input:
        return False, f"Device {device.name} is not an input device"
    
    if not is_input and not device.is_output:
        return False, f"Device {device.name} is not an output device"
    
    return True, f"Device OK: {device.name}"


def test_input_device(device_index: Optional[int] = None, duration: float = 0.5) -> Dict[str, Any]:
    """
    Test an input device by recording briefly.
    
    Args:
        device_index: Device to test (None for default)
        duration: Test duration in seconds
    
    Returns:
        Dict with test results
    """
    if not SOUNDDEVICE_AVAILABLE:
        return {"success": False, "error": "sounddevice not available"}
    
    try:
        import numpy as np
        
        # Record a short sample
        recording = sd.rec(
            int(duration * 16000),
            samplerate=16000,
            channels=1,
            dtype='float32',
            device=device_index
        )
        sd.wait()
        
        # Calculate RMS
        rms = float(np.sqrt(np.mean(recording ** 2)))
        peak = float(np.max(np.abs(recording)))
        
        return {
            "success": True,
            "device_index": device_index,
            "duration": duration,
            "rms": rms,
            "peak": peak,
            "samples": len(recording),
            "has_signal": rms > 0.001,
        }
        
    except Exception as e:
        return {
            "success": False,
            "device_index": device_index,
            "error": str(e),
        }


def test_output_device(device_index: Optional[int] = None, duration: float = 0.5) -> Dict[str, Any]:
    """
    Test an output device by playing a tone.
    
    Args:
        device_index: Device to test (None for default)
        duration: Test duration in seconds
    
    Returns:
        Dict with test results
    """
    if not SOUNDDEVICE_AVAILABLE:
        return {"success": False, "error": "sounddevice not available"}
    
    try:
        
        # Generate a test tone (440 Hz)
        sample_rate = 44100
        t = np.linspace(0, duration, int(sample_rate * duration), False)
        tone = 0.3 * np.sin(2 * np.pi * 440 * t)
        
        # Fade in/out to avoid clicks
        fade_samples = int(0.01 * sample_rate)
        tone[:fade_samples] *= np.linspace(0, 1, fade_samples)
        tone[-fade_samples:] *= np.linspace(1, 0, fade_samples)
        
        # Play the tone
        sd.play(tone.astype('float32'), sample_rate, device=device_index)
        sd.wait()
        
        return {
            "success": True,
            "device_index": device_index,
            "duration": duration,
            "frequency": 440,
        }
        
    except Exception as e:
        return {
            "success": False,
            "device_index": device_index,
            "error": str(e),
        }


def get_device_info() -> Dict[str, Any]:
    """
    Get comprehensive device information for diagnostics.
    
    Returns:
        Dict with device information
    """
    info = {
        "sounddevice_available": SOUNDDEVICE_AVAILABLE,
        "input_devices": [],
        "output_devices": [],
        "default_input": None,
        "default_output": None,
        "alsa_inputs": [],
        "alsa_outputs": [],
    }
    
    if SOUNDDEVICE_AVAILABLE:
        info["input_devices"] = [d.to_dict() for d in list_input_devices()]
        info["output_devices"] = [d.to_dict() for d in list_output_devices()]
        
        default_in = get_default_input_device()
        default_out = get_default_output_device()
        
        if default_in:
            info["default_input"] = default_in.to_dict()
        if default_out:
            info["default_output"] = default_out.to_dict()
    
    # Get ALSA devices as additional info
    alsa_in, alsa_out = _get_alsa_devices()
    info["alsa_inputs"] = alsa_in
    info["alsa_outputs"] = alsa_out
    
    return info


def print_devices():
    """Print device information to console (for CLI)."""
    logging.info("\n" + "=" * 60)
    logging.info("  PANDA.1 Audio Devices")
    logging.info("=" * 60)
    
    if not SOUNDDEVICE_AVAILABLE:
        logging.info("\n  ⚠ sounddevice not installed!")
        logging.info("  Run: pip install sounddevice")
        return
    
    # Input devices
    logging.info("\n  📥 INPUT DEVICES (Microphones)")
    logging.info("  " + "-" * 40)
    inputs = list_input_devices()
    if inputs:
        for d in inputs:
            default = " ★ DEFAULT" if d.is_default_input else ""
            logging.info(f"  [{d.index:2d}] {d.name[:35]:<35}{default}")
    else:
        logging.info("  No input devices found!")
    
    # Output devices
    logging.info("\n  📤 OUTPUT DEVICES (Speakers)")
    logging.info("  " + "-" * 40)
    outputs = list_output_devices()
    if outputs:
        for d in outputs:
            default = " ★ DEFAULT" if d.is_default_output else ""
            logging.info(f"  [{d.index:2d}] {d.name[:35]:<35}{default}")
    else:
        logging.info("  No output devices found!")
    
    # ALSA info
    alsa_in, alsa_out = _get_alsa_devices()
    if alsa_in or alsa_out:
        logging.info("\n  🐧 ALSA DEVICES")
        logging.info("  " + "-" * 40)
        for d in alsa_in:
            logging.info(f"  [IN]  {d['alsa_id']}: {d['name']}")
        for d in alsa_out:
            logging.info(f"  [OUT] {d['alsa_id']}: {d['name']}")
    
    logging.info()
