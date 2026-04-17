"""
Generates hyper-personalized outreach emails using Claude.
Every output is specific to one person at one company.
No templates. No generic phrases. Real personalization.
"""

import json
import anthropic
from candidate_profile import CANDIDATE
from config import settings


class EmailGenerator:

    BANNED_PHRASES = [
        "i hope this email finds you well",
        "i am writing to express my interest",
        "i would love the opportunity",
        "please find attached",
        "results-driven",
        "passionate about",
        "i came across your",
        "dynamic leader",
        "leverage synergies",
        "i'd like to connect"
    ]

    def __init__(self):
        self.client = anthropic.Anthropic(
            api_key=settings.ANTHROPIC_API_KEY
        )

    def generate_all(
        self,
        company_name: str,
        sector: str,
        country: str,
        trigger_signal: str,
        trigger_source: str,
        contact_name: str,
        contact_title: str,
        contact_email: str,
        open_role: str = None,
        recent_activity: str = None,
        recent_activity_url: str = None,
        job_description: str = None,
    ) -> dict:
        """
        Generate all outreach assets for one target.
        Returns complete, ready-to-use content.
        """

        print(f"  → Selecting best achievements for {sector}...")
        top_achievements = self._select_achievements(
            sector, trigger_signal, country
        )

        print(f"  → Generating personalized cold email...")
        cold_email = self._generate_cold_email(
            company_name, sector, country, trigger_signal,
            trigger_source, contact_name, contact_title,
            contact_email, open_role, recent_activity,
            recent_activity_url, top_achievements
        )

        cold_email = self._validate_and_fix_email(
            cold_email, company_name, contact_name,
            trigger_signal, top_achievements
        )

        print(f"  → Generating LinkedIn note...")
        linkedin_note = self._generate_linkedin_note(
            company_name, sector, country, trigger_signal,
            contact_name, contact_title, recent_activity
        )

        print(f"  → Generating follow-up email...")
        followup = self._generate_followup(
            company_name, contact_name, contact_title,
            cold_email["subject"], trigger_signal,
            top_achievements
        )

        print(f"  → Generating cover letter...")
        cover_letter = self._generate_cover_letter(
            company_name, sector, country, trigger_signal,
            open_role, contact_name, contact_title,
            job_description, top_achievements
        )

        return {
            "cold_email": cold_email,
            "linkedin_note": linkedin_note,
            "followup_email": followup,
            "cover_letter": cover_letter,
            "achievements_used": [a["id"] for a in top_achievements],
            "personalization_hooks": self._describe_hooks(
                trigger_signal, recent_activity, sector
            )
        }

    def _select_achievements(
        self, sector: str, trigger: str, country: str
    ) -> list:
        """Select 3 most relevant achievements for this target."""
        sector_l = sector.lower()
        trigger_l = trigger.lower()
        country_l = country.lower()

        scored = []
        for ach in CANDIDATE["achievements"]:
            score = 0
            tags = [t.lower() for t in ach["tags"]]

            if "power" in sector_l:
                if any(t in tags for t in ["power","kaizen","downtime"]):
                    score += 4
            if "infrastructure" in sector_l:
                if any(t in tags for t in ["infrastructure","portfolio"]):
                    score += 4
            if "mining" in sector_l:
                if "maintenance" in tags or "downtime" in tags:
                    score += 3
            if "renewable" in sector_l or "energy" in sector_l:
                if any(t in tags for t in ["power","efficiency"]):
                    score += 3
            if "ai" in sector_l or "tech" in sector_l:
                if any(t in tags for t in ["ai","digital","innovation"]):
                    score += 4

            if "turnaround" in trigger_l or "restructur" in trigger_l:
                if any(t in tags for t in ["turnaround","rescue","P&L"]):
                    score += 5
            if "expansion" in trigger_l or "new market" in trigger_l:
                if any(t in tags for t in ["expansion","international"]):
                    score += 5
            if "fund" in trigger_l or "growth" in trigger_l:
                if any(t in tags for t in ["revenue","growth"]):
                    score += 3
            if "digital" in trigger_l or "transform" in trigger_l:
                if any(t in tags for t in ["digital","ai","innovation"]):
                    score += 4

            if "africa" in country_l:
                if "africa" in tags or "infrastructure" in tags:
                    score += 2

            scored.append((score, ach))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [a for _, a in scored[:3]]

    def _generate_cold_email(
        self, company_name, sector, country, trigger,
        trigger_source, contact_name, contact_title,
        contact_email, open_role, recent_activity,
        recent_activity_url, top_achievements
    ) -> dict:
        """Generate cold outreach email via Claude."""

        first_name = contact_name.split()[0] if contact_name else "there"

        achievements_text = "\n".join([
            f"- {a['headline']}: {a['one_liner']}"
            for a in top_achievements
        ])

        recent_text = ""
        if recent_activity:
            recent_text = f"""
PERSONALIZATION HOOK — USE THIS IN OPENING:
{contact_name} recently: {recent_activity}
Source: {recent_activity_url or 'N/A'}
Instruction: Reference this SPECIFICALLY in your opening line.
This makes the email feel researched and personal.
"""

        prompt = f"""
Write a cold outreach email. This must feel like a senior executive
wrote it specifically for this one person, not a template.

══ RECIPIENT ══
Name: {contact_name}
First Name (use this): {first_name}
Title: {contact_title}
Company: {company_name}
Sector: {sector}
Country: {country}
Email: {contact_email}

══ WHY THIS EMAIL NOW ══
Company Trigger: {trigger}
Source URL: {trigger_source}
Open Role: {open_role or "Not publicly advertised"}
{recent_text}

══ SENDER ══
Name: {CANDIDATE['name']}
Current Role: Lead Project Manager, $150M+ infrastructure portfolio,
Vulcan Group, South Africa
Background: 12+ years, $370M+ assets, $125M+ revenue growth,
12 countries, Toshiba JSW + Reliance Industries + AmpFy (AI founder)

TOP 3 MOST RELEVANT ACHIEVEMENTS FOR THIS TARGET:
{achievements_text}

Contact: {CANDIDATE['phone']} | {CANDIDATE['email']}

══ RULES YOU CANNOT BREAK ══

STRUCTURE:
Subject: [specific to their situation — references their company/news]

{first_name},

[OPENING — 1-2 sentences MAXIMUM]
Start with THEIR world. Their news. Their challenge. Their quote.
Reference {trigger} or {recent_activity or 'their company situation'}.
Do NOT mention the sender in the opening.
Do NOT say "I hope" or "I came across" or "I noticed".
Write as if you follow their sector closely and something
specific made you write TODAY.

[MIDDLE — 2-3 sentences]
Bridge from their situation to sender's most relevant experience.
Use ONE achievement with exact numbers from the achievement bank above.
Pick the achievement most relevant to {trigger} and {sector}.
"Which is precisely where I've built my career..." type transitions.

[VALUE ADD — 1-2 sentences]
What makes sender uniquely suited to THEIR specific challenge.
Something they won't find in most CVs.
Reference the geography match ({country} / Africa / international)
if relevant.

[CTA — 1 sentence]
Peer-level. Not asking for a favor.
Not "I would love". Not "Would you consider".
Options: "Worth a 20-minute call to see if there's a fit?"
         "Happy to share specifics if the timing is right."
         "Would a brief conversation make sense?"

[Signature]
{CANDIDATE['name']}
{CANDIDATE['phone']}
{CANDIDATE['email']}

WORD COUNT: Body must be 150-185 words. Count them.

BANNED PHRASES — these will disqualify the email:
"I hope this email finds you well"
"I am writing to express my interest"
"I would love the opportunity"
"Please find attached"
"results-driven", "passionate", "dynamic"
"proven track record" (show it, don't say it)
"I came across your profile"
"leverage synergies"
Any sentence that starts with "I" as the first word of the email

TONE: Senior executive to senior executive.
Confident. Specific. Concise. No buzzwords. No fluff.

══ OUTPUT ══
Return ONLY valid JSON:
{{
    "subject": "exact subject line",
    "body": "complete email as it will be sent — include greeting and signature",
    "word_count": 0,
    "first_line": "copy of just the first line",
    "achievement_used": "which achievement you referenced and why",
    "personalization_element": "what specific thing you personalized and how",
    "tone_assessment": "brief note on tone achieved"
}}
"""

        response = self.client.messages.create(
            model="claude-opus-4-5",
            max_tokens=1500,
            messages=[{"role": "user", "content": prompt}]
        )

        raw = response.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]

        return json.loads(raw.strip())

    def _validate_and_fix_email(
        self, email_dict: dict, company_name: str,
        contact_name: str, trigger: str, achievements: list
    ) -> dict:
        """
        Check for banned phrases. If found, regenerate.
        Max 2 attempts.
        """
        body_lower = email_dict.get("body", "").lower()
        violations = [
            phrase for phrase in self.BANNED_PHRASES
            if phrase in body_lower
        ]

        if violations:
            print(f"  ⚠ Banned phrases found: {violations}")
            print(f"  → Regenerating email...")
            fix_prompt = f"""
The email you wrote contained these banned phrases that must be removed:
{violations}

Rewrite the email completely avoiding ALL of these.
Original context: email to {contact_name} at {company_name}
about: {trigger}

Return same JSON structure as before.
"""
            response = self.client.messages.create(
                model="claude-opus-4-5",
                max_tokens=1500,
                messages=[
                    {"role": "user", "content": fix_prompt}
                ]
            )
            raw = response.content[0].text.strip()
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            email_dict = json.loads(raw.strip())

        return email_dict

    def _generate_linkedin_note(
        self, company_name, sector, country, trigger,
        contact_name, contact_title, recent_activity
    ) -> dict:
        """Generate LinkedIn connection request note."""

        first_name = contact_name.split()[0] if contact_name else ""

        prompt = f"""
Write a LinkedIn connection request note for:
{contact_name}, {contact_title} at {company_name}
Trigger: {trigger}
Recent Activity: {recent_activity or "Not available"}
Sender: {CANDIDATE['name']}, Global Ops Executive,
        12 years, $370M+ assets managed

RULES:
- MAXIMUM 295 characters TOTAL (hard LinkedIn limit)
- Count characters before finalizing
- Reference something SPECIFIC about them or their company
- Sound like a peer reaching out, not a job seeker
- No "I'd like to add you to my network"
- No "I came across your profile"
- Should prompt a reply or acceptance

Return JSON:
{{
    "note": "the complete note text",
    "character_count": 0,
    "hook": "what specific thing you referenced"
}}
"""
        response = self.client.messages.create(
            model="claude-opus-4-5",
            max_tokens=400,
            messages=[{"role": "user", "content": prompt}]
        )
        raw = response.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        result = json.loads(raw.strip())

        if len(result.get("note", "")) > 300:
            result["note"] = result["note"][:295] + "..."
            result["character_count"] = len(result["note"])

        return result

    def _generate_followup(
        self, company_name, contact_name, contact_title,
        original_subject, trigger, achievements
    ) -> dict:
        """Generate follow-up for non-replies at day 5."""

        first_name = contact_name.split()[0] if contact_name else ""
        top_ach = achievements[0] if achievements else None

        prompt = f"""
Write a follow-up email. Original email had no reply after 5 days.

To: {contact_name}, {contact_title} at {company_name}
Original Subject: {original_subject}
Context: {trigger}
New angle to add: {top_ach['one_liner'] if top_ach else 'Additional relevant experience'}
Sender: {CANDIDATE['name']}

RULES:
- Under 80 words in body (count them)
- Subject: Re: {original_subject}
- Do NOT start with "Just following up" or "Checking in"
- Add ONE new piece of information not in original email
- Even softer CTA — give easy out ("If timing isn't right,
  no worries at all")
- Not desperate. Not apologetic. Still peer-level.
- Can reference something new that happened at their company
  or in the sector if relevant

Return JSON:
{{
    "subject": "Re: {original_subject}",
    "body": "complete follow-up body with greeting and signature",
    "word_count": 0,
    "new_value_added": "what new thing you added"
}}
"""
        response = self.client.messages.create(
            model="claude-opus-4-5",
            max_tokens=600,
            messages=[{"role": "user", "content": prompt}]
        )
        raw = response.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw.strip())

    def _generate_cover_letter(
        self, company_name, sector, country, trigger,
        open_role, contact_name, contact_title,
        jd, achievements
    ) -> dict:
        """Generate formal cover letter for portal applications."""

        salutation = (
            f"Dear {contact_name}," if contact_name
            else "Dear Hiring Team,"
        )
        ach_text = "\n".join([
            f"- {a['headline']}: {a['one_liner']}"
            for a in achievements
        ])

        candidate_name = CANDIDATE['name']
        candidate_phone = CANDIDATE['phone']
        candidate_email = CANDIDATE['email']

        prompt = f"""
Write an executive cover letter for a formal application.

Target: {open_role or "Senior Operations/Strategy Executive"}
at {company_name}, {country}
Sector: {sector}
Context: {trigger}
Addressed to: {salutation}
JD Available: {jd or "Not provided — infer from role and sector"}
Sender: {CANDIDATE['name']}
Background: 12 years, $370M+ assets, $125M+ revenue growth, 12 countries

Best achievements for this role:
{ach_text}

STRUCTURE (follow exactly):

Para 1 (3 sentences):
Start with THEIR situation — reference {trigger}
State role being applied for in sentence 2
Why this specific company is uniquely interesting (not generic)

Para 2 (4 sentences):
Most relevant experience story with numbers
Make it read like a mini case study
Connect directly to what {company_name} is trying to achieve

Para 3 (3 sentences):
Second relevant achievement mapped to their need
Show understanding of {sector} specific challenges
The cross-geography or cross-cultural angle

Para 4 (2 sentences):
What you bring beyond metrics — judgment, agility,
board-level presence
The thing that doesn't appear on a spreadsheet

Para 5 (2 sentences):
CTA — confident, not desperate
Invite a conversation

Closing: "Yours sincerely," or "Best regards,"

RULES:
- NEVER start Para 1 with "I am writing to apply"
- Every substantive paragraph must have at least one number
- 380-450 words total
- Specific to {company_name} throughout

Return JSON:
{{
    "salutation": "{salutation}",
    "body": "all paragraphs as one string with blank lines between",
    "closing": "Yours sincerely,\\n\\n{candidate_name}\\n{candidate_phone}\\n{candidate_email}",
    "full_text": "salutation + blank line + body + blank line + closing",
    "word_count": 0
}}
"""
        response = self.client.messages.create(
            model="claude-opus-4-5",
            max_tokens=1500,
            messages=[{"role": "user", "content": prompt}]
        )
        raw = response.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw.strip())

    def _describe_hooks(
        self, trigger: str, recent_activity: str, sector: str
    ) -> list:
        """Describe what was personalized for transparency."""
        hooks = []
        if trigger:
            hooks.append(f"Company trigger: {trigger[:100]}")
        if recent_activity:
            hooks.append(f"Contact activity: {recent_activity[:100]}")
        hooks.append(f"Sector-matched achievements for: {sector}")
        return hooks
