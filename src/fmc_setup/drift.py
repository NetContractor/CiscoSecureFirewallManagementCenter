"""Configuration drift report - compares the setup workbook with the current FMC configuration.

Read-only: nothing is changed on FMC and the workbook itself is not modified. The report is a copy of the
workbook: rows missing on FMC are red, rows that exist only on FMC are added at the bottom in green and
cells that differ are yellow (the FMC value is in the cell comment). Only what the workbook can describe
is compared - FMC objects the export cannot represent are reported as not comparable, never as drift.
"""

import re
from datetime import datetime
from pathlib import Path

from openpyxl import load_workbook
from openpyxl.comments import Comment
from openpyxl.styles import Font, PatternFill

from fmc_setup.actions import get_acp_name
from fmc_setup.client import SetupError
from fmc_setup.config_export import (
    acp_rows,
    category_rows,
    host_network_rows,
    network_group_rows,
    port_group_rows,
    port_rows,
    security_zone_rows,
)
from fmc_setup.layout import HEADER_FILL, HEADER_FONT
from fmc_setup.workbook import cell, split_names

# sheet -> (columns, column that makes a row count, key column, compared columns as (index, label, kind))
SHEETS = {
    "SecurityZones": (1, 0, 0, ()),
    "Categories": (1, 0, 0, ()),
    "Port": (3, 0, 0, ((1, "Protocol", "text"), (2, "Port number", "text"))),
    "PortGroup": (2, 0, 0, ((1, "Port Object", "set"),)),
    "HostNetwork": (
        4, 0, 1, ((0, "ObjectType", "text"), (2, "ObjectValue", "text"), (3, "Description", "text")),
    ),
    "NetworkGroup": (2, 0, 0, ((1, "Network Objects", "set"),)),
    # The object type columns are only a lookup hint for the import, so they are not compared
    "ACP": (
        13, 1, 3,
        (
            (2, "Category", "text"), (4, "SRC Zone", "set"), (5, "DST Zone", "set"), (7, "SRC IP", "set"),
            (9, "DST IP", "set"), (11, "Service", "set"), (12, "Action", "action"),
        ),
    ),
}

MISSING_ON_FMC = "Missing on FMC"
ONLY_ON_FMC = "Missing in workbook"
DIFFERS = "Differs"
ORDER_DIFFERS = "Order differs"
NOT_COMPARABLE = "Not comparable"
SKIPPED = "Skipped"

RED = PatternFill("solid", fgColor="FFC7CE")
GREEN = PatternFill("solid", fgColor="C6EFCE")
YELLOW = PatternFill("solid", fgColor="FFEB9C")
GREY = PatternFill("solid", fgColor="D9D9D9")
STATUS_FILLS = {
    MISSING_ON_FMC: RED, ONLY_ON_FMC: GREEN, DIFFERS: YELLOW, ORDER_DIFFERS: YELLOW, NOT_COMPARABLE: GREY,
}

# Export notes meaning "this object exists on FMC but cannot be described in the workbook"
NOT_EXPORTED_NOTES = ("Rule not exported", "Interface mode", "ICMPv4 objects other than PING")


def normalize(kind, value):
    text = cell(value) or ""
    if kind == "set":
        return frozenset() if text.lower() == "any" else frozenset(split_names(text))
    if kind == "action":
        return text.upper() or "ALLOW"
    return text


def display(kind, value):
    if kind == "set":
        return ", ".join(sorted(normalize(kind, value))) or "Any"
    return normalize(kind, value) or "(empty)"


def read_rows(worksheet, width, presence, key):
    """[(worksheet row number, cleaned values)] for rows that have a value in the presence and key columns."""
    rows = []
    for number, row in enumerate(worksheet.iter_rows(min_row=2, max_col=width, values_only=True), start=2):
        values = [cell(value) for value in row] + [None] * (width - len(row))
        if values[presence] is not None and values[key] is not None:
            rows.append((number, values))
    return rows


