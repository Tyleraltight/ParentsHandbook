import httpx
import re
from typing import Optional, Tuple
from src.config import settings

class TMDBResolutionError(Exception):
    """Exception raised for errors in the TMDB resolution process."""
    pass

class TMDBResolver:
    """
    Resolves movie titles to exact IMDb IDs using the TMDB API.
    """
    def __init__(self):
        self.api_key = settings.tmdb_api_key
        if not self.api_key or self.api_key == "your_tmdb_api_key_here":
            raise ValueError("TMDB_API_KEY is missing or invalid in the environment/config.")
        self.base_url = "https://api.themoviedb.org/3"

    @staticmethod
    def _parse_title_and_year(raw_title: str) -> Tuple[str, Optional[str]]:
        """
        Extract year from user input. Supports formats:
          'The Matrix 1999'  ->  ('The Matrix', '1999')
          'The Matrix (1999)' -> ('The Matrix', '1999')
          'The Matrix'       -> ('The Matrix', None)
        """
        # Match trailing (YYYY) or bare YYYY
        m = re.search(r'\(?\b((?:19|20)\d{2})\b\)?\s*$', raw_title)
        if m:
            year = m.group(1)
            title = raw_title[:m.start()].strip()
            return title, year
        return raw_title.strip(), None

    def search_movie(self, title: str) -> str:
        """
        Searches for a movie by title and retrieves its IMDb ID.
        :param title: The title of the movie (e.g., 'The Matrix')
        :return: The IMDb ID string (e.g., 'tt0133093')
        """
        # Parse optional year from title string
        clean_title, year = self._parse_title_and_year(title)

        search_url = f"{self.base_url}/search/movie"
        params = {
            "query": clean_title,
            "api_key": self.api_key,
            "language": "en-US",
            "page": 1,
            "include_adult": "false"
        }
        if year:
            params["year"] = year
        
        with httpx.Client() as client:
            response = client.get(search_url, params=params)
            response.raise_for_status()
            data = response.json()

            results = data.get("results", [])
            if not results:
                raise TMDBResolutionError(f"No movies found for title: {title}")
            
            # 我们默认选取匹配度最高的首个结果
            first_movie = results[0]
            tmdb_id = first_movie.get("id")

            # 第二步：通过 TMDB ID 获取电影详情，提取 imdb_id
            details_url = f"{self.base_url}/movie/{tmdb_id}"
            details_params = {
                "api_key": self.api_key,
                "language": "en-US"
            }
            
            details_response = client.get(details_url, params=details_params)
            details_response.raise_for_status()
            details_data = details_response.json()
            
            imdb_id = details_data.get("imdb_id")
            if not imdb_id:
                raise TMDBResolutionError(f"Movie found in TMDB (id: {tmdb_id}) but it lacks an IMDb ID.")

            return imdb_id

    async def async_search_movie(self, title: str) -> str:
        """
        Async version of search_movie for use with FastAPI.
        """
        clean_title, year = self._parse_title_and_year(title)

        search_url = f"{self.base_url}/search/movie"
        params = {
            "query": clean_title,
            "api_key": self.api_key,
            "language": "en-US",
            "page": 1,
            "include_adult": "false"
        }
        if year:
            params["year"] = year
        
        async with httpx.AsyncClient() as client:
            response = await client.get(search_url, params=params)
            response.raise_for_status()
            data = response.json()

            results = data.get("results", [])
            if not results:
                raise TMDBResolutionError(f"No movies found for title: {title}")
            
            first_movie = results[0]
            tmdb_id = first_movie.get("id")

            details_url = f"{self.base_url}/movie/{tmdb_id}"
            details_params = {
                "api_key": self.api_key,
                "language": "en-US"
            }
            
            details_response = await client.get(details_url, params=details_params)
            details_response.raise_for_status()
            details_data = details_response.json()
            
            imdb_id = details_data.get("imdb_id")
            if not imdb_id:
                raise TMDBResolutionError(f"Movie found in TMDB (id: {tmdb_id}) but it lacks an IMDb ID.")

            return imdb_id

    async def async_get_movie_meta(self, imdb_id: str) -> dict:
        """
        Fetch movie metadata (poster, title, year) from TMDB using an IMDb ID.
        Lightweight call used by the frontend for display purposes.
        """
        find_url = f"{self.base_url}/find/{imdb_id}"
        params = {
            "api_key": self.api_key,
            "external_source": "imdb_id",
        }
        async with httpx.AsyncClient() as client:
            resp = await client.get(find_url, params=params)
            resp.raise_for_status()
            data = resp.json()
            results = data.get("movie_results", [])
            is_tv = False
            
            if not results:
                results = data.get("tv_results", [])
                is_tv = True
                
            if not results:
                return {}
                
            m = results[0]
            poster_path = m.get("poster_path", "")
            
            # TV shows use 'name' and 'first_air_date', movies use 'title' and 'release_date'
            title = m.get("name") if is_tv else m.get("title")
            raw_date = m.get("first_air_date") if is_tv else m.get("release_date")
            year = (raw_date or "")[:4]
            
            return {
                "title": title or "",
                "year": year,
                "poster_url": f"https://image.tmdb.org/t/p/w500{poster_path}" if poster_path else "",
                "overview": m.get("overview", ""),
                "vote_average": m.get("vote_average", 0),
            }

if __name__ == "__main__":
    # 简易本地调试脚本
    try:
        resolver = TMDBResolver()
        print(f"Resolving 'The Matrix'...")
        imdb_id = resolver.search_movie("The Matrix")
        print(f"Result IMDb ID for 'The Matrix': {imdb_id}")
    except Exception as e:
        print(f"Error during resolution: {e}")
