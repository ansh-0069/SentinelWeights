"""Render a signed PDF evidence artifact with ReportLab (pure-python, offline).

Visual language matches the SentinelWeights web UI: ink / forest / paper,
gate-colored verdict, sectioned evidence — not a plain table dump.
"""
from __future__ import annotations

import io
from datetime import datetime, timezone
from typing import Any
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

# Brand tokens (aligned with web/tailwind.config.js)
INK = colors.HexColor("#14110F")
INK_600 = colors.HexColor("#5C564E")
INK_400 = colors.HexColor("#8A8278")
PAPER = colors.HexColor("#F3EFE8")
PAPER_CARD = colors.HexColor("#FFFCF8")
LINE = colors.HexColor("#E6E0D6")
FOREST = colors.HexColor("#1F6F5B")
FOREST_DIM = colors.HexColor("#E7F2EE")
RUST = colors.HexColor("#B42318")
RUST_DIM = colors.HexColor("#F8E8E6")
CLAY = colors.HexColor("#C2410C")
CLAY_DIM = colors.HexColor("#F8EDE4")
BUTTER = colors.HexColor("#B07D0C")
BUTTER_DIM = colors.HexColor("#FEF6E0")
WHITE = colors.white

GATE_STYLE = {
    "APPROVE": (FOREST, FOREST_DIM),
    "APPROVE_WITH_CAVEATS": (colors.HexColor("#4D7C0F"), colors.HexColor("#F0F7E6")),
    "REVIEW": (BUTTER, BUTTER_DIM),
    "HARD_BLOCK": (RUST, RUST_DIM),
    "QUARANTINE": (CLAY, CLAY_DIM),
}

SEV_BG = {
    "CRITICAL": RUST_DIM,
    "HIGH": RUST_DIM,
    "MEDIUM": BUTTER_DIM,
    "LOW": FOREST_DIM,
    "INFO": PAPER,
}


def _esc(text: Any) -> str:
    return escape(str(text if text is not None else ""))


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "brand": ParagraphStyle(
            "Brand",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=16,
            leading=20,
            textColor=WHITE,
        ),
        "tagline": ParagraphStyle(
            "Tagline",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=8,
            leading=11,
            textColor=colors.HexColor("#C9C3B8"),
        ),
        "badge": ParagraphStyle(
            "Badge",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=7,
            leading=9,
            textColor=colors.HexColor("#D4CFC5"),
            alignment=TA_RIGHT,
        ),
        "section": ParagraphStyle(
            "Section",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=9,
            leading=12,
            textColor=INK,
            spaceBefore=2,
            spaceAfter=4,
        ),
        "body": ParagraphStyle(
            "Body",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=8.5,
            leading=12,
            textColor=INK,
        ),
        "muted": ParagraphStyle(
            "Muted",
            parent=base["Normal"],
            fontName="Helvetica-Oblique",
            fontSize=7.5,
            leading=10,
            textColor=INK_600,
        ),
        "mono": ParagraphStyle(
            "Mono",
            parent=base["Normal"],
            fontName="Courier",
            fontSize=6.5,
            leading=8.5,
            textColor=INK_600,
        ),
        "score": ParagraphStyle(
            "Score",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=28,
            leading=32,
            textColor=INK,
            alignment=TA_CENTER,
        ),
        "scoreLabel": ParagraphStyle(
            "ScoreLabel",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=7,
            leading=9,
            textColor=INK_400,
            alignment=TA_CENTER,
        ),
        "gate": ParagraphStyle(
            "Gate",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=14,
            textColor=INK,
            alignment=TA_CENTER,
        ),
        "meta": ParagraphStyle(
            "Meta",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=7.5,
            leading=10,
            textColor=INK_600,
        ),
        "cell": ParagraphStyle(
            "Cell",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=7.5,
            leading=10,
            textColor=INK,
        ),
        "cellHead": ParagraphStyle(
            "CellHead",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=7,
            leading=9,
            textColor=WHITE,
        ),
        "footer": ParagraphStyle(
            "Footer",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=7,
            leading=9,
            textColor=INK_400,
            alignment=TA_CENTER,
        ),
    }


