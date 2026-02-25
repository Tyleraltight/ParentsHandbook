from abc import ABC, abstractmethod
from typing import Dict

class BaseScraper(ABC):
    """Abstract base class for IMDb Parental Guide scrapers."""
    
    @abstractmethod
    def fetch_parental_guide(self, imdb_id: str) -> Dict[str, str]:
        """
        Fetches and extracts parental guide content from IMDb (synchronous).
        :param imdb_id: The IMDb ID of the movie (e.g., 'tt0133093').
        :return: A dictionary mapping dimensions to text.
                 Keys: 'Sex & Nudity', 'Violence & Gore', 'Profanity', 
                       'Frightening Scenes'
        """
        pass

    @abstractmethod
    async def async_fetch_parental_guide(self, imdb_id: str) -> Dict[str, str]:
        """
        Async version of fetch_parental_guide for use with FastAPI.
        """
        pass