def compare(sheet, workbook_rows, fmc_rows, not_comparable=None):
    """Differences between the workbook rows [(row number, values)] and the FMC rows [values] of one sheet.

    not_comparable maps names of FMC objects the workbook cannot describe to the reason.
    """
    _, _, key_column, fields = SHEETS[sheet]
    not_comparable = not_comparable or {}
    fmc_by_key = {cell(row[key_column]): row for row in fmc_rows}
    result = {"missing": [], "extra": [], "changed": [], "not_comparable": []}
    seen = set()
    for number, row in workbook_rows:
        key = row[key_column]
        seen.add(key)
        if key in not_comparable:
            result["not_comparable"].append((number, key, not_comparable[key]))
            continue
        fmc_row = fmc_by_key.get(key)
        if fmc_row is None:
            result["missing"].append((number, key))
            continue
        if sheet == "Port" and key == "PING":
            continue  # protocol and port are ignored for the ICMP echo object
        differences = [
            (index, label, display(kind, fmc_row[index]), display(kind, row[index]))
            for index, label, kind in fields
            if normalize(kind, row[index]) != normalize(kind, fmc_row[index])
        ]
        if differences:
            result["changed"].append((number, key, differences))
    result["extra"] = [row for row in fmc_rows if cell(row[key_column]) not in seen]
    return result


def order_difference(workbook_rows, fmc_rows):
    """Rules present in both, as (workbook order, FMC order) - None when the order is the same."""
    key = SHEETS["ACP"][2]
    in_fmc = [row[key] for row in fmc_rows]
    in_workbook_names = {row[key] for _, row in workbook_rows}

    def rule_number(item):
        number = item[1][1]
        return int(number) if number.isdigit() else float("inf")

    workbook_order = [
        row[key] for _, row in sorted(workbook_rows, key=rule_number) if row[key] in set(in_fmc)
    ]
    fmc_order = [name for name in in_fmc if name in in_workbook_names]
    return None if workbook_order == fmc_order else (workbook_order, fmc_order)


def last_used_row(worksheet, width):
    for number in range(worksheet.max_row, 1, -1):
        if any(worksheet.cell(number, column).value not in (None, "") for column in range(1, width + 1)):
            return number
    return 1


def mark_sheet(worksheet, name, result):
    """Colors the sheet and appends the rows that exist only on FMC. Returns {key: row number} of those rows."""
    width, _, key_column, _ = SHEETS[name]
    for number, _key in result["missing"]:
        for column in range(1, width + 1):
            worksheet.cell(number, column).fill = RED
    for number, _key, _note in result["not_comparable"]:
        for column in range(1, width + 1):
            worksheet.cell(number, column).fill = GREY
    for number, _key, differences in result["changed"]:
        for index, _label, fmc_value, _own_value in differences:
            target = worksheet.cell(number, index + 1)
            target.fill = YELLOW
            target.comment = Comment(f"FMC: {fmc_value}", "fmc-setup")
    added = {}
    row_number = last_used_row(worksheet, width)
    for row in result["extra"]:
        row_number += 1
        values = list(row)
        if name == "ACP":
            values[0] = None  # policy name belongs to the first row only
        for column, value in enumerate(values, start=1):
            worksheet.cell(row_number, column, value).fill = GREEN
        added[cell(row[key_column])] = row_number
    return added


def sheet_findings(name, result, added_rows):
    found = []
    for number, key in result["missing"]:
        found.append((name, key, MISSING_ON_FMC, f"Workbook row {number} is not on FMC"))
    for row in result["extra"]:
        key = cell(row[SHEETS[name][2]])
        found.append((name, key, ONLY_ON_FMC, f"On FMC, not in the workbook - added in row {added_rows[key]}"))
    for number, key, differences in result["changed"]:
        detail = "; ".join(
            f"{label}: workbook {own_value}, FMC {fmc_value}" for _index, label, fmc_value, own_value in differences
        )
        found.append((name, key, DIFFERS, f"Row {number} - {detail}"))
    for number, key, note in result["not_comparable"]:
        found.append((name, key, NOT_COMPARABLE, f"Row {number} - {note}"))
    return found


def fetch_fmc_tables(fmc, policy, notes):
    """Current FMC configuration in the rows of the setup workbook (the same functions as the export)."""
    acp = [row for row in acp_rows(fmc, policy, notes) if row[1] is not None] if policy else []
    return {
        "SecurityZones": security_zone_rows(fmc.get_all("object/securityzones"), notes),
        "Categories": category_rows(fmc, policy),
        "Port": port_rows(fmc, notes),
        "PortGroup": port_group_rows(fmc),
        "HostNetwork": host_network_rows(fmc),
        "NetworkGroup": network_group_rows(fmc, notes),
        "ACP": acp,
    }


