# fmc-setup

[![CI](../../actions/workflows/ci.yml/badge.svg)](../../actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.9%2B-blue)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

Configure **Cisco Secure Firewall Management Center (FMC)** from an Excel workbook through the FMC REST API.

Describe the configuration in one workbook (security zones, objects, groups, access rules, HA,
EtherChannels, subinterfaces) and push it to FMC from an interactive menu. Building a new firewall
policy then takes minutes instead of hours of clicking.

It also works the other way: option `12` reads an existing FMC and writes its configuration to a workbook
in the same format. You can use it to document a firewall, as a backup, or as a starting point for a
migration to another FMC.

## Features

| Option | Action | Workbook sheet |
|---|---|---|
| `1` | Register new FTD devices | `Devices` |
| `2` | Configure physical interfaces | `Interfaces` |
| `3` | Add security zones | `SecurityZones` |
| `4` | Add an Access Control Policy (default action: Block) | `ACP` (cell A2) |
| `5` | Add rule categories to the policy | `Categories` |
| `6` | Add port objects (`PING` creates an ICMPv4 echo object) | `Port` |
| `7` | Add port groups | `PortGroup` |
| `8` | Add host, network and range objects | `HostNetwork` |
| `9` | Add network groups | `NetworkGroup` |
| `10` | Add access rules | `ACP` |
| `11` | Export Access Control Policies to CSV | none |
| `12` | Export the current FMC configuration to a new setup workbook | all sheets |
| `13` | Create an FTD High Availability pair | `HA` |
| `14` | Create an EtherChannel on the primary firewall | `EtherChannel` |
| `15` | Create subinterfaces on EtherChannels | `SubInterfaces` |
| `16` | Exit | none |

The FMC client handles:
- pagination (collections larger than 1000 objects)
- token renewal (FMC tokens expire after 30 minutes)
- the API rate limit (120 requests per minute)

When FMC rejects a request, its error message is shown.

## Requirements

- Python 3.9 or newer
- Cisco FMC with the REST API enabled (*System > Configuration > REST API Preferences*)
- An FMC user with permissions for the changes you make. A dedicated API user is recommended,
  because FMC logs out other sessions of the same user.

## Installation

```bash
git clone https://github.com/NetContractor/CiscoSecureFirewallManagementCenter.git
cd fmc-setup
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install .
```

Without installing the package: `pip install -r requirements.txt`, then run `python -m fmc_setup` from the `src` directory.

## Quick start

