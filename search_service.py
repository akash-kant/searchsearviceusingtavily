"""
Maya Search Service (Structural with FastAPI + Advanced Features)

- Tavily search with DuckDuckGo fallback
- Structural programming (functions, not OOP)
- FastAPI endpoints
- Caching with TTL
- Summarization & content cleaning
- Optional text extraction from URLs
"""

import os
import asyncio
import hashlib
import time
import re
import requests
from bs4 import BeautifulSoup
from fastapi import FastAPI, Query
from pydantic import BaseModel
import spacy

# Defensive import
try:
    from tavily import TavilyClient
except ImportError:
    TavilyClient = None
    print("⚠️ Install 'tavily-python' for web search.")

# --- Config ---
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
CACHE_TTL = 600
NEWS_CACHE_TTL = 300

# Tavily client
tavily_client = None
if TavilyClient and TAVILY_API_KEY:
    try:
        tavily_client = TavilyClient(api_key=TAVILY_API_KEY)
        print("✅ Tavily initialized.")
    except Exception as e:
        print(f"⚠️ Tavily init failed: {e}")

# SpaCy model
try:
    nlp = spacy.load("en_core_web_sm")
except Exception:
    nlp = None
    print("⚠️ SpaCy model not available. Summarization disabled.")

# --- Cache ---
cache = {}

def cache_key(query: str, search_type: str) -> str:
    return hashlib.sha256(f"{query}:{search_type}".encode()).hexdigest()

def cache_get(query: str, search_type: str):
    key = cache_key(query, search_type)
    if key in cache:
        data, ts = cache[key]
        ttl = NEWS_CACHE_TTL if search_type == "news" else CACHE_TTL
        if time.time() - ts < ttl:
            return data
        del cache[key]
    return None

def cache_set(query: str, search_type: str, data):
    cache[cache_key(query, search_type)] = (data, time.time())

# --- Utils ---
def clean_text(text: str) -> str:
    text = re.sub(r"(LOGIN|Subscribe|e-?Paper|Account|Image \d+:)", "", text, flags=re.I)
    text = re.sub(r"\s+", " ", text)
    return text.strip()

def extract_text_from_url(url: str) -> str:
    try:
        resp = requests.get(url, timeout=5)
        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style", "header", "footer", "nav"]):
            tag.extract()
        return clean_text(soup.get_text(separator=" "))
    except Exception:
        return ""

def summarize_text(text: str, max_sentences: int = 2) -> str:
    if not nlp:
        return text[:250]  # fallback: truncate
    doc = nlp(text)
    sents = list(doc.sents)
    return " ".join([str(s) for s in sents[:max_sentences]]) if sents else text[:250]

# --- Core Search ---
async def tavily_search(query: str, search_type: str = "general"):
    if not tavily_client:
        return await duckduckgo_fallback(query)

    params = {"query": query[:400], "search_depth": "basic", "max_results": 5}
    if search_type == "news":
        params["search_depth"] = "advanced"
    if search_type == "image":
        params["include_images"] = True

    return await asyncio.to_thread(tavily_client.search, **params)

async def duckduckgo_fallback(query: str):
    try:
        url = f"https://api.duckduckgo.com/?q={query}&format=json"
        resp = requests.get(url, timeout=5)
        data = resp.json()
        return {
            "status": "fallback",
            "answer": data.get("AbstractText", "No direct answer."),
            "related": [t.get("Text", "") for t in data.get("RelatedTopics", [])[:3]]
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

async def search_the_web(query: str, phone_number: str, search_type: str = "general") -> dict:
    print(f"🔍 LOG: {phone_number} searching '{query[:50]}'")

    cached = cache_get(query, search_type)
    if cached:
        return {"source": "cache", **cached}

    response = await tavily_search(query, search_type)

    # Enhance results
    results = response.get("results", [])
    formatted = []
    for r in results[:3]:  # only top 3
        text = r.get("content", "")
        if r.get("url"):
            text += " " + extract_text_from_url(r["url"])
        formatted.append({
            "title": r.get("title", "No title"),
            "url": r.get("url", ""),
            "summary": summarize_text(clean_text(text))
        })

    final = {
        "answer": response.get("answer") or (formatted[0]["summary"] if formatted else "No good answer found."),
        "results": formatted,
        "type": search_type
    }
    cache_set(query, search_type, final)
    return final

# --- FastAPI App ---
app = FastAPI(title="Maya Search Service")

class SearchRequest(BaseModel):
    query: str
    phone_number: str
    search_type: str = "general"

@app.post("/search")
async def search_post(req: SearchRequest):
    return await search_the_web(req.query, req.phone_number, req.search_type)

@app.get("/search")
async def search_get(
    query: str = Query(...),
    phone_number: str = Query("anonymous"),
    search_type: str = Query("general", enum=["general", "news", "image"])
):
    return await search_the_web(query, phone_number, search_type)
