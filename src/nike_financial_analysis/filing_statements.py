"""Helpers for SEC-rendered face-statement evidence."""

from __future__ import annotations

from html.parser import HTMLParser
from decimal import Decimal, InvalidOperation
import re
from xml.etree import ElementTree


class _StatementTableParser(HTMLParser):
    """Collect visible cell text from SEC-rendered statement tables."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: list[list[str]] = []
        self._row: list[str] | None = None
        self._cell_parts: list[str] | None = None

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        del attrs
        if tag.casefold() == "tr":
            self._row = []
        elif tag.casefold() in {"td", "th"} and self._row is not None:
            self._cell_parts = []

    def handle_data(self, data: str) -> None:
        if self._cell_parts is not None:
            self._cell_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        normalized = tag.casefold()
        if normalized in {"td", "th"} and self._cell_parts is not None:
            text = re.sub(r"\s+", " ", " ".join(self._cell_parts)).strip()
            if self._row is not None:
                self._row.append(text)
            self._cell_parts = None
        elif normalized == "tr" and self._row is not None:
            if any(self._row):
                self.rows.append(self._row)
            self._row = None
            self._cell_parts = None


def parse_statement_rows(html: str) -> list[list[str]]:
    """Return visible rows and cells from one SEC-rendered statement file."""

    parser = _StatementTableParser()
    parser.feed(html)
    parser.close()
    return parser.rows


def parse_display_number(value: str) -> Decimal | None:
    """Parse one SEC-rendered numeric cell while retaining its displayed sign."""

    text = value.strip().replace("$", "").replace(",", "").replace("\u2212", "-")
    if not text or text in {"-", "--", "\u2014"}:
        return None
    negative = text.startswith("(") and text.endswith(")")
    if negative:
        text = text[1:-1].strip()
    try:
        number = Decimal(text)
    except InvalidOperation:
        return None
    return -number if negative else number


def extract_statement_value(
    rows: list[list[str]],
    *,
    labels: tuple[str, ...],
    period_end: str,
) -> tuple[str, Decimal] | None:
    """Find an exact face-statement label and period value in USD millions."""

    year = period_end[:4]
    period_pattern = re.compile(rf"May\s+31,\s*{re.escape(year)}", re.IGNORECASE)
    period_labels: list[str] = []
    for row in rows[:4]:
        for cell in row:
            if re.search(r"May\s+31,\s*\d{4}", cell, re.IGNORECASE):
                period_labels.append(cell)
    column_index = next(
        (index for index, label in enumerate(period_labels) if period_pattern.search(label)),
        None,
    )
    if column_index is None:
        return None

    normalized_labels = {label.casefold(): label for label in labels}
    for row in rows:
        if not row or row[0].strip().casefold() not in normalized_labels:
            continue
        value_index = column_index + 1
        if value_index >= len(row):
            continue
        number = parse_display_number(row[value_index])
        if number is not None:
            return row[0].strip(), number
    return None


def find_face_statement_files(summary_xml: str) -> dict[str, str]:
    """Map the three core face statements to rendered SEC HTML filenames."""

    try:
        root = ElementTree.fromstring(summary_xml)
    except ElementTree.ParseError as exc:
        raise ValueError("SEC FilingSummary XML could not be parsed.") from exc

    targets = {
        "income_statement": "consolidated statements of income",
        "balance_sheet": "consolidated balance sheets",
        "cash_flow_statement": "consolidated statements of cash flows",
    }
    found: dict[str, str] = {}
    for report in root.findall(".//Report"):
        short_name = (report.findtext("ShortName") or "").strip().casefold()
        long_name = (report.findtext("LongName") or "").strip().casefold()
        file_name = (report.findtext("HtmlFileName") or "").strip()
        for statement_type, target in targets.items():
            if short_name == target or long_name.endswith(f"statement - {target}"):
                found[statement_type] = file_name

    missing = set(targets).difference(found)
    if missing:
        raise ValueError(
            "SEC FilingSummary is missing face statements: "
            + ", ".join(sorted(missing))
        )
    return found
