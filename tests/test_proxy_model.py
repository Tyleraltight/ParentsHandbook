"""Test that proxy + correct model name both work."""
import sys, os, asyncio
sys.path.insert(0, 'e:/ClaudeCode/PROJECTS/ParentsHandbook')
from dotenv import load_dotenv
load_dotenv()

from google import genai
from google.genai import types
from src.llm_reasoner import AllDimensionsResult

client = genai.Client(api_key=os.environ['GOOGLE_API_KEY'])
model = os.environ.get('BASE_PARSING_MODEL', 'gemini-2.5-flash-preview-04-17')
print('Model:', model)
print('HTTPS_PROXY:', os.environ.get('HTTPS_PROXY'))

async def test():
    resp = await client.aio.models.generate_content(
        model=model,
        contents="Say hello in JSON: {\"message\": \"hello\"}",
    )
    print('OK - text:', repr(resp.text[:100]) if resp.text else 'NONE')
    if resp.candidates:
        print('finish_reason:', resp.candidates[0].finish_reason)

asyncio.run(test())
