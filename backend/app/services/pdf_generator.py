"""
Enterprise-grade PDF generator.

Field resolution rules
──────────────────────
1. entity mappings  → payload[entity][attribute]
2. literal mappings → the stored literal string
3. system fields    → auto-computed (date, year, doc number)
4. unmapped fields  → flagged; never silently blank

Any field that cannot be resolved is replaced with [MISSING: FIELD_KEY]
and added to flagged_fields so the caller knows exactly what is missing.
"""
import os
import re
import uuid
import json
from datetime import date, datetime
from typing import Optional

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm, inch
from reportlab.lib import colors
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    PageTemplate,
    Paragraph,
    Spacer,
    HRFlowable,
    KeepTogether,
    Table,
    TableStyle,
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY, TA_RIGHT
from reportlab.pdfgen import canvas as pdfgen_canvas

from app.core.config import GENERATED_DIR
from app.models.mapping import FieldMapping


class GenerationError(Exception):
    pass


# ─── Field Resolution ──────────────────────────────────────────────────────────

def _resolve_system_field(attribute: str, doc_number: str) -> str:
    today = date.today()
    if attribute == "today_date":
        return today.strftime("%d %B %Y")
    if attribute == "current_year":
        return str(today.year)
    if attribute == "document_number":
        return doc_number
    return ""


def resolve_fields(
    mappings: list[FieldMapping],
    payload: dict,
    all_field_keys: list[str],
    doc_number: str,
) -> tuple[dict[str, str], list[dict]]:
    resolved: dict[str, str] = {}
    flagged: list[dict] = []
    mapping_by_key = {m.field_key: m for m in mappings}

    # field_overrides are direct field_key → value entries supplied by the user
    # at generation time. They take the highest priority.
    overrides: dict = payload.get("field_overrides") or {}

    for key in all_field_keys:
        # ── Priority 1: user-supplied override at generation time ──
        if key in overrides and str(overrides[key]).strip():
            resolved[key] = str(overrides[key]).strip()
            continue

        mapping: Optional[FieldMapping] = mapping_by_key.get(key)

        if mapping is None or mapping.mapping_type == "unmapped":
            resolved[key] = f"[MISSING: {key}]"
            flagged.append({"key": key, "reason": "No mapping defined"})
            continue

        if mapping.mapping_type == "literal":
            if mapping.literal_value:
                resolved[key] = mapping.literal_value
            else:
                resolved[key] = f"[MISSING: {key}]"
                flagged.append({"key": key, "reason": "Literal value is empty"})
            continue

        if mapping.mapping_type == "entity":
            entity = mapping.entity
            attribute = mapping.attribute
            if not entity or not attribute:
                resolved[key] = f"[MISSING: {key}]"
                flagged.append({"key": key, "reason": "Entity or attribute not set"})
                continue
            if entity == "system":
                val = _resolve_system_field(attribute, doc_number)
                resolved[key] = val if val else f"[MISSING: {key}]"
                if not val:
                    flagged.append({"key": key, "reason": f"Unknown system attribute: {attribute}"})
                continue
            entity_data = payload.get(entity)
            if not entity_data:
                resolved[key] = f"[MISSING: {key}]"
                flagged.append({"key": key, "reason": f"Entity '{entity}' not in payload"})
                continue
            val = entity_data.get(attribute)
            if val is None:
                resolved[key] = f"[MISSING: {key}]"
                flagged.append({"key": key, "reason": f"'{entity}.{attribute}' not in payload"})
            else:
                resolved[key] = str(val)

    return resolved, flagged


def fill_template_body(template_body: str, resolved: dict[str, str]) -> str:
    def replacer(match):
        key = match.group(1)
        return resolved.get(key, f"[MISSING: {key}]")
    return re.sub(r"\{\{([A-Z0-9_]+)\}\}", replacer, template_body)


# ─── Styles ────────────────────────────────────────────────────────────────────

