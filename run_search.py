"""
Interactive Search Runner for Maya

This script allows testing the EnhancedSearchService with full feature support.
It handles any query input and displays:
- Direct answer if available  
- Structured insights with summaries and keywords
- Multiple results with detailed formatting
- Source URLs and metadata
- Cache performance indicators
"""

import asyncio
from search_service import search_web, SearchConfig

async def main():
    print("🔍 Welcome to Maya Enhanced Search Service!")
    print("=" * 50)

    phone_number = input("📱 Enter your phone number for logging: ").strip()
    if not phone_number:
        phone_number = "anonymous"

    print("\n✨ Features available:")
    print("• Multiple search types (general/news/image)")  
    print("• Smart caching with TTL")
    print("• Keyword extraction and insights")
    print("• Content summarization")
    print("• Fallback search support")
    print("• Advanced filtering options")
    print("=" * 50)

    while True:
        print("\n" + "="*60)
        query = input("🔎 Enter your search query (or 'exit'/'help'): ").strip()

        if query.lower() == "exit":
            print("👋 Thanks for using Maya Search! Goodbye!")
            break

        if query.lower() == "help":
            print("\n📖 Help - Available Commands:")
            print("• General search: Just type your query")
            print("• News search: Specify 'news' when prompted") 
            print("• Image search: Specify 'image' when prompted")
            print("• Advanced options: Follow the prompts for filtering")
            print("• 'exit' - Quit the application")
            print("• 'help' - Show this help message")
            continue

        if not query:
            print("⚠️  Please enter a valid search query.")
            continue

        # Search type selection
        print("\n🔧 Search Configuration:")
        search_type_input = input("Search type (general/news/image) [default: general]: ").strip().lower()
        search_type = search_type_input if search_type_input in ["general", "news", "image"] else "general"

        # Advanced options
        advanced = input("Use advanced options? (y/n) [default: n]: ").strip().lower() == 'y'

        config = SearchConfig(search_type=search_type)

        if advanced:
            print("\n⚙️  Advanced Configuration:")

            # Max results
            try:
                max_results = int(input("Max results (1-20) [default: 10]: ") or "10")
                config.max_results = min(max(max_results, 1), 20)
            except ValueError:
                config.max_results = 10

            # Search depth  
            depth = input("Search depth (basic/advanced) [default: advanced]: ").strip().lower()
            config.search_depth = depth if depth in ["basic", "advanced"] else "advanced"

            # Time frame for news
            if search_type == "news":
                time_frame = input("Time frame (auto/day/week/month) [default: auto]: ").strip().lower()
                config.time_frame = time_frame if time_frame in ["auto", "day", "week", "month"] else "auto"

            # Include images
            if search_type != "image":
                include_images = input("Include images? (y/n) [default: n]: ").strip().lower() == 'y'
                config.include_images = include_images

        # Perform search with loading indicator
        print(f"\n🔄 Searching for: '{query}' [{search_type} search]...")
        print("⏳ Please wait...")

        try:
            result = await search_web(query, phone_number, config)

            print("\n" + "="*60)
            print("📊 SEARCH RESULTS")
            print("="*60)

            # Performance indicators
            if result.get("source"):
                cache_emoji = "💾" if result["source"] == "cache" else "🌐"
                print(f"{cache_emoji} Source: {result['source'].upper()}")

            if "metadata" in result:
                metadata = result["metadata"]
                print(f"📈 Results: {metadata.get('result_count', 'N/A')}")
                print(f"⏰ Query Time: {metadata.get('query_time', 'N/A')}")

            print("-" * 60)

            # 1️⃣ Direct Answer (Priority display)
            if result.get("direct_answer"):
                print("\n💡 **DIRECT ANSWER:**")
                print("=" * 40)
                print(result["direct_answer"])
                print("=" * 40)

            # 2️⃣ Enhanced Insights (Main feature)
            if result.get("insights"):
                print("\n📰 **DETAILED INSIGHTS:**")
                print("=" * 40)

                for idx, insight in enumerate(result["insights"][:5], start=1):  # Show top 5
                    print(f"\n[{idx}] 📄 {insight.get('title', 'No Title')}")
                    print("─" * 50)

                    summary = insight.get('summary', '')
                    if summary:
                        print(f"📝 Summary: {summary}")

                    keywords = insight.get('keywords', [])
                    if keywords:
                        print(f"🏷️  Keywords: {', '.join(keywords[:5])}")  # Top 5 keywords

                    url = insight.get('url', '')
                    if url:
                        print(f"🔗 Source: {url}")

                    print()

            # 3️⃣ Formatted Results (Backup/Alternative view)
            elif result.get("formatted_results"):
                print("\n📋 **FORMATTED RESULTS:**")
                print("=" * 40)

                for idx, res in enumerate(result["formatted_results"][:5], start=1):
                    print(f"\n[{idx}] 📰 {res.get('title', res.get('headline', 'No Title'))}")
                    print("─" * 50)

                    # Handle different result types
                    content_key = 'content' if 'content' in res else 'summary' if 'summary' in res else 'description'
                    content = res.get(content_key, '')
                    if content:
                        print(f"📄 Content: {content}")

                    # Additional metadata for different search types
                    if search_type == "news" and res.get('source'):
                        print(f"📰 Source: {res['source']}")
                    elif search_type == "image" and res.get('image_url'):
                        print(f"🖼️  Image: {res['image_url']}")

                    if res.get('published_date'):
                        print(f"📅 Date: {res['published_date']}")

                    if res.get('url') or res.get('source_url'):
                        print(f"🔗 URL: {res.get('url') or res.get('source_url')}")

                    print()

            # 4️⃣ Fallback/Error handling
            elif result.get("status") in ["fallback", "error"]:
                print("\n⚠️  **FALLBACK/ERROR RESULT:**")
                print("=" * 40)

                answer = result.get("answer") or result.get("message", "No additional information available.")
                print(f"📄 Response: {answer}")

                if result.get("related_topics"):
                    print(f"🔗 Related: {', '.join(result['related_topics'])}")

                if result.get("source"):
                    print(f"📡 Via: {result['source']}")

            # 5️⃣ No results case
            else:
                print("\n❌ **NO RESULTS FOUND**")
                print("Try:")
                print("• Different keywords")  
                print("• Broader search terms")
                print("• Different search type")

            print("\n" + "="*60)

            # Ask for follow-up
            followup = input("\n🔄 Search again with same settings? (y/n): ").strip().lower()
            if followup != 'y':
                continue

        except Exception as e:
            print(f"\n❌ **ERROR OCCURRED:**")
            print(f"🚨 {str(e)}")
            print("Please try again with a different query.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n👋 Search interrupted by user. Goodbye!")
    except Exception as e:
        print(f"\n\n🚨 Application error: {e}")
        print("Please check your search service configuration.")
