"""Report exports: safe CSV, typed XLSX cells and paginated Unicode PDF tables."""

from __future__ import annotations

import csv
import datetime as dt
import io
import zipfile
from decimal import Decimal
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

Row = dict[str, Any]

WAITER_COLUMNS = (
    ("Location", "locationName"),
    ("Waiter Name", "waiterName"),
    ("Email", "waiterEmail"),
    ("Total Orders", "totalOrders"),
    ("Working Hours", "workingHours"),
    ("Average Feedback", "avgServiceFeedback"),
    ("Minimal Feedback", "minServiceFeedback"),
    ("Delta Avg Feedback, %", "deltaAvgServiceFeedback"),
    ("Delta Orders, %", "deltaTotalOrders"),
)
LOCATION_COLUMNS = (
    ("Location", "locationName"),
    ("Total Orders", "totalOrders"),
    ("Revenue", "revenue"),
    ("Average Cuisine Feedback", "avgCuisineFeedback"),
    ("Minimal Cuisine Feedback", "minCuisineFeedback"),
    ("Delta Avg Cuisine Feedback, %", "deltaAvgCuisineFeedback"),
    ("Delta Revenue, %", "deltaRevenue"),
)
CONTENT_TYPES = {
    "csv": "text/csv",
    "excel": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "pdf": "application/pdf",
}
EXTENSIONS = {"csv": "csv", "excel": "xlsx", "pdf": "pdf"}
SUPPORTED_LOCALES = ("en", "uk", "fr", "es", "de")
# Column keys stay stable; only their presentation changes.
LABELS = {
    "locationName": ("Location", "Локація", "Établissement", "Local", "Standort"),
    "waiterName": (
        "Waiter Name",
        "Ім’я офіціанта",
        "Nom du serveur",
        "Nombre del camarero",
        "Name der Servicekraft",
    ),
    "waiterEmail": (
        "Email",
        "Електронна пошта",
        "E-mail",
        "Correo electrónico",
        "E-Mail",
    ),
    "totalOrders": (
        "Total Orders",
        "Усього замовлень",
        "Total des commandes",
        "Total de pedidos",
        "Bestellungen gesamt",
    ),
    "workingHours": (
        "Working Hours",
        "Робочі години",
        "Heures travaillées",
        "Horas trabajadas",
        "Arbeitsstunden",
    ),
    "avgServiceFeedback": (
        "Average Feedback",
        "Середня оцінка",
        "Note moyenne",
        "Valoración media",
        "Durchschnittliche Bewertung",
    ),
    "minServiceFeedback": (
        "Minimal Feedback",
        "Найнижча оцінка",
        "Note minimale",
        "Valoración mínima",
        "Niedrigste Bewertung",
    ),
    "deltaAvgServiceFeedback": (
        "Delta Avg Feedback, %",
        "Зміна середньої оцінки, %",
        "Évolution de la note moyenne, %",
        "Variación de la valoración media, %",
        "Änderung der durchschnittlichen Bewertung, %",
    ),
    "deltaTotalOrders": (
        "Delta Orders, %",
        "Зміна кількості замовлень, %",
        "Évolution des commandes, %",
        "Variación de pedidos, %",
        "Änderung der Bestellungen, %",
    ),
    "revenue": ("Revenue", "Виторг", "Chiffre d’affaires", "Ingresos", "Umsatz"),
    "avgCuisineFeedback": (
        "Average Cuisine Feedback",
        "Середня оцінка кухні",
        "Note moyenne de la cuisine",
        "Valoración media de la cocina",
        "Durchschnittliche Küchenbewertung",
    ),
    "minCuisineFeedback": (
        "Minimal Cuisine Feedback",
        "Найнижча оцінка кухні",
        "Note minimale de la cuisine",
        "Valoración mínima de la cocina",
        "Niedrigste Küchenbewertung",
    ),
    "deltaAvgCuisineFeedback": (
        "Delta Avg Cuisine Feedback, %",
        "Зміна середньої оцінки кухні, %",
        "Évolution de la note moyenne de la cuisine, %",
        "Variación de la valoración media de la cocina, %",
        "Änderung der durchschnittlichen Küchenbewertung, %",
    ),
    "deltaRevenue": (
        "Delta Revenue, %",
        "Зміна виторгу, %",
        "Évolution du chiffre d’affaires, %",
        "Variación de ingresos, %",
        "Umsatzänderung, %",
    ),
    "serviceTitle": (
        "Service Report",
        "Звіт про обслуговування",
        "Rapport de service",
        "Informe de servicio",
        "Servicebericht",
    ),
    "salesTitle": (
        "Sales Report",
        "Звіт про продажі",
        "Rapport des ventes",
        "Informe de ventas",
        "Umsatzbericht",
    ),
    "report": ("Report", "Звіт", "Rapport", "Informe", "Bericht"),
    "page": ("Page", "Сторінка", "Page", "Página", "Seite"),
    "range": (
        "{start} to {end}",
        "{start} — {end}",
        "{start} au {end}",
        "{start} a {end}",
        "{start} bis {end}",
    ),
}


