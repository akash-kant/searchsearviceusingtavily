"""
Search Service for Maya - Her connection to the world's knowledge.

This module uses the Tavily Search API to answer general knowledge questions,
find local businesses, stock prices, get sports scores, and more. This is a key component
in making Maya a true all-in-one assistant, a core tenet of our billion-dollar vision.

Added Features & Enhancements:
1. Multiple search types: general, news, image
2. Cleans and summarizes extracted content from URLs for readability
3. Keyword extraction from content to provide insights
4. Extract full content from URLs to enrich search results
5. Caching with TTL for repeated queries to improve efficiency
6. Async wrapper for synchronous Tavily client to avoid blocking
7. Configurable search options: depth, include/exclude domains, time frame, language
8. DuckDuckGo fallback search if Tavily is unavailable
9. Logging of queries with phone number for monitoring
10. Graceful error handling to ensure robust operation
11. Supports structured insights, formatted results, and direct answers
"""


import os
import asyncio
import hashlib
import time
import json
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass
from dotenv import load_dotenv
load_dotenv()

# Optional: Web extraction & NLP
import requests
import re
from bs4 import BeautifulSoup
import spacy

# Defensive import of Tavily client
try:
    from tavily import TavilyClient
except ImportError:
    TavilyClient = None
    print("⚠️ 'tavily-python' not installed. Web search will be disabled.")

# Load SpaCy model for keyword extraction & summarization
nlp = spacy.load("en_core_web_sm")

# --- Configuration ---
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
CACHE_TTL = 60 * 10       # 10 min for normal searches
NEWS_CACHE_TTL = 60 * 5   # 5 min for news

@dataclass
class SearchConfig:
    """Configuration for each search query"""
    search_depth: str = "advanced"        # 'basic' or 'advanced'
    include_images: bool = False
    include_domains: List[str] = None
    exclude_domains: List[str] = None
    max_results: int = 10
    search_type: str = "general"          # general, news, image
    time_frame: str = "auto"              # auto, day, week, month
    language: str = "en"

# --- Caching system ---
class AdvancedCache:
    """Cache with TTL, supports different search types"""
    def __init__(self):
        self.cache = {}

    def get_key(self, query: str, config: SearchConfig) -> str:
        """Unique cache key based on query and config"""
        config_str = json.dumps({
            'depth': config.search_depth,
            'type': config.search_type,
            'time': config.time_frame
        })
        return hashlib.sha256(f"{query}:{config_str}".encode()).hexdigest()

    def get(self, query: str, config: SearchConfig) -> Optional[Dict]:
        key = self.get_key(query, config)
        if key in self.cache:
            data, timestamp = self.cache[key]
            ttl = NEWS_CACHE_TTL if config.search_type == "news" else CACHE_TTL
            if time.time() - timestamp < ttl:
                return data
            del self.cache[key]
        return None

    def set(self, query: str, config: SearchConfig, data: Dict):
        key = self.get_key(query, config)
        self.cache[key] = (data, time.time())

# --- Utility Functions ---
def clean_text(text: str) -> str:
    """Remove boilerplate and extra whitespace"""
    text = re.sub(r"(LOGIN|Subscribe|e-?Paper|Account|Image \d+:)", "", text, flags=re.I)
    text = re.sub(r"\s+", " ", text)
    return text.strip()

def summarize_text(text: str, max_sentences: int = 3) -> str:
    """Return a concise summary of the content"""
    doc = nlp(text)
    sentences = list(doc.sents)
    if not sentences:
        return text[:500]  # fallback truncate
    return " ".join([str(s) for s in sentences[:max_sentences]])

def extract_keywords(text: str, max_keywords: int = 5) -> List[str]:
    """Extract main keywords using SpaCy noun chunks"""
    doc = nlp(text)
    keywords = [chunk.text for chunk in doc.noun_chunks][:max_keywords]
    return keywords

def extract_text_from_url(url: str) -> str:
    """Fetch page content and return readable text"""
    try:
        resp = requests.get(url, timeout=5)
        soup = BeautifulSoup(resp.text, "html.parser")
        # Remove scripts, styles, and extra tags
        for script in soup(["script", "style", "header", "footer", "nav"]):
            script.extract()
        text = soup.get_text(separator=" ")
        return clean_text(text)
    except Exception:
        return ""

