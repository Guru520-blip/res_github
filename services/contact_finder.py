"""
Multi-layer contact finding system.
Tries each method in sequence. Returns best result found.
Labels every email with exact confidence level.
Never crashes — always returns something.
"""

import httpx
import asyncio
import re
import json
import dns.resolver
from typing import Optional


class ContactFinder:

    EMAIL_PATTERNS = [
        "{first}.{last}",
        "{f}{last}",
        "{first}",
        "{first}{last}",
        "{f}.{last}",
        "{last}.{first}",
        "{first}_{last}",
        "{last}"
    ]

    async def find_email(
        self,
        first_name: str,
        last_name: str,
        domain: str,
        company_name: str,
        hunter_key: str = None,
        apollo_key: str = None
    ) -> dict:
        """
        Master finder. Runs all layers, returns best result.
        Return structure:
        {
            "email": "found@company.com or None",
            "confidence": "VERIFIED|HIGH|MEDIUM|LOW|NONE",
            "confidence_score": 0-100,
            "source": "hunter|apollo|pattern|scraped|none",
            "pattern_used": "first.last@domain or None",
            "mx_valid": True/False,
            "smtp_check": "valid|invalid|unknown",
            "all_attempts": [...],
            "recommended_email": "best guess even if unverified"
        }
        """

        result = {
            "email": None,
            "confidence": "NONE",
            "confidence_score": 0,
            "source": "none",
            "pattern_used": None,
            "mx_valid": False,
            "smtp_check": "unknown",
            "all_attempts": [],
            "recommended_email": None
        }

        # Layer 1: Hunter.io
        if hunter_key:
            hunter_result = await self._try_hunter(
                first_name, last_name, domain, hunter_key
            )
            result["all_attempts"].append(hunter_result)
            if hunter_result.get("email"):
                result.update({
                    "email": hunter_result["email"],
                    "confidence": hunter_result["confidence"],
                    "confidence_score": hunter_result["score"],
                    "source": "hunter"
                })
                verified = await self._verify_email_deliverability(
                    hunter_result["email"]
                )
                result.update(verified)
                if result["confidence_score"] >= 70:
                    result["recommended_email"] = result["email"]
                    return result

        # Layer 2: Apollo.io
        if apollo_key:
            apollo_result = await self._try_apollo(
                first_name, last_name, company_name, apollo_key
            )
            result["all_attempts"].append(apollo_result)
            if apollo_result.get("email"):
                result.update({
                    "email": apollo_result["email"],
                    "confidence": "HIGH",
                    "confidence_score": 75,
                    "source": "apollo"
                })
                verified = await self._verify_email_deliverability(
                    apollo_result["email"]
                )
                result.update(verified)
                result["recommended_email"] = result["email"]
                return result

        # Layer 3: Scrape domain for email pattern detection
        scraped_pattern = await self._detect_domain_pattern(domain)
        if scraped_pattern:
            constructed = self._construct_email(
                first_name, last_name, domain, scraped_pattern
            )
            mx_ok = await self._check_mx(domain)
            result.update({
                "email": constructed,
                "confidence": "MEDIUM" if mx_ok else "LOW",
                "confidence_score": 60 if mx_ok else 35,
                "source": "pattern",
                "pattern_used": scraped_pattern,
                "mx_valid": mx_ok,
                "recommended_email": constructed
            })
            result["all_attempts"].append({
                "method": "pattern_from_scrape",
                "email": constructed,
                "pattern": scraped_pattern
            })
            return result

        # Layer 4: Common pattern attempts with MX verification
        mx_ok = await self._check_mx(domain)
        if mx_ok:
            best_pattern = self.EMAIL_PATTERNS[0]  # first.last most common
            constructed = self._construct_email(
                first_name, last_name, domain, best_pattern + "@{domain}"
            )
            result.update({
                "email": constructed,
                "confidence": "LOW",
                "confidence_score": 30,
                "source": "pattern_guess",
                "pattern_used": best_pattern,
                "mx_valid": True,
                "recommended_email": constructed
            })
            result["all_attempts"].append({
                "method": "common_pattern",
                "email": constructed,
                "pattern": best_pattern
            })

            all_patterns = []
            for p in self.EMAIL_PATTERNS:
                guess = self._construct_email(
                    first_name, last_name, domain, p + "@{domain}"
                )
                all_patterns.append(guess)
            result["all_pattern_guesses"] = all_patterns

        return result

    async def _try_hunter(
        self, first: str, last: str, domain: str, api_key: str
    ) -> dict:
        """Hunter.io email finder API call."""
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(
                    "https://api.hunter.io/v2/email-finder",
                    params={
                        "domain": domain,
                        "first_name": first,
                        "last_name": last,
                        "api_key": api_key
                    }
                )
                if response.status_code == 200:
                    data = response.json().get("data", {})
                    email = data.get("email")
                    score = data.get("score", 0)
                    if email:
                        confidence = (
                            "VERIFIED" if score >= 80 else
                            "HIGH" if score >= 60 else
                            "MEDIUM"
                        )
                        return {
                            "method": "hunter",
                            "email": email,
                            "score": score,
                            "confidence": confidence,
                            "sources": data.get("sources", [])
                        }
        except Exception as e:
            return {"method": "hunter", "error": str(e), "email": None}
        return {"method": "hunter", "email": None}

    async def _try_apollo(
        self, first: str, last: str,
        company: str, api_key: str
    ) -> dict:
        """Apollo.io people match API call."""
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    "https://api.apollo.io/v1/people/match",
                    json={
                        "first_name": first,
                        "last_name": last,
                        "organization_name": company,
                        "reveal_personal_emails": False
                    },
                    headers={
                        "x-api-key": api_key,
                        "Content-Type": "application/json",
                        "Cache-Control": "no-cache"
                    }
                )
                if response.status_code == 200:
                    person = response.json().get("person", {})
                    email = person.get("email")
                    if email and "@" in email:
                        return {
                            "method": "apollo",
                            "email": email,
                            "linkedin_url": person.get("linkedin_url"),
                            "title": person.get("title"),
                            "phone": (
                                person.get("phone_numbers", [{}])[0]
                                .get("sanitized_number")
                                if person.get("phone_numbers") else None
                            )
                        }
        except Exception as e:
            return {"method": "apollo", "error": str(e), "email": None}
        return {"method": "apollo", "email": None}

    async def _detect_domain_pattern(self, domain: str) -> Optional[str]:
        """
        Scrape company domain to find any real email addresses.
        Infer pattern from found addresses.
        """
        pages_to_check = [
            f"https://{domain}/contact",
            f"https://{domain}/about",
            f"https://{domain}/team",
            f"https://www.{domain}/contact",
            f"https://www.{domain}/about"
        ]

        email_regex = re.compile(
            r'\b[A-Za-z0-9._%+-]+@' + re.escape(domain) + r'\b',
            re.IGNORECASE
        )

        async with httpx.AsyncClient(
            timeout=10.0,
            follow_redirects=True,
            headers={"User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
            )}
        ) as client:
            for url in pages_to_check:
                try:
                    resp = await client.get(url)
                    emails_found = email_regex.findall(resp.text)
                    real_emails = [
                        e for e in emails_found
                        if not any(g in e.lower() for g in [
                            "info@", "support@", "admin@",
                            "noreply@", "hello@", "contact@"
                        ])
                    ]
                    if real_emails:
                        return self._infer_pattern(real_emails[0], domain)
                    if emails_found:
                        return "{first}.{last}@{domain}"
                except Exception:
                    continue
        return None

    def _infer_pattern(self, email: str, domain: str) -> str:
        """Infer email pattern from a real example email."""
        local = email.split("@")[0].lower()
        if "." in local:
            parts = local.split(".")
            if len(parts) == 2:
                if len(parts[0]) == 1:
                    return "{f}.{last}@{domain}"
                return "{first}.{last}@{domain}"
        if "_" in local:
            return "{first}_{last}@{domain}"
        if len(local) <= 3:
            return "{f}{last}@{domain}"
        return "{first}@{domain}"

    def _construct_email(
        self, first: str, last: str, domain: str, pattern: str
    ) -> str:
        """Apply pattern to construct email address."""
        first = first.lower().strip().replace(" ", "")
        last = last.lower().strip().replace(" ", "")
        f = first[0] if first else ""
        return (pattern
            .replace("{first}", first)
            .replace("{last}", last)
            .replace("{f}", f)
            .replace("{domain}", domain)
        )

    async def _check_mx(self, domain: str) -> bool:
        """Check if domain has valid MX records (can receive email)."""
        try:
            loop = asyncio.get_event_loop()
            records = await loop.run_in_executor(
                None,
                lambda: dns.resolver.resolve(domain, 'MX')
            )
            return len(records) > 0
        except Exception:
            return False

    async def _verify_email_deliverability(self, email: str) -> dict:
        """
        Verify email using AbstractAPI email validation.
        Falls back to MX check only if no API key.
        """
        from config import settings

        if settings.ABSTRACT_API_KEY:
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.get(
                        "https://emailvalidation.abstractapi.com/v1/",
                        params={
                            "api_key": settings.ABSTRACT_API_KEY,
                            "email": email
                        }
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        is_valid = (
                            data.get("is_valid_format", {})
                                .get("value", False) and
                            data.get("is_mx_found", {})
                                .get("value", False)
                        )
                        deliverability = data.get(
                            "deliverability", "UNKNOWN"
                        )
                        smtp_valid = data.get("is_smtp_valid", {})
                        smtp_value = smtp_valid.get("value", False)

                        if deliverability == "DELIVERABLE" and smtp_value:
                            return {
                                "smtp_check": "valid",
                                "mx_valid": True,
                                "confidence": "VERIFIED",
                                "confidence_score": 95
                            }
                        elif is_valid:
                            return {
                                "smtp_check": "unknown",
                                "mx_valid": True,
                                "confidence": "HIGH",
                                "confidence_score": 70
                            }
                        else:
                            return {
                                "smtp_check": "invalid",
                                "mx_valid": False,
                                "confidence": "LOW",
                                "confidence_score": 15
                            }
            except Exception:
                pass

        # Fallback: MX only
        domain = email.split("@")[1]
        mx_ok = await self._check_mx(domain)
        return {
            "smtp_check": "unknown",
            "mx_valid": mx_ok,
            "confidence": "MEDIUM" if mx_ok else "LOW",
            "confidence_score": 45 if mx_ok else 20
        }

    async def find_decision_makers_web(
        self, company_name: str, domain: str
    ) -> list:
        """
        Search web for decision makers at company.
        Returns list of {name, title, source_url}
        """

        PRIORITY_TITLES = [
            "COO", "Chief Operating Officer",
            "VP Operations", "Vice President Operations",
            "Director of Operations", "Head of Operations",
            "Managing Director", "CEO",
            "Chief People Officer", "Head of HR",
            "VP Human Resources", "Head of Talent"
        ]

        found_people = []

        async with httpx.AsyncClient(
            timeout=15.0,
            headers={"User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
            )}
        ) as client:

            for path in ["/about/team", "/leadership",
                         "/our-team", "/management", "/about"]:
                try:
                    url = f"https://{domain}{path}"
                    resp = await client.get(url, follow_redirects=True)
                    if resp.status_code == 200:
                        from bs4 import BeautifulSoup
                        soup = BeautifulSoup(resp.text, "html.parser")
                        people = self._extract_people_from_page(
                            soup, PRIORITY_TITLES
                        )
                        if people:
                            found_people.extend(people)
                            break
                except Exception:
                    continue

        return found_people[:5]

    def _extract_people_from_page(
        self, soup, priority_titles: list
    ) -> list:
        """Extract names and titles from leadership page."""
        people = []

        selectors = [
            ("[class*='team']", "h3,h4,p"),
            ("[class*='leader']", "h3,h4,p"),
            ("[class*='exec']", "h3,h4,p"),
            ("[class*='member']", "h3,h4,p"),
            ("[class*='person']", "h3,h4,p"),
            ("article", "h3,h4"),
            (".card", "h3,h4,p"),
        ]

        for container_sel, text_sel in selectors:
            cards = soup.select(container_sel)
            for card in cards[:10]:
                texts = [
                    el.get_text(strip=True)
                    for el in card.select(text_sel)
                    if el.get_text(strip=True)
                ]
                if len(texts) >= 2:
                    potential_name = texts[0]
                    potential_title = texts[1]

                    is_dm = any(
                        pt.lower() in potential_title.lower()
                        for pt in priority_titles
                    )

                    if (is_dm and
                        self._looks_like_name(potential_name) and
                        len(potential_name) < 50):
                        parts = potential_name.strip().split()
                        if len(parts) >= 2:
                            people.append({
                                "full_name": potential_name,
                                "first_name": parts[0],
                                "last_name": parts[-1],
                                "title": potential_title,
                                "source": "company_website"
                            })

            if people:
                break

        return people

    def _looks_like_name(self, text: str) -> bool:
        """Basic check if string looks like a person's name."""
        if not text or len(text) > 60 or len(text) < 4:
            return False
        words = text.strip().split()
        if len(words) < 2 or len(words) > 5:
            return False
        if re.search(r'[0-9@#$%^&*()_+=\[\]{}<>]', text):
            return False
        return True
