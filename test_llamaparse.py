import asyncio
import os
import logging
from app.services.pdf_processing import extract_text
from app.core.config import settings

logging.basicConfig(level=logging.INFO)

async def main():
    print(f"API KEY: {settings.LLAMA_CLOUD_API_KEY}")
    
    test_content = b"This is a test pitch deck. We need $1M to build a great AI startup. We have 10,000 users and growing at 20% MoM."
    
    result = await extract_text(test_content, "test.txt")
    print("\n--- EXTRACTION RESULT ---")
    print(f"Success: {result.success}")
    print(f"Cleaned Text:\n{result.cleaned_text}")
    print(f"Error: {result.error}")
    
if __name__ == "__main__":
    asyncio.run(main())