def label(key: str, locale: str) -> str:
    return LABELS[key][SUPPORTED_LOCALES.index(locale)]


def columns_for(rows: list[Row], locale: str = "en") -> tuple[tuple[str, str], ...]:
    columns = WAITER_COLUMNS if rows and "waiterId" in rows[0] else LOCATION_COLUMNS
    return tuple((label(key, locale), key) for _, key in columns)


def title_for(rows: list[Row], locale: str = "en") -> str:
    return label("serviceTitle" if rows and "waiterId" in rows[0] else "salesTitle", locale)


def _cell(value: Any, locale: str = "en") -> str:
    if locale != "en" and isinstance(value, (int, float, Decimal)) and not isinstance(value, bool):
        text = f"{value:,}" if isinstance(value, int) else f"{value:,.2f}"
        group = "\u202f" if locale == "fr" else "\u00a0" if locale == "uk" else "."
        return text.replace(",", "\0").replace(".", ",").replace("\0", group)
    if isinstance(value, float):
        return f"{value:.2f}"
    return "" if value is None else str(value)


def table(rows: list[Row], locale: str = "en") -> tuple[list[str], list[list[str]]]:
    columns = columns_for(rows, locale)
    return [title for title, _ in columns], [[_cell(row.get(key), locale) for _, key in columns] for row in rows]


def _csv_cell(value: Any, locale: str = "en") -> str:
    text = _cell(value, locale)
    # Spreadsheet programs treat leading =,+,-,@ as formulas even in quoted CSV cells.
    # Only text is escaped: numeric negatives remain useful spreadsheet numbers.
    if isinstance(value, str) and text.lstrip().startswith(("=", "+", "-", "@")):
        return "'" + text
    return text


def to_csv(rows: list[Row], locale: str = "en") -> bytes:
    columns = columns_for(rows, locale)
    header = [title for title, _ in columns]
    body = [[_csv_cell(row.get(key), locale) for _, key in columns] for row in rows]
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(header)
    writer.writerows(body)
    return buffer.getvalue().encode("utf-8")


def _xlsx_cell(ref: str, value: Any) -> str:
    if isinstance(value, (int, float, Decimal)) and not isinstance(value, bool):
        style = 1 if isinstance(value, int) else 2
        return f'<c r="{ref}" s="{style}"><v>{value}</v></c>'
    return f'<c r="{ref}" t="inlineStr"><is><t>{escape(_cell(value))}</t></is></c>'


def _column_letter(index: int) -> str:
    letters = ""
    index += 1
    while index:
        index, remainder = divmod(index - 1, 26)
        letters = chr(65 + remainder) + letters
    return letters


def to_xlsx(rows: list[Row], locale: str = "en") -> bytes:
    columns = columns_for(rows, locale)
    lines = [[title for title, _ in columns]] + [[row.get(key) for _, key in columns] for row in rows]
    sheet_rows = "".join(
        f'<row r="{r + 1}">'
        + "".join(_xlsx_cell(f"{_column_letter(c)}{r + 1}", v) for c, v in enumerate(line))
        + "</row>"
        for r, line in enumerate(lines)
    )
    ns = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
    rel_ns = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    # Numeric XML values remain locale-independent. Spreadsheet apps apply these
    # number formats and their own locale separators without losing numeric types.
    language_id = {"en": "409", "uk": "422", "fr": "40C", "es": "C0A", "de": "407"}[locale]
    files = {
        "[Content_Types].xml": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/xl/workbook.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
            '<Override PartName="/xl/worksheets/sheet1.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
            "</Types>"
        ),
        "_rels/.rels": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            f'<Relationship Id="rId1" Type="{rel_ns}/officeDocument" Target="xl/workbook.xml"/>'
            "</Relationships>"
        ),
        "xl/workbook.xml": (
            f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><workbook {ns} xmlns:r="{rel_ns}">'
            f'<sheets><sheet name="{label("report", locale)}" sheetId="1" r:id="rId1"/></sheets></workbook>'
        ),
        "xl/_rels/workbook.xml.rels": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            f'<Relationship Id="rId1" Type="{rel_ns}/worksheet" Target="worksheets/sheet1.xml"/>'
            f'<Relationship Id="rId2" Type="{rel_ns}/styles" Target="styles.xml"/>'
            "</Relationships>"
        ),
        "xl/worksheets/sheet1.xml": (
            f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><worksheet {ns}>'
            f"<sheetData>{sheet_rows}</sheetData></worksheet>"
        ),
        "xl/styles.xml": (
            f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><styleSheet {ns}>'
            f'<numFmts count="2"><numFmt numFmtId="164" formatCode="[$-{language_id}]#,##0"/>'
            f'<numFmt numFmtId="165" formatCode="[$-{language_id}]#,##0.00"/></numFmts>'
            '<fonts count="1"><font><sz val="11"/><name val="Calibri"/></font></fonts>'
            '<fills count="2"><fill><patternFill patternType="none"/></fill>'
            '<fill><patternFill patternType="gray125"/></fill></fills>'
            '<borders count="1"><border/></borders>'
            '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
            '<cellXfs count="3"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>'
            '<xf numFmtId="164" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/>'
            '<xf numFmtId="165" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/></cellXfs>'
            '<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles></styleSheet>'
        ),
    }
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return buffer.getvalue()


