import asyncio, os
from google import genai
from google.genai import types
from src.llm_reasoner import AllDimensionsResult
from dotenv import load_dotenv
load_dotenv()

async def t():
    client = genai.Client(api_key=os.environ['GOOGLE_API_KEY'])
    resp = await client.aio.models.generate_content(
        model='gemini-2.5-flash',
        contents='Analyze violence: he killed him with a gun',
        config=types.GenerateContentConfig(
            response_mime_type='application/json',
            response_schema=AllDimensionsResult
        )
    )
    print("TEXT:", resp.text)
    print("FINISH REASON:", resp.candidates[0].finish_reason if resp.candidates else "No candidates")

if __name__ == "__main__":
    asyncio.run(t())
