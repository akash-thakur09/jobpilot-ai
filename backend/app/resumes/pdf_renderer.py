import io
from typing import List, Dict, Any
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    HRFlowable,
    ListFlowable,
    ListItem,
)
from backend.app.resumes.schemas import TailoredResumeContent


class ResumePdfRenderer:
    """
    Renders clean, single-column, ATS-parseable resumes using ReportLab.
    Strictly avoids multi-column layouts, graphics, or non-standard fonts.
    """

    @classmethod
    def render_to_bytes(cls, content: TailoredResumeContent) -> bytes:
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            leftMargin=40,
            rightMargin=40,
            topMargin=40,
            bottomMargin=40,
        )

        styles = getSampleStyleSheet()

        # Custom typography styles
        name_style = ParagraphStyle(
            "ResumeName",
            fontName="Helvetica-Bold",
            fontSize=18,
            leading=22,
            alignment=1,  # Centered
            textColor=colors.HexColor("#1A202C"),
        )

        contact_style = ParagraphStyle(
            "ResumeContact",
            fontName="Helvetica",
            fontSize=9,
            leading=13,
            alignment=1,  # Centered
            textColor=colors.HexColor("#4A5568"),
        )

        section_heading_style = ParagraphStyle(
            "ResumeSectionHeading",
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=15,
            textColor=colors.HexColor("#2B6CB0"),
            spaceBefore=10,
            spaceAfter=3,
        )

        body_style = ParagraphStyle(
            "ResumeBody",
            fontName="Helvetica",
            fontSize=9.5,
            leading=13.5,
            textColor=colors.HexColor("#2D3748"),
        )

        item_header_style = ParagraphStyle(
            "ResumeItemHeader",
            fontName="Helvetica-Bold",
            fontSize=10,
            leading=14,
            textColor=colors.HexColor("#1A202C"),
        )

        sub_header_style = ParagraphStyle(
            "ResumeSubHeader",
            fontName="Helvetica-Oblique",
            fontSize=9,
            leading=13,
            textColor=colors.HexColor("#4A5568"),
        )

        bullet_style = ParagraphStyle(
            "ResumeBullet",
            fontName="Helvetica",
            fontSize=9,
            leading=12.5,
            textColor=colors.HexColor("#2D3748"),
            leftIndent=12,
            firstLineIndent=-8,
        )

        story = []

        # 1. Header (Name & Contact)
        story.append(Paragraph(content.full_name, name_style))
        story.append(Spacer(1, 4))

        contact_parts = [content.email]
        if content.phone:
            contact_parts.append(content.phone)
        contact_parts.append(content.location)
        contact_str = " | ".join(contact_parts)
        story.append(Paragraph(contact_str, contact_style))

        if content.links:
            links_str = " | ".join(content.links)
            story.append(Paragraph(links_str, contact_style))

        story.append(Spacer(1, 6))
        story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#CBD5E0"), spaceAfter=8))

        # 2. Professional Summary
        story.append(Paragraph("PROFESSIONAL SUMMARY", section_heading_style))
        story.append(Paragraph(content.summary, body_style))
        story.append(Spacer(1, 6))

        # 3. Technical Skills
        if content.skills_by_category:
            story.append(Paragraph("TECHNICAL SKILLS", section_heading_style))
            for category, skills in content.skills_by_category.items():
                skills_str = f"<b>{category}:</b> " + ", ".join(skills)
                story.append(Paragraph(skills_str, body_style))
                story.append(Spacer(1, 2))
            story.append(Spacer(1, 4))

        # 4. Professional Experience
        if content.experiences:
            story.append(Paragraph("PROFESSIONAL EXPERIENCE", section_heading_style))
            for exp in content.experiences:
                loc_part = f" — {exp.location}" if exp.location else ""
                date_part = f"{exp.start_date} – {'Present' if exp.is_current else exp.end_date or 'Present'}"
                story.append(Paragraph(f"<b>{exp.role}</b>, {exp.company}{loc_part}", item_header_style))
                story.append(Paragraph(date_part, sub_header_style))
                story.append(Spacer(1, 2))

                for bullet in exp.bullet_points:
                    story.append(Paragraph(f"• {bullet}", bullet_style))
                    story.append(Spacer(1, 1.5))
                story.append(Spacer(1, 4))

        # 5. Key Projects
        if content.projects:
            story.append(Paragraph("KEY PROJECTS", section_heading_style))
            for proj in content.projects:
                tech_str = f" (<i>{', '.join(proj.technologies)}</i>)" if proj.technologies else ""
                url_str = f" — {proj.url}" if proj.url else ""
                story.append(Paragraph(f"<b>{proj.title}</b>{tech_str}{url_str}", item_header_style))
                story.append(Paragraph(proj.description, body_style))
                story.append(Spacer(1, 2))

                for bullet in proj.bullet_points:
                    story.append(Paragraph(f"• {bullet}", bullet_style))
                    story.append(Spacer(1, 1.5))
                story.append(Spacer(1, 4))

        # 6. Education
        if content.educations:
            story.append(Paragraph("EDUCATION", section_heading_style))
            for edu in content.educations:
                edu_text = f"<b>{edu.degree} in {edu.field_of_study}</b> — {edu.institution} ({edu.graduation_year})"
                story.append(Paragraph(edu_text, body_style))
                story.append(Spacer(1, 2))

        doc.build(story)
        return buffer.getvalue()
