# Security Policy

## Reporting a vulnerability

Please do not open a public issue for security problems. Use
[GitHub private vulnerability reporting](../../security/advisories/new) for this repository instead.

## Using the tool safely

- Do not store FMC credentials in files that are committed. Use the interactive prompt or
  environment variables (`FMC_PASSWORD`, `FMC_REG_KEY`, `FMC_HA_SHARED_KEY`).
- Use a dedicated FMC API user with the minimum role required for the changes you make.
- Verify the FMC certificate with `--ca-cert` whenever possible.
- Setup workbooks and CSV exports contain network details. Keep them out of public repositories
  (`.gitignore` excludes `*.xlsx`, `*.csv` and `*.json` except the example template).
- Test the workbook against a lab FMC before running it in production.
