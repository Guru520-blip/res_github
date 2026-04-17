"""
Analyze resume against job description for ATS compatibility.
Returns detailed keyword match report.
"""

import json
import anthropic
from config import settings


class ATSChecker:

    def __init__(self):
        self.client = anthropic.Anthropic(
            api_key=settings.ANTHROPIC_API_KEY
        )

    def analyze(
        self,
        resume_content: dict,
        job_description: str,
        role_title: str,
        sector: str
    ) -> dict:
        """Full ATS analysis. Returns detailed report."""

        if not job_description:
            return self._sector_based_check(
                resume_content, role_title, sector
            )

        resume_text = self._extract_resume_text(resume_content)

        prompt = f"""
Analyze this resume against this job description for ATS compatibility.

JOB DESCRIPTION:
{job_description}

RESUME TEXT:
{resume_text}

Return JSON with this exact structure:
{{
    "overall_score": 0-10,
    "keyword_match_rate": "percentage as string e.g. '73%'",
    "matched_keywords": ["keyword1", "keyword2"],
    "missing_keywords": ["keyword1", "keyword2"],
    "missing_critical": ["most important missing keywords"],
    "phrase_matches": ["exact phrases from JD found in resume"],
    "recommendations": [
        "Specific change to improve ATS score"
    ],
    "section_scores": {{
        "summary": 0-10,
        "experience": 0-10,
        "skills": 0-10
    }},
    "verdict": "STRONG MATCH|GOOD MATCH|PARTIAL MATCH|WEAK MATCH"
}}

Return ONLY JSON.
"""
        response = self.client.messages.create(
            model="claude-opus-4-5",
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}]
        )

        raw = response.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]

        return json.loads(raw.strip())

    def _sector_based_check(
        self, resume_content: dict,
        role_title: str, sector: str
    ) -> dict:
        """ATS check based on sector/role when no JD available."""

        resume_text = self._extract_resume_text(resume_content)

        sector_keywords = {
            "power": [
                "power generation", "thermal", "turbine", "steam",
                "MW", "GW", "O&M", "predictive maintenance",
                "planned outage", "forced outage", "heat rate"
            ],
            "infrastructure": [
                "project delivery", "EPC", "procurement", "stakeholders",
                "milestone", "critical path", "CAPEX", "lifecycle"
            ],
            "mining": [
                "extraction", "ore", "processing", "EBITDA",
                "throughput", "equipment availability", "maintenance"
            ],
            "energy": [
                "renewable", "solar", "wind", "grid", "capacity",
                "PPA", "IPP", "offtake", "energy transition"
            ]
        }

        sector_l = sector.lower()
        keywords = []
        for k, v in sector_keywords.items():
            if k in sector_l:
                keywords.extend(v)

        keywords.extend([
            "P&L", "EBITDA", "stakeholder", "portfolio",
            "turnaround", "cross-functional", "transformation",
            "strategic", "operational excellence", "revenue growth"
        ])

        resume_lower = resume_text.lower()
        matched = [kw for kw in keywords if kw.lower() in resume_lower]
        missing = [kw for kw in keywords if kw.lower() not in resume_lower]

        score = round((len(matched) / len(keywords)) * 10, 1) if keywords else 5.0

        return {
            "overall_score": score,
            "keyword_match_rate": f"{int(score * 10)}%",
            "matched_keywords": matched,
            "missing_keywords": missing[:10],
            "missing_critical": missing[:5],
            "phrase_matches": [],
            "recommendations": [
                f"Add '{kw}' to resume — common in {sector} sector"
                for kw in missing[:3]
            ],
            "section_scores": {
                "summary": score,
                "experience": score,
                "skills": score
            },
            "verdict": (
                "STRONG MATCH" if score >= 7 else
                "GOOD MATCH" if score >= 5 else
                "PARTIAL MATCH"
            )
        }

    def _extract_resume_text(self, content: dict) -> str:
        """Extract plain text from tailored resume content."""
        parts = []
        parts.append(content.get("tailored_headline", ""))
        parts.append(content.get("tailored_summary", ""))
        parts.extend(content.get("executive_highlights", []))
        for job in content.get("tailored_experience", []):
            parts.append(job.get("title", ""))
            parts.extend(job.get("bullets", []))
        comp = content.get("core_competencies", {})
        for skills in comp.values():
            parts.extend(skills)
        return " ".join(parts)
