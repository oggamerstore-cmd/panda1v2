"""
PANDA.1 TTS Streamer
====================
Real-time speak-as-it-types with intelligent text chunking.

Version: 0.2.10

Features:
- Buffers streaming text until sentence boundaries
- Generates TTS audio chunks with low latency
- Queues audio for seamless playback
- Supports interruption and cancellation
"""

import re
import time
import logging
import threading
from queue import Queue, Empty
from typing import Optional, Generator, Callable
from dataclasses import dataclass

from .tts_kokoro import KokoroTTS, get_tts, detect_language

logger = logging.getLogger(__name__)


@dataclass
class StreamChunk:
    """A chunk of text ready for TTS."""
    text: str
    lang: str
    is_final: bool = False


class TTSStreamer:
    """
    Real-time TTS streamer for speak-as-it-types.
    
    Buffers incoming text stream and generates TTS audio chunks
    at natural sentence boundaries for low-latency playback.
    
    Usage:
        streamer = TTSStreamer()
        streamer.start()
        
        # Feed text as it streams
        for token in llm_stream:
            streamer.feed(token)
        
        streamer.end()  # Signal end of stream
        
        # Get audio chunks
        for audio in streamer.get_audio():
            play(audio)
    """
    
    # Sentence-ending punctuation
    SENTENCE_ENDS_EN = r'[.!?]'
    SENTENCE_ENDS_KO = r'[.!?。？！]'
    
    # Minimum characters before forcing a chunk
    MIN_CHUNK_CHARS = 40
    MAX_CHUNK_CHARS = 200
    
    def __init__(
        self,
        tts: Optional[KokoroTTS] = None,
        default_lang: str = "en",
        min_chunk_chars: int = 40,
        max_chunk_chars: int = 200,
        on_chunk_ready: Optional[Callable[[bytes], None]] = None,
    ):
        """
        Initialize TTS streamer.
        
        Args:
            tts: KokoroTTS instance (or uses global)
            default_lang: Default language for synthesis
            min_chunk_chars: Minimum characters before chunking
            max_chunk_chars: Maximum characters before forcing chunk
            on_chunk_ready: Callback when audio chunk is ready
        """
        self.tts = tts or get_tts()
        self.default_lang = default_lang
        self.min_chunk_chars = min_chunk_chars
        self.max_chunk_chars = max_chunk_chars
        self.on_chunk_ready = on_chunk_ready
        
        self._text_buffer = ""
        self._audio_queue: Queue = Queue()
        self._text_queue: Queue = Queue()
        self._synthesis_thread: Optional[threading.Thread] = None
        self._running = False
        self._stream_ended = False
        self._lock = threading.Lock()
        
        # Stats
        self._chunks_generated = 0
        self._total_audio_duration = 0.0
    
    @property
    def is_running(self) -> bool:
        """Check if streamer is active."""
        return self._running
    
    def start(self) -> bool:
        """
        Start the streamer.
        
        Returns:
            True if started successfully
        """
        if self._running:
            return True
        
        # Ensure TTS is initialized
        if not self.tts.is_initialized:
            if not self.tts.initialize():
                logger.error("Failed to initialize TTS")
                return False
        
        self._running = True
        self._stream_ended = False
        self._text_buffer = ""
        self._chunks_generated = 0
        self._total_audio_duration = 0.0
        
        # Clear queues
        while not self._audio_queue.empty():
            try:
                self._audio_queue.get_nowait()
            except Empty:
                break
        
        while not self._text_queue.empty():
            try:
                self._text_queue.get_nowait()
            except Empty:
                break
        
        # Start synthesis thread
        self._synthesis_thread = threading.Thread(
            target=self._synthesis_worker,
            daemon=True
        )
        self._synthesis_thread.start()
        
        logger.debug("TTS streamer started")
        return True
    
    def stop(self) -> None:
        """Stop the streamer and discard pending audio."""
        self._running = False
        self._stream_ended = True
        
        # Signal thread to exit
        self._text_queue.put(None)
        
        if self._synthesis_thread and self._synthesis_thread.is_alive():
            self._synthesis_thread.join(timeout=2.0)
        
        logger.debug(
            f"TTS streamer stopped "
            f"(chunks={self._chunks_generated}, dur={self._total_audio_duration:.2f}s)"
        )
    
    def feed(self, text: str) -> None:
        """
        Feed text to the streamer.
        
        Text is buffered and chunked at natural boundaries.
        
        Args:
            text: Text token to add
        """
        if not self._running:
            return
        
        with self._lock:
            self._text_buffer += text
            
            # Check for natural chunk boundaries
            chunks = self._extract_chunks()
            for chunk in chunks:
                self._text_queue.put(chunk)
    
    def end(self) -> None:
        """Signal end of text stream."""
        with self._lock:
            # Flush remaining buffer
            if self._text_buffer.strip():
                lang = detect_language(self._text_buffer)
                self._text_queue.put(StreamChunk(
                    text=self._text_buffer.strip(),
                    lang=lang,
                    is_final=True
                ))
                self._text_buffer = ""
        
        self._stream_ended = True
        self._text_queue.put(None)  # Signal end
    
    def get_audio(self, timeout: float = 0.1) -> Generator[bytes, None, None]:
        """
        Get audio chunks as they become available.
        
        Yields:
            WAV audio bytes
        """
        while self._running or not self._audio_queue.empty():
            try:
                audio = self._audio_queue.get(timeout=timeout)
                if audio is None:
                    break
                yield audio
            except Empty:
                if self._stream_ended and self._audio_queue.empty():
                    break
                continue
    
    def _extract_chunks(self) -> list:
        """Extract complete chunks from buffer."""
        chunks = []
        
        while True:
            # Detect language of current buffer
            lang = detect_language(self._text_buffer)
            pattern = self.SENTENCE_ENDS_KO if lang == "ko" else self.SENTENCE_ENDS_EN
            
            # Find sentence end
            match = re.search(pattern, self._text_buffer)
            
            if match:
                end_pos = match.end()
                
                # Check if we have enough text
                if end_pos >= self.min_chunk_chars or len(self._text_buffer) >= self.max_chunk_chars:
                    chunk_text = self._text_buffer[:end_pos].strip()
                    self._text_buffer = self._text_buffer[end_pos:].lstrip()
                    
                    if chunk_text:
                        chunks.append(StreamChunk(
                            text=chunk_text,
                            lang=lang,
                        ))
                else:
                    break
            elif len(self._text_buffer) >= self.max_chunk_chars:
                # Force chunk at max length
                # Try to break at a space
                break_pos = self._text_buffer.rfind(' ', 0, self.max_chunk_chars)
                if break_pos < self.min_chunk_chars:
                    break_pos = self.max_chunk_chars
                
                chunk_text = self._text_buffer[:break_pos].strip()
                self._text_buffer = self._text_buffer[break_pos:].lstrip()
                
                if chunk_text:
                    chunks.append(StreamChunk(
                        text=chunk_text,
                        lang=lang,
                    ))
            else:
                break
        
        return chunks
    
    def _synthesis_worker(self) -> None:
        """Background thread for TTS synthesis."""
        logger.debug("Synthesis worker started")
        
        while self._running:
            try:
                chunk = self._text_queue.get(timeout=0.1)
                
                if chunk is None:
                    # End signal
                    self._audio_queue.put(None)
                    break
                
                # Synthesize the chunk
                result = self.tts.synthesize(chunk.text, chunk.lang)
                
                if result.success and result.audio_data:
                    self._audio_queue.put(result.audio_data)
                    self._chunks_generated += 1
                    self._total_audio_duration += result.duration
                    
                    # Callback if provided
                    if self.on_chunk_ready:
                        try:
                            self.on_chunk_ready(result.audio_data)
                        except Exception as e:
                            logger.debug(f"Chunk callback error: {e}")
                else:
                    logger.warning(f"Chunk synthesis failed: {result.error}")
                    
            except Empty:
                continue
            except Exception as e:
                logger.error(f"Synthesis worker error: {e}")
        
        logger.debug("Synthesis worker stopped")
    
    def get_stats(self) -> dict:
        """Get streaming statistics."""
        return {
            "running": self._running,
            "stream_ended": self._stream_ended,
            "chunks_generated": self._chunks_generated,
            "total_audio_duration": self._total_audio_duration,
            "pending_audio_chunks": self._audio_queue.qsize(),
            "pending_text_chunks": self._text_queue.qsize(),
            "buffer_length": len(self._text_buffer),
        }