def _header_table(styles: dict[str, ParagraphStyle]) -> Table:
    left = [
        Paragraph("SentinelWeights", styles["brand"]),
        Paragraph("Zero Trust for AI Models", styles["tagline"]),
    ]
    right = Paragraph(
        "DEMO ATTESTATION<br/>Not a production PKI signature",
        styles["badge"],
    )
    t = Table([[left, right]], colWidths=[120 * mm, 55 * mm])
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), INK),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ]
        )
    )
    return t


def _verdict_hero(report: dict, styles: dict[str, ParagraphStyle]) -> Table:
    v = report["verdict"]
    gate = v.get("gate", "—")
    fg, bg = GATE_STYLE.get(gate, (INK_600, PAPER))
    cov = report.get("coverage") or {}
    conf = cov.get("confidence_pct", "—")

    score_cell = [
        Paragraph(str(v.get("risk_score", "—")), styles["score"]),
        Paragraph("RISK SCORE", styles["scoreLabel"]),
    ]
    gate_style = ParagraphStyle(
        "GateColored",
        parent=styles["gate"],
        textColor=fg,
    )
    meta_style = ParagraphStyle(
        "GateMeta",
        parent=styles["meta"],
        alignment=TA_CENTER,
        textColor=INK_600,
    )
    gate_cell = [
        Paragraph(_esc(gate).replace("_", " "), gate_style),
        Paragraph(
            f"Band {_esc(v.get('band', '—'))} · Coverage {_esc(conf)}%",
            meta_style,
        ),
    ]
    lang = Paragraph(_esc(v.get("language", "")), styles["body"])

    inner = Table([[score_cell, gate_cell]], colWidths=[45 * mm, 130 * mm])
    inner.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("BACKGROUND", (0, 0), (0, 0), PAPER),
                ("BACKGROUND", (1, 0), (1, 0), bg),
                ("BOX", (0, 0), (-1, -1), 0.6, LINE),
                ("LINEAFTER", (0, 0), (0, 0), 0.6, LINE),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 12),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
            ]
        )
    )

    wrap = Table([[inner], [lang]], colWidths=[175 * mm])
    wrap.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 1), (0, 1), PAPER_CARD),
                ("BOX", (0, 0), (-1, -1), 0.6, LINE),
                ("LEFTPADDING", (0, 1), (0, 1), 10),
                ("RIGHTPADDING", (0, 1), (0, 1), 10),
                ("TOPPADDING", (0, 1), (0, 1), 8),
                ("BOTTOMPADDING", (0, 1), (0, 1), 8),
            ]
        )
    )
    return wrap


def _section_card(title: str, body_flowables: list, styles: dict) -> KeepTogether:
    head = Paragraph(_esc(title).upper(), styles["section"])
    rows = [[head]] + [[f] for f in body_flowables]
    t = Table(rows, colWidths=[175 * mm])
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), PAPER),
                ("BACKGROUND", (0, 1), (-1, -1), PAPER_CARD),
                ("BOX", (0, 0), (-1, -1), 0.5, LINE),
                ("LINEBELOW", (0, 0), (-1, 0), 0.5, LINE),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (0, 0), 6),
                ("BOTTOMPADDING", (0, 0), (0, 0), 4),
                ("TOPPADDING", (0, 1), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 1), (-1, -1), 4),
            ]
        )
    )
    return KeepTogether([t])


def _bom_block(report: dict, styles: dict) -> Any:
    bom = report.get("mlbom") or {}
    sha = str(bom.get("sha256") or "")
    sha_short = f"{sha[:20]}…{sha[-12:]}" if len(sha) > 36 else sha
    size = bom.get("size_bytes")
    size_s = f"{size:,} B" if isinstance(size, int) else _esc(size)
    params = bom.get("total_params")
    params_s = f"{params:,}" if isinstance(params, int) else _esc(params)

    kv = [
        ("Filename", bom.get("filename")),
        ("Format", bom.get("format")),
        ("Parameters", params_s),
        ("Tensors", bom.get("num_tensors")),
        ("Size", size_s),
        ("Weights loadable", bom.get("weights_loadable")),
        ("Policy", bom.get("policy_version")),
        ("License", bom.get("license")),
    ]
    cells = []
    for i in range(0, len(kv), 2):
        row = []
        for label, val in kv[i : i + 2]:
            row.append(
                Paragraph(
                    f"<font color='#8A8278'>{_esc(label)}</font><br/>"
                    f"<b>{_esc(val)}</b>",
                    styles["cell"],
                )
            )
        if len(row) == 1:
            row.append(Paragraph("", styles["cell"]))
        cells.append(row)

    grid = Table(cells, colWidths=[87 * mm, 87 * mm])
    grid.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    sha_p = Paragraph(f"SHA-256  <font face='Courier' size='6.5'>{_esc(sha_short)}</font>", styles["meta"])
    return _section_card("Artifact · ML-BOM", [grid, Spacer(1, 2), sha_p], styles)


