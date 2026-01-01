"""
PANDA.1 Core Orchestrator
=========================
Central hub for coordinating all PANDA.1 components.

Version: 0.2.11

Features:
- BOS-specific system prompt
- SCOTT news agent integration
- PENNY finance agent integration
- OpenAI cloud LLM for research/latest info
- SENSEI learning hub integration (deep learning from lessons)
- Intent-based command routing with example matching
- Language mode switching (Korean/English)
- Memory system with identity awareness
- Graceful offline handling for all services

Routing Rules:
- News/headlines -> SCOTT
- Research/latest/current -> OpenAI (if enabled)
- Learn/SENSEI commands -> SENSEI (downloads to memory)
- Everything else -> Local Ollama
"""

import logging
import re
from typing import Optional, Dict, Any, Generator, Tuple
from pathlib import Path

from config import get_config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class PandaCore:
    """
    Main orchestrator for PANDA.1 - BOS Personal Edition.

    Coordinates between:
    - LLM Handler (Ollama integration)
    - OpenAI Client (cloud LLM for research)
    - Memory System (conversation history + identity)
    - Voice Handler (STT/TTS)
    - Mood System (emotional state)
    - SCOTT Client (news agent)
    - PENNY Client (finance agent)
    - SENSEI Client (learning hub)
    - Intent Detector (command routing)
    - Language Mode Manager
    """
    
    def __init__(self):
        """Initialize PANDA.1 core."""
        self.config = get_config()
        
        # Initialize LLM handler (Ollama)
        from llm_handler import LLMHandler
        self.llm = LLMHandler()
        logger.info(f"LLM initialized: {self.config.llm_model}")
        
        # Initialize OpenAI client (optional)
        self.openai_client = None
        if self.config.cloud_llm_enabled:
            try:
                from openai_client import OpenAIClient
                self.openai_client = OpenAIClient()
                if self.openai_client.is_available():
                    logger.info(f"OpenAI client initialized: {self.config.openai_model}")
                else:
                    logger.warning("OpenAI client not available (no API key?)")
                    self.openai_client = None
            except Exception as e:
                logger.warning(f"OpenAI client unavailable: {e}")
        
        # Initialize memory system (optional)
        self.memory = None
        if self.config.enable_memory:
            try:
                from memory import MemorySystem
                self.memory = MemorySystem()
                if self.memory.is_available:
                    logger.info("Memory system initialized")
            except Exception as e:
                logger.warning(f"Memory unavailable: {e}")
        
        # Initialize mood system (optional)
        self.mood = None
        try:
            from mood_system import MoodSystem
            self.mood = MoodSystem()
            logger.info("Mood system initialized")
        except ImportError:
            pass
        
        # Initialize language mode manager
        from language_mode import get_language_manager
        self.lang_manager = get_language_manager()
        logger.info(f"Language mode: {self.lang_manager.mode}")
        
        # Initialize intent detector (optional)
        self.intent_detector = None
        if self.config.enable_intent_detection:
            try:
                from intent_detector import IntentDetector
                self.intent_detector = IntentDetector()
                logger.info("Intent detector initialized")
            except ImportError:
                pass
        
        # Initialize example-based intent matcher (optional)
        self.intent_matcher = None
        try:
            from example_intent_matcher import get_intent_matcher
            self.intent_matcher = get_intent_matcher()
            status = self.intent_matcher.get_status()
            logger.info(f"Intent matcher initialized: {status['total_examples']} examples")
        except Exception as e:
            logger.debug(f"Intent matcher not available: {e}")
        
        # Initialize SCOTT client (optional)
        self.scott_client = None
        if self.config.scott_enabled:
            try:
                from scott_client import ScottClient
                self.scott_client = ScottClient(
                    base_url=self.config.scott_api_url,
                    timeout=self.config.scott_timeout
                )
                logger.info(f"SCOTT client initialized: {self.config.scott_api_url}")
            except ImportError:
                pass
        
        # Initialize PENNY client (optional)
        self.penny_client = None
        if self.config.penny_enabled:
            try:
                from penny_client import PennyClient
                self.penny_client = PennyClient(
                    base_url=self.config.penny_api_url,
                    timeout=self.config.penny_timeout
                )
                logger.info(f"PENNY client initialized: {self.config.penny_api_url}")
            except ImportError:
                pass

        # Initialize SENSEI client (optional)
        self.sensei_client = None
        if self.config.sensei_enabled:
            try:
                from sensei_client import SenseiClient
                self.sensei_client = SenseiClient(
                    base_url=self.config.sensei_api_url,
                    timeout=self.config.sensei_timeout
                )
                logger.info(f"SENSEI client initialized: {self.config.sensei_api_url}")
            except ImportError:
                pass

        # Initialize ECHO client (optional)
        self.echo_client = None
        if self.config.echo_enabled:
            try:
                from echo_client import EchoClient
                api_key = self.config.echo_api_key or None
                self.echo_client = EchoClient(
                    base_url=self.config.echo_base_url,
                    timeout=self.config.echo_timeout,
                    api_key=api_key,
                )
                logger.info(f"ECHO client initialized: {self.config.echo_base_url}")
            except ImportError:
                pass

        # Conversation history
        self.conversation_history = []
        self.max_history = 10
        
        # System prompt - BOS-specific
        self.system_prompt = self._build_system_prompt()
        
        logger.info("PANDA.1 Core v0.2.11 initialized")
    
    def _build_system_prompt(self) -> str:
        """Build the BOS-specific system prompt for the LLM."""
        base_prompt = """The only user is BOS. Always call him BOS, never "user".
BOS runs JNJ FOODS LLC with brands: Mama Kim's Kimchi, Mama Kim's Korean BBQ, Moka's Matcha.
Follow BOS's preferences for concise, practical answers with clear next actions.
You are PANDA.1, BOS's Personal AI Navigator & Digital Assistant."""
        
        # Add language instruction
        base_prompt += self.lang_manager.get_system_prompt_suffix()
        
        return base_prompt
    
    def _is_news_query(self, text: str) -> bool:
        """Check if this is a news query (should go to SCOTT)."""
        text_lower = text.lower()
        news_keywords = [
            'news', 'headlines', 'top stories', 'breaking',
            'what happened', 'korea news', 'tech news',
            'world news', 'latest news', 'today\'s news',
            'current events', 'news about'
        ]
        return any(kw in text_lower for kw in news_keywords)
    
    def _is_research_query(self, text: str) -> bool:
        """Check if this needs OpenAI for research/latest info."""
        from openai_client import is_research_query, is_time_sensitive_query
        return is_research_query(text) or is_time_sensitive_query(text)

    def _is_learning_command(self, text: str) -> bool:
        """Check if this is a learning command (should go to SENSEI)."""
        from sensei_client import is_learning_command
        return is_learning_command(text)

    def _get_routing_target(self, user_input: str) -> Tuple[str, float]:
        """
        Determine routing target for user input.

        Returns:
            Tuple of (target, confidence)
            target: 'scott', 'penny', 'openai', 'sensei', 'local'
        """
        # Check for explicit commands
        if user_input.startswith('/cloud '):
            return 'openai', 1.0
        if user_input.startswith('/local '):
            return 'local', 1.0
        if user_input.startswith('/news '):
            return 'scott', 1.0
        if user_input.startswith('/learn '):
            return 'sensei', 1.0
        if user_input.startswith('/echo '):
            return 'echo', 1.0

        # Learning commands go to SENSEI
        if self._is_learning_command(user_input):
            if self.sensei_client:
                return 'sensei', 0.95

        # News queries go to SCOTT
        if self._is_news_query(user_input):
            if self.scott_client:
                return 'scott', 0.9

        # Research/latest queries go to OpenAI
        if self._is_research_query(user_input) and self.openai_client:
            return 'openai', 0.85

        # Try example-based matching
        if self.intent_matcher:
            from example_intent_matcher import match_intent
            result = match_intent(user_input)
            
            if result.confidence >= self.config.intent_confidence_threshold:
                return result.routing_target, result.confidence
        
        # Fall back to regex patterns
        if self.intent_detector:
            intent = self.intent_detector.detect(user_input)
            
            if intent == "news" and self.scott_client:
                return "scott", 0.8
        
        # Check for finance patterns
        if self.penny_client:
            from penny_client import is_finance_query
            if is_finance_query(user_input):
                return "penny", 0.7
        
        return "local", 0.5
    
    def process(self, user_input: str, **kwargs) -> str:
        """
        Process user input and generate a response.
        
        Args:
            user_input: The user's message
            **kwargs: Additional context
        
        Returns:
            Response string
        """
        if not user_input.strip():
            return "I didn't catch that, BOS. Could you say that again?"
        
        try:
            # Check for language switch command
            from language_mode import process_language_command
            is_switch, ack = process_language_command(user_input)
            if is_switch and ack:
                # Update system prompt
                self.system_prompt = self._build_system_prompt()
                return ack
            
            # Strip command prefixes
            actual_input = user_input
            if user_input.startswith('/cloud '):
                actual_input = user_input[7:]
            elif user_input.startswith('/local '):
                actual_input = user_input[7:]
            elif user_input.startswith('/news '):
                actual_input = user_input[6:]
            elif user_input.startswith('/learn '):
                actual_input = user_input[7:]
            elif user_input.startswith('/echo '):
                actual_input = user_input[6:]
            elif user_input.startswith('/echo '):
                actual_input = user_input[6:]

            # Route based on intent
            target, confidence = self._get_routing_target(user_input)

            if target == "sensei" and self.sensei_client:
                return self._handle_sensei_learning(actual_input)

            if target == "scott" and self.scott_client:
                return self._handle_news_intent(actual_input)

            if target == "penny" and self.penny_client:
                return self._handle_penny_intent(actual_input)

            if target == "echo" and self.echo_client:
                return self._handle_echo_query(actual_input)

            if target == "openai" and self.openai_client:
                return self._handle_openai_query(actual_input)
            
            # Default: Local LLM processing
            messages = self._build_messages(actual_input)
            response = self.llm.generate(messages, **kwargs)
            
            self._add_to_history(actual_input, response)
            
            if self.memory and self.memory.is_available:
                self._store_memory(actual_input, response)
            
            return response
            
        except Exception as e:
            logger.error(f"Error processing input: {e}")
            if self.lang_manager.mode == "ko":
                return f"처리 중 오류가 발생했습니다: {str(e)}"
            return f"Sorry BOS, an error occurred: {str(e)}"
    
    def process_stream(self, user_input: str, **kwargs) -> Generator[str, None, None]:
        """
        Process user input and stream the response.
        
        Args:
            user_input: The user's message
            **kwargs: Additional context
        
        Yields:
            Response chunks
        """
        if not user_input.strip():
            yield "I didn't catch that, BOS. Could you say that again?"
            return
        
        try:
            # Check for language switch
            from language_mode import process_language_command
            is_switch, ack = process_language_command(user_input)
            if is_switch and ack:
                self.system_prompt = self._build_system_prompt()
                yield ack
                return
            
            # Strip command prefixes
            actual_input = user_input
            if user_input.startswith('/cloud '):
                actual_input = user_input[7:]
            elif user_input.startswith('/local '):
                actual_input = user_input[7:]
            elif user_input.startswith('/news '):
                actual_input = user_input[6:]
            elif user_input.startswith('/learn '):
                actual_input = user_input[7:]

            # Route based on intent
            target, confidence = self._get_routing_target(user_input)

            if target == "sensei" and self.sensei_client:
                yield self._handle_sensei_learning(actual_input)
                return

            if target == "scott" and self.scott_client:
                yield self._handle_news_intent(actual_input)
                return

            if target == "penny" and self.penny_client:
                yield self._handle_penny_intent(actual_input)
                return

            if target == "echo" and self.echo_client:
                yield self._handle_echo_query(actual_input)
                return

            if target == "openai" and self.openai_client:
                # Stream from OpenAI
                messages = self._build_messages(actual_input)
                full_response = ""
                for chunk in self.openai_client.generate_stream(messages, **kwargs):
                    full_response += chunk
                    yield chunk
                self._add_to_history(actual_input, full_response)
                return
            
            # Build messages
            messages = self._build_messages(actual_input)
            
            # Stream response from local LLM
            full_response = ""
            for chunk in self.llm.generate_stream(messages, **kwargs):
                full_response += chunk
                yield chunk
            
            # Store after complete
            self._add_to_history(actual_input, full_response)
            
            if self.memory and self.memory.is_available:
                self._store_memory(actual_input, full_response)
                
        except Exception as e:
            logger.error(f"Error in streaming: {e}")
            yield f"\n[Error: {str(e)}]"
    
    def _build_messages(self, user_input: str) -> list:
        """Build message list for LLM including context."""
        # Update system prompt with current language
        current_prompt = self._build_system_prompt()
        messages = [{"role": "system", "content": current_prompt}]
        
        # Add conversation history
        for exchange in self.conversation_history[-self.max_history:]:
            messages.append({"role": "user", "content": exchange["user"]})
            messages.append({"role": "assistant", "content": exchange["assistant"]})
        
        # Add memory context if available
        if self.memory and self.memory.is_available:
            try:
                relevant = self.memory.search(user_input, limit=3)
                if relevant:
                    context = "\n".join([f"- {m['content']}" for m in relevant])
                    messages[0]["content"] += f"\n\nRelevant memories:\n{context}"
            except Exception:
                pass

        if self.echo_client:
            try:
                echo_context = self._get_echo_context(user_input)
                if echo_context:
                    messages[0]["content"] += f"\n\nECHO context:\n{echo_context}"
            except Exception:
                pass
        
        # Add current input
        messages.append({"role": "user", "content": user_input})
        
        return messages

    def _get_echo_context(self, user_input: str) -> str:
        """Fetch top-k context snippets from ECHO."""
        if not self.echo_client or not user_input.strip():
            return ""
        result = self.echo_client.query(
            user_input,
            top_k=self.config.echo_top_k,
        )
        if not result.get("success"):
            return ""
        items = result.get("results", [])
        if not items:
            return ""
        return "\n".join([f"- {item.get('text', '')}" for item in items if item.get("text")])
    
    def _add_to_history(self, user_input: str, response: str) -> None:
        """Add exchange to conversation history."""
        self.conversation_history.append({
            "user": user_input,
            "assistant": response
        })
        
        # Trim history
        while len(self.conversation_history) > self.max_history:
            self.conversation_history.pop(0)
    
    def _store_memory(self, user_input: str, response: str) -> None:
        """Store exchange in memory system."""
        try:
            # Check for explicit "remember this" commands
            remember_patterns = [
                r"remember (?:this|that)[:\s]+(.+)",
                r"(?:please )?(?:don't forget|note)[:\s]+(.+)",
                r"save (?:this|that)[:\s]+(.+)",
            ]
            
            for pattern in remember_patterns:
                match = re.search(pattern, user_input, re.IGNORECASE)
                if match:
                    fact = match.group(1).strip()
                    self.memory.store(fact, memory_type="fact")
                    return
        except Exception as e:
            logger.warning(f"Could not store memory: {e}")
    
    def _handle_openai_query(self, user_input: str) -> str:
        """Handle query via OpenAI."""
        if not self.openai_client:
            return "OpenAI is not configured."
        
        try:
            messages = self._build_messages(user_input)
            response = self.openai_client.generate(messages)
            
            self._add_to_history(user_input, response)
            return response
            
        except Exception as e:
            logger.error(f"OpenAI error: {e}")
            # Fall back to local LLM
            logger.info("Falling back to local LLM")
            messages = self._build_messages(user_input)
            return self.llm.generate(messages)
    
    def _handle_news_intent(self, user_input: str) -> str:
        """Handle news-related requests via SCOTT."""
        if not self.scott_client:
            if self.lang_manager.mode == "ko":
                return "뉴스 기능(SCOTT)이 설정되어 있지 않습니다."
            return "News feature (SCOTT) is not configured."
        
        try:
            # Check SCOTT health first
            if not self.scott_client.is_healthy():
                if self.lang_manager.mode == "ko":
                    return "SCOTT에 연결할 수 없습니다. 나중에 다시 시도해주세요."
                return "Cannot connect to SCOTT. Please try again later."
            
            # Parse for topic/count
            count = 5  # default
            topic = None
            
            # Extract count
            count_match = re.search(r'(?:top\s+)?(\d+)', user_input)
            if count_match:
                count = min(int(count_match.group(1)), 20)
            
            # Get articles
            articles = self.scott_client.get_top_articles(limit=count, topic=topic)
            
            if not articles:
                if self.lang_manager.mode == "ko":
                    return "현재 사용 가능한 뉴스 기사가 없습니다, BOS."
                return "No news articles available right now, BOS."
            
            # Format response
            if self.lang_manager.mode == "ko":
                lines = [f"주요 뉴스 {len(articles)}개입니다:"]
            else:
                lines = [f"Here are the top {len(articles)} news stories:"]
            
            for i, article in enumerate(articles, 1):
                title = article.get('title', 'Untitled')
                source = article.get('source', 'Unknown')
                lines.append(f"\n{i}. **{title}**\n   Source: {source}")
            
            return "\n".join(lines)
            
        except Exception as e:
            logger.error(f"SCOTT error: {e}")
            if self.lang_manager.mode == "ko":
                return f"뉴스를 가져올 수 없습니다: {str(e)}"
            return f"Couldn't fetch news: {str(e)}"
    
    def _handle_penny_intent(self, user_input: str) -> str:
        """Handle finance-related requests via PENNY."""
        if not self.penny_client:
            if self.lang_manager.mode == "ko":
                return "재무 기능(PENNY)이 설정되어 있지 않습니다."
            return "Finance feature (PENNY) is not configured."
        
        try:
            # Check PENNY health first
            if not self.penny_client.is_healthy():
                # Fall back to LLM with note
                logger.info("PENNY offline, falling back to LLM")
                messages = self._build_messages(user_input)
                response = self.llm.generate(messages)
                
                if self.lang_manager.mode == "ko":
                    note = "\n\n[참고: PENNY가 오프라인이어서 일반 지식으로 응답했습니다.]"
                else:
                    note = "\n\n[Note: PENNY is offline, responded from general knowledge.]"
                
                return response + note
            
            # Query PENNY
            result = self.penny_client.query(user_input)
            
            if result.get("success"):
                return result.get("response", "No response from PENNY.")
            else:
                # Fall back to LLM
                error = result.get("error", "Unknown error")
                logger.warning(f"PENNY query failed: {error}")
                
                messages = self._build_messages(user_input)
                response = self.llm.generate(messages)
                
                if self.lang_manager.mode == "ko":
                    note = f"\n\n[참고: PENNY 오류 ({error}), 일반 지식으로 응답했습니다.]"
                else:
                    note = f"\n\n[Note: PENNY error ({error}), responded from general knowledge.]"
                
                return response + note
            
        except Exception as e:
            logger.error(f"PENNY error: {e}")
            # Fall back to LLM
            messages = self._build_messages(user_input)
            return self.llm.generate(messages)

    def _handle_echo_query(self, user_input: str) -> str:
        """Handle explicit ECHO queries."""
        if not self.echo_client:
            if self.lang_manager.mode == "ko":
                return "ECHO 기능이 설정되어 있지 않습니다."
            return "ECHO is not configured."

        try:
            if not self.echo_client.is_healthy():
                if self.lang_manager.mode == "ko":
                    return "ECHO에 연결할 수 없습니다. 나중에 다시 시도해주세요."
                return "Cannot connect to ECHO. Please try again later."

            result = self.echo_client.query(
                user_input,
                top_k=self.config.echo_top_k,
            )
            if not result.get("success"):
                error = result.get("error", "Unknown error")
                if self.lang_manager.mode == "ko":
                    return f"ECHO 쿼리 실패: {error}"
                return f"ECHO query failed: {error}"

            items = result.get("results", [])
            if not items:
                if self.lang_manager.mode == "ko":
                    return "ECHO에서 일치하는 컨텍스트가 없습니다."
                return "No matching context from ECHO."

            if self.lang_manager.mode == "ko":
                lines = ["ECHO에서 찾은 컨텍스트입니다:"]
            else:
                lines = ["Here is the context from ECHO:"]

            for i, item in enumerate(items, 1):
                text = item.get("text", "")
                score = item.get("score")
                score_line = f" (score: {score:.3f})" if isinstance(score, float) else ""
                lines.append(f"\n{i}. {text}{score_line}")

            return "\n".join(lines)
        except Exception as exc:
            logger.error(f"ECHO error: {exc}")
            if self.lang_manager.mode == "ko":
                return f"ECHO 오류: {str(exc)}"
            return f"ECHO error: {str(exc)}"

    def _handle_sensei_learning(self, user_input: str) -> str:
        """
        Handle learning requests via SENSEI.

        Downloads knowledge from SENSEI and stores it in memory.
        """
        if not self.sensei_client:
            if self.lang_manager.mode == "ko":
                return "학습 기능(SENSEI)이 설정되어 있지 않습니다."
            return "Learning feature (SENSEI) is not configured."

        try:
            # Check SENSEI health first
            if not self.sensei_client.is_healthy():
                if self.lang_manager.mode == "ko":
                    return "SENSEI에 연결할 수 없습니다. 나중에 다시 시도해주세요."
                return "Cannot connect to SENSEI. Please try again later."

            # Extract topic if specified
            topic = None
            topic_keywords = ["about", "on", "regarding", "for"]
            input_lower = user_input.lower()
            for kw in topic_keywords:
                if kw in input_lower:
                    parts = input_lower.split(kw)
                    if len(parts) > 1:
                        topic = parts[-1].strip()
                        break

            # Download knowledge from SENSEI
            result = self.sensei_client.download_knowledge(topic=topic)

            if not result.get("success"):
                error = result.get("error", "Unknown error")
                if self.lang_manager.mode == "ko":
                    return f"SENSEI에서 지식을 다운로드할 수 없습니다: {error}"
                return f"Could not download knowledge from SENSEI: {error}"

            knowledge_items = result.get("knowledge", [])
            count = result.get("count", 0)

            if count == 0:
                if self.lang_manager.mode == "ko":
                    return "SENSEI에 학습할 새로운 내용이 없습니다."
                return "No new lessons available from SENSEI."

            # Store knowledge in memory
            stored_count = 0
            if self.memory and self.memory.is_available:
                for item in knowledge_items:
                    content = item.get("content", item) if isinstance(item, dict) else str(item)
                    category = item.get("category", "sensei") if isinstance(item, dict) else "sensei"

                    if content:
                        self.memory.store(
                            content=content,
                            memory_type="fact",
                            metadata={
                                "source": "sensei",
                                "category": category,
                                "topic": topic or "general"
                            }
                        )
                        stored_count += 1

                logger.info(f"Stored {stored_count} knowledge items from SENSEI")

                if self.lang_manager.mode == "ko":
                    return f"SENSEI에서 {stored_count}개의 지식을 학습했습니다, BOS!"
                return f"Learned {stored_count} knowledge items from SENSEI, BOS!"
            else:
                if self.lang_manager.mode == "ko":
                    return f"SENSEI에서 {count}개의 항목을 받았지만 메모리 시스템이 비활성화되어 있습니다."
                return f"Received {count} items from SENSEI but memory system is not available."

        except Exception as e:
            logger.error(f"SENSEI learning error: {e}")
            if self.lang_manager.mode == "ko":
                return f"학습 중 오류가 발생했습니다: {str(e)}"
            return f"Error during learning: {str(e)}"

    def get_status(self) -> Dict[str, Any]:
        """Get comprehensive system status."""
        status = {
            "version": "0.2.11",
            "llm": self.llm.health_check(),
            "openai": None,
            "memory": None,
            "scott": None,
            "penny": None,
            "sensei": None,
            "echo": None,
            "mood": None,
            "language": self.lang_manager.mode,
        }

        if self.openai_client:
            status["openai"] = self.openai_client.get_status()

        if self.memory:
            status["memory"] = self.memory.get_status()

        if self.scott_client:
            status["scott"] = self.scott_client.health_check()

        if self.penny_client:
            status["penny"] = self.penny_client.health_check()

        if self.sensei_client:
            status["sensei"] = self.sensei_client.health_check()

        if self.echo_client:
            status["echo"] = self.echo_client.health_check()

        if self.mood:
            status["mood"] = self.mood.get_state()

        return status
    
    def get_mood_state(self) -> Dict[str, Any]:
        """Get current mood state for GUI."""
        if self.mood:
            return self.mood.get_state()
        return {"mood": "neutral", "color": "#00d4ff"}
    
    def clear_history(self) -> None:
        """Clear conversation history."""
        self.conversation_history = []
        logger.info("Conversation history cleared")