def add_drift_sheet(book, findings, title):
    if "Drift" in book.sheetnames:
        del book["Drift"]
    sheet = book.create_sheet("Drift")
    sheet["A1"] = "Configuration drift report"
    sheet["A1"].font = Font(bold=True, size=14)
    sheet["A2"] = title
    for column, text in enumerate(("Sheet", "Object", "Status", "Detail"), start=1):
        header = sheet.cell(4, column, text)
        header.font, header.fill = HEADER_FONT, HEADER_FILL
    for row_number, finding in enumerate(findings or [("-", "-", "No drift found", "")], start=5):
        for column, value in enumerate(finding, start=1):
            sheet.cell(row_number, column, value)
        if finding[2] in STATUS_FILLS:
            sheet.cell(row_number, 3).fill = STATUS_FILLS[finding[2]]
    for letter, width in zip("ABCD", (16, 36, 22, 110)):
        sheet.column_dimensions[letter].width = width
    sheet.freeze_panes = "A5"


def drift_report(fmc, workbook, output_dir="."):
    if not workbook.path.is_file():
        raise SetupError(f"Workbook {workbook.path} does not exist")
    print("Comparing the workbook with the FMC configuration (read-only)")
    findings = []
    notes = []

    policy, policy_problem = None, None
    try:
        acp_name = get_acp_name(workbook)
    except SetupError as err:
        policy_problem = str(err)
    else:
        policy = next((item for item in fmc.get_all("policy/accesspolicies") if item["name"] == acp_name), None)
        if policy is None:
            findings.append((
                "ACP", acp_name, MISSING_ON_FMC,
                "Access Control Policy does not exist on FMC - all its rules and categories are reported as missing",
            ))

    fmc_tables = fetch_fmc_tables(fmc, policy, notes)
    not_comparable = {}
    for sheet, name, note in notes:
        if note.startswith(NOT_EXPORTED_NOTES):
            not_comparable.setdefault(sheet, {})[name] = note
        elif sheet == "ACP" and note.startswith("Default action"):
            findings.append((sheet, name, DIFFERS, note))

    report_book = load_workbook(workbook.path)
    summary = []
    for name in SHEETS:
        if name in ("ACP", "Categories") and policy_problem:
            findings.append((name, "-", SKIPPED, policy_problem))
            continue
        try:
            worksheet = workbook.sheet(name)
        except SetupError as err:
            findings.append((name, "-", SKIPPED, str(err)))
            continue
        width, presence, key_column, _ = SHEETS[name]
        workbook_rows = read_rows(worksheet, width, presence, key_column)
        result = compare(name, workbook_rows, fmc_tables[name], not_comparable.get(name))
        added_rows = mark_sheet(report_book[name], name, result)
        findings += sheet_findings(name, result, added_rows)

        in_workbook = {row[key_column] for _, row in workbook_rows}
        for key, note in not_comparable.get(name, {}).items():
            if key not in in_workbook:
                findings.append((name, key, NOT_COMPARABLE, f"On FMC only - {note}"))
        if name == "ACP":
            order = order_difference(workbook_rows, fmc_tables[name])
            if order:
                findings.append(("ACP", "-", ORDER_DIFFERS, "Workbook: " + ", ".join(order[0])
                                 + " | FMC: " + ", ".join(order[1])))
        summary.append((name, len(result["missing"]), len(result["extra"]), len(result["changed"])))

    compared_at = datetime.now()
    add_drift_sheet(
        report_book, findings,
        f"FMC {fmc.host} - {compared_at:%Y-%m-%d %H:%M} - workbook {workbook.path.name}",
    )
    host = re.sub(r"[^\w.-]", "_", fmc.host)
    path = Path(output_dir) / f"fmc-drift-{host}-{compared_at:%Y%m%d-%H%M%S}.xlsx"
    report_book.save(path)

    for name, missing, extra, changed in summary:
        print(f"{name}: {missing} missing on FMC, {extra} missing in the workbook, {changed} differ")
    for sheet, _name, status, detail in findings:
        if status == SKIPPED:
            print(f"SKIPPED: {sheet} - {detail}")
    if not any(missing or extra or changed for _name, missing, extra, changed in summary):
        print("No drift found.")
    print(f"File is at: {path}")
    return path