def _timeline_block(report: dict, styles: dict) -> Any:
    tl = report.get("timeline") or []
    if not tl:
        return _section_card(
            "Scan timeline",
            [Paragraph("No timing data.", styles["muted"])],
            styles,
        )
    header = [
        Paragraph("Step", styles["cellHead"]),
        Paragraph("Elapsed", styles["cellHead"]),
    ]
    rows = [header]
    for step in tl:
        rows.append(
            [
                Paragraph(_esc(step.get("step")), styles["cell"]),
                Paragraph(f"{_esc(step.get('elapsed_ms', 0))} ms", styles["cell"]),
            ]
        )
    t = Table(rows, colWidths=[130 * mm, 40 * mm])
    style_cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), INK),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [PAPER_CARD, PAPER]),
        ("BOX", (0, 0), (-1, -1), 0.4, LINE),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, LINE),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
    ]
    t.setStyle(TableStyle(style_cmds))
    total = report.get("total_ms")
    extras = [t]
    if total is not None:
        extras.append(Paragraph(f"End-to-end  <b>{_esc(total)} ms</b>", styles["meta"]))
    return _section_card("Scan timeline", extras, styles)


def _findings_block(report: dict, styles: dict) -> Any:
    findings = report.get("findings") or []
    if not findings:
        return _section_card(
            "Findings",
            [Paragraph("No findings within scan scope.", styles["body"])],
            styles,
        )
    header = [
        Paragraph("Sev", styles["cellHead"]),
        Paragraph("Code", styles["cellHead"]),
        Paragraph("Message", styles["cellHead"]),
    ]
    rows = [header]
    for f in findings[:20]:
        sev = str(f.get("severity") or "INFO").upper()
        rows.append(
            [
                Paragraph(_esc(sev), styles["cell"]),
                Paragraph(_esc(f.get("code")), styles["cell"]),
                Paragraph(_esc(str(f.get("message", ""))[:120]), styles["cell"]),
            ]
        )
    t = Table(rows, colWidths=[22 * mm, 42 * mm, 106 * mm])
    cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), INK),
        ("BOX", (0, 0), (-1, -1), 0.4, LINE),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, LINE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]
    for i, f in enumerate(findings[:20], start=1):
        sev = str(f.get("severity") or "INFO").upper()
        cmds.append(("BACKGROUND", (0, i), (-1, i), SEV_BG.get(sev, PAPER_CARD)))
    t.setStyle(TableStyle(cmds))
    return _section_card("Findings", [t], styles)


def _narratives_block(report: dict, styles: dict) -> Any | None:
    narr = report.get("narratives") or []
    if not narr:
        return None
    parts = []
    for n in narr[:6]:
        title = n.get("title") or n.get("severity") or "Note"
        body = n.get("body") or n.get("text") or ""
        parts.append(
            Paragraph(
                f"<b>{_esc(title)}</b><br/>{_esc(body)}",
                styles["body"],
            )
        )
        parts.append(Spacer(1, 3))
    return _section_card("Explainability", parts[:-1] if parts else parts, styles)