class StreamingPlayer:
    """
    Plays audio chunks from TTS streamer in real-time.
    
    Usage:
        player = StreamingPlayer()
        player.start()
        
        # From streamer
        for audio in streamer.get_audio():
            player.queue(audio)
        
        player.wait()  # Wait for playback to complete
    """
    
    def __init__(self, device_index: Optional[int] = None):
        """
        Initialize streaming player.
        
        Args:
            device_index: Output device index (None for default)
        """
        self.device_index = device_index
        
        self._audio_queue: Queue = Queue()
        self._playback_thread: Optional[threading.Thread] = None
        self._running = False
        self._muted = False
    
    @property
    def is_playing(self) -> bool:
        """Check if currently playing."""
        return self._running and not self._audio_queue.empty()
    
    @property
    def is_muted(self) -> bool:
        """Check if muted."""
        return self._muted
    
    def mute(self, muted: bool = True) -> None:
        """Set mute state."""
        self._muted = muted
    
    def start(self) -> None:
        """Start the player."""
        if self._running:
            return
        
        self._running = True
        self._playback_thread = threading.Thread(
            target=self._playback_worker,
            daemon=True
        )
        self._playback_thread.start()
    
    def stop(self) -> None:
        """Stop the player."""
        self._running = False
        self._audio_queue.put(None)
        
        if self._playback_thread and self._playback_thread.is_alive():
            self._playback_thread.join(timeout=2.0)
    
    def queue(self, audio: bytes) -> None:
        """Queue audio for playback."""
        if self._running:
            self._audio_queue.put(audio)
    
    def wait(self, timeout: Optional[float] = None) -> None:
        """Wait for all queued audio to play."""
        if self._playback_thread:
            self._audio_queue.put(None)  # Signal end
            self._playback_thread.join(timeout=timeout)
    
    def clear(self) -> None:
        """Clear the audio queue."""
        while not self._audio_queue.empty():
            try:
                self._audio_queue.get_nowait()
            except Empty:
                break
    
    def _playback_worker(self) -> None:
        """Background thread for audio playback."""
        try:
            import sounddevice as sd
            import numpy as np
            import wave
            import io
        except ImportError:
            logger.error("sounddevice/numpy not available for playback")
            return
        
        while self._running:
            try:
                audio_bytes = self._audio_queue.get(timeout=0.1)
                
                if audio_bytes is None:
                    break
                
                if self._muted:
                    continue
                
                # Parse WAV
                wav_io = io.BytesIO(audio_bytes)
                with wave.open(wav_io, 'rb') as wav:
                    sample_rate = wav.getframerate()
                    frames = wav.readframes(wav.getnframes())
                    audio = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32767
                
                # Play
                sd.play(audio, sample_rate, device=self.device_index)
                sd.wait()
                
            except Empty:
                continue
            except Exception as e:
                logger.error(f"Playback error: {e}")
