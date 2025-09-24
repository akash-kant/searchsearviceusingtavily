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
12. FastAPI endpoints for web API access
"""

import os
import asyncio
import hashlib
import time
import json
from datetime import datetime
from typing import Dict, List, Optional, Union
from dataclasses import dataclass
from dotenv import load_dotenv

# FastAPI imports
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
import uvicorn

load_dotenv()

# Optional: Web extraction & NLP
import requests
import re
from bs4 import BeautifulSoup
import spacy

# Defensive import of Tavily client
try:
    from tavily import TavilyClient
    tavily_client = None
    if os.getenv("TAVILY_API_KEY"):
        tavily_client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))
        print("✅ Tavily search client initialized.")
except ImportError:
    tavily_client = None
    print("⚠️ 'tavily-python' not installed. Web search will be disabled.")

# Load SpaCy model for keyword extraction & summarization
try:
    nlp = spacy.load("en_core_web_sm")
except OSError:
    print("⚠️ SpaCy model 'en_core_web_sm' not found. NLP features will be limited.")
    nlp = None

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

# Pydantic models for FastAPI
class SearchRequest(BaseModel):
    query: str
    phone_number: str
    search_depth: str = "advanced"
    include_images: bool = False
    include_domains: Optional[List[str]] = None
    exclude_domains: Optional[List[str]] = None
    max_results: int = 10
    search_type: str = "general"
    time_frame: str = "auto"
    language: str = "en"

class SearchResponse(BaseModel):
    status: str
    data: Dict
    source: Optional[str] = None

# --- Global Cache ---
_cache_store = {}

def get_cache_key(query: str, config: SearchConfig) -> str:
    """Generate unique cache key based on query and config"""
    config_str = json.dumps({
        'depth': config.search_depth,
        'type': config.search_type,
        'time': config.time_frame
    })
    return hashlib.sha256(f"{query}:{config_str}".encode()).hexdigest()

def get_cached_result(query: str, config: SearchConfig) -> Optional[Dict]:
    """Retrieve cached result if valid"""
    key = get_cache_key(query, config)
    if key in _cache_store:
        data, timestamp = _cache_store[key]
        ttl = NEWS_CACHE_TTL if config.search_type == "news" else CACHE_TTL
        if time.time() - timestamp < ttl:
            return data
        del _cache_store[key]
    return None

def set_cached_result(query: str, config: SearchConfig, data: Dict):
    """Store result in cache"""
    key = get_cache_key(query, config)
    _cache_store[key] = (data, time.time())

# --- Utility Functions ---
def clean_text(text: str) -> str:
    """Remove boilerplate and extra whitespace"""
    if not text:
        return ""
    text = re.sub(r"(LOGIN|Subscribe|e-?Paper|Account|Image \d+:)", "", text, flags=re.I)
    text = re.sub(r"\s+", " ", text)
    return text.strip()

def summarize_text(text: str, max_sentences: int = 3) -> str:
    """Return a concise summary of the content"""
    if not text or not nlp:
        return text[:500] if text else ""
    
    doc = nlp(text)
    sentences = list(doc.sents)
    if not sentences:
        return text[:500]  # fallback truncate
    return " ".join([str(s) for s in sentences[:max_sentences]])

def extract_keywords(text: str, max_keywords: int = 5) -> List[str]:
    """Extract main keywords using SpaCy noun chunks"""
    if not text or not nlp:
        return []
    
    doc = nlp(text)
    keywords = [chunk.text for chunk in doc.noun_chunks][:max_keywords]
    return keywords

def extract_text_from_url(url: str) -> str:
    """Fetch page content and return readable text"""
    try:
        resp = requests.get(url, timeout=5, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        soup = BeautifulSoup(resp.text, "html.parser")
        # Remove scripts, styles, and extra tags
        for script in soup(["script", "style", "header", "footer", "nav"]):
            script.extract()
        text = soup.get_text(separator=" ")
        return clean_text(text)
    except Exception as e:
        print(f"Error extracting text from {url}: {e}")
        return ""

# --- Search Functions ---
async def perform_general_search(**params) -> Dict:
    """Perform general search using Tavily"""
    return await asyncio.to_thread(tavily_client.search, **params)

async def perform_news_search(**params) -> Dict:
    """Perform news search using Tavily"""
    params["search_depth"] = "advanced"
    return await asyncio.to_thread(tavily_client.search, **params)

async def perform_image_search(**params) -> Dict:
    """Perform image search using Tavily"""
    params["include_images"] = True
    return await asyncio.to_thread(tavily_client.search, **params)

def format_general_results(results: List[Dict]) -> List[Dict]:
    """Format general search results"""
    return [{
        "title": r.get("title", "No title"),
        "content": r.get("content", "")[:200] + "..." if len(r.get("content", "")) > 200 else r.get("content", ""),
        "url": r.get("url", ""),
        "score": r.get("score", 0),
        "published_date": r.get("published_date", "Unknown")
    } for r in results]

def format_news_results(results: List[Dict]) -> List[Dict]:
    """Format news search results"""
    return [{
        "headline": r.get("title", "No headline"),
        "summary": r.get("content", "")[:150] + "..." if len(r.get("content", "")) > 150 else r.get("content", ""),
        "source": r.get("url", "").split("/")[2] if r.get("url") else "",
        "url": r.get("url", ""),
        "published_date": r.get("published_date", "Unknown")
    } for r in results]

def format_image_results(results: List[Dict]) -> List[Dict]:
    """Format image search results"""
    return [{
        "title": r.get("title", "No title"),
        "image_url": r.get("image_url", ""),
        "source_url": r.get("url", ""),
        "description": r.get("content", "")[:100] + "..." if len(r.get("content", "")) > 100 else r.get("content", "")
    } for r in results if r.get("image_url")]

async def enhance_search_results(response: Dict, config: SearchConfig) -> Dict:
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
        
        # Optionally extract more content from URL
        if url and len(content) < 100:
            additional_content = extract_text_from_url(url)
            content += " " + additional_content
        
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
        enhanced["formatted_results"] = format_news_results(results)
    elif config.search_type == "image":
        enhanced["formatted_results"] = format_image_results(results)
    else:
        enhanced["formatted_results"] = format_general_results(results)

    # Direct answer if available
    if response.get("answer"):
        enhanced["direct_answer"] = response["answer"]

    return enhanced

async def perform_fallback_search(query: str) -> Dict:
    """DuckDuckGo fallback search when Tavily is unavailable"""
    try:
        encoded_query = requests.utils.quote(query[:400])
        url = f"https://api.duckduckgo.com/?q={encoded_query}&format=json&no_html=1"
        response = requests.get(url, timeout=5)
        data = response.json()
        
        return {
            "status": "fallback",
            "source": "duckduckgo",
            "answer": data.get("AbstractText", "No direct answer found."),
            "related_topics": [t.get("Text", "") for t in data.get("RelatedTopics", [])[:3] if isinstance(t, dict)]
        }
    except Exception as e:
        return {
            "status": "error", 
            "message": "Search temporarily unavailable", 
            "error": str(e)
        }

async def search_web(query: str, phone_number: str, config: SearchConfig = SearchConfig()) -> Dict:
    """Main search function handling all query types and enhancements"""
    if not query.strip():
        return {"status": "error", "message": "Please provide a search query."}

    # Log search
    print(f"🔍 SEARCH LOG: {phone_number} searching: {query[:50]}...")

    # Check cache
    cached = get_cached_result(query, config)
    if cached:
        return {**cached, "source": "cache"}

    # If Tavily unavailable, fallback
    if not tavily_client:
        return await perform_fallback_search(query)

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
            response = await perform_news_search(**params)
        elif config.search_type == "image":
            response = await perform_image_search(**params)
        else:
            response = await perform_general_search(**params)

        # Enhance results
        enhanced = await enhance_search_results(response, config)

        # Cache and return
        set_cached_result(query, config, enhanced)
        return enhanced

    except Exception as e:
        print(f"❌ Tavily search error: {e}")
        return await perform_fallback_search(query)

# --- Legacy wrapper for backward compatibility ---
async def search_the_web(query: str, phone_number: str) -> str:
    """Legacy function for backward compatibility"""
    result = await search_web(query, phone_number)
    
    if "direct_answer" in result:
        return result["direct_answer"]
    if result.get("insights"):
        return result["insights"][0]["summary"]
    if result.get("formatted_results"):
        return result["formatted_results"][0]["content"]
    return "I couldn't find a good answer for that query."

# --- FastAPI Application ---
app = FastAPI(
    title="Maya Search Service",
    description="Enhanced search service with multiple search types and intelligent insights",
    version="2.0.0"
)

@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "message": "Maya Search Service is running",
        "version": "2.0.0",
        "tavily_available": tavily_client is not None,
        "nlp_available": nlp is not None
    }

@app.post("/search", response_model=SearchResponse)
async def api_search(request: SearchRequest):
    """Enhanced search endpoint with full configuration"""
    try:
        config = SearchConfig(
            search_depth=request.search_depth,
            include_images=request.include_images,
            include_domains=request.include_domains,
            exclude_domains=request.exclude_domains,
            max_results=request.max_results,
            search_type=request.search_type,
            time_frame=request.time_frame,
            language=request.language
        )
        
        result = await search_web(request.query, request.phone_number, config)
        
        return SearchResponse(
            status="success",
            data=result,
            source=result.get("source", "tavily")
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")

@app.get("/search/simple")
async def simple_search(
    query: str = Query(..., description="Search query"),
    phone_number: str = Query(..., description="User phone number for logging"),
    search_type: str = Query("general", description="Search type: general, news, or image")
):
    """Simple search endpoint with minimal parameters"""
    try:
        config = SearchConfig(search_type=search_type)
        result = await search_web(query, phone_number, config)
        
        return {
            "query": query,
            "answer": result.get("direct_answer", ""),
            "results": result.get("formatted_results", [])[:5],  # Top 5 results
            "source": result.get("source", "tavily")
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")

@app.get("/search/news")
async def news_search(
    query: str = Query(..., description="News search query"),
    phone_number: str = Query(..., description="User phone number for logging"),
    max_results: int = Query(10, description="Maximum number of results")
):
    """Dedicated news search endpoint"""
    try:
        config = SearchConfig(
            search_type="news",
            max_results=max_results,
            time_frame="week"  # Default to recent news
        )
        result = await search_web(query, phone_number, config)
        
        return {
            "query": query,
            "news_results": result.get("formatted_results", []),
            "insights": result.get("insights", []),
            "source": result.get("source", "tavily")
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"News search failed: {str(e)}")

@app.get("/search/images")
async def image_search(
    query: str = Query(..., description="Image search query"),
    phone_number: str = Query(..., description="User phone number for logging"),
    max_results: int = Query(10, description="Maximum number of results")
):
    """Dedicated image search endpoint"""
    try:
        config = SearchConfig(
            search_type="image",
            include_images=True,
            max_results=max_results
        )
        result = await search_web(query, phone_number, config)
        
        return {
            "query": query,
            "image_results": result.get("formatted_results", []),
            "source": result.get("source", "tavily")
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Image search failed: {str(e)}")

@app.get("/cache/stats")
async def cache_stats():
    """Get cache statistics"""
    return {
        "cache_size": len(_cache_store),
        "cache_keys": list(_cache_store.keys())[:10],  # Show first 10 keys
        "cache_ttl_normal": CACHE_TTL,
        "cache_ttl_news": NEWS_CACHE_TTL
    }

@app.delete("/cache/clear")
async def clear_cache():
    """Clear the entire cache"""
    global _cache_store
    cache_size = len(_cache_store)
    _cache_store.clear()
    return {"message": f"Cache cleared. Removed {cache_size} entries."}

# --- Run the FastAPI app ---
if __name__ == "__main__":
    uvicorn.run(
        "search_service:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
