#!/usr/bin/env python3
"""
PANDA.1 TTS Smoke Test
======================
Run: python tools/smoke_tts.py
"""

import sys
import os

# Add app to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app'))

def main():
    print("=" * 50)
    print("PANDA.1 TTS Smoke Test")
    print("=" * 50)
    print()
    
    # Test 1: Import base
    print("[1/4] Testing base imports...")
    try:
        from panda_tts.base import TTSEngine, detect_language, chunk_text
        print("  ✓ Base imports OK")
    except Exception as e:
        print(f"  ✗ Base import failed: {e}")
        return 1
    
    # Test 2: Language detection
    print("[2/4] Testing language detection...")
    try:
        assert detect_language("Hello world") == "en"
        assert detect_language("안녕하세요") == "ko"
        assert detect_language("") == "en"
        print("  ✓ Language detection OK")
    except Exception as e:
        print(f"  ✗ Language detection failed: {e}")
        return 1
    
    # Test 3: Text chunking
    print("[3/4] Testing text chunking...")
    try:
        chunks = chunk_text("Hello. World. Test.")
        assert len(chunks) > 0
        print(f"  ✓ Chunking OK ({len(chunks)} chunks)")
    except Exception as e:
        print(f"  ✗ Chunking failed: {e}")
        return 1
    
    # Test 4: Manager with null fallback
    print("[4/4] Testing TTS manager...")
    try:
        from panda_tts.manager import TTSManager
        manager = TTSManager()
        manager.initialize(engine='null')
        
        assert manager.engine_name == 'null'
        assert manager.is_ready
        
        # Test speak
        manager.speak("Test message", blocking=True)
        
        health = manager.healthcheck()
        assert health['healthy']
        
        print(f"  ✓ Manager OK (engine={manager.engine_name})")
    except Exception as e:
        print(f"  ✗ Manager failed: {e}")
        return 1
    
    print()
    print("=" * 50)
    print("✓ All smoke tests passed!")
    print("=" * 50)
    return 0


if __name__ == '__main__':
    sys.exit(main())
