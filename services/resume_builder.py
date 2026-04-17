"""
AI-powered resume tailoring using Claude API.
Produces complete, immediately-usable tailored resume.
Outputs formatted Word document.
"""

import json
import os
import anthropic
from datetime import datetime
from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from candidate_profile import CANDIDATE
from config import settings


class ResumeBuilder:

    def __init__(self):
        self.client = anthropic.Anthropic(
            api_key=settings.ANTHROPIC_API_KEY
        )

    def tailor_resume(
        self,
        company_name: str,
        sector: str,
        country: str,
        trigger_signal: str,
        open_role: str,
        job_description: str = None,
        contact_name: str = None,
        contact_title: str = None,
    ) -> dict:
        """
        Main entry point.
        Returns dict with tailored content + file path.
        """

        print(f"  → Analyzing opportunity at {company_name}...")

        tailored = self._ai_tailor(
            company_name, sector, country, trigger_signal,
            open_role, job_description, contact_name, contact_title
        )

        print(f"  → Building Word document...")
        docx_path = self._build_docx(tailored, company_name)
        print(f"  → Resume saved: {docx_path}")

        # PDF generation
        from services.pdf_exporter import PDFExporter
        exporter = PDFExporter()
        pdf_path = exporter.export_from_docx(docx_path)
        if not os.path.exists(pdf_path):
            pdf_path = exporter.build_pdf_from_content(tailored, company_name)
        print(f"  → PDF saved: {pdf_path}")

        # ATS analysis
        from services.ats_checker import ATSChecker
        checker = ATSChecker()
        ats_report = checker.analyze(
            tailored, job_description, open_role, sector
        )

        return {
            "tailored_content": tailored,
            "docx_path": docx_path,
            "pdf_path": pdf_path,
            "ats_score": ats_report.get("overall_score", 0),
            "ats_report": ats_report,
            "changes_count": len(tailored.get("changes_made", []))
        }

    def _ai_tailor(
        self,
        company_name, sector, country, trigger,
        role, jd, contact_name, contact_title
    ) -> dict:
        """
        Single Claude API call that does all tailoring intelligence.
        Returns complete structured resume content.
        """

        prompt = f"""
You are a world-class executive resume writer. Your job is to tailor
this candidate's resume specifically for ONE opportunity. Every section
must be rewritten with this specific company and role in mind.

══ TARGET OPPORTUNITY ══
Company: {company_name}
Sector: {sector}
Country: {country}
Role: {role or "Senior Operations/Strategy Executive"}
Decision Maker: {contact_name or "Not identified"}, {contact_title or ""}
Why This Company Now: {trigger}
Job Description: {jd or "Not available — infer from company/role context"}

══ CANDIDATE ORIGINAL PROFILE ══
Name: {CANDIDATE['name']}
Headline: {CANDIDATE['headline']}

Summary: {CANDIDATE['summary']}

Experience:
{json.dumps(CANDIDATE['experience'], indent=2)}

Key Metrics: {json.dumps(CANDIDATE['metrics'], indent=2)}

Achievements Bank:
{json.dumps(CANDIDATE['achievements'], indent=2)}

══ YOUR TAILORING TASK ══

1. HEADLINE: Rewrite to match exactly what {company_name} needs.
   Must be specific, not generic. Max 12 words.
   Example format: "Power Sector Turnaround Leader | $220M Recovery |
   6-Country Expansion Expert"

2. SUMMARY (EXACTLY 4 sentences):
   Sentence 1: Mirror {company_name}'s challenge or need — start
               with THEIR context
   Sentence 2: Most relevant achievement with exact numbers
   Sentence 3: Specific geography/sector experience that matches
   Sentence 4: What candidate brings that is hard to find elsewhere

   BANNED in summary:
   "results-driven", "passionate", "dynamic", "leverage",
   "synergies", "proven track record" (show it), "seeking"

3. EXECUTIVE HIGHLIGHTS (5 bullet points):
   Each bullet = one metric-led achievement
   Select from achievements bank — choose most relevant to {sector}
   and {trigger}
   Format: "▸ [Action verb] + [what] + [result with number]"

4. EXPERIENCE (rewrite bullets for relevance):
   Keep all 4 jobs. For each role:
   - Move most relevant bullet to position #1
   - Rewrite bullets to use language from job description
     (if provided) or from {sector} vocabulary
   - Every bullet must have at least ONE number
   - Lead with impact, not activity
   - Bad: "Responsible for managing team"
   - Good: "Directed 30-member cross-cultural team generating
            $80M across 6 new markets"

5. CORE COMPETENCIES (4 groups of 4-5 skills each):
   Strategic | Operational | Leadership | Technology
   Emphasize skills most relevant to {role} at {company_name}
   Inject these keywords if present in JD or sector vocabulary

6. CHANGES MADE (explain your reasoning):
   List every significant change and WHY you made it for
   this specific opportunity.

Return ONLY valid JSON in exactly this structure:
{{
    "tailored_headline": "string — max 15 words",
    "tailored_summary": "string — exactly 4 sentences",
    "executive_highlights": [
        "▸ bullet with number",
        "▸ bullet with number",
        "▸ bullet with number",
        "▸ bullet with number",
        "▸ bullet with number"
    ],
    "tailored_experience": [
        {{
            "title": "string",
            "company": "string",
            "location": "string",
            "period": "string",
            "bullets": ["string", "string", "string"]
        }}
    ],
    "core_competencies": {{
        "strategic": ["skill1", "skill2", "skill3", "skill4"],
        "operational": ["skill1", "skill2", "skill3", "skill4"],
        "leadership": ["skill1", "skill2", "skill3", "skill4"],
        "technology": ["skill1", "skill2", "skill3", "skill4"]
    }},
    "ats_keywords": ["keyword1", "keyword2"],
    "changes_made": [
        "Change: [what changed] | Reason: [why for this company]"
    ],
    "tailoring_rationale": "2-3 sentence explanation of overall approach"
}}

Return ONLY the JSON. No text before or after.
"""

        response = self.client.messages.create(
            model="claude-opus-4-5",
            max_tokens=4000,
            messages=[{"role": "user", "content": prompt}]
        )

        raw = response.content[0].text.strip()

        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()

        return json.loads(raw)

    def _build_docx(self, content: dict, company_name: str) -> str:
        """
        Build professional Word document from tailored content.
        Clean, ATS-friendly, executive-grade formatting.
        """

        doc = Document()

        for section in doc.sections:
            section.top_margin = Inches(0.65)
            section.bottom_margin = Inches(0.65)
            section.left_margin = Inches(0.75)
            section.right_margin = Inches(0.75)

        NAVY    = RGBColor(0x1B, 0x2A, 0x4A)
        BLUE    = RGBColor(0x2E, 0x86, 0xAB)
        DARK    = RGBColor(0x1A, 0x1A, 0x2E)
        GRAY    = RGBColor(0x55, 0x55, 0x55)
        LGRAY   = RGBColor(0x99, 0x99, 0x99)

        candidate = CANDIDATE

        # NAME
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_after = Pt(2)
        run = p.add_run(candidate["name"].upper())
        run.font.size = Pt(24)
        run.font.bold = True
        run.font.color.rgb = NAVY
        run.font.name = "Calibri"

        # TAILORED HEADLINE
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_after = Pt(3)
        run = p.add_run(content["tailored_headline"])
        run.font.size = Pt(11)
        run.font.color.rgb = BLUE
        run.font.italic = True
        run.font.name = "Calibri"

        # CONTACT LINE
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_after = Pt(6)
        contact_str = (
            f"{candidate['phone']}  |  {candidate['email']}  |  "
            f"{candidate['location']}  |  {candidate['linkedin']}"
        )
        run = p.add_run(contact_str)
        run.font.size = Pt(9)
        run.font.color.rgb = GRAY
        run.font.name = "Calibri"

        # DIVIDER
        self._add_divider(doc, NAVY)

        # EXECUTIVE SUMMARY
        self._section_header(doc, "EXECUTIVE SUMMARY", NAVY)
        p = doc.add_paragraph()
        p.paragraph_format.space_after = Pt(6)
        run = p.add_run(content["tailored_summary"])
        run.font.size = Pt(10)
        run.font.name = "Calibri"
        run.font.color.rgb = DARK

        # EXECUTIVE HIGHLIGHTS
        self._section_header(doc, "EXECUTIVE HIGHLIGHTS", NAVY)
        for bullet in content.get("executive_highlights", []):
            p = doc.add_paragraph()
            p.paragraph_format.left_indent = Inches(0.15)
            p.paragraph_format.space_after = Pt(3)
            run = p.add_run(bullet)
            run.font.size = Pt(10)
            run.font.name = "Calibri"
            run.font.color.rgb = DARK

        # PROFESSIONAL EXPERIENCE
        self._section_header(doc, "PROFESSIONAL EXPERIENCE", NAVY)

        for job in content["tailored_experience"]:
            p = doc.add_paragraph()
            p.paragraph_format.space_after = Pt(1)
            r1 = p.add_run(job["title"].upper())
            r1.font.bold = True
            r1.font.size = Pt(10.5)
            r1.font.color.rgb = NAVY
            r1.font.name = "Calibri"

            r2 = p.add_run("   |   ")
            r2.font.color.rgb = LGRAY
            r2.font.size = Pt(10)

            r3 = p.add_run(job["company"])
            r3.font.bold = True
            r3.font.size = Pt(10.5)
            r3.font.color.rgb = BLUE
            r3.font.name = "Calibri"

            p2 = doc.add_paragraph()
            p2.paragraph_format.space_after = Pt(3)
            r4 = p2.add_run(
                f"{job['location']}   |   {job['period']}"
            )
            r4.font.size = Pt(9)
            r4.font.italic = True
            r4.font.color.rgb = GRAY
            r4.font.name = "Calibri"

            for bullet in job["bullets"]:
                p3 = doc.add_paragraph(style="List Bullet")
                p3.paragraph_format.left_indent = Inches(0.2)
                p3.paragraph_format.space_after = Pt(2)
                r5 = p3.add_run(bullet)
                r5.font.size = Pt(10)
                r5.font.name = "Calibri"
                r5.font.color.rgb = DARK

            doc.add_paragraph().paragraph_format.space_after = Pt(4)

        # CORE COMPETENCIES
        self._section_header(doc, "CORE COMPETENCIES", NAVY)

        comp = content.get("core_competencies", {})
        labels = {
            "strategic": "Strategic Leadership",
            "operational": "Operational Excellence",
            "leadership": "Stakeholder & Team Leadership",
            "technology": "Technology & Innovation"
        }

        for key, label in labels.items():
            skills = comp.get(key, [])
            if skills:
                p = doc.add_paragraph()
                p.paragraph_format.space_after = Pt(3)
                r1 = p.add_run(f"{label}: ")
                r1.font.bold = True
                r1.font.size = Pt(10)
                r1.font.name = "Calibri"
                r1.font.color.rgb = NAVY
                r2 = p.add_run("  •  ".join(skills))
                r2.font.size = Pt(10)
                r2.font.name = "Calibri"
                r2.font.color.rgb = DARK

        # SAVE
        os.makedirs("output/resumes", exist_ok=True)
        safe = "".join(
            c for c in company_name if c.isalnum() or c == " "
        ).replace(" ", "_")
        ts = datetime.now().strftime("%Y%m%d_%H%M")
        path = f"output/resumes/Resume_{safe}_{ts}.docx"
        doc.save(path)
        return path

    def _section_header(self, doc, text: str, color: RGBColor):
        """Add formatted section header with bottom border."""
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(8)
        p.paragraph_format.space_after = Pt(4)

        pPr = p._p.get_or_add_pPr()
        pBdr = OxmlElement("w:pBdr")
        bottom = OxmlElement("w:bottom")
        bottom.set(qn("w:val"), "single")
        bottom.set(qn("w:sz"), "6")
        bottom.set(qn("w:space"), "1")
        bottom.set(qn("w:color"), "1B2A4A")
        pBdr.append(bottom)
        pPr.append(pBdr)

        run = p.add_run(text)
        run.font.bold = True
        run.font.size = Pt(11)
        run.font.color.rgb = color
        run.font.name = "Calibri"

    def _add_divider(self, doc, color: RGBColor):
        """Full-width divider line."""
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(2)
        p.paragraph_format.space_after = Pt(4)
        pPr = p._p.get_or_add_pPr()
        pBdr = OxmlElement("w:pBdr")
        bottom = OxmlElement("w:bottom")
        bottom.set(qn("w:val"), "single")
        bottom.set(qn("w:sz"), "12")
        bottom.set(qn("w:space"), "1")
        bottom.set(qn("w:color"), "1B2A4A")
        pBdr.append(bottom)
        pPr.append(pBdr)

    def _calc_ats_score(
        self, content: dict, jd: str
    ) -> float:
        """Estimate ATS keyword match score."""
        if not jd:
            return 0.0
        jd_lower = jd.lower()
        keywords = content.get("ats_keywords", [])
        if not keywords:
            return 0.0
        matched = sum(
            1 for kw in keywords if kw.lower() in jd_lower
        )
        return round((matched / len(keywords)) * 10, 1)
