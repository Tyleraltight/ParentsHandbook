import asyncio
from src.llm_reasoner import LLMReasoner
from dotenv import load_dotenv

load_dotenv()

async def main():
    reasoner = LLMReasoner()
    try:
        res = await reasoner._async_generate_all_dimensions_content("Analyze this movie for violence: There is a gun.")
        print("Result:", res)
    except Exception as e:
        print("Exception:", type(e), e)

if __name__ == "__main__":
    asyncio.run(main())
