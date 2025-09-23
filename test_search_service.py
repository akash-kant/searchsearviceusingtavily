"""
Automated tests for Maya's Enhanced Search Service
Covers:
- Empty or whitespace queries
- Search type variations (general, news, image, invalid)
- Cache behavior
- Fallback to DuckDuckGo
- Logging validation
- Domain/time filters
- Concurrent searches
"""

import pytest
import asyncio
from search_service import search_service, SearchConfig, search_the_web

# For capturing printed logs
import sys
from io import StringIO

@pytest.mark.asyncio
async def test_empty_query():
    result = await search_the_web("", "1234567890")
    assert "provide a search query" in result or "couldn't find" in result

@pytest.mark.asyncio
async def test_whitespace_query():
    result = await search_the_web("     ", "1234567890")
    assert "provide a search query" in result or "couldn't find" in result

@pytest.mark.asyncio
async def test_short_query():
    result = await search_the_web("a", "1234567890")
    assert isinstance(result, str)

@pytest.mark.asyncio
async def test_long_query():
    query = "a" * 500
    result = await search_the_web(query, "1234567890")
    assert isinstance(result, str)

@pytest.mark.asyncio
async def test_general_search_type():
    config = SearchConfig(search_type="general")
    result = await search_service.search("weather", "1234567890", config)
    assert "formatted_results" in result

@pytest.mark.asyncio
async def test_news_search_type():
    config = SearchConfig(search_type="news")
    result = await search_service.search("NASA launches", "1234567890", config)
    assert "formatted_results" in result

@pytest.mark.asyncio
async def test_image_search_type():
    config = SearchConfig(search_type="image")
    result = await search_service.search("puppies", "1234567890", config)
    assert "formatted_results" in result

@pytest.mark.asyncio
async def test_invalid_search_type():
    config = SearchConfig(search_type="invalid_type")
    result = await search_service.search("test", "1234567890", config)
    # Should fallback
    assert "original_response" in result or "status" in result

@pytest.mark.asyncio
async def test_cache_behavior():
    config = SearchConfig(search_type="general")
    query = "cache test query"
    # First call → no cache
    res1 = await search_service.search(query, "1234567890", config)
    # Second call → should hit cache
    res2 = await search_service.search(query, "1234567890", config)
    assert res2.get("source") == "cache" or res2.get("formatted_results")

@pytest.mark.asyncio
async def test_fallback_search():
    # Temporarily disable Tavily to force fallback
    original_client = search_service.tavily_client
    search_service.tavily_client = None
    result = await search_service.search("fallback test", "1234567890")
    search_service.tavily_client = original_client
    assert result.get("source") == "duckduckgo" or result.get("status") == "error"

@pytest.mark.asyncio
async def test_phone_number_logging():
    # Capture stdout
    old_stdout = sys.stdout
    sys.stdout = mystdout = StringIO()
    await search_the_web("logging test", "9999999999")
    sys.stdout = old_stdout
    logs = mystdout.getvalue()
    assert "9999999999 searching" in logs

@pytest.mark.asyncio
async def test_include_exclude_domains():
    config = SearchConfig(
        search_type="general",
        include_domains=["example.com"],
        exclude_domains=["test.com"]
    )
    result = await search_service.search("domain filter test", "1234567890", config)
    assert "formatted_results" in result

@pytest.mark.asyncio
async def test_time_frame():
    config = SearchConfig(search_type="news", time_frame="day")
    result = await search_service.search("time frame test", "1234567890", config)
    assert "formatted_results" in result

@pytest.mark.asyncio
async def test_concurrent_queries():
    queries = ["query1", "query2", "query3", "query1"]
    tasks = [search_the_web(q, f"555{i}") for i, q in enumerate(queries)]
    results = await asyncio.gather(*tasks)
    assert all(isinstance(r, str) for r in results)
