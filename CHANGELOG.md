# Changelog

All notable changes to this project are documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [1.0.0] - 2026-10-25

First release.

### Added
- Installable package with the `fmc-setup` command (`python -m fmc_setup` also works).
- Command line options: `--workbook`, `--host`, `--username`, `--ca-cert`, `--output-dir`, `--option`.
- Credentials from environment variables (`FMC_HOST`, `FMC_USER`, `FMC_PASSWORD`, `FMC_REG_KEY`,
  `FMC_HA_SHARED_KEY`) or an interactive prompt. No credentials are stored in the code.
- Menu to build an FMC configuration from a workbook: registration of new FTD devices; physical
  interface configuration (IP, security zone, enabled); security zones; an Access Control Policy
  with categories; port, host, network and range objects and groups; access rules, with action
  `ALLOW` or `BLOCK` read from the ACP sheet; FTD High Availability pairs; EtherChannels; and
  subinterfaces.
- Device registration creates the Access Control Policy named in `ACP!A2` first if it does not
  exist yet on FMC, and polls the FMC task until the registration completes.
- Export of Access Control Policies to CSV.
- Export of the current FMC configuration to a setup workbook in the same format as the import.
  Settings the workbook cannot describe are listed in an ExportNotes sheet, and access rules the
  import would create differently are not exported.
- FMC REST client with pagination of large collections, automatic re-authentication when the access
  token expires, retry after the API rate limit, and FMC error descriptions shown for failed requests.
- Example workbook `examples/fmc-setup-template.xlsx`, unit tests and CI.