def to_pdf(rows: list[Row], subtitle: str, locale: str = "en") -> bytes:
    """Landscape A4 report; cells wrap and rows can continue onto subsequent pages.

    Noto Sans is bundled with its OFL license, so Lambda/container/desktop exports
    use the same font and preserve Ukrainian text without platform font discovery.
    """
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import (
        LongTable,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        TableStyle,
    )

    font_name = "RestaurantNotoSans"
    if font_name not in pdfmetrics.getRegisteredFontNames():
        font_path = Path(__file__).with_name("fonts") / "NotoSans-Regular.ttf"
        pdfmetrics.registerFont(TTFont(font_name, str(font_path)))
    header, body = table(rows, locale)
    width, height = landscape(A4)
    margin = 30
    available_width = width - 2 * margin
    style = ParagraphStyle("Cell", fontName=font_name, fontSize=8, leading=11, splitLongWords=True)
    title_style = ParagraphStyle("Title", parent=style, fontSize=15, leading=20, spaceAfter=8)
    header_style = ParagraphStyle("Header", parent=style, textColor=colors.white)

    def paragraph(value: str, cell_style: Any = style) -> Any:
        # User text is content, never ReportLab paragraph markup.
        return Paragraph(escape(value).replace("\n", "<br/>"), cell_style)

    data = [[paragraph(label, header_style) for label in header]]
    data.extend([paragraph(cell) for cell in row] for row in body)
    # Give names/addresses room while leaving numeric columns readable.
    weights = (
        [1.8, 1.4, 1.8, 0.8, 0.9, 1, 1, 1, 1] if rows and "waiterId" in rows[0] else [2.2, 1, 1.2, 1.2, 1.2, 1.1, 1.1]
    )
    table_widths = [available_width * weight / sum(weights) for weight in weights]
    report_table = LongTable(data, colWidths=table_widths, repeatRows=1, splitByRow=1, splitInRow=1)
    report_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0F7A37")),
                (
                    "ROWBACKGROUNDS",
                    (0, 1),
                    (-1, -1),
                    [colors.white, colors.HexColor("#F0FAF2")],
                ),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("LINEBELOW", (0, 0), (-1, -1), 0.3, colors.HexColor("#DADADA")),
            ]
        )
    )
    buffer = io.BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=(width, height),
        leftMargin=margin,
        rightMargin=margin,
        topMargin=margin,
        bottomMargin=margin,
        title=f"{title_for(rows, locale)} {subtitle}",
        author="Green & Tasty",
        pageCompression=1,
    )

    def page_number(canvas: Any, doc: Any) -> None:
        canvas.saveState()
        canvas.setFont(font_name, 8)
        canvas.drawRightString(width - margin, 15, f"{label('page', locale)} {doc.page}")
        canvas.restoreState()

    document.build(
        [
            paragraph(f"{title_for(rows, locale)} {subtitle}", title_style),
            Spacer(1, 8),
            report_table,
        ],
        onFirstPage=page_number,
        onLaterPages=page_number,
    )
    return buffer.getvalue()


def render(
    rows: list[Row],
    file_format: str,
    start_date: str,
    end_date: str,
    locale: str = "en",
) -> tuple[bytes, str, str]:
    """``(content, file name, content type)`` for ``csv`` / ``excel`` / ``pdf``."""
    fmt = file_format if file_format in CONTENT_TYPES else "csv"
    if fmt == "excel":
        content = to_xlsx(rows, locale)
    elif fmt == "pdf":
        date_format = "%Y-%m-%d" if locale == "en" else "%d/%m/%Y" if locale in ("fr", "es") else "%d.%m.%Y"
        subtitle = label("range", locale).format(
            start=dt.date.fromisoformat(start_date).strftime(date_format),
            end=dt.date.fromisoformat(end_date).strftime(date_format),
        )
        content = to_pdf(rows, f"({subtitle})", locale)
    else:
        content = to_csv(rows, locale)
    return (
        content,
        f"report_{start_date}-{end_date}.{EXTENSIONS[fmt]}",
        CONTENT_TYPES[fmt],
    )
