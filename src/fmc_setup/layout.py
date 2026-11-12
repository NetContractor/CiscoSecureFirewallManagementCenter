"""Layout of the setup workbook - sheets, headers and formatting used when a workbook is created."""

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

NETWORK_TYPES = ("Host", "Network", "Range", "NetworkGroup")

# Table sheets: header, column widths, list validations (column, allowed values)
TABLES = {
    "ACP": (
        ["ACP name", "Rule number", "Category", "Access rule name", "SRC Zone", "DST Zone",
         "Source Network Object Type\nHost\nNetwork\nRange\nNetworkGroup", "SRC IP",
         "Destination Network Object Type\nHost\nNetwork\nRange\nNetworkGroup", "DST IP",
         "Service Object Type\nService\nServiceGroup", "Service", "Action\nALLOW\nBLOCK"],
        [16, 10, 20, 22, 24, 24, 16, 30, 16, 30, 14, 20, 12],
        [("G", NETWORK_TYPES), ("I", NETWORK_TYPES), ("K", ("Service", "ServiceGroup")), ("M", ("ALLOW", "BLOCK"))],
    ),
    "SecurityZones": (["Security Zone Name"], [30], []),
    "Categories": (["Category Name"], [30], []),
    "Port": (["Protocol Name", "Protocol", "Port number"], [32, 10, 14], [("B", ("TCP", "UDP"))]),
    "PortGroup": (["Port Group", "Port Object"], [20, 120], []),
    "HostNetwork": (
        ["ObjectType", "ObjectName", "ObjectValue", "Description"],
        [12, 24, 26, 30],
        [("A", ("Host", "Network", "Range"))],
    ),
    "NetworkGroup": (["Network Group", "Network Objects"], [20, 80], []),
    "SubInterfaces": (
        ["Port-channel", "VLAN", "NAME", "IP Address", "Netmask", "Security Zone"],
        [16, 8, 14, 16, 16, 18],
        [],
    ),
    "ExportNotes": (["Sheet", "Object", "Note"], [16, 36, 120], []),
}

# Form sheets: title in A1, labels in column A from row 2, values from column B
FORMS = {
    "HA": (
        "High Availability",
        ("HA Name", "Primary FW Name", "Secondary FW Name", "HA Link Name", "HA Interface",
         "HA Primary IP", "HA Secondary IP", "HA Subnet Mask", "HA State Link Name", "HA State Interface",
         "HA State Primary IP", "HA State Secondary IP", "HA State Subnet Mask"),
    ),
    "EtherChannel": ("EtherChannel", ("Number", "Name", "Selected Interfaces", "Security Zone")),
}

SHEET_ORDER = (
    "Readme", "ACP", "SecurityZones", "Categories", "Port", "PortGroup", "HA",
    "HostNetwork", "NetworkGroup", "EtherChannel", "SubInterfaces", "ExportNotes",
)

README = [
    ("FMC Build", None),
    ("Script version", None),
    (None, None),
    ("Sheet", "Used by menu option"),
    ("SecurityZones", "1 - Add security zones"),
    ("ACP", "2 - Add Access Control Policy (name in A2), 8 - Add access rules"),
    ("Categories", "3 - Add categories to the policy from ACP!A2"),
    ("Port", "4 - Add ports (name PING creates ICMPv4 echo object)"),
    ("PortGroup", "5 - Add port groups (comma separated port objects)"),
    ("HostNetwork", "6 - Add hosts, networks and ranges"),
    ("NetworkGroup", "7 - Add network groups (comma separated network objects)"),
    ("HA", "11 - Create FTD HA pair"),
    ("EtherChannel", "12 - Create EtherChannel on the primary firewall (HA!B3)"),
    ("SubInterfaces", "13 - Create subinterfaces on EtherChannels of the primary firewall"),
    (None, None),
    ("Notes", "Lists of objects are comma separated. 'Any' or an empty cell in ACP leaves the condition unset. "
              "ACP column M (Action) is ALLOW or BLOCK, empty defaults to ALLOW."),
]

HEADER_FONT = Font(bold=True, color="FFFFFF")
HEADER_FILL = PatternFill("solid", fgColor="1F4E78")
LABEL_FONT = Font(bold=True)
LABEL_FILL = PatternFill("solid", fgColor="DDEBF7")


def build_workbook(tables, forms, version, readme_lines=()):
    """Workbook with the given table rows {sheet: rows} and form values {sheet: [[value, ...], ...]}.

    Sheets are created in SHEET_ORDER. ExportNotes is created only when it has rows.
    """
    workbook = Workbook()
    workbook.remove(workbook.active)
    for name in SHEET_ORDER:
        if name == "Readme":
            _readme(workbook, version, readme_lines)
        elif name in FORMS:
            _form(workbook, name, forms.get(name, []))
        elif name != "ExportNotes" or tables.get(name):
            _table(workbook, name, tables.get(name, []))
    return workbook


def _readme(workbook, version, extra_lines):
    sheet = workbook.create_sheet("Readme")
    for line in README:
        sheet.append(list(line))
    sheet["B2"] = version
    for line in extra_lines:
        sheet.append([None, line])
    sheet["A1"].font = Font(bold=True, size=14)
    sheet["A4"].font = sheet["B4"].font = LABEL_FONT
    sheet.column_dimensions["A"].width = 18
    sheet.column_dimensions["B"].width = 95


def _table(workbook, name, rows):
    header, widths, validations = TABLES[name]
    sheet = workbook.create_sheet(name)
    sheet.append(header)
    for header_cell in sheet[1]:
        header_cell.font, header_cell.fill = HEADER_FONT, HEADER_FILL
        header_cell.alignment = Alignment(wrap_text=True, vertical="top")
    for row in rows:
        sheet.append(list(row))
    for column, width in enumerate(widths, start=1):
        sheet.column_dimensions[get_column_letter(column)].width = width
    sheet.freeze_panes = "A2"
    for column, values in validations:
        validation = DataValidation(type="list", formula1='"' + ",".join(values) + '"', allow_blank=True)
        validation.add(f"{column}2:{column}1000")
        sheet.add_data_validation(validation)


def _form(workbook, name, values):
    title, labels = FORMS[name]
    sheet = workbook.create_sheet(name)
    sheet["A1"] = title
    sheet["A1"].font = Font(bold=True, size=12)
    for row, label in enumerate(labels, start=2):
        label_cell = sheet.cell(row, 1, label)
        label_cell.font, label_cell.fill = LABEL_FONT, LABEL_FILL
        row_values = values[row - 2] if row - 2 < len(values) else []
        for column, value in enumerate(row_values, start=2):
            sheet.cell(row, column, value)
    sheet.column_dimensions["A"].width = 24
    for column in "BCD":
        sheet.column_dimensions[column].width = 22