BRAND_DARK   = colors.HexColor("#0D1B2A")   # Deep navy
BRAND_MID    = colors.HexColor("#1B4F72")   # Corporate blue
BRAND_ACCENT = colors.HexColor("#2E86AB")   # Accent blue
BRAND_LINE   = colors.HexColor("#B0BEC5")   # Subtle grey line
BRAND_LIGHT  = colors.HexColor("#F4F6F8")   # Off-white bg
TEXT_BODY    = colors.HexColor("#212121")
TEXT_MUTED   = colors.HexColor("#546E7A")


def _build_styles():
    base = getSampleStyleSheet()

    body = ParagraphStyle(
        "DocBody",
        parent=base["Normal"],
        fontName="Times-Roman",
        fontSize=10,
        leading=15,
        alignment=TA_JUSTIFY,
        textColor=TEXT_BODY,
        spaceAfter=6,
    )

    heading = ParagraphStyle(
        "DocHeading",
        parent=base["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=14,
        leading=18,
        alignment=TA_CENTER,
        spaceAfter=4,
        spaceBefore=0,
        textColor=BRAND_DARK,
    )

    subheading = ParagraphStyle(
        "DocSubHeading",
        parent=base["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=10.5,
        leading=14,
        alignment=TA_LEFT,
        spaceAfter=4,
        spaceBefore=10,
        textColor=BRAND_MID,
    )

    numbered = ParagraphStyle(
        "Numbered",
        parent=body,
        leftIndent=0,
        firstLineIndent=0,
        spaceAfter=5,
    )

    sig_label = ParagraphStyle(
        "SigLabel",
        parent=base["Normal"],
        fontName="Helvetica",
        fontSize=8.5,
        textColor=TEXT_MUTED,
        leading=12,
        spaceAfter=0,
    )

    sig_value = ParagraphStyle(
        "SigValue",
        parent=base["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9.5,
        textColor=TEXT_BODY,
        leading=13,
        spaceAfter=2,
    )

    sig_header = ParagraphStyle(
        "SigHeader",
        parent=base["Normal"],
        fontName="Helvetica-Bold",
        fontSize=10,
        textColor=BRAND_DARK,
        leading=14,
        spaceAfter=4,
    )

    agreed = ParagraphStyle(
        "Agreed",
        parent=base["Normal"],
        fontName="Helvetica-Bold",
        fontSize=10,
        textColor=BRAND_DARK,
        spaceAfter=8,
        spaceBefore=10,
    )

    return {
        "body": body,
        "heading": heading,
        "subheading": subheading,
        "numbered": numbered,
        "sig_label": sig_label,
        "sig_value": sig_value,
        "sig_header": sig_header,
        "agreed": agreed,
        "base": base,
    }


# ─── Signature Block Builder ───────────────────────────────────────────────────

def _make_signature_block(resolved: dict[str, str], styles: dict, page_width: float) -> list:
    """
    Build a professional two-column signature table that mirrors the original PDF.
    Left column = Company (the other party), Right column = Flexera.
    """
    col_w = (page_width - 5 * cm) / 2  # two equal columns with gutter

    def sig_field(label: str, value: str, missing: bool = False) -> list:
        # If it is a signature field and it is missing or empty, render a blank space for physical signing
        if label == "Authorized Signature" and (missing or not value or value.startswith("[MISSING:")):
            value = ""
            missing = False

        val_color = colors.red if missing else TEXT_BODY
        items = [
            Paragraph(f'<font color="#{val_color.hexval()[2:]}">{value}</font>', styles["sig_value"]) if missing
            else Paragraph(value, styles["sig_value"]),
            HRFlowable(width="100%", thickness=0.5, color=BRAND_LINE, spaceAfter=1),
            Paragraph(label, styles["sig_label"]),
            Spacer(1, 6),
        ]
        return items

    def _get_first(*keys: str) -> tuple[str, bool]:
        # 1. Try to find a resolved value that is NOT missing
        for k in keys:
            if k in resolved and not resolved[k].startswith("[MISSING:"):
                return resolved[k], False
        
        # 2. Check if any of the keys were actually defined in the template (but are missing)
        for k in keys:
            if k in resolved:
                return resolved[k], True
        
        # 3. If none of the keys were even defined in the template, return an empty string
        return "", False

    company_name, company_missing  = _get_first(
        "COMPANY_NAME",
        "COUNTERPARTY_COMPANY_NAME",
        "COUNTERPARTY_NAME",
        "OTHER_PARTY_COMPANY_NAME",
        "OTHER_PARTY_NAME",
        "RECIPIENT_COMPANY_NAME",
        "RECIPIENT_NAME",
        "BUYER_COMPANY_NAME",
        "CLIENT_COMPANY_NAME",
        "BUYER_NAME",
        "CLIENT_NAME",
    )
    company_sig, csig_missing      = _get_first(
        "COMPANY_SIGNATURE",
        "COUNTERPARTY_SIGNATURE",
        "COUNTERPARTY_COMPANY_SIGNATURE",
        "OTHER_PARTY_SIGNATURE",
        "RECIPIENT_SIGNATURE",
        "BUYER_SIGNATURE",
        "CLIENT_SIGNATURE",
    )
    company_signer, csn_missing    = _get_first(
        "COMPANY_SIGNER_NAME",
        "COMPANY_PRINTED_NAME",
        "COUNTERPARTY_SIGNER_NAME",
        "COUNTERPARTY_PRINTED_NAME",
        "COUNTERPARTY_SIGNATORY_NAME",
        "OTHER_PARTY_SIGNATORY_NAME",
        "OTHER_PARTY_SIGNER_NAME",
        "OTHER_PARTY_PRINTED_NAME",
        "RECIPIENT_SIGNER_NAME",
        "RECIPIENT_SIGNATORY_NAME",
        "RECIPIENT_PRINTED_NAME",
        "BUYER_SIGNER_NAME",
        "CLIENT_SIGNER_NAME",
        "BUYER_PRINTED_NAME",
        "CLIENT_PRINTED_NAME",
    )
    company_title, cst_missing     = _get_first(
        "COMPANY_SIGNER_TITLE",
        "COMPANY_TITLE",
        "COUNTERPARTY_SIGNER_TITLE",
        "COUNTERPARTY_TITLE",
        "COUNTERPARTY_SIGNATORY_TITLE",
        "OTHER_PARTY_SIGNATORY_TITLE",
        "OTHER_PARTY_SIGNER_TITLE",
        "OTHER_PARTY_TITLE",
        "RECIPIENT_SIGNER_TITLE",
        "RECIPIENT_SIGNATORY_TITLE",
        "RECIPIENT_TITLE",
        "BUYER_SIGNER_TITLE",
        "CLIENT_SIGNER_TITLE",
        "BUYER_TITLE",
        "CLIENT_TITLE",
    )
    agreement_date, date_missing   = _get_first(
        "AGREEMENT_DATE",
        "COUNTERPARTY_SIGNATURE_DATE",
        "COMPANY_SIGNATURE_DATE",
        "SIGNATURE_DATE",
        "AGREEMENT_EFFECTIVE_DATE",
        "EFFECTIVE_DATE",
        "BUYER_SIGNATURE_DATE",
        "CLIENT_SIGNATURE_DATE",
        "DATE",
    )
    company_email, ce_missing      = _get_first(
        "COMPANY_SIGNER_EMAIL",
        "COMPANY_EMAIL",
        "COUNTERPARTY_SIGNER_EMAIL",
        "COUNTERPARTY_EMAIL_ADDRESS",
        "COUNTERPARTY_EMAIL",
        "OTHER_PARTY_EMAIL_ADDRESS",
        "OTHER_PARTY_EMAIL",
        "OTHER_PARTY_SIGNER_EMAIL",
        "RECIPIENT_SIGNER_EMAIL",
        "RECIPIENT_EMAIL_ADDRESS",
        "RECIPIENT_EMAIL",
        "BUYER_SIGNER_EMAIL",
        "CLIENT_SIGNER_EMAIL",
        "BUYER_EMAIL",
        "CLIENT_EMAIL",
    )

    flexera_sig, fsig_missing    = _get_first(
        "FLEXERA_SIGNATURE",
        "FLEXERA_AUTHORIZED_SIGNATURE",
    )
    flexera_signer, fsgn_missing = _get_first(
        "FLEXERA_SIGNER_NAME",
        "FLEXERA_PRINTED_NAME",
        "FLEXERA_SIGNATORY_NAME",
        "FLEXERA_SIGNER",
        "FLEXERA_SOFTWARE_LIMITED_SIGNER_NAME",
        "FLEXERA_SOFTWARE_LLC_SIGNER_NAME",
    )
    flexera_title, fst_missing   = _get_first(
        "FLEXERA_SIGNER_TITLE",
        "FLEXERA_TITLE",
        "FLEXERA_SIGNATORY_TITLE",
        "FLEXERA_SOFTWARE_LIMITED_SIGNER_TITLE",
        "FLEXERA_SOFTWARE_LLC_SIGNER_TITLE",
    )

    # If the AI didn't extract Flexera fields separately, use known static values
    if not flexera_signer or fsgn_missing:
        flexera_signer, fsgn_missing = "Kraig Washburn", False
    if not flexera_title or fst_missing:
        flexera_title, fst_missing = "General Counsel", False

    # ── Left cell: Company (counterparty) ──
    left_items = []
    left_items += sig_field("Company", company_name if company_name else "[Company]", company_missing)
    left_items += sig_field("Authorized Signature", company_sig, csig_missing)
    left_items += sig_field("Printed Name", company_signer, csn_missing)
    left_items += sig_field("Title", company_title, cst_missing)
    left_items += sig_field("Date", agreement_date, date_missing)
    left_items += sig_field("E-Mail Address", company_email, ce_missing)

    # ── Right cell: Flexera (issuing party) ──
    right_items = []
    right_items += sig_field("Company", "Flexera", False)
    right_items += sig_field("Authorized Signature", flexera_sig, fsig_missing)
    right_items += sig_field("Printed Name", flexera_signer, fsgn_missing)
    right_items += sig_field("Title", flexera_title, fst_missing)

    left_cell  = left_items
    right_cell = right_items

    sig_table = Table(
        [[left_cell, right_cell]],
        colWidths=[col_w, col_w],
        hAlign="LEFT",
    )
    sig_table.setStyle(TableStyle([
        ("VALIGN",      (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING",  (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
        ("TOPPADDING",   (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 0),
    ]))
    return [sig_table]


# ─── Smart Text → Flowables ────────────────────────────────────────────────────

# Patterns that likely start the "AGREED" / signature section
_AGREED_RE  = re.compile(r"^AGREED\s*[:\.]?\s*$", re.IGNORECASE)
_SIGNING_RE = re.compile(r"by signing below.*agree.*bound", re.IGNORECASE)

# Numbered section headings like "1." or "8." or "1.2"
_SECTION_RE = re.compile(r"^\d+(\.\d+)*\.?\s+[A-Z]")


def _escape(text: str) -> str:
    return (
        text
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _highlight_missing(text: str) -> str:
    return re.sub(
        r"(\[MISSING: [A-Z0-9_]+\])",
        r'<font color="red"><b>\1</b></font>',
        text,
    )


def _text_to_flowables(
    filled_text: str,
    styles: dict,
    resolved: dict,
    page_width: float,
    template_name: str,
) -> list:
    flowables = []
    paragraphs = [p.strip() for p in re.split(r"\n{2,}", filled_text)]
    sig_block_inserted = False

    for para_text in paragraphs:
        if not para_text:
            continue

        lines = para_text.split("\n")
        first = lines[0].strip()

        # ── Page separator ──
        if first.startswith("--- PAGE"):
            flowables.append(Spacer(1, 0.25 * cm))
            flowables.append(HRFlowable(width="100%", thickness=0.4, color=BRAND_LINE))
            flowables.append(Spacer(1, 0.15 * cm))
            continue

        combined = " ".join(l.strip() for l in lines if l.strip())
        if not combined:
            continue

        # ── Detect "AGREED" section → inject signature block ──
        if not sig_block_inserted and (_AGREED_RE.match(first) or _SIGNING_RE.search(combined)):
            # Only keep text that appears BEFORE the "AGREED" keyword as preamble.
            # Everything after (the raw inline signature text) is discarded because
            # the proper two-column signature table will replace it.
            agreed_split = re.split(r'\bAGREED\b', combined, maxsplit=1, flags=re.IGNORECASE)
            preamble = agreed_split[0].strip()

            flowables.append(Spacer(1, 0.3 * cm))
            flowables.append(HRFlowable(width="100%", thickness=0.8, color=BRAND_MID, spaceAfter=8))
            if preamble:
                safe_preamble = _highlight_missing(_escape(preamble))
                flowables.append(Paragraph(safe_preamble, styles["body"]))
            flowables.append(Spacer(1, 0.15 * cm))
            flowables.append(Paragraph("AGREED:", styles["agreed"]))
            flowables.extend(_make_signature_block(resolved, styles, page_width))
            sig_block_inserted = True
            continue

        # ── Skip ALL content after the signature block has been inserted ──
        # The raw template body still contains the inline signature text; we discard it.
        if sig_block_inserted:
            continue

        safe = _highlight_missing(_escape(combined))

        # ── All-caps heading ──
        if combined.isupper() and len(combined) < 100:
            flowables.append(Spacer(1, 0.15 * cm))
            flowables.append(Paragraph(safe, styles["heading"]))
            continue

        # ── Numbered section ──
        if _SECTION_RE.match(combined):
            flowables.append(Paragraph(safe, styles["numbered"]))
            continue

        # ── Sub-heading ──
        if combined.endswith(":") and len(combined) < 70 and not combined[0].isdigit():
            flowables.append(Paragraph(safe, styles["subheading"]))
            continue

        # ── Default body ──
        flowables.append(Paragraph(safe, styles["body"]))

    # ── Fallback Signature Block ──
    # If the signature block was never inserted (e.g. template text truncated or "AGREED" pattern not matched),
    # always append it to the very end of the flowables list to guarantee signature capture.
    if not sig_block_inserted:
        flowables.append(Spacer(1, 0.4 * cm))
        flowables.append(HRFlowable(width="100%", thickness=0.8, color=BRAND_MID, spaceAfter=8))
        flowables.append(Paragraph("AGREED:", styles["agreed"]))
        flowables.extend(_make_signature_block(resolved, styles, page_width))

    return flowables


# ─── Page Decorators ──────────────────────────────────────────────────────────

def _make_page_decorator(template_name: str, doc_number: str, total_pages_ref: list):
    """
    Returns an onPage callback that draws the header/footer on every page.
    total_pages_ref is a one-element list so we can fill it in after build.
    """
    def _draw(canv: pdfgen_canvas.Canvas, doc):
        page_num = canv.getPageNumber()
        w, h = A4

        canv.saveState()

        # ── Header bar ──
        canv.setFillColor(BRAND_DARK)
        canv.rect(0, h - 1.4 * cm, w, 1.4 * cm, fill=1, stroke=0)

        canv.setFont("Helvetica-Bold", 9)
        canv.setFillColor(colors.white)
        canv.drawString(1.5 * cm, h - 0.95 * cm, template_name.upper())

        canv.setFont("Helvetica", 8)
        canv.setFillColor(colors.HexColor("#90CAF9"))
        canv.drawRightString(w - 1.5 * cm, h - 0.95 * cm, doc_number)

        # ── Footer ──
        canv.setStrokeColor(BRAND_LINE)
        canv.setLineWidth(0.5)
        canv.line(1.5 * cm, 1.2 * cm, w - 1.5 * cm, 1.2 * cm)

        canv.setFont("Helvetica", 7.5)
        canv.setFillColor(TEXT_MUTED)
        canv.drawString(1.5 * cm, 0.65 * cm,
                        f"Generated: {date.today().strftime('%d %B %Y')}  •  CONFIDENTIAL")
        canv.drawRightString(w - 1.5 * cm, 0.65 * cm, f"Page {page_num}")

        canv.restoreState()

    return _draw


# ─── Main Entry Point ──────────────────────────────────────────────────────────

def generate_pdf(
    template_body: str,
    template_name: str,
    mappings: list[FieldMapping],
    payload: dict,
    all_field_keys: list[str],
) -> tuple[str, str, list[dict]]:
    """
    Generate a filled enterprise-grade PDF.

    Returns:
        output_path: absolute path to generated PDF
        output_filename: filename only
        flagged: list of {key, reason} problem dicts
    """
    doc_number = f"DTE-{uuid.uuid4().hex[:8].upper()}"
    resolved, flagged = resolve_fields(mappings, payload, all_field_keys, doc_number)
    filled_text = fill_template_body(template_body, resolved)

    filename = f"{doc_number}.pdf"
    output_path = os.path.join(GENERATED_DIR, filename)

    styles = _build_styles()

    # ── Page geometry ──
    PAGE_W, PAGE_H = A4
    MARGIN_TOP    = 2.2 * cm   # room for header bar (1.4cm) + gap
    MARGIN_BOTTOM = 2.0 * cm   # room for footer
    MARGIN_SIDE   = 2.5 * cm

    frame = Frame(
        MARGIN_SIDE,
        MARGIN_BOTTOM,
        PAGE_W - 2 * MARGIN_SIDE,
        PAGE_H - MARGIN_TOP - MARGIN_BOTTOM - 0.6 * cm,
        leftPadding=0,
        rightPadding=0,
        topPadding=0,
        bottomPadding=0,
    )

    total_pages_ref = [0]
    on_page = _make_page_decorator(template_name, doc_number, total_pages_ref)

    doc = BaseDocTemplate(
        output_path,
        pagesize=A4,
        leftMargin=MARGIN_SIDE,
        rightMargin=MARGIN_SIDE,
        topMargin=MARGIN_TOP + 0.6 * cm,
        bottomMargin=MARGIN_BOTTOM,
        title=template_name,
        author="AI Document Template Engine",
    )
    doc.addPageTemplates([
        PageTemplate(id="main", frames=[frame], onPage=on_page),
    ])

    content_width = PAGE_W - 2 * MARGIN_SIDE

    story = []

    # ── Document title block ──
    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph(template_name.upper(), styles["heading"]))
    story.append(Spacer(1, 0.15 * cm))
    story.append(HRFlowable(width="100%", thickness=2, color=BRAND_ACCENT, spaceAfter=6))

    # ── Missing fields warning ──
    if flagged:
        warn_style = ParagraphStyle(
            "Warn",
            parent=styles["base"]["Normal"],
            fontName="Helvetica-Bold",
            fontSize=9,
            textColor=colors.red,
            spaceAfter=6,
        )
        story.append(Spacer(1, 0.1 * cm))
        story.append(Paragraph(
            f'<font color="red">⚠  {len(flagged)} field(s) could not be resolved — '
            f'highlighted in red below.</font>',
            warn_style,
        ))
        story.append(Spacer(1, 0.15 * cm))

    # ── Body ──
    story.extend(
        _text_to_flowables(filled_text, styles, resolved, content_width, template_name)
    )

    try:
        doc.build(story)
    except Exception as e:
        raise GenerationError(f"PDF build failed: {str(e)}") from e

    return output_path, filename, flagged