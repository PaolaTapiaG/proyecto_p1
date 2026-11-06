from dataclasses import dataclass
from datetime import datetime, timezone

import httpx

from app.core.config import settings


@dataclass(frozen=True)
class CharacterResearch:
    title: str
    summary: str
    url: str
    researched_at: datetime


class CharacterResearchService:
    """Consulta Wikipedia sin permitir URLs arbitrarias proporcionadas por usuarios."""

    endpoints = (
        "https://es.wikipedia.org/w/api.php",
        "https://en.wikipedia.org/w/api.php",
    )

    def research(self, character_name: str, source_name: str | None) -> CharacterResearch | None:
        if not settings.character_research_enabled:
            return None
        query = " ".join(value for value in (character_name, source_name) if value).strip()
        if not query:
            return None

        for endpoint in self.endpoints:
            try:
                result = self._query_endpoint(endpoint, query)
            except httpx.HTTPError:
                continue
            if result:
                return result
        return None

    def _query_endpoint(self, endpoint: str, query: str) -> CharacterResearch | None:
        response = httpx.get(
            endpoint,
            params={
                "action": "query",
                "generator": "search",
                "gsrsearch": query,
                "gsrnamespace": 0,
                "gsrlimit": 3,
                "prop": "extracts|info",
                "exintro": 1,
                "explaintext": 1,
                "inprop": "url",
                "redirects": 1,
                "format": "json",
                "formatversion": 2,
            },
            headers={
                "User-Agent": "LumoraRoleplay/0.2 (contact: paola@lumora.local)"
            },
            timeout=settings.character_research_timeout_seconds,
            follow_redirects=True,
        )
        response.raise_for_status()
        pages = (response.json().get("query") or {}).get("pages") or []
        page = next((item for item in pages if item.get("extract")), None)
        if not page:
            return None
        return CharacterResearch(
            title=page.get("title", query),
            summary=page["extract"].strip()[:7000],
            url=page.get("fullurl", endpoint),
            researched_at=datetime.now(timezone.utc),
        )


research_service = CharacterResearchService()
