"""
Convert Word resume to PDF using LibreOffice (if available)
or generate PDF directly using reportlab as fallback.
"""

import os
import subprocess
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, cm
from reportlab.lib.colors import HexColor
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer,
    HRFlowable, ListFlowable, ListItem
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from candidate_profile import CANDIDATE


class PDFExporter:

    NAVY = HexColor("#1B2A4A")
    BLUE = HexColor("#2E86AB")
    DARK = HexColor("#1A1A2E")
    GRAY = HexColor("#555555")
    LIGHT = HexColor("#888888")

    def export_from_docx(self, docx_path: str) -> str:
        """
        Try LibreOffice conversion first.
        Falls back to reportlab rebuild.
        Returns PDF path.
        """
        pdf_path = docx_path.replace(".docx", ".pdf")

        try:
            result = subprocess.run(
                [
                    "libreoffice", "--headless",
                    "--convert-to", "pdf",
                    "--outdir", os.path.dirname(docx_path),
                    docx_path
                ],
                capture_output=True,
                timeout=30
            )
            if result.returncode == 0 and os.path.exists(pdf_path):
                return pdf_path
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        return pdf_path  # Caller checks existence and falls back

    def build_pdf_from_content(
        self, tailored_content: dict, company_name: str
    ) -> str:
        """Build PDF directly from tailored content dict."""

        os.makedirs("output/resumes", exist_ok=True)
        safe = "".join(
            c for c in company_name if c.isalnum() or c == " "
        ).replace(" ", "_")
        from datetime import datetime
        ts = datetime.now().strftime("%Y%m%d_%H%M")
        pdf_path = f"output/resumes/Resume_{safe}_{ts}.pdf"

        doc = SimpleDocTemplate(
            pdf_path,
            pagesize=A4,
            leftMargin=1.8 * cm,
            rightMargin=1.8 * cm,
            topMargin=1.5 * cm,
            bottomMargin=1.5 * cm
        )

        story = []

        name_style = ParagraphStyle(
            "CandidateName",
            fontSize=22,
            fontName="Helvetica-Bold",
            textColor=self.NAVY,
            alignment=TA_CENTER,
            spaceAfter=4
        )
        headline_style = ParagraphStyle(
            "Headline",
            fontSize=11,
            fontName="Helvetica-Oblique",
            textColor=self.BLUE,
            alignment=TA_CENTER,
            spaceAfter=4
        )
        contact_style = ParagraphStyle(
            "Contact",
            fontSize=9,
            fontName="Helvetica",
            textColor=self.GRAY,
            alignment=TA_CENTER,
            spaceAfter=10
        )
        section_style = ParagraphStyle(
            "SectionHeader",
            fontSize=11,
            fontName="Helvetica-Bold",
            textColor=self.NAVY,
            spaceBefore=10,
            spaceAfter=4
        )
        body_style = ParagraphStyle(
            "Body",
            fontSize=10,
            fontName="Helvetica",
            textColor=self.DARK,
            leading=14,
            spaceAfter=4,
            alignment=TA_JUSTIFY
        )
        job_title_style = ParagraphStyle(
            "JobTitle",
            fontSize=10.5,
            fontName="Helvetica-Bold",
            textColor=self.NAVY,
            spaceAfter=1
        )
        job_meta_style = ParagraphStyle(
            "JobMeta",
            fontSize=9,
            fontName="Helvetica-Oblique",
            textColor=self.GRAY,
            spaceAfter=4
        )
        bullet_style = ParagraphStyle(
            "BulletPoint",
            fontSize=10,
            fontName="Helvetica",
            textColor=self.DARK,
            leftIndent=15,
            bulletIndent=5,
            spaceAfter=2,
            leading=13
        )
        highlight_style = ParagraphStyle(
            "Highlight",
            fontSize=10,
            fontName="Helvetica",
            textColor=self.DARK,
            leftIndent=10,
            spaceAfter=3,
            leading=13
        )
        comp_style = ParagraphStyle(
            "Competency",
            fontSize=10,
            fontName="Helvetica",
            textColor=self.DARK,
            spaceAfter=3,
            leading=13
        )

        candidate = CANDIDATE

        # Name
        story.append(Paragraph(
            candidate["name"].upper(), name_style
        ))

        # Headline
        story.append(Paragraph(
            tailored_content["tailored_headline"], headline_style
        ))

        # Contact line
        story.append(Paragraph(
            f"{candidate['phone']}  |  {candidate['email']}  "
            f"|  {candidate['location']}  |  {candidate['linkedin']}",
            contact_style
        ))

        # Divider
        story.append(HRFlowable(
            width="100%", thickness=2,
            color=self.NAVY, spaceAfter=6
        ))

        # Executive Summary
        story.append(Paragraph("EXECUTIVE SUMMARY", section_style))
        story.append(HRFlowable(
            width="100%", thickness=0.5,
            color=self.NAVY, spaceAfter=4
        ))
        story.append(Paragraph(
            tailored_content["tailored_summary"], body_style
        ))
        story.append(Spacer(1, 4))

        # Executive Highlights
        highlights = tailored_content.get("executive_highlights", [])
        if highlights:
            story.append(Paragraph(
                "EXECUTIVE HIGHLIGHTS", section_style
            ))
            story.append(HRFlowable(
                width="100%", thickness=0.5,
                color=self.NAVY, spaceAfter=4
            ))
            for h in highlights:
                story.append(Paragraph(h, highlight_style))
            story.append(Spacer(1, 4))

        # Professional Experience
        story.append(Paragraph(
            "PROFESSIONAL EXPERIENCE", section_style
        ))
        story.append(HRFlowable(
            width="100%", thickness=0.5,
            color=self.NAVY, spaceAfter=4
        ))

        for job in tailored_content.get("tailored_experience", []):
            story.append(Paragraph(
                f"<font color='#1B2A4A'><b>{job['title'].upper()}</b></font>"
                f"   |   "
                f"<font color='#2E86AB'><b>{job['company']}</b></font>",
                job_title_style
            ))
            story.append(Paragraph(
                f"{job['location']}   |   {job['period']}",
                job_meta_style
            ))
            for bullet in job.get("bullets", []):
                story.append(Paragraph(f"• {bullet}", bullet_style))
            story.append(Spacer(1, 6))

        # Core Competencies
        story.append(Paragraph("CORE COMPETENCIES", section_style))
        story.append(HRFlowable(
            width="100%", thickness=0.5,
            color=self.NAVY, spaceAfter=4
        ))

        comp = tailored_content.get("core_competencies", {})
        labels = {
            "strategic": "Strategic Leadership",
            "operational": "Operational Excellence",
            "leadership": "Stakeholder & Team Leadership",
            "technology": "Technology & Innovation"
        }
        for key, label in labels.items():
            skills = comp.get(key, [])
            if skills:
                story.append(Paragraph(
                    f"<font color='#1B2A4A'><b>{label}:</b></font>  "
                    + "  •  ".join(skills),
                    comp_style
                ))

        doc.build(story)
        return pdf_path
