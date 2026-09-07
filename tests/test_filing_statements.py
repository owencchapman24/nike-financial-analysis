from decimal import Decimal

import pytest

from nike_financial_analysis.filing_statements import (
    extract_statement_value,
    find_face_statement_files,
    parse_display_number,
    parse_statement_rows,
)


SUMMARY_XML = """
<FilingSummary><MyReports>
  <Report><ShortName>Consolidated Statements of Income</ShortName><HtmlFileName>R3.htm</HtmlFileName></Report>
  <Report><ShortName>Consolidated Balance Sheets</ShortName><HtmlFileName>R5.htm</HtmlFileName></Report>
  <Report><ShortName>Consolidated Statements of Cash Flows</ShortName><HtmlFileName>R7.htm</HtmlFileName></Report>
</MyReports></FilingSummary>
"""

STATEMENT_HTML = """
<table>
  <tr><th>CONSOLIDATED STATEMENTS OF CASH FLOWS</th><th>12 Months Ended</th></tr>
  <tr><th>May 31, 2026</th><th>May 31, 2025</th></tr>
  <tr><td>Additions to property, plant and equipment</td><td>($ 684)</td><td>(430)</td></tr>
</table>
"""


def test_filing_summary_maps_core_face_statements():
    assert find_face_statement_files(SUMMARY_XML) == {
        "income_statement": "R3.htm",
        "balance_sheet": "R5.htm",
        "cash_flow_statement": "R7.htm",
    }


def test_filing_summary_fails_when_a_face_statement_is_missing():
    with pytest.raises(ValueError, match="missing face statements"):
        find_face_statement_files(
            "<FilingSummary><Report><ShortName>Consolidated Balance Sheets"
            "</ShortName><HtmlFileName>R5.htm</HtmlFileName></Report></FilingSummary>"
        )


def test_statement_parser_preserves_displayed_outflow_sign():
    rows = parse_statement_rows(STATEMENT_HTML)
    label, value = extract_statement_value(
        rows,
        labels=("Additions to property, plant and equipment",),
        period_end="2026-05-31",
    )

    assert label == "Additions to property, plant and equipment"
    assert value == Decimal("-684")


@pytest.mark.parametrize(
    ("text", "expected"),
    [("$ 1,234", Decimal("1234")), ("(53)", Decimal("-53")), ("--", None)],
)
def test_display_number_parsing(text, expected):
    assert parse_display_number(text) == expected
