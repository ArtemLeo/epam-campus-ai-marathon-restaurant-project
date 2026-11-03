"""Exports keep real names and complete long text, and CSV text cannot execute formulas."""

from __future__ import annotations

import csv
import io
import sys
import unittest
import zipfile
from pathlib import Path
from xml.etree import ElementTree

from pypdf import PdfReader

API_HANDLER = Path(__file__).resolve().parents[1] / "src" / "lambdas" / "api_handler"
if str(API_HANDLER) not in sys.path:
    sys.path.insert(0, str(API_HANDLER))

from services import report_files  # noqa: E402


class ReportFilesTests(unittest.TestCase):
    def test_localized_exports_preserve_numbers_names_and_formula_protection(
        self,
    ) -> None:
        rows = [{"locationName": "=Original name", "totalOrders": 1234, "revenue": 1234.5}]
        labels = {
            "en": "Location",
            "uk": "Локація",
            "fr": "Établissement",
            "es": "Local",
            "de": "Standort",
        }
        values = {
            "en": "1234.50",
            "uk": "1\u00a0234,50",
            "fr": "1\u202f234,50",
            "es": "1.234,50",
            "de": "1.234,50",
        }
        ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
        for locale in report_files.SUPPORTED_LOCALES:
            with self.subTest(locale=locale):
                csv_rows = list(csv.reader(io.StringIO(report_files.to_csv(rows, locale).decode())))
                self.assertEqual(labels[locale], csv_rows[0][0])
                self.assertEqual("'=Original name", csv_rows[1][0])
                self.assertEqual(values[locale], csv_rows[1][2])
                xlsx = report_files.to_xlsx(rows, locale)
                with zipfile.ZipFile(io.BytesIO(xlsx)) as archive:
                    sheet = ElementTree.fromstring(archive.read("xl/worksheets/sheet1.xml"))
                    style = ElementTree.fromstring(archive.read("xl/styles.xml"))
                cells = {cell.attrib["r"]: cell for cell in sheet.findall(".//m:c", ns)}
                self.assertEqual(labels[locale], cells["A1"].find("m:is/m:t", ns).text)
                self.assertEqual("1234.5", cells["C2"].find("m:v", ns).text)
                self.assertNotIn("t", cells["C2"].attrib)
                self.assertEqual("2", cells["C2"].attrib["s"])
                self.assertIsNotNone(style.find("m:numFmts", ns))

    def test_pdf_translates_headers_dates_and_page_labels_in_all_languages(
        self,
    ) -> None:
        expected = {
            "en": ("Sales Report", "2026-10-01", "Page 1"),
            "uk": ("Звіт про продажі", "01.10.2026", "Сторінка 1"),
            "fr": ("Rapport des ventes", "01/10/2026", "Page 1"),
            "es": ("Informe de ventas", "01/10/2026", "Página 1"),
            "de": ("Umsatzbericht", "01.10.2026", "Seite 1"),
        }
        rows = [{"locationName": "Original location", "revenue": 12.5}]
        for locale, strings in expected.items():
            with self.subTest(locale=locale):
                content, name, mime = report_files.render(rows, "pdf", "2026-10-01", "2026-10-31", locale)
                text = " ".join(page.extract_text() for page in PdfReader(io.BytesIO(content)).pages)
                for value in strings:
                    self.assertIn(value, text)
                self.assertIn("Original location", text)
                self.assertEqual("report_2026-10-01-2026-10-31.pdf", name)
                self.assertEqual("application/pdf", mime)

    def test_pdf_preserves_ukrainian_text_and_wraps_long_rows_across_pages(
        self,
    ) -> None:
        # One row is deliberately taller than a page; it must split, not truncate or raise LayoutError.
        location = "Ресторан «Зелений гай» — Львів " + "довгий опис локації " * 140 + "КІНЕЦЬАДРЕСИ"
        rows = [
            {
                "locationName": location,
                "waiterId": "waiter-1",
                "waiterName": "Олена Їжак",
                "waiterEmail": "long.email.address+test@example.restaurant",
                "totalOrders": 12,
                "workingHours": 8.5,
                "avgServiceFeedback": 4.75,
                "minServiceFeedback": 4,
                "deltaAvgServiceFeedback": -3.25,
                "deltaTotalOrders": 20,
            }
        ]
        pdf = report_files.to_pdf(rows, "2026-10-01 — 2026-10-31")
        reader = PdfReader(io.BytesIO(pdf))
        text = "\n".join(page.extract_text() for page in reader.pages)
        compact = "".join(text.split())
        self.assertGreater(len(reader.pages), 1)
        self.assertIn("ОленаЇжак", compact)
        self.assertIn("КІНЕЦЬАДРЕСИ", compact)
        for word in ("довгий", "опис", "локації"):
            self.assertEqual(140, compact.count(word))
        self.assertNotIn("?", text)
        for page in reader.pages:
            self.assertIn("Location", page.extract_text())

    def test_pdf_treats_markup_as_text(self) -> None:
        pdf = report_files.to_pdf([{"locationName": "<b>Київ & Львів</b>", "revenue": 120}], "Period")
        text = "".join(PdfReader(io.BytesIO(pdf)).pages[0].extract_text().split())
        self.assertIn("<b>Київ&Львів</b>", text)

    def test_csv_escapes_formula_text_but_keeps_negative_numbers_numeric(self) -> None:
        for value in (
            '=HYPERLINK("https://example.test")',
            "+SUM(1,2)",
            "-1+1",
            "@SUM(A1:A2)",
            "\t=1+1",
            "\r\n=1+1",
        ):
            with self.subTest(value=value):
                content = report_files.to_csv([{"locationName": value, "revenue": -12.5}]).decode()
                rows = list(csv.reader(io.StringIO(content)))
                self.assertEqual("'" + value, rows[1][0])
                self.assertEqual("-12.50", rows[1][2])

    def test_xlsx_keeps_user_text_as_strings_without_formulas(self) -> None:
        content = report_files.to_xlsx([{"locationName": "=1+1", "revenue": -12.5}])
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            sheet = archive.read("xl/worksheets/sheet1.xml").decode()
        self.assertIn("<t>=1+1</t>", sheet)
        self.assertIn("<v>-12.5</v>", sheet)
        self.assertNotIn("<f>", sheet)
