"""
PANDA.1 PENNY Client
====================
Client for communicating with PENNY (Personal ENterprise financialNY advisor) finance agent.

Version: 2.0

Network Configuration:
- PENNY runs on 192.168.0.119:8003 by default
- Configure via PANDA_PENNY_API_URL environment variable
"""

import logging
from typing import List, Dict, Optional, Any

import requests

logger = logging.getLogger(__name__)


class PennyClient:
    """
    Client for PENNY finance agent API.
    
    PENNY is a separate service that handles finance-related queries
    including business accounting, invoices, expenses, and financial reports.
    """
    
    def __init__(self, base_url: str, timeout: int = 20):
        """
        Initialize PENNY client.
        
        Args:
            base_url: PENNY API base URL (e.g., http://192.168.0.119:8003/api)
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        logger.info(f"PENNY client initialized: {self.base_url}")
    
    def health_check(self) -> Dict[str, Any]:
        """
        Check PENNY health status.
        
        Returns:
            Dict with health info
        """
        result = {
            "healthy": False,
            "url": self.base_url,
            "error": None
        }
        
        try:
            response = requests.get(
                f"{self.base_url}/health",
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                result["healthy"] = True
                result["data"] = response.json()
            else:
                result["error"] = f"Status {response.status_code}"
                
        except requests.exceptions.ConnectionError:
            result["error"] = f"Cannot connect to PENNY at {self.base_url}"
            logger.debug(f"PENNY connection error: {self.base_url}/health")
        except requests.exceptions.Timeout:
            result["error"] = "Connection timeout"
        except Exception as e:
            result["error"] = str(e)
        
        return result
    
    def is_healthy(self) -> bool:
        """Quick health check - returns bool."""
        return self.health_check().get("healthy", False)
    
    def query(
        self, 
        prompt: str, 
        context: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Send a query to PENNY.
        
        Args:
            prompt: The finance-related question or request
            context: Additional context (e.g., date range, brand)
        
        Returns:
            Dict with response from PENNY
        """
        result = {
            "success": False,
            "response": None,
            "error": None
        }
        
        try:
            payload = {
                "prompt": prompt,
                "context": context or {}
            }
            
            response = requests.post(
                f"{self.base_url}/query",
                json=payload,
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                data = response.json()
                result["success"] = True
                result["response"] = data.get("response", data)
                result["data"] = data
            else:
                result["error"] = f"PENNY returned status {response.status_code}"
                try:
                    error_data = response.json()
                    result["error"] = error_data.get("error", result["error"])
                except Exception as e:
                    logging.error(f'Exception caught: {e}')
                    pass
                
        except requests.exceptions.ConnectionError:
            result["error"] = f"Cannot connect to PENNY at {self.base_url}"
            logger.error(f"PENNY connection error: {self.base_url}/query")
        except requests.exceptions.Timeout:
            result["error"] = "PENNY request timed out"
        except Exception as e:
            result["error"] = str(e)
            logger.error(f"PENNY error: {e}")
        
        return result
    
    def get_summary(
        self, 
        period: str = "month",
        brand: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get financial summary from PENNY.
        
        Args:
            period: Time period ('day', 'week', 'month', 'quarter', 'year')
            brand: Optional brand filter
        
        Returns:
            Dict with summary data
        """
        result = {
            "success": False,
            "summary": None,
            "error": None
        }
        
        try:
            params = {"period": period}
            if brand:
                params["brand"] = brand
            
            response = requests.get(
                f"{self.base_url}/summary",
                params=params,
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                data = response.json()
                result["success"] = True
                result["summary"] = data
            else:
                result["error"] = f"Status {response.status_code}"
                
        except requests.exceptions.ConnectionError:
            result["error"] = f"Cannot connect to PENNY"
            logger.debug(f"PENNY connection error: {self.base_url}/summary")
        except Exception as e:
            result["error"] = str(e)
        
        return result
    
    def get_brands(self) -> List[str]:
        """
        Get list of tracked brands from PENNY.
        
        Returns:
            List of brand names
        """
        try:
            response = requests.get(
                f"{self.base_url}/brands",
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get("brands", [])
            return []
            
        except Exception as e:
            logger.debug(f"Failed to get brands: {e}")
            return []
    
    def get_transactions(
        self,
        limit: int = 10,
        brand: Optional[str] = None,
        category: Optional[str] = None
    ) -> List[Dict]:
        """
        Get recent transactions from PENNY.
        
        Args:
            limit: Maximum transactions to return
            brand: Filter by brand
            category: Filter by category
        
        Returns:
            List of transaction dicts
        """
        try:
            params = {"limit": limit}
            if brand:
                params["brand"] = brand
            if category:
                params["category"] = category
            
            response = requests.get(
                f"{self.base_url}/transactions",
                params=params,
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get("transactions", [])
            return []
            
        except Exception as e:
            logger.debug(f"Failed to get transactions: {e}")
            return []


# Finance-related intent patterns
FINANCE_PATTERNS = [
    # Core financial terms
    r"\b(?:money|revenue|income|expense|profit|loss|budget|cost)\b",
    r"\b(?:invoice|receipt|payment|transaction|accounting)\b",
    r"\b(?:sales|earnings|cash flow|balance|account)\b",
    r"\b(?:financial|finance|fiscal|quarterly|monthly)\s+(?:report|summary|status)",
    r"\b(?:how much|total|sum|calculate)\b.*\b(?:money|spent|earned|made)\b",
    r"\b(?:brand|store|shop)\b.*\b(?:revenue|sales|profit)\b",
    # JNJ FOODS LLC brands
    r"\b(?:mama kim|moka|sticky creations|og gamer)\b.*\b(?:sales|revenue|money)\b",
    r"\bjnj\s*foods?\b",
    r"\bmama\s*kim'?s?\s*(?:kimchi|korean\s*bbq|bbq)?\b",
    r"\bmoka'?s?\s*matcha\b",
    # Business operations
    r"\b(?:payroll|employees|wages|salary|salaries)\b",
    r"\b(?:inventory|stock|supplies|orders)\b",
    r"\b(?:taxes|tax|irs|deduction|write-?off)\b",
    r"\b(?:rent|utilities|lease|overhead)\b",
    r"\b(?:loan|credit|debt|interest|financing)\b",
    # PENNY-specific commands
    r"\bask\s+penny\b",
    r"\bpenny\s+(?:check|show|tell|get|what)\b",
    r"\b(?:check|show|tell)\s+(?:me\s+)?(?:the\s+)?(?:finances?|accounting|numbers)\b",
    # Reporting
    r"\b(?:p&l|profit\s*(?:and|&)\s*loss|income\s+statement)\b",
    r"\b(?:balance\s+sheet|cash\s+flow\s+statement)\b",
    r"\b(?:daily|weekly|monthly|quarterly|yearly|annual)\s+(?:report|summary|numbers)\b",
    # Questions
    r"\bhow\s+(?:is|are)\s+(?:the\s+)?(?:business|finances?|sales|we\s+doing)\b",
    r"\bwhat'?s?\s+(?:the|our)\s+(?:revenue|profit|loss|balance|income)\b",
]


def is_finance_query(text: str) -> bool:
    """
    Check if text appears to be a finance-related query.
    
    Args:
        text: User input text
    
    Returns:
        True if appears to be finance-related
    """
    import re
    
    text_lower = text.lower()
    
    for pattern in FINANCE_PATTERNS:
        if re.search(pattern, text_lower, re.IGNORECASE):
            return True
    
    return False
