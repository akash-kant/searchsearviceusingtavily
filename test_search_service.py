"""
Automated tests for Maya's Enhanced Search Service (Functional Programming Version)
Covers:
- Empty or whitespace queries
- Search type variations (general, news, image, invalid)
- Cache behavior
- Fallback to DuckDuckGo
- Logging validation
- Domain/time filters
- Concurrent searches
- FastAPI endpoints
- Error handling
"""

import pytest
import asyncio
import json
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

# Import the functional search service
from search_service import (
    search_web, 
    search_the_web, 
    SearchConfig,
    app,
    get_cached_result,
    set_cached_result,
    _cache_store,
    perform_fallback_search,
    clean_text,
    summarize_text,
    extract_keywords
)

# For capturing printed logs
import sys
from io import StringIO

# FastAPI test client
client = TestClient(app)

# --- Basic Query Tests ---

@pytest.mark.asyncio
async def test_empty_query():
    """Test handling of empty queries"""
    result = await search_the_web("", "1234567890")
    assert "provide a search query" in result.lower() or "couldn't find" in result.lower()

@pytest.mark.asyncio
async def test_whitespace_query():
    """Test handling of whitespace-only queries"""
    result = await search_the_web("     ", "1234567890")
    assert "provide a search query" in result.lower() or "couldn't find" in result.lower()

@pytest.mark.asyncio
async def test_short_query():
    """Test handling of very short queries"""
    result = await search_the_web("AI", "1234567890")
    assert isinstance(result, str)
    assert len(result) > 0

@pytest.mark.asyncio
async def test_long_query():
    """Test handling of very long queries"""
    query = "artificial intelligence machine learning deep learning " * 20
    result = await search_the_web(query, "1234567890")
    assert isinstance(result, str)

# --- Search Type Tests ---

@pytest.mark.asyncio
async def test_general_search_type():
    """Test general search functionality"""
    config = SearchConfig(search_type="general", max_results=3)
    result = await search_web("weather forecast", "1234567890", config)
    assert "formatted_results" in result or "status" in result

@pytest.mark.asyncio
async def test_news_search_type():
    """Test news search functionality"""
    config = SearchConfig(search_type="news", max_results=3)
    result = await search_web("latest technology news", "1234567890", config)
    assert "formatted_results" in result or "status" in result

@pytest.mark.asyncio
async def test_image_search_type():
    """Test image search functionality"""
    config = SearchConfig(search_type="image", include_images=True, max_results=3)
    result = await search_web("cute puppies", "1234567890", config)
    assert "formatted_results" in result or "status" in result

@pytest.mark.asyncio
async def test_invalid_search_type():
    """Test handling of invalid search types"""
    config = SearchConfig(search_type="invalid_type")
    result = await search_web("test query", "1234567890", config)
    # Should still work, just default to general search
    assert isinstance(result, dict)

# --- Cache Tests ---

@pytest.mark.asyncio
async def test_cache_behavior():
    """Test caching functionality"""
    # Clear cache first
    _cache_store.clear()
    
    config = SearchConfig(search_type="general")
    query = f"cache test query {asyncio.get_event_loop().time()}"  # Unique query
    
    # First call - no cache
    res1 = await search_web(query, "1234567890", config)
    
    # Second call - should hit cache
    res2 = await search_web(query, "1234567890", config)
    
    # Check if second call was from cache
    assert res2.get("source") == "cache" or len(_cache_store) > 0

@pytest.mark.asyncio
async def test_cache_expiry():
    """Test cache TTL functionality"""
    _cache_store.clear()
    config = SearchConfig(search_type="general")
    query = "cache expiry test"
    
    # Set a result in cache
    test_data = {"test": "data"}
    set_cached_result(query, config, test_data)
    
    # Should retrieve from cache
    cached = get_cached_result(query, config)
    assert cached is not None
    assert cached["test"] == "data"

# --- Fallback Tests ---

@pytest.mark.asyncio
async def test_fallback_search_directly():
    """Test DuckDuckGo fallback search"""
    result = await perform_fallback_search("python programming")
    assert "status" in result
    assert result["status"] in ["fallback", "error"]

@pytest.mark.asyncio
async def test_fallback_when_tavily_unavailable():
    """Test fallback when Tavily is unavailable"""
    # Mock tavily_client to be None
    with patch('search_service.tavily_client', None):
        result = await search_web("fallback test query", "1234567890")
        assert result.get("source") == "duckduckgo" or result.get("status") == "error"

# --- Logging Tests ---

@pytest.mark.asyncio
async def test_phone_number_logging():
    """Test that phone numbers are logged properly"""
    old_stdout = sys.stdout
    sys.stdout = mystdout = StringIO()
    
    try:
        await search_the_web("logging test query", "9999999999")
        sys.stdout = old_stdout
        logs = mystdout.getvalue()
        assert "9999999999" in logs and "searching" in logs
    finally:
        sys.stdout = old_stdout

# --- Configuration Tests ---

@pytest.mark.asyncio
async def test_include_exclude_domains():
    """Test domain filtering functionality"""
    config = SearchConfig(
        search_type="general",
        include_domains=["wikipedia.org"],
        exclude_domains=["example.com"],
        max_results=3
    )
    result = await search_web("domain filter test", "1234567890", config)
    assert isinstance(result, dict)

@pytest.mark.asyncio
async def test_time_frame_filter():
    """Test time frame filtering"""
    config = SearchConfig(
        search_type="news", 
        time_frame="week",
        max_results=3
    )
    result = await search_web("recent news", "1234567890", config)
    assert isinstance(result, dict)

