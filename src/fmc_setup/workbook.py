"""Reading the setup workbook."""

from pathlib import Path

from openpyxl import load_workbook

from fmc_setup.client import SetupError


class SetupWorkbook:
    """Setup workbook. Loaded again for every menu option, so it can be edited while the program runs."""

    def __init__(self, path):
        self.path = Path(path)

    def sheet(self, name):
        if not self.path.is_file():
            raise SetupError(f"Workbook {self.path} does not exist")
        workbook = load_workbook(self.path, data_only=True)
        if name not in workbook.sheetnames:
            raise SetupError(f"Sheet '{name}' does not exist in {self.path}")
        return workbook[name]


def cell(value):
    """Cell value as a stripped string, None for empty cells."""
    if value is None:
        return None
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    value = str(value).strip()
    return value or None


def data_rows(sheet, columns, key_column=0):
    """Rows (without header) with a value in key_column, as lists of `columns` cleaned values."""
    for row in sheet.iter_rows(min_row=2, max_col=columns, values_only=True):
        row = [cell(v) for v in row] + [None] * (columns - len(row))
        if row[key_column] is not None:
            yield row


def split_names(value):
    """Comma separated cell value as a list of names."""
    return [name.strip() for name in str(value).split(",") if name.strip()]
