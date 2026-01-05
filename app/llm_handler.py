"""
PANDA.1 LLM Handler
===================
Handles communication with Ollama for local LLM inference.

Version: 0.2.11

Features:
- Configurable Ollama endpoint (supports localhost and remote)
- Model name matching (panda1 matches panda1:latest)
- /api/chat with fallback to /api/generate for older Ollama
- Streaming and non-streaming generation
- Health check and model verification
- Graceful offline handling

Network Notes:
- Default: http://localhost:11434 (local Ollama)
- Remote: Ollama must be bound to 0.0.0.0:11434
- See docs/NETWORKING.md for LAN configuration
"""

import logging
import requests
import json
from typing import List, Dict, Optional, Generator, Any

from config import get_config

logger = logging.getLogger(__name__)


class OllamaConnectionError(Exception):
    """Raised when Ollama is unreachable."""
    pass


class OllamaModelNotFoundError(Exception):
    """Raised when specified model is not available."""
    pass


class LLMHandler:
    """
    Handler for Ollama LLM communication.
    
    Provides:
    - Synchronous and streaming generation
    - Model availability checking
    - Health check functionality
    - Automatic fallback model support
    
    Configuration:
    - Uses PANDA_OLLAMA_HOST environment variable
    - Default: http://localhost:11434
    """
    
    def __init__(self):
        """Initialize the LLM handler."""
        self.config = get_config()
        self.base_url = self.config.ollama_host
        self.model = self.config.llm_model
        self.fallback_model = self.config.llm_fallback_model
        self.temperature = self.config.llm_temperature
        self.max_tokens = self.config.llm_max_tokens
        self.context_length = self.config.llm_context_length
        
        # Track API capabilities
        self._has_chat_api = True  # Assume yes until 404
        self._chat_fallback_warned = False
        self._active_model: Optional[str] = None
        
        # Verify connection on init
        self._verify_connection()
    
    def _model_name_matches(self, model_name: str, available_models: List[str]) -> bool:
        """
        Check if a model name matches any available model.
        
        Handles the case where config has 'panda1' but Ollama shows 'panda1:latest'.
        A model name without colon is treated as a base name that matches any tag.
        
        Args:
            model_name: Model name to check
            available_models: List of available model names from Ollama
        
        Returns:
            True if model exists (exact match or base name match)
        """
        # Exact match
        if model_name in available_models:
            return True
        
        # Base name match: if model has no colon, check for any tag
        if ':' not in model_name:
            base_prefix = model_name + ':'
            for name in available_models:
                if name.startswith(base_prefix) or name == model_name:
                    return True
        
        return False
    
    def _verify_connection(self) -> None:
        """Verify Ollama is accessible and determine which model to use."""
        try:
            response = requests.get(
                f"{self.base_url}/api/tags",
                timeout=5
            )
            
            if response.status_code != 200:
                logger.warning(f"Ollama returned status {response.status_code}")
                return
            
            models = response.json().get('models', [])
            model_names = [m.get('name', '') for m in models]
            
            # Check primary model
            if self._model_name_matches(self.model, model_names):
                self._active_model = self.model
                logger.info(f"LLM Handler initialized: {self.model} @ {self.base_url}")
                return
            
            # Try fallback model
            if self._model_name_matches(self.fallback_model, model_names):
                self._active_model = self.fallback_model
                logger.warning(
                    f"Primary model '{self.model}' not found. "
                    f"Using fallback: {self.fallback_model}"
                )
                return
            
            # No suitable model found
            logger.error(
                f"Neither '{self.model}' nor '{self.fallback_model}' found. "
                f"Available models: {model_names}"
            )
            logger.info(f"To fix, run: ollama pull {self.fallback_model}")
            self._active_model = self.model  # Try anyway
            
        except requests.exceptions.ConnectionError:
            logger.error(
                f"Cannot connect to Ollama at {self.base_url}. "
                "Ensure Ollama is running: systemctl status ollama"
            )
            self._active_model = self.model
        except Exception as e:
            logger.error(f"Error verifying Ollama connection: {e}")
            self._active_model = self.model
    
    def health_check(self) -> Dict[str, Any]:
        """
        Comprehensive health check for Ollama.
        
        Returns dict with:
        - healthy: bool - Overall health status
        - connected: bool - Can reach Ollama
        - models: list - Available models
        - primary_model_available: bool - Is panda1:latest present
        - fallback_model_available: bool - Is fallback present
        - active_model: str - Currently active model
        - error: str|None - Error message if any
        """
        result = {
            "healthy": False,
            "connected": False,
            "url": self.base_url,
            "models": [],
            "primary_model": self.model,
            "primary_model_available": False,
            "fallback_model": self.fallback_model,
            "fallback_model_available": False,
            "active_model": self._active_model,
            "error": None
        }
        
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            
            if response.status_code != 200:
                result["error"] = f"Ollama returned status {response.status_code}"
                return result
            
            result["connected"] = True
            
            models = response.json().get('models', [])
            model_names = [m.get('name', '') for m in models]
            result["models"] = model_names
            
            # Check model availability
            result["primary_model_available"] = self._model_name_matches(
                self.model, model_names
            )
            result["fallback_model_available"] = self._model_name_matches(
                self.fallback_model, model_names
            )
            
            # Overall health: connected and at least one model available
            result["healthy"] = (
                result["primary_model_available"] or 
                result["fallback_model_available"]
            )
            
        except requests.exceptions.ConnectionError:
            result["error"] = f"Cannot connect to Ollama at {self.base_url}"
        except requests.exceptions.Timeout:
            result["error"] = f"Timeout connecting to Ollama at {self.base_url}"
        except Exception as e:
            result["error"] = str(e)
        
        return result
    
    def is_healthy(self) -> bool:
        """Quick health check - just returns bool."""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            return response.status_code == 200
        except Exception as e:
            logging.error(f'Exception caught: {e}')
            return False
    
    def list_models(self) -> List[str]:
        """List available Ollama models."""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            response.raise_for_status()
            models = response.json().get('models', [])
            return [m.get('name', '') for m in models]
        except Exception as e:
            logger.error(f"Could not list models: {e}")
            return []
    
    def generate(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """
        Generate a response (non-streaming).
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            **kwargs: Additional generation parameters
        
        Returns:
            Generated text response
        
        Raises:
            OllamaConnectionError: If Ollama is unreachable
        """
        model = self._active_model or self.model
        
        try:
            if self._has_chat_api:
                return self._generate_via_chat(messages, model, **kwargs)
            else:
                return self._generate_via_generate(messages, model, **kwargs)
        except requests.exceptions.ConnectionError:
            raise OllamaConnectionError(
                f"Cannot connect to Ollama at {self.base_url}. "
                "Is Ollama running? Try: systemctl status ollama"
            )
    
    def _generate_via_chat(
        self, 
        messages: List[Dict[str, str]], 
        model: str,
        **kwargs
    ) -> str:
        """Generate using /api/chat endpoint."""
        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": kwargs.get('temperature', self.temperature),
                "num_predict": kwargs.get('max_tokens', self.max_tokens),
                "num_ctx": kwargs.get('context_length', self.context_length),
            }
        }
        
        response = requests.post(
            f"{self.base_url}/api/chat",
            json=payload,
            timeout=120
        )
        
        # Handle 404 - fallback to /api/generate
        if response.status_code == 404:
            if not self._chat_fallback_warned:
                logger.info("Ollama /api/chat not available, using /api/generate")
                self._chat_fallback_warned = True
            self._has_chat_api = False
            return self._generate_via_generate(messages, model, **kwargs)
        
        response.raise_for_status()
        return response.json().get('message', {}).get('content', '')
    
    def _generate_via_generate(
        self, 
        messages: List[Dict[str, str]], 
        model: str,
        **kwargs
    ) -> str:
        """Generate using /api/generate endpoint (legacy fallback)."""
        # Convert messages to single prompt
        prompt = self._messages_to_prompt(messages)
        
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": kwargs.get('temperature', self.temperature),
                "num_predict": kwargs.get('max_tokens', self.max_tokens),
                "num_ctx": kwargs.get('context_length', self.context_length),
            }
        }
        
        response = requests.post(
            f"{self.base_url}/api/generate",
            json=payload,
            timeout=120
        )
        response.raise_for_status()
        return response.json().get('response', '')
    
    def generate_stream(
        self, 
        messages: List[Dict[str, str]], 
        **kwargs
    ) -> Generator[str, None, None]:
        """
        Generate a response with streaming.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            **kwargs: Additional generation parameters
        
        Yields:
            Text chunks as they are generated
        """
        model = self._active_model or self.model
        
        try:
            if self._has_chat_api:
                yield from self._stream_via_chat(messages, model, **kwargs)
            else:
                yield from self._stream_via_generate(messages, model, **kwargs)
        except requests.exceptions.ConnectionError:
            yield "[Error: Cannot connect to Ollama. Is it running?]"
    
    def _stream_via_chat(
        self, 
        messages: List[Dict[str, str]], 
        model: str,
        **kwargs
    ) -> Generator[str, None, None]:
        """Stream using /api/chat endpoint."""
        payload = {
            "model": model,
            "messages": messages,
            "stream": True,
            "options": {
                "temperature": kwargs.get('temperature', self.temperature),
                "num_predict": kwargs.get('max_tokens', self.max_tokens),
                "num_ctx": kwargs.get('context_length', self.context_length),
            }
        }
        
        response = requests.post(
            f"{self.base_url}/api/chat",
            json=payload,
            stream=True,
            timeout=120
        )
        
        if response.status_code == 404:
            self._has_chat_api = False
            yield from self._stream_via_generate(messages, model, **kwargs)
            return
        
        response.raise_for_status()
        
        for line in response.iter_lines():
            if line:
                try:
                    data = json.loads(line)
                    if 'message' in data and 'content' in data['message']:
                        yield data['message']['content']
                except json.JSONDecodeError:
                    continue
    
    def _stream_via_generate(
        self, 
        messages: List[Dict[str, str]], 
        model: str,
        **kwargs
    ) -> Generator[str, None, None]:
        """Stream using /api/generate endpoint."""
        prompt = self._messages_to_prompt(messages)
        
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": True,
            "options": {
                "temperature": kwargs.get('temperature', self.temperature),
                "num_predict": kwargs.get('max_tokens', self.max_tokens),
                "num_ctx": kwargs.get('context_length', self.context_length),
            }
        }
        
        response = requests.post(
            f"{self.base_url}/api/generate",
            json=payload,
            stream=True,
            timeout=120
        )
        response.raise_for_status()
        
        for line in response.iter_lines():
            if line:
                try:
                    data = json.loads(line)
                    if 'response' in data:
                        yield data['response']
                except json.JSONDecodeError:
                    continue
    
    def _messages_to_prompt(self, messages: List[Dict[str, str]]) -> str:
        """Convert chat messages to a single prompt string."""
        parts = []
        for msg in messages:
            role = msg.get('role', 'user')
            content = msg.get('content', '')
            if role == 'system':
                parts.append(f"System: {content}")
            elif role == 'assistant':
                parts.append(f"Assistant: {content}")
            else:
                parts.append(f"User: {content}")
        parts.append("Assistant:")
        return "\n\n".join(parts)
    
    def get_model_info(self) -> Dict:
        """Get information about the current model."""
        model = self._active_model or self.model
        try:
            response = requests.post(
                f"{self.base_url}/api/show",
                json={"name": model},
                timeout=10
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Could not get model info: {e}")
            return {}
    
    def pull_model(self, model_name: str) -> bool:
        """
        Pull a model from Ollama registry.
        
        Args:
            model_name: Name of the model to pull
        
        Returns:
            True if successful
        """
        try:
            logger.info(f"Pulling model: {model_name}")
            response = requests.post(
                f"{self.base_url}/api/pull",
                json={"name": model_name},
                stream=True,
                timeout=3600  # 1 hour for large models
            )
            response.raise_for_status()
            
            for line in response.iter_lines():
                if line:
                    data = json.loads(line)
                    status = data.get('status', '')
                    if 'completed' in status.lower():
                        logger.info(f"Model pull complete: {model_name}")
            
            return True
        except Exception as e:
            logger.error(f"Failed to pull model: {e}")
            return False