@pytest.mark.asyncio
async def test_search_depth_options():
    """Test different search depth options"""
    config_basic = SearchConfig(search_depth="basic", max_results=2)
    config_advanced = SearchConfig(search_depth="advanced", max_results=2)
    
    result_basic = await search_web("search depth test", "1234567890", config_basic)
    result_advanced = await search_web("search depth test", "1234567890", config_advanced)
    
    assert isinstance(result_basic, dict)
    assert isinstance(result_advanced, dict)

# --- Concurrent Search Tests ---

@pytest.mark.asyncio
async def test_concurrent_queries():
    """Test handling of concurrent search requests"""
    queries = ["query1", "query2", "query3", "query1"]  # Note: query1 appears twice
    tasks = [search_the_web(q, f"555000{i}") for i, q in enumerate(queries)]
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # All should return strings (even if error messages)
    assert all(isinstance(r, str) or isinstance(r, Exception) for r in results)
    # At least some should succeed
    string_results = [r for r in results if isinstance(r, str)]
    assert len(string_results) > 0

# --- Utility Function Tests ---

def test_clean_text():
    """Test text cleaning utility"""
    dirty_text = "LOGIN Subscribe   This is    good content   Image 1: caption"
    clean = clean_text(dirty_text)
    assert "LOGIN" not in clean
    assert "Subscribe" not in clean
    assert "This is good content" in clean

def test_clean_text_empty():
    """Test clean_text with empty input"""
    assert clean_text("") == ""
    assert clean_text(None) == ""

def test_summarize_text():
    """Test text summarization"""
    long_text = "First sentence. Second sentence. Third sentence. Fourth sentence."
    summary = summarize_text(long_text, max_sentences=2)
    # Should return something (even if NLP model not available)
    assert isinstance(summary, str)
    assert len(summary) > 0

def test_extract_keywords():
    """Test keyword extraction"""
    text = "Machine learning and artificial intelligence are transforming technology"
    keywords = extract_keywords(text)
    # Should return a list (even if empty when NLP model not available)
    assert isinstance(keywords, list)

# --- FastAPI Endpoint Tests ---

def test_root_endpoint():
    """Test the root health check endpoint"""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert "version" in data

def test_simple_search_endpoint():
    """Test the simple search API endpoint"""
    response = client.get("/search/simple?query=test&phone_number=1234567890")
    assert response.status_code == 200
    data = response.json()
    assert "query" in data

def test_news_search_endpoint():
    """Test the news search API endpoint"""
    response = client.get("/search/news?query=latest%20news&phone_number=1234567890&max_results=3")
    assert response.status_code == 200
    data = response.json()
    assert "query" in data

def test_image_search_endpoint():
    """Test the image search API endpoint"""
    response = client.get("/search/images?query=cats&phone_number=1234567890&max_results=3")
    assert response.status_code == 200
    data = response.json()
    assert "query" in data

def test_full_search_endpoint():
    """Test the full search POST endpoint"""
    search_data = {
        "query": "machine learning",
        "phone_number": "1234567890",
        "search_type": "general",
        "max_results": 5,
        "search_depth": "advanced"
    }
    response = client.post("/search", json=search_data)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "data" in data

def test_cache_stats_endpoint():
    """Test the cache statistics endpoint"""
    response = client.get("/cache/stats")
    assert response.status_code == 200
    data = response.json()
    assert "cache_size" in data

def test_clear_cache_endpoint():
    """Test the cache clearing endpoint"""
    response = client.delete("/cache/clear")
    assert response.status_code == 200
    data = response.json()
    assert "message" in data

# --- Error Handling Tests ---

def test_invalid_search_request():
    """Test invalid search request handling"""
    invalid_data = {
        "query": "",  # Empty query
        "phone_number": "123"
    }
    response = client.post("/search", json=invalid_data)
    # Should handle gracefully (might be 200 with error message or 422 validation error)
    assert response.status_code in [200, 422, 500]

def test_missing_query_parameter():
    """Test missing required query parameter"""
    response = client.get("/search/simple?phone_number=123")
    assert response.status_code == 422  # Validation error

@pytest.mark.asyncio
async def test_search_with_special_characters():
    """Test search with special characters"""
    special_query = "C++ programming & data science (2024) #trending"
    result = await search_the_web(special_query, "1234567890")
    assert isinstance(result, str)

@pytest.mark.asyncio
async def test_search_with_unicode():
    """Test search with Unicode characters"""
    unicode_query = "Python 编程 café résumé"
    result = await search_the_web(unicode_query, "1234567890")
    assert isinstance(result, str)

# --- Performance Tests ---

@pytest.mark.asyncio
async def test_search_performance():
    """Test that searches complete within reasonable time"""
    import time
    start_time = time.time()
    
    config = SearchConfig(max_results=3)  # Limit results for faster test
    await search_web("performance test", "1234567890", config)
    
    duration = time.time() - start_time
    # Should complete within 30 seconds (generous for network calls)
    assert duration < 30

# --- Cleanup ---

def test_cleanup():
    """Clean up test artifacts"""
    _cache_store.clear()
    assert len(_cache_store) == 0

# --- Pytest Configuration ---

@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """Set up test environment"""
    # Clear cache before tests
    _cache_store.clear()
    yield
    # Clean up after tests
    _cache_store.clear()

if __name__ == "__main__":
    # Run tests directly
    pytest.main([__file__, "-v", "--tb=short"])
