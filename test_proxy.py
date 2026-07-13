import httpx
import asyncio

async def main():
    try:
        async with httpx.AsyncClient(proxy="http://127.0.0.1:6922") as client:
            resp = await client.get("https://api.themoviedb.org/3/movie/550?api_key=b827ac4f417c02388793eceeec901298")
            print(f"Proxy status: {resp.status_code}")
    except Exception as e:
        print(f"Proxy failed: {e}")

if __name__ == "__main__":
    asyncio.run(main())
