"""
🔧 BASE TOOL CLASS
Foundation for all Alpha Intelligence tools
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List
from dataclasses import dataclass


@dataclass
class ToolResult:
    """Standard result format for all tools"""
    success: bool
    data: Dict[str, Any]
    error: str = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "data": self.data,
            "error": self.error
        }


class BaseTool(ABC):
    """
    Base class for all Alpha Intelligence tools.
    
    Each tool provides access to a specific capability:
    - DP Intelligence: Dark pool levels
    - Narrative Brain: Market context
    - Signal Synthesis: Unified analysis
    - etc.
    """
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Tool name for routing"""
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """Tool description for LLM context"""
        pass
    
    @property
    @abstractmethod
    def capabilities(self) -> List[str]:
        """List of capabilities this tool provides"""
        pass
    
    @property
    def keywords(self) -> List[str]:
        """Keywords that trigger this tool (for simple routing)"""
        return []
    
    @abstractmethod
    def execute(self, params: Dict[str, Any]) -> ToolResult:
        """
        Execute the tool with given parameters.
        
        Args:
            params: Dictionary of parameters (e.g., {"symbol": "SPY"})
            
        Returns:
            ToolResult with success status and data
        """
        pass
    
    def matches_query(self, query: str) -> bool:
        """
        Check if this tool matches a query (simple keyword matching).
        
        Args:
            query: User query string
            
        Returns:
            True if tool should handle this query
        """
        query_lower = query.lower()
        return any(keyword in query_lower for keyword in self.keywords)
    
    def extract_symbol(self, query: str) -> str:
        """
        Extract ticker symbol from query.
        
        Args:
            query: User query string
            
        Returns:
            Symbol (default: SPY)
        """
        # Common symbols to look for
        symbols = ['SPY', 'QQQ', 'AAPL', 'MSFT', 'TSLA', 'NVDA', 'AMZN', 'META', 'GOOGL']
        
        query_upper = query.upper()
        for symbol in symbols:
            if symbol in query_upper:
                return symbol
        
        # Default to SPY
        return 'SPY'
    
    def to_prompt_context(self) -> str:
        """Generate context string for LLM routing prompt"""
        return f"{self.name}: {self.description} - Capabilities: {', '.join(self.capabilities)}"



