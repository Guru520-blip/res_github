"""
Scrape the web for company signals in real-time.
Uses SerpAPI (if key available) or direct Bing search.
Feeds raw data into Claude for intelligent extraction.
"""

import httpx
import json
import asyncio
import random
from bs4 import BeautifulSoup
import anthropic
from config import settings
from candidate_profile import CANDIDATE


class SignalScraper:

    USER_AGENTS = [
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ]

    SEARCH_QUERIES = [
        '("VP Operations" OR "COO" OR "Director of Operations") '
        '(infrastructure OR "power generation" OR EPC) job 2025',

        '("Managing Director" OR "Country Manager") '
        '(Africa OR "Middle East" OR Singapore) '
        'operations industrial 2025',

        '(infrastructure OR energy OR "power generation") company '
        '"expanding into" OR "new markets" OR "regional expansion" 2025',

        '("PE acquisition" OR "private equity" OR "turnaround") '
        'industrial operations COO hire 2025',

        '(infrastructure OR EPC OR "power" OR "energy") '
        'company "Series B" OR "Series C" OR "raised" '
        'operations 2024 2025',

        '"contract awarded" OR "new contract" '
        '(infrastructure OR EPC OR power) '
        '(Africa OR "Middle East" OR Asia) 2025'
    ]

    def __init__(self):
        self.client = anthropic.Anthropic(
            api_key=settings.ANTHROPIC_API_KEY
        )

    async def run_discovery(
        self,
        custom_queries: list = None,
        max_results: int = 20
    ) -> list:
        """
        Run search queries, extract company signals.
        Returns list of opportunity dicts scored by relevance.
        """

        queries = custom_queries or self.SEARCH_QUERIES
        all_signals = []
        seen_companies = set()

        async with httpx.AsyncClient(
            timeout=15.0,
            follow_redirects=True
        ) as client:
            for query in queries:
                print(f"  Searching: {query[:60]}...")

                urls = await self._search(client, query)

                for url in urls[:4]:
                    if any(
                        skip in url for skip in [
                            "linkedin.com", "facebook.com",
                            "twitter.com", "instagram.com",
                            "youtube.com", "wikipedia.org"
                        ]
                    ):
                        continue

                    signal = await self._extract_signal(client, url, query)

                    if signal and signal.get("company_name"):
                        co_key = signal["company_name"].lower().strip()
                        if co_key not in seen_companies:
                            seen_companies.add(co_key)
                            scored = self._score_signal(signal)
                            if scored["priority_score"] >= 3.0:
                                all_signals.append(scored)
                                print(
                                    f"  ✓ Found: {signal['company_name']} "
                                    f"(score: {scored['priority_score']})"
                                )

                await asyncio.sleep(random.uniform(1.5, 3.0))

                if len(all_signals) >= max_results:
                    break

        return sorted(
            all_signals,
            key=lambda x: x["priority_score"],
            reverse=True
        )[:max_results]

    async def _search(
        self, client: httpx.AsyncClient, query: str
    ) -> list:
        """Search web for query, return list of URLs."""

        if settings.SERP_API_KEY:
            try:
                resp = await client.get(
                    "https://serpapi.com/search",
                    params={
                        "q": query,
                        "api_key": settings.SERP_API_KEY,
                        "num": 8,
                        "hl": "en",
                        "gl": "us"
                    }
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return [
                        r["link"]
                        for r in data.get("organic_results", [])
                        if r.get("link")
                    ]
            except Exception:
                pass

        # Fallback: Bing search
        try:
            resp = await client.get(
                "https://www.bing.com/search",
                params={"q": query, "count": 10},
                headers={"User-Agent": random.choice(self.USER_AGENTS)}
            )
            soup = BeautifulSoup(resp.text, "html.parser")
            links = []
            for a in soup.select("li.b_algo h2 a"):
                href = a.get("href", "")
                if href.startswith("http"):
                    links.append(href)
            return links[:8]
        except Exception:
            return []

    async def _extract_signal(
        self,
        client: httpx.AsyncClient,
        url: str,
        query: str
    ) -> dict:
        """Visit URL, extract company signal via Claude."""

        try:
            resp = await client.get(
                url,
                headers={"User-Agent": random.choice(self.USER_AGENTS)}
            )
            soup = BeautifulSoup(resp.text, "html.parser")

            for el in soup(["script", "style", "nav", "footer",
                            "header", "aside", "iframe"]):
                el.decompose()

            text = soup.get_text(separator=" ", strip=True)
            text = " ".join(text.split())[:2500]

            if len(text) < 100:
                return {}

            extract_prompt = f"""
Extract company opportunity signal from this web content.
Search query: {query}
URL: {url}

Content:
{text}

If this page describes a real company with a signal relevant to an
Operations/Strategy Executive opportunity, extract and return JSON.
If not relevant, return {{"is_relevant": false}}.

Relevant signals: funding rounds, international expansion,
new contracts, PE acquisition, leadership hire, turnaround,
restructuring, digital transformation initiative.

Return JSON:
{{
    "is_relevant": true/false,
    "company_name": "string",
    "website_hint": "domain if visible",
    "country": "headquarters country",
    "sector": "primary sector",
    "trigger_type": "funding|expansion|job_posting|restructuring|new_contract|leadership_change",
    "trigger_signal": "specific 1-2 sentence description of the signal",
    "open_role_title": "exact role title if job posting found, else null",
    "relevance_reason": "why relevant for ops/strategy executive"
}}

Return ONLY JSON. No other text.
"""
            response = self.client.messages.create(
                model="claude-opus-4-5",
                max_tokens=500,
                messages=[{"role": "user", "content": extract_prompt}]
            )

            raw = response.content[0].text.strip()
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]

            result = json.loads(raw.strip())

            if result.get("is_relevant"):
                result["trigger_source_url"] = url
                return result

        except Exception:
            pass

        return {}

    def _score_signal(self, signal: dict) -> dict:
        """Score opportunity signal 0-10."""
        score = 0.0

        trigger = signal.get("trigger_type", "").lower()
        sig_text = signal.get("trigger_signal", "").lower()
        country = signal.get("country", "").lower()
        sector = signal.get("sector", "").lower()

        trigger_pts = {
            "job_posting": 3.5,
            "restructuring": 3.5,
            "funding": 3.0,
            "expansion": 3.0,
            "leadership_change": 2.5,
            "new_contract": 2.0
        }
        score += trigger_pts.get(trigger, 1.0)

        hv_keywords = [
            "coo", "vp operations", "director of operations",
            "turnaround", "transformation", "new markets",
            "pe acquisition", "restructuring"
        ]
        score += sum(0.4 for kw in hv_keywords if kw in sig_text)

        p1_geo = ["uae", "saudi", "qatar", "singapore", "oman"]
        p2_geo = ["south africa", "uk", "australia", "malaysia", "kenya"]
        if any(g in country for g in p1_geo):
            score += 1.5
        elif any(g in country for g in p2_geo):
            score += 1.0

        p1_sectors = ["power", "infrastructure", "epc", "industrial"]
        p2_sectors = ["mining", "oil", "gas", "logistics", "energy"]
        if any(s in sector for s in p1_sectors):
            score += 1.5
        elif any(s in sector for s in p2_sectors):
            score += 1.0

        signal["priority_score"] = round(min(score, 10.0), 1)
        return signal
