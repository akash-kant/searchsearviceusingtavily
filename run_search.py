"""
Interactive Search Runner for Maya

This script allows testing the EnhancedSearchService.
It handles any query input and displays:
- Direct answer if available
- Multiple results with summaries
- Keywords for context
- Source URLs
"""

import asyncio
from search_service import search_the_web, search_service, SearchConfig

async def main():
    print("📝 Welcome to Maya Search Service!")
    phone_number = input("Enter your phone number for logging purposes: ")

    while True:
        query = input("\nEnter your query (or type 'exit' to quit): ").strip()
        if query.lower() == "exit":
            print("👋 Goodbye!")
            break
        if not query:
            print("⚠️ Please enter a valid query.")
            continue

        # Ask user if they want a specific search type
        search_type_input = input("Search type? (general/news/image, default general): ").strip().lower()
        search_type = search_type_input if search_type_input in ["general", "news", "image"] else "general"

        # Configure search
        config = SearchConfig(search_type=search_type)

        # Perform search
        result = await search_service.search(query, phone_number, config)

        print("\n=== Search Results ===\n")

        # 1️⃣ Direct Answer
        if "direct_answer" in result:
            print("💡 Direct Answer:")
            print(result["direct_answer"])
            print("\n----------------\n")

        # 2️⃣ Insights (Structured summary with keywords)
        if result.get("insights"):
            print("📰 Insights / Summaries:")
            for idx, insight in enumerate(result["insights"], start=1):
                print(f"\nResult #{idx}:")
                print(f"Title   : {insight.get('title')}")
                print(f"Summary : {insight.get('summary')}")
                print(f"Keywords: {', '.join(insight.get('keywords', []))}")
                print(f"URL     : {insight.get('url')}")
                print("----------------------------")

        # 3️⃣ Formatted results fallback
        elif result.get("formatted_results"):
            print("📄 Formatted Results (fallback):")
            for idx, fr in enumerate(result["formatted_results"], start=1):
                print(f"\nResult #{idx}:")
                print(f"Title  : {fr.get('title', 'No title')}")
                print(f"Content: {fr.get('content', '')}")
                print(f"URL    : {fr.get('url', '')}")
                print("----------------------------")

        # 4️⃣ DuckDuckGo fallback or errors
        elif result.get("status") in ["fallback", "error"]:
            print("⚠️ Fallback / Error:")
            print(result.get("answer") or result.get("message"))
            if "related_topics" in result:
                print("Related Topics:", ", ".join(result["related_topics"]))

        print("\n========================\n")

# Entry point
if __name__ == "__main__":
    asyncio.run(main())