# --- Main Enhanced Search Service ---
class EnhancedSearchService:
    """Handles all web searches with caching, fallback, and result enhancement"""
    def __init__(self):
        self.cache = AdvancedCache()
        self.tavily_client = None
        self.initialize_tavily()

    def initialize_tavily(self):
        """Initialize Tavily client"""
        if TavilyClient and TAVILY_API_KEY:
            try:
                self.tavily_client = TavilyClient(api_key=TAVILY_API_KEY)
                print("✅ Tavily search client initialized.")
            except Exception as e:
                print(f"⚠️ Failed to initialize Tavily client: {e}")

    async def search(self, query: str, phone_number: str, config: SearchConfig = SearchConfig()) -> Dict:
        """Main search method handling all query types and enhancements"""
        if not query.strip():
            return {"status": "error", "message": "Please provide a search query."}

        # Log search
        print(f"🔍 SEARCH LOG: {phone_number} searching: {query[:50]}...")

        # Check cache
        cached = self.cache.get(query, config)
        if cached:
            return {**cached, "source": "cache"}

        # If Tavily unavailable, fallback
        if not self.tavily_client:
            return await self._fallback_search(query)

        try:
            params = {
                "query": query[:400],
                "search_depth": config.search_depth,
                "include_images": config.include_images,
                "max_results": config.max_results,
                "language": config.language
            }
            if config.include_domains:
                params["include_domains"] = config.include_domains
            if config.exclude_domains:
                params["exclude_domains"] = config.exclude_domains
            if config.time_frame != "auto":
                params["time_frame"] = config.time_frame

            # Execute search by type
            if config.search_type == "news":
                response = await self._news_search(**params)
            elif config.search_type == "image":
                response = await self._image_search(**params)
            else:
                response = await self._general_search(**params)

            # Enhance results
            enhanced = await self._enhance_results(response, config)

            # Cache and return
            self.cache.set(query, config, enhanced)
            return enhanced

        except Exception as e:
            print(f"❌ Tavily search error: {e}")
            return await self._fallback_search(query)

    # --- Search Helpers ---
    async def _general_search(self, **params) -> Dict:
        return await asyncio.to_thread(self.tavily_client.search, **params)

    async def _news_search(self, **params) -> Dict:
        params["search_depth"] = "advanced"
        return await asyncio.to_thread(self.tavily_client.search, **params)

    async def _image_search(self, **params) -> Dict:
        params["include_images"] = True
        return await asyncio.to_thread(self.tavily_client.search, **params)

    async def _enhance_results(self, response: Dict, config: SearchConfig) -> Dict:
        """Format results, add summaries, insights, keywords"""
        enhanced = {
            "original_response": response,
            "metadata": {
                "query_time": datetime.now().isoformat(),
                "result_count": len(response.get("results", [])),
                "search_type": config.search_type
            },
            "formatted_results": [],
            "insights": []
        }

        results = response.get("results", [])

        # Extract insights with summary & keywords
        for r in results:
            url = r.get("url")
            content = r.get("content", "")
            if url:
                content += " " + extract_text_from_url(url)
            content = clean_text(content)
            summary = summarize_text(content)
            keywords = extract_keywords(content)
            enhanced["insights"].append({
                "title": r.get("title", "No title"),
                "url": url,
                "summary": summary,
                "keywords": keywords
            })

        # Add formatted results for backward compatibility
        if config.search_type == "news":
            enhanced["formatted_results"] = self._format_news_results(results)
        elif config.search_type == "image":
            enhanced["formatted_results"] = self._format_image_results(results)
        else:
            enhanced["formatted_results"] = self._format_general_results(results)

        # Direct answer if available
        if response.get("answer"):
            enhanced["direct_answer"] = response["answer"]

        return enhanced

    # --- Result formatting ---
    def _format_general_results(self, results: List[Dict]) -> List[Dict]:
        return [{
            "title": r.get("title", "No title"),
            "content": r.get("content", "")[:200] + "...",
            "url": r.get("url", ""),
            "score": r.get("score", 0),
            "published_date": r.get("published_date", "Unknown")
        } for r in results]

    def _format_news_results(self, results: List[Dict]) -> List[Dict]:
        return [{
            "headline": r.get("title", "No headline"),
            "summary": r.get("content", "")[:150] + "...",
            "source": r.get("url", "").split("/")[2] if r.get("url") else "",
            "url": r.get("url", ""),
            "published_date": r.get("published_date", "Unknown")
        } for r in results]

    def _format_image_results(self, results: List[Dict]) -> List[Dict]:
        return [{
            "title": r.get("title", "No title"),
            "image_url": r.get("image_url", ""),
            "source_url": r.get("url", ""),
            "description": r.get("content", "")[:100] + "..."
        } for r in results if r.get("image_url")]

    # --- Fallback if Tavily fails ---
    async def _fallback_search(self, query: str) -> Dict:
        """DuckDuckGo fallback search"""
        try:
            url = f"https://api.duckduckgo.com/?q={query[:400]}&format=json"
            response = requests.get(url, timeout=5)
            data = response.json()
            return {
                "status": "fallback",
                "source": "duckduckgo",
                "answer": data.get("AbstractText", "No direct answer found."),
                "related_topics": [t.get("Text", "") for t in data.get("RelatedTopics", [])[:3]]
            }
        except Exception as e:
            return {"status": "error", "message": "Search temporarily unavailable", "error": str(e)}

# --- Initialize service ---
search_service = EnhancedSearchService()

# --- Legacy wrapper for backward compatibility ---
async def search_the_web(query: str, phone_number: str) -> str:
    result = await search_service.search(query, phone_number)
    if "direct_answer" in result:
        return result["direct_answer"]
    if result.get("insights"):
        return result["insights"][0]["summary"]
    if result.get("formatted_results"):
        return result["formatted_results"][0]["content"]
    return "I couldn't find a good answer for that query."
