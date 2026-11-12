# Contributing

Issues and pull requests are welcome.

## Development setup

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

## Before opening a pull request

```bash
ruff check .
pytest
```

- Tests run against a fake FMC client (`tests/conftest.py`), no FMC is needed.
- New menu options go to `src/fmc_setup/actions.py` and are registered in `MENU` in `src/fmc_setup/cli.py`.
  If the option uses a new sheet or column, update `src/fmc_setup/layout.py`, `examples/fmc-setup-template.xlsx`,
  the configuration export in `src/fmc_setup/config_export.py` and `README.md`.
  `tests/test_config_export.py` checks that importing the template and exporting it again gives the same workbook.
- Never commit real workbooks, exports, IP addresses or credentials.
- Describe the change in `CHANGELOG.md` under an `Unreleased` section.