1. Copy `examples/fmc-setup-template.xlsx`, for example to `fmc-setup.xlsx`, and fill it in (see [Workbook](#workbook)).
2. Run:

   ```bash
   fmc-setup --workbook fmc-setup.xlsx --host fmc.example.com --username api-user
   ```

3. Enter the password and select options from the menu. The usual order for a brand new device is
   `1` → `2` → `3` → `4` → `5` → `6` → `7` → `8` → `9` → `10`, because each step uses objects created
   by the previous ones. If the device is already registered and configured in FMC, start at `3`.

To run options without the menu, use `--option`, for example `fmc-setup -o 3 -o 8 -o 9`.

## Configuration

Settings come from command line options. If an option is not given, the environment variable is used. If neither is set, the program asks for the value.

| Option | Environment variable | Description |
|---|---|---|
| `-w`, `--workbook` | `FMC_SETUP_WORKBOOK` | Setup workbook. Default: `fmc-setup.xlsx` |
| `--host` | `FMC_HOST` | FMC address (hostname or IP) |
| `-u`, `--username` | `FMC_USER` | FMC user. Default: `admin` |
| none | `FMC_PASSWORD` | FMC password. Prompted without echo if not set (with echo outside a terminal, e.g. in an IDE console) |
| none | `FMC_REG_KEY` | FTD registration key (option 1), the same value set on the device with `configure manager add`. Prompted if not set |
| none | `FMC_HA_SHARED_KEY` | HA encryption key (option 13). Prompted if not set |
| `--ca-cert` | `FMC_CA_CERT` | CA bundle to verify the FMC certificate |
| `--output-dir` | none | Directory for CSV and workbook export. Default: current directory |
| `-o`, `--option` | none | Menu option to run. Can be repeated |

> [!WARNING]
> Without `--ca-cert` the FMC certificate is **not verified**, because FMC uses a self-signed
> certificate by default. Use `--ca-cert` outside lab networks.

## Workbook

The template [`examples/fmc-setup-template.xlsx`](examples/fmc-setup-template.xlsx) contains every sheet with example data.
The first row of every table sheet is a header.

Rules that apply to all sheets:
- Lists of objects are separated with commas.
- Spaces around values are ignored.
- The workbook is read again for every option, so you can edit it while the program is running.

### Devices
| A | B |
|---|---|
| Device name (as it will appear in FMC) | Management IP address of the FTD |

Registers each device with FMC. If the Access Control Policy named in `ACP!A2` does not exist yet
on FMC, it is created first (default action: Block) so it can be assigned at registration time.
The registration key itself is **not** a workbook column - it comes from `FMC_REG_KEY` or a prompt,
and must match what was set on the device with `configure manager add <FMC address> <key>`. The same
key is used for every device in one run; use separate runs for devices with different keys.
Registration is asynchronous - the program polls FMC until it completes or a 5 minute timeout passes.

### Interfaces
| A | B | C | D | E | F | G |
|---|---|---|---|---|---|---|
| Device name (must already be registered) | Physical interface, e.g. `GigabitEthernet0/0` | Logical name (`ifname`) | IP address | Netmask or prefix length | Security zone | `TRUE`/`FALSE`, empty defaults to `TRUE` |

Configures an existing physical interface (interfaces always exist once a device is registered -
they are updated, not created). An invalid value in column G skips the row with a warning instead
of guessing.

### SecurityZones
| A |
|---|
| Security zone name (created in routed mode) |

### ACP
Cell **A2** contains the Access Control Policy name. Every row with a rule number in column B is one access rule:

| Column | Content |
|---|---|
| A | Policy name (row 2 only) |
| B | Rule number. The row is processed only if this cell is set |
| C | Category (must exist, see option 5) |
| D | Rule name |
| E / F | Source / destination security zones |
| G / I | Source / destination object type: `Host`, `Network`, `Range`, `NetworkGroup` |
| H / J | Source / destination objects |
| K | Service type: `Service` (port or ICMP object) or `ServiceGroup` |
| L | Services |
| M | Action: `ALLOW` or `BLOCK`. Empty defaults to `ALLOW` |

Rules are created with logging at connection beginning and events sent to FMC.
`Any` or an empty cell leaves the condition unset. If any referenced object does not exist on FMC,
the rule is **skipped** and the missing objects are listed. This prevents a rule from being created wider than intended.
An action other than `ALLOW`/`BLOCK` also skips the rule, with a warning.

### Categories
| A |
|---|
| Category name (added to the mandatory section of the policy from ACP!A2) |

### Port
| A | B | C |
|---|---|---|
| Object name | `TCP` / `UDP` | Port or range, e.g. `443`, `49152-65535` |

A row named `PING` creates an ICMPv4 object (echo request), and columns B and C are ignored.

### PortGroup
| A | B |
|---|---|
| Group name | Port objects |

### HostNetwork
| A | B | C | D |
|---|---|---|---|
| `Host`, `Network` or `Range` | Object name | Value, e.g. `192.0.2.10`, `192.0.2.0/24`, `192.0.2.10-192.0.2.20` | Description (optional) |

### NetworkGroup
| A | B |
|---|---|
| Group name | Network objects or groups created in earlier rows |

### HA
Values in column B, rows 2–14:

HA name, primary FTD, secondary FTD, failover link name, failover interface, primary and secondary IP,
subnet mask, stateful link name, stateful interface, stateful primary and secondary IP, stateful subnet mask.

Both firewalls must already be registered in FMC (option 1). If the failover and stateful interfaces are the same,
one link is used for both. Before it creates the pair, the program checks that the primary firewall has no
pending changes and asks for confirmation.

### EtherChannel
Column B: row 2 EtherChannel ID, row 3 interface name (`ifname`), row 4 member interfaces
(one per column from B to the right), row 5 security zone. The EtherChannel is created on the primary firewall (`HA!B3`)
with LACP active, 1 Gbps, full duplex.

### SubInterfaces
| A | B | C | D | E | F |
|---|---|---|---|---|---|
| EtherChannel, e.g. `Port-channel1` | VLAN ID (also used as subinterface ID) | Interface name | IP address | Netmask or prefix length | Security zone |

## CSV export

Option `11` lists the Access Control Policies and exports the selected ones (or all of them) to
`<policy name>.csv`. The file has one row per rule with zones, networks, ports, URLs, applications, VLAN tags,
action, policies, logging settings, time ranges and comments. Values in one cell are separated with `;`.

## Configuration export to a workbook

Option `12` creates `fmc-export-<host>-<date>.xlsx` in the output directory. The file uses the same layout as the
template and can be imported again with options `3`–`10` and `13`–`15`.

You are asked to select the Access Control Policy, and the HA pair if FMC has more than one. If there is no
HA pair, you select the device instead. Its name goes to `HA!B3`, and its EtherChannels and subinterfaces are exported.

The workbook can describe only part of the FMC configuration. Everything it cannot describe goes to the
**ExportNotes** sheet with the reason. Nothing is silently left out.

| Not exported | Reason |
|---|---|
| Access rules with action other than `ALLOW`/`BLOCK`, disabled rules, rules with literal values or with conditions other than zones, networks and destination ports (applications, URLs, users, source ports, VLAN tags, time ranges, ...) | The import would create a different, possibly wider rule |
| Intrusion and file policies of rules | Not in the workbook. The rule is exported, the policy is listed in ExportNotes |
| System defined and inherited objects (e.g. `HTTPS`) | They already exist on every FMC |
| ICMP objects other than `PING` (echo request), FQDN objects | Not supported by the workbook |
| Literal values in network groups | Only objects are exported. The literals are listed in ExportNotes |
| Security zones in other modes than routed | The import creates routed zones |
| More than one EtherChannel, subinterfaces outside EtherChannels or without a static IPv4 address | The sheet holds one EtherChannel, and the import creates EtherChannel subinterfaces with a static IPv4 address |
| Device registration and physical interface configuration | Not described by the export; the `Devices`/`Interfaces` sheets are for initial device setup (options 1-2), not reported back |

Network groups are ordered so that nested groups come after the groups they contain.

## Development

```bash
pip install -e ".[dev]"
ruff check .
pytest
```

The tests use a fake FMC client and the example workbook, so no FMC is needed. See [CONTRIBUTING.md](CONTRIBUTING.md).

## Disclaimer

This tool makes configuration changes on FMC. Test your workbook in a lab first and review the changes in FMC
before you deploy them to devices. This project is not affiliated with or endorsed by Cisco Systems, Inc.

## License

[MIT](LICENSE) © Dominik Nowicki, NetContractor
