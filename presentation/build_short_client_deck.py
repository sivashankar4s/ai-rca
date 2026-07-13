#!/usr/bin/env python3
"""Build a short client meeting deck in both PPTX and PDF formats.

Outputs:
- presentation/Sentinel-AI-Client-Short-Overview.pptx
- presentation/Sentinel-AI-Client-Short-Overview.pdf
"""

from __future__ import annotations

from datetime import date
from pathlib import Path


def _get_slides() -> list[dict[str, object]]:
    today = date.today().isoformat()
    return [
        {
            "title": "Sentinel AI - Client Architecture Brief",
            "subtitle": "AI-powered service health and root-cause analysis for AWS data pipelines",
            "bullets": [
                "Audience: client architects and platform leaders",
                "Scope: live capabilities, architecture fit, and measurable impact",
                f"Version date: {today}",
            ],
        },
        {
            "title": "Problem We Solve",
            "subtitle": "Current incident analysis is manual and slow",
            "bullets": [
                "Engineers manually query failures, build log queries, and inspect hundreds of lines",
                "Root cause write-up and stakeholder summary are done separately",
                "Recurring incidents are not consistently linked to prior cases",
                "Result: high mean-time-to-root-cause and high dependence on senior experts",
            ],
        },
        {
            "title": "What The Application Delivers",
            "subtitle": "Two-step workflow with guided AI analysis",
            "bullets": [
                "Step 1: Fetch FAILED records by time range and component",
                "Step 2: Analyze selected records using LLM + log backend queries",
                "Output includes grouped failure patterns, root cause, likely fix, and escalation path",
                "One-click deep-link opens the exact CloudWatch/Grafana query and window",
            ],
        },
        {
            "title": "Core Features",
            "subtitle": "Production-focused capabilities",
            "bullets": [
                "Paginated failure table with cross-page selection and bulk analyze",
                "Executive summary generated for ticket/incident communication",
                "Recurring issue detection via root-cause signature and CRM case linking",
                "Pluggable providers for data source, LLM, and log backend",
                "GitHub MCP code-change context for failures in the selected time window",
            ],
        },
        {
            "title": "Architecture Fit",
            "subtitle": "Composable design for enterprise environments",
            "bullets": [
                "Frontend SPA + FastAPI backend + provider strategy interfaces",
                "Backend isolates DataSource, LLM, and LogAnalysis with plugin registry",
                "Provider swap via configuration, without orchestration code changes",
                "Postgres persistence stores case history and recurrence signals",
            ],
        },
        {
            "title": "Business Advantages",
            "subtitle": "Why this is valuable for platform operations",
            "bullets": [
                "Faster incident diagnosis and higher on-call confidence",
                "Standardized RCA quality across teams and shifts",
                "Reduced reliance on tribal knowledge and ad-hoc runbooks",
                "Higher transparency: repeat failures become visible and actionable",
            ],
        },
        {
            "title": "Time Effect",
            "subtitle": "Indicative effort comparison per incident",
            "bullets": [
                "Manual baseline: 60-180 minutes (querying, log digging, report writing)",
                "With Sentinel AI: 2-10 minutes (fetch, analyze, review output)",
                "Estimated reduction: 85%-98% in time-to-root-cause",
                "Assumption: read-only cloud access and configured providers are available",
            ],
        },
        {
            "title": "Adoption Path",
            "subtitle": "Low-friction rollout plan",
            "bullets": [
                "Pilot with one data pipeline profile and one operations squad",
                "Track MTRC, recurrence closure rate, and false-positive trend",
                "Expand to additional services and teams after pilot baseline",
                "Roadmap: deeper automation and broader source-code intelligence",
            ],
        },
    ]


