"""
Diagnose why response.text is None - check if safety settings work,
if schema kills output, what the finish_reason is.
"""
import asyncio, os
from google import genai
from google.genai import types
from src.llm_reasoner import AllDimensionsResult, LLMReasoner
from dotenv import load_dotenv
load_dotenv()

IMDB_SAMPLE = """
Sex & Nudity: A woman is seen fully nude in a shower scene. Couple has sex on screen, breasts shown.
Violence & Gore: A man is shot in the head. Blood splatters on the wall. Brutal fight scene with stabbing.
Profanity: F-word used over 30 times. Several uses of 'shit', 'ass', and 'bitch'.
Frightening: Jump scares. Graphic depiction of torture.
"""

async def test1_raw_no_schema():
    """Plain call, no schema - does the API even respond?"""
    client = genai.Client(api_key=os.environ['GOOGLE_API_KEY'])
    resp = await client.aio.models.generate_content(
        model='gemini-2.5-flash',
        contents=f"Summarize this in one sentence: {IMDB_SAMPLE}",
    )
    print(f"[TEST1 no-schema] text={repr(resp.text[:100]) if resp.text else 'NONE'}")
    print(f"[TEST1 no-schema] finish_reason={resp.candidates[0].finish_reason if resp.candidates else 'N/A'}")

async def test2_schema_no_safety():
    """With schema, no safety override - what happens?"""
    client = genai.Client(api_key=os.environ['GOOGLE_API_KEY'])
    resp = await client.aio.models.generate_content(
        model='gemini-2.5-flash',
        contents=f"Analyze this film guide text:\n{IMDB_SAMPLE}",
        config=types.GenerateContentConfig(
            response_mime_type='application/json',
            response_schema=AllDimensionsResult,
        )
    )
    print(f"[TEST2 schema-no-safety] text={repr(resp.text[:100]) if resp.text else 'NONE'}")
    if resp.candidates:
        print(f"[TEST2 schema-no-safety] finish_reason={resp.candidates[0].finish_reason}")
        print(f"[TEST2 schema-no-safety] safety_ratings={resp.candidates[0].safety_ratings}")

async def test3_schema_with_safety():
    """With schema + BLOCK_NONE safety override"""
    client = genai.Client(api_key=os.environ['GOOGLE_API_KEY'])
    safety = [
        types.SafetySetting(category=c, threshold="BLOCK_NONE") for c in [
            "HARM_CATEGORY_HATE_SPEECH", "HARM_CATEGORY_DANGEROUS_CONTENT",
            "HARM_CATEGORY_SEXUALLY_EXPLICIT", "HARM_CATEGORY_HARASSMENT"
        ]
    ]
    resp = await client.aio.models.generate_content(
        model='gemini-2.5-flash',
        contents=f"Analyze this film guide text:\n{IMDB_SAMPLE}",
        config=types.GenerateContentConfig(
            response_mime_type='application/json',
            response_schema=AllDimensionsResult,
            safety_settings=safety,
        )
    )
    print(f"[TEST3 schema+safety] text={repr(resp.text[:100]) if resp.text else 'NONE'}")
    if resp.candidates:
        print(f"[TEST3 schema+safety] finish_reason={resp.candidates[0].finish_reason}")
        print(f"[TEST3 schema+safety] safety_ratings={resp.candidates[0].safety_ratings}")

async def test4_reasoner():
    """Full LLMReasoner._async_generate_all_dimensions_content"""
    reasoner = LLMReasoner()
    try:
        result = await reasoner._async_generate_all_dimensions_content(
            f"Analyze this film guide text:\n{IMDB_SAMPLE}"
        )
        print(f"[TEST4 reasoner] OK text={repr(result[:100])}")
    except Exception as e:
        print(f"[TEST4 reasoner] FAILED: {type(e).__name__}: {e}")

if __name__ == "__main__":
    async def main():
        for fn in [test1_raw_no_schema, test2_schema_no_safety, test3_schema_with_safety, test4_reasoner]:
            print(f"\n{'='*60}")
            try:
                await fn()
            except Exception as e:
                print(f"CRASH: {type(e).__name__}: {e}")
    asyncio.run(main())
