"""
🔍 TAVILY CLIENT
================
Deep search API client for non-mainstream, full-context research.

Tavily specializes in:
- Academic sources
- Research papers
- Financial analysis sites
- Expert commentary
- NOT mainstream news regurgitation
"""

import os
import logging
import requests
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class TavilyResult:
    """Single search result from Tavily."""
    title: str
    url: str
    content: str
    score: float = 0.0
    published_date: Optional[str] = None
    
    def __post_init__(self):
        # Clean up content
        if self.content:
            self.content = self.content.strip()


@dataclass  
class TavilyResponse:
    """Full response from Tavily search."""
    query: str
    answer: str  # AI-synthesized answer
    results: List[TavilyResult] = field(default_factory=list)
    response_time: float = 0.0
    
    @property
    def top_sources(self) -> List[str]:
        """Get top source URLs."""
        return [r.url for r in self.results[:3]]
    
    @property
    def full_context(self) -> str:
        """Combine all result content."""
        return "\n\n".join([r.content for r in self.results if r.content])


class TavilyClient:
    """
    Tavily API client for deep, contextual research.
    
    Unlike Perplexity (mainstream news), Tavily digs into:
    - Financial research sites
    - Expert analysis
    - Academic papers
    - Specialized forums
    """
    
    BASE_URL = "https://api.tavily.com"
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Tavily client.
        
        Args:
            api_key: Tavily API key (or TAVILY_API_KEY env var)
        """
        self.api_key = api_key or os.getenv('TAVILY_API_KEY')
        if not self.api_key:
            raise ValueError("TAVILY_API_KEY required")
        
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json'
        })
        
        logger.info("🔍 Tavily client initialized")
    
    def search(
        self,
        query: str,
        search_depth: str = "advanced",  # "basic" or "advanced"
        include_answer: bool = True,
        include_raw_content: bool = False,
        max_results: int = 5,
        include_domains: List[str] = None,
        exclude_domains: List[str] = None,
    ) -> TavilyResponse:
        """
        Execute deep search query.
        
        Args:
            query: Search query (be specific!)
            search_depth: "basic" (faster) or "advanced" (deeper)
            include_answer: Include AI-synthesized answer
            include_raw_content: Include full page content
            max_results: Max results to return
            include_domains: Only search these domains
            exclude_domains: Skip these domains
            
        Returns:
            TavilyResponse with answer and results
        """
        start_time = datetime.now()
        
        # Build request
        payload = {
            "api_key": self.api_key,
            "query": query,
            "search_depth": search_depth,
            "include_answer": include_answer,
            "include_raw_content": include_raw_content,
            "max_results": max_results,
        }
        
        if include_domains:
            payload["include_domains"] = include_domains
        if exclude_domains:
            payload["exclude_domains"] = exclude_domains
        
        try:
            response = self.session.post(
                f"{self.BASE_URL}/search",
                json=payload,
                timeout=30
            )
            response.raise_for_status()
            data = response.json()
            
            # Parse results
            results = []
            for r in data.get('results', []):
                results.append(TavilyResult(
                    title=r.get('title', ''),
                    url=r.get('url', ''),
                    content=r.get('content', ''),
                    score=r.get('score', 0.0),
                    published_date=r.get('published_date')
                ))
            
            elapsed = (datetime.now() - start_time).total_seconds()
            
            return TavilyResponse(
                query=query,
                answer=data.get('answer', ''),
                results=results,
                response_time=elapsed
            )
            
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Tavily search failed: {e}")
            return TavilyResponse(query=query, answer="")
        except Exception as e:
            logger.error(f"❌ Tavily error: {e}")
            return TavilyResponse(query=query, answer="")
    
    def search_financial(
        self,
        query: str,
        max_results: int = 5
    ) -> TavilyResponse:
        """
        Search financial/trading-focused sources.
        
        Includes expert sites, excludes mainstream news.
        """
        return self.search(
            query=query,
            search_depth="advanced",
            max_results=max_results,
            include_domains=[
                "zerohedge.com",
                "seekingalpha.com",
                "investopedia.com",
                "thestreet.com",
                "marketwatch.com",
                "barrons.com",
                "wsj.com",
                "ft.com",
                "bloomberg.com",
                "reuters.com",
            ],
            exclude_domains=[
                "reddit.com",  # Skip retail noise
                "twitter.com",
                "facebook.com",
            ]
        )
    
    def search_fed(
        self,
        query: str,
        max_results: int = 5
    ) -> TavilyResponse:
        """
        Search Fed/central bank focused sources.
        """
        return self.search(
            query=query,
            search_depth="advanced",
            max_results=max_results,
            include_domains=[
                "federalreserve.gov",
                "newyorkfed.org",
                "cmegroup.com",
                "ft.com",
                "wsj.com",
                "bloomberg.com",
                "reuters.com",
            ]
        )
    
    def search_institutional(
        self,
        query: str,
        max_results: int = 5
    ) -> TavilyResponse:
        """
        Search institutional/smart money focused sources.
        """
        return self.search(
            query=query,
            search_depth="advanced", 
            max_results=max_results,
            include_domains=[
                "sec.gov",
                "bloomberg.com",
                "ft.com",
                "wsj.com",
                "hedgeweek.com",
                "institutionalinvestor.com",
                "pensions-investments.com",
            ]
        )