def build_pptx(slides: list[dict[str, object]], output_file: Path) -> None:
    try:
        from pptx import Presentation
        from pptx.dml.color import RGBColor
        from pptx.enum.text import PP_ALIGN
        from pptx.util import Inches, Pt
    except ImportError as exc:
        raise SystemExit("Missing dependency: python-pptx. Install with: pip install python-pptx") from exc

    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    blank = prs.slide_layouts[6]

    bg = RGBColor(10, 15, 30)
    card = RGBColor(30, 45, 71)
    border = RGBColor(42, 63, 94)
    title_color = RGBColor(232, 240, 254)
    subtitle_color = RGBColor(143, 168, 200)
    accent = RGBColor(0, 180, 216)

    for idx, slide_data in enumerate(slides, start=1):
        s = prs.slides.add_slide(blank)

        bg_rect = s.shapes.add_shape(
            1, 0, 0, prs.slide_width, prs.slide_height  # rectangle
        )
        bg_rect.fill.solid()
        bg_rect.fill.fore_color.rgb = bg
        bg_rect.line.fill.background()

        title_box = s.shapes.add_textbox(Inches(0.8), Inches(0.6), Inches(11.8), Inches(1.0))
        tf = title_box.text_frame
        tf.clear()
        p = tf.paragraphs[0]
        p.text = str(slide_data["title"])
        p.font.size = Pt(36)
        p.font.bold = True
        p.font.color.rgb = title_color

        subtitle_box = s.shapes.add_textbox(Inches(0.8), Inches(1.65), Inches(11.8), Inches(0.55))
        stf = subtitle_box.text_frame
        stf.clear()
        sp = stf.paragraphs[0]
        sp.text = str(slide_data["subtitle"])
        sp.font.size = Pt(18)
        sp.font.color.rgb = subtitle_color

        card_rect = s.shapes.add_shape(1, Inches(0.8), Inches(2.35), Inches(11.8), Inches(4.5))
        card_rect.fill.solid()
        card_rect.fill.fore_color.rgb = card
        card_rect.line.color.rgb = border

        bullets_box = s.shapes.add_textbox(Inches(1.15), Inches(2.7), Inches(11.0), Inches(3.9))
        btf = bullets_box.text_frame
        btf.word_wrap = True
        btf.clear()

        bullets = slide_data["bullets"]
        for i, bullet in enumerate(bullets):
            para = btf.paragraphs[0] if i == 0 else btf.add_paragraph()
            para.text = f"- {bullet}"
            para.font.size = Pt(20)
            para.font.color.rgb = title_color
            para.space_after = Pt(8)

        footer_box = s.shapes.add_textbox(Inches(0.8), Inches(7.0), Inches(12.0), Inches(0.3))
        ft = footer_box.text_frame
        ft.clear()
        fp = ft.paragraphs[0]
        fp.text = f"Sentinel AI | Client Short Overview | {idx}/{len(slides)}"
        fp.font.size = Pt(10)
        fp.font.color.rgb = accent
        fp.alignment = PP_ALIGN.RIGHT

    output_file.parent.mkdir(parents=True, exist_ok=True)
    prs.save(str(output_file))


def build_pdf(slides: list[dict[str, object]], output_file: Path) -> None:
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import landscape
        from reportlab.lib.units import inch
        from reportlab.pdfgen import canvas
    except ImportError as exc:
        raise SystemExit("Missing dependency: reportlab. Install with: pip install reportlab") from exc

    width, height = landscape((13.333 * 72, 7.5 * 72))
    c = canvas.Canvas(str(output_file), pagesize=(width, height))

    bg = colors.Color(10 / 255, 15 / 255, 30 / 255)
    card = colors.Color(30 / 255, 45 / 255, 71 / 255)
    border = colors.Color(42 / 255, 63 / 255, 94 / 255)
    title_color = colors.Color(232 / 255, 240 / 255, 254 / 255)
    subtitle_color = colors.Color(143 / 255, 168 / 255, 200 / 255)
    accent = colors.Color(0 / 255, 180 / 255, 216 / 255)

    for idx, slide_data in enumerate(slides, start=1):
        c.setFillColor(bg)
        c.rect(0, 0, width, height, stroke=0, fill=1)

        c.setFillColor(title_color)
        c.setFont("Helvetica-Bold", 28)
        c.drawString(0.8 * inch, height - 1.0 * inch, str(slide_data["title"]))

        c.setFillColor(subtitle_color)
        c.setFont("Helvetica", 14)
        c.drawString(0.8 * inch, height - 1.45 * inch, str(slide_data["subtitle"]))

        card_x = 0.8 * inch
        card_y = 0.65 * inch
        card_w = width - (1.6 * inch)
        card_h = height - (3.2 * inch)
        c.setFillColor(card)
        c.setStrokeColor(border)
        c.rect(card_x, card_y, card_w, card_h, stroke=1, fill=1)

        c.setFillColor(title_color)
        c.setFont("Helvetica", 14)
        y = height - 2.2 * inch
        for bullet in slide_data["bullets"]:
            c.drawString(1.1 * inch, y, f"- {bullet}")
            y -= 0.55 * inch
            if y < 1.2 * inch:
                break

        c.setFillColor(accent)
        c.setFont("Helvetica", 9)
        c.drawRightString(width - 0.8 * inch, 0.35 * inch, f"Sentinel AI | Client Short Overview | {idx}/{len(slides)}")

        c.showPage()

    output_file.parent.mkdir(parents=True, exist_ok=True)
    c.save()


def main() -> int:
    deck = _get_slides()
    out_dir = Path(__file__).resolve().parent

    pptx_path = out_dir / "Sentinel-AI-Client-Short-Overview.pptx"
    pdf_path = out_dir / "Sentinel-AI-Client-Short-Overview.pdf"

    build_pptx(deck, pptx_path)
    build_pdf(deck, pdf_path)

    print(f"Created: {pptx_path}")
    print(f"Created: {pdf_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