def _atlas_block(report: dict, styles: dict) -> Any:
    atlas = report.get("atlas_mapping") or []
    if not atlas:
        return _section_card(
            "MITRE ATLAS",
            [Paragraph("No ATLAS techniques mapped for this scan.", styles["muted"])],
            styles,
        )
    parts = []
    for a in atlas:
        parts.append(
            Paragraph(
                f"<font color='#1F6F5B'><b>{_esc(a.get('technique'))}</b></font>"
                f"  {_esc(a.get('name'))}"
                f"<br/><font color='#5C564E'>{_esc(a.get('note', ''))}</font>",
                styles["body"],
            )
        )
    return _section_card("MITRE ATLAS", parts, styles)


def _attestation_block(signature: dict, report: dict, styles: dict) -> Any:
    parts = [
        Paragraph(
            f"Algorithm  <b>{_esc(signature.get('algo'))}</b>"
            f"  ·  Key  <b>{_esc(signature.get('key_id'))}</b>",
            styles["body"],
        ),
        Spacer(1, 3),
        Paragraph("Report SHA-256", styles["meta"]),
        Paragraph(_esc(signature.get("report_sha256")), styles["mono"]),
        Spacer(1, 3),
        Paragraph("Signature (base64)", styles["meta"]),
        Paragraph(_esc(signature.get("signature_b64")), styles["mono"]),
        Spacer(1, 6),
    ]
    for d in report.get("disclaimers") or []:
        parts.append(Paragraph(f"• {_esc(d)}", styles["muted"]))
    if signature.get("disclaimer"):
        parts.append(Spacer(1, 4))
        parts.append(Paragraph(_esc(signature["disclaimer"]), styles["muted"]))
    return _section_card("Cryptographic attestation", parts, styles)


def _draw_page(canvas, doc, *, first: bool) -> None:
    canvas.saveState()
    w, h = A4
    # Top accent rule
    canvas.setStrokeColor(FOREST)
    canvas.setLineWidth(2)
    canvas.line(14 * mm, h - 10 * mm, w - 14 * mm, h - 10 * mm)
    # Footer
    canvas.setStrokeColor(LINE)
    canvas.setLineWidth(0.5)
    canvas.line(14 * mm, 12 * mm, w - 14 * mm, 12 * mm)
    canvas.setFillColor(INK_400)
    canvas.setFont("Helvetica", 7)
    canvas.drawCentredString(
        w / 2,
        7 * mm,
        "SentinelWeights  ·  cybersecurity clearance ≠ clinical validation  ·  local demo key",
    )
    canvas.setFont("Helvetica", 7)
    canvas.drawRightString(w - 14 * mm, 7 * mm, f"{doc.page}")
    canvas.restoreState()


def render_pdf(report: dict, signature: dict) -> bytes:
    buf = io.BytesIO()
    styles = _styles()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=14 * mm,
        rightMargin=14 * mm,
        topMargin=16 * mm,
        bottomMargin=18 * mm,
        title="SentinelWeights Evidence Report",
        author="SentinelWeights",
    )

    story: list = []
    story.append(_header_table(styles))
    story.append(Spacer(1, 6))

    generated = report.get("generated_at")
    if generated:
        try:
            ts = datetime.fromtimestamp(int(generated), tz=timezone.utc).strftime(
                "%Y-%m-%d %H:%M UTC"
            )
        except (TypeError, ValueError, OSError):
            ts = str(generated)
        story.append(
            Paragraph(
                f"Model security evidence report  ·  Generated {_esc(ts)}",
                styles["meta"],
            )
        )
    story.append(Spacer(1, 6))

    story.append(_verdict_hero(report, styles))
    story.append(Spacer(1, 8))
    story.append(_bom_block(report, styles))
    story.append(Spacer(1, 6))
    story.append(_timeline_block(report, styles))
    story.append(Spacer(1, 6))
    story.append(_findings_block(report, styles))
    story.append(Spacer(1, 6))

    narr = _narratives_block(report, styles)
    if narr is not None:
        story.append(narr)
        story.append(Spacer(1, 6))

    story.append(_atlas_block(report, styles))
    story.append(Spacer(1, 6))
    story.append(_attestation_block(signature, report, styles))

    def on_first(c, d):
        _draw_page(c, d, first=True)

    def on_later(c, d):
        _draw_page(c, d, first=False)

    doc.build(story, onFirstPage=on_first, onLaterPages=on_later)
    return buf.getvalue()
