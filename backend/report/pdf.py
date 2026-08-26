"""Render a signed PDF evidence artifact with ReportLab (pure-python, offline)."""
from __future__ import annotations

import io

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                TableStyle)


def render_pdf(report: dict, signature: dict) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=18 * mm, bottomMargin=18 * mm)
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle("Mono", fontName="Courier", fontSize=7, leading=9))
    story = []

    v = report["verdict"]
    story.append(Paragraph("SentinelWeights — Model Security Evidence Report", styles["Title"]))
    story.append(Paragraph("Zero Trust for AI Models · Demo attestation", styles["Italic"]))
    story.append(Spacer(1, 8))

    bom = report["mlbom"]
    story.append(Paragraph(f"<b>Artifact:</b> {bom.get('filename')} ({bom.get('format')})", styles["Normal"]))
    story.append(Paragraph(f"<b>SHA-256:</b> <font face='Courier' size=7>{bom.get('sha256')}</font>", styles["Normal"]))
    story.append(Spacer(1, 8))

    band_color = {"green": colors.green, "lime": colors.HexColor("#7CB342"),
                  "amber": colors.orange, "red": colors.red}.get(v["color"], colors.grey)
    verdict_tbl = Table([
        ["Risk Score", str(v["risk_score"])],
        ["Band", v["band"]],
        ["Gate", v["gate"]],
        ["Coverage / Confidence", f"{report['coverage']['confidence_pct']}%"],
    ], colWidths=[60 * mm, 100 * mm])
    verdict_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#0f172a")),
        ("TEXTCOLOR", (0, 0), (0, -1), colors.white),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.grey),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
        ("BACKGROUND", (1, 0), (1, 0), band_color),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
    ]))
    story.append(verdict_tbl)
    story.append(Spacer(1, 6))
    story.append(Paragraph(v["language"], styles["Normal"]))
    story.append(Spacer(1, 10))

    story.append(Paragraph("<b>Findings</b>", styles["Heading3"]))
    findings = report.get("findings", [])
    if findings:
        rows = [["Severity", "Code", "Message"]]
        for f in findings[:20]:
            rows.append([f.get("severity"), f.get("code"), f.get("message", "")[:70]])
        t = Table(rows, colWidths=[22 * mm, 45 * mm, 95 * mm])
        t.setStyle(TableStyle([("FONTSIZE", (0, 0), (-1, -1), 7),
                               ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e293b")),
                               ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                               ("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey)]))
        story.append(t)
    else:
        story.append(Paragraph("No findings within scan scope.", styles["Normal"]))
    story.append(Spacer(1, 10))

    story.append(Paragraph("<b>ATLAS Mapping</b>", styles["Heading3"]))
    for a in report.get("atlas_mapping", []) or [{"technique": "—", "name": "None", "note": ""}]:
        story.append(Paragraph(f"{a['technique']} — {a['name']}: {a.get('note','')}", styles["Normal"]))
    story.append(Spacer(1, 10))

    story.append(Paragraph("<b>Cryptographic Attestation</b>", styles["Heading3"]))
    story.append(Paragraph(f"Algorithm: {signature['algo']} · Key: {signature['key_id']}", styles["Normal"]))
    story.append(Paragraph(f"Report SHA-256: {signature['report_sha256']}", styles["Mono"]))
    story.append(Paragraph(f"Signature: {signature['signature_b64']}", styles["Mono"]))
    story.append(Spacer(1, 8))

    for d in report.get("disclaimers", []):
        story.append(Paragraph(f"• {d}", styles["Italic"]))
    story.append(Spacer(1, 6))
    story.append(Paragraph(signature["disclaimer"], styles["Italic"]))

    doc.build(story)
    return buf.getvalue()
