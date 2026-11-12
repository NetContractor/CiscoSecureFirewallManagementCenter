"""Export of the current FMC configuration to a setup workbook - the reverse of options 0-7 and 22-24.

Only settings the workbook can describe are exported. Everything else is listed in the ExportNotes sheet.
Access rules that would be created differently by the import (other action, disabled, extra conditions,
literal values) are not exported at all, so importing the file never creates a wider rule.
"""

import re
from datetime import datetime
from pathlib import Path

from fmc_setup import __version__, layout
from fmc_setup.workbook import cell

RULE_CONDITIONS = {
    "sourceZones": {"SecurityZone"},
    "destinationZones": {"SecurityZone"},
    "sourceNetworks": {"Host", "Network", "Range", "NetworkGroup"},
    "destinationNetworks": {"Host", "Network", "Range", "NetworkGroup"},
    "destinationPorts": {"ProtocolPortObject", "ICMPV4Object", "PortObjectGroup"},
}
# Rule fields that are not conditions and can be ignored
IGNORED_RULE_FIELDS = {"metadata", "links", "commentHistoryList", "newComments"}
UNDEFINED_CATEGORY = "--Undefined--"


def is_user_defined(obj):
    """False for system defined objects and objects inherited from other domains."""
    read_only = obj.get("metadata", {}).get("readOnly")
    if isinstance(read_only, dict):
        return not read_only.get("state")
    return not read_only


def choose(items, what):
    """Lets the user select one item. Returns None for an empty list."""
    if len(items) <= 1:
        return items[0] if items else None
    print(f"{what} available on FMC:")
    for number, item in enumerate(items, start=1):
        print(f"\t{number}. {item['name']}")
    while True:
        answer = input(f"Select {what} (number or name): ").strip()
        if answer.isdigit() and 1 <= int(answer) <= len(items):
            return items[int(answer) - 1]
        for item in items:
            if item["name"] == answer:
                return item
        print("Incorrect selection. Please try again.")


def export_configuration(fmc, workbook, output_dir="."):
    print("Exporting FMC configuration to the xlsx")
    notes = []
    zones = fmc.get_all("object/securityzones")
    zone_names = {zone["id"]: zone["name"] for zone in zones}
    policy = choose(fmc.get_all("policy/accesspolicies"), "Access Control Policy")
    ha_values, device = ha_form(fmc, notes)
    etherchannel_values, etherchannels = etherchannel_form(fmc, device, zone_names, notes)

    tables = {
        "ACP": acp_rows(fmc, policy, notes),
        "SecurityZones": security_zone_rows(zones, notes),
        "Categories": category_rows(fmc, policy),
        "Port": port_rows(fmc, notes),
        "PortGroup": port_group_rows(fmc),
        "HostNetwork": host_network_rows(fmc),
        "NetworkGroup": network_group_rows(fmc, notes),
        "SubInterfaces": subinterface_rows(fmc, device, etherchannels, zone_names, notes),
        "ExportNotes": notes,
    }
    forms = {"HA": ha_values, "EtherChannel": etherchannel_values}

    exported_at = datetime.now()
    result = layout.build_workbook(
        tables, forms, __version__,
        readme_lines=[f"Exported from FMC {fmc.host} on {exported_at:%Y-%m-%d %H:%M}"],
    )
    host = re.sub(r"[^\w.-]", "_", fmc.host)
    path = Path(output_dir) / f"fmc-export-{host}-{exported_at:%Y%m%d-%H%M%S}.xlsx"
    result.save(path)

    for sheet, name, note in notes:
        print(f"NOTE: {sheet} - {name}: {note}")
    for sheet in ("ACP", "SecurityZones", "Categories", "Port", "PortGroup", "HostNetwork", "NetworkGroup",
                  "SubInterfaces"):
        count = sum(1 for row in tables[sheet] if row[1 if sheet == "ACP" else 0] is not None)
        print(f"{sheet}: {count} exported")
    if notes:
        print(f"{len(notes)} notes - see sheet ExportNotes.")
    print(f"File is at: {path}")
    return path


def acp_rows(fmc, policy, notes):
    if policy is None:
        notes.append(["ACP", "-", "No Access Control Policy on FMC"])
        return []
    default_action = policy.get("defaultAction", {}).get("action")
    if default_action not in (None, "BLOCK"):
        notes.append(["ACP", policy["name"], f"Default action is {default_action}, import creates BLOCK"])

    rows = []
    rules = fmc.get_all(f"policy/accesspolicies/{policy['id']}/accessrules")
    for number, rule in enumerate(rules, start=1):
        problems = unsupported_rule_settings(rule)
        if problems:
            notes.append(["ACP", rule["name"], "Rule not exported - " + "; ".join(problems)])
            continue
        for field, label in (("ipsPolicy", "Intrusion policy"), ("filePolicy", "File policy")):
            if rule.get(field):
                notes.append(["ACP", rule["name"], f"{label} {rule[field].get('name')} is not exported"])

        category = rule.get("metadata", {}).get("category")
        src = rule.get("sourceNetworks", {}).get("objects", [])
        dst = rule.get("destinationNetworks", {}).get("objects", [])
        services = rule.get("destinationPorts", {}).get("objects", [])
        rows.append([
            None, number, None if category in (None, "", UNDEFINED_CATEGORY) else category, rule["name"],
            names(rule.get("sourceZones", {}).get("objects", [])),
            names(rule.get("destinationZones", {}).get("objects", [])),
            network_type(src), names(src),
            network_type(dst), names(dst),
            service_type(services), names(services),
            rule.get("action"),
        ])
    if rows:
        rows[0][0] = policy["name"]
    else:
        rows.append([policy["name"]] + [None] * 12)
    return rows


def unsupported_rule_settings(rule):
    """Settings of an access rule that the workbook cannot describe."""
    problems = []
    if rule.get("action") not in ("ALLOW", "BLOCK"):
        problems.append(f"action {rule.get('action')}")
    if rule.get("enabled") is False:
        problems.append("rule is disabled")
    for field, allowed_types in RULE_CONDITIONS.items():
        condition = rule.get(field) or {}
        if condition.get("literals"):
            problems.append(f"literal values in {field}")
        other_types = sorted({obj.get("type", "?") for obj in condition.get("objects", [])} - allowed_types)
        if other_types:
            problems.append(f"{field} objects of type {', '.join(other_types)}")
    for field, value in rule.items():
        if field in RULE_CONDITIONS or field in IGNORED_RULE_FIELDS:
            continue
        # Conditions are lists or objects containing lists (sourcePorts, applications, urls, users, ...)
        if (isinstance(value, list) and value) or (
            isinstance(value, dict) and any(isinstance(v, list) and v for v in value.values())
        ):
            problems.append(f"{field} condition")
    return problems


def names(objects):
    return ",".join(obj["name"] for obj in objects) if objects else "Any"


def network_type(objects):
    if not objects:
        return None
    if any(obj["type"] == "NetworkGroup" for obj in objects):
        return "NetworkGroup"
    return objects[0]["type"]


def service_type(objects):
    if not objects:
        return None
    return "ServiceGroup" if any(obj["type"] == "PortObjectGroup" for obj in objects) else "Service"


def security_zone_rows(zones, notes):
    rows = []
    for zone in zones:
        mode = zone.get("interfaceMode")
        if mode not in (None, "ROUTED"):
            notes.append(["SecurityZones", zone["name"], f"Interface mode {mode} - import creates ROUTED zones only"])
            continue
        rows.append([zone["name"]])
    return rows


def category_rows(fmc, policy):
    if policy is None:
        return []
    categories = fmc.get_all(f"policy/accesspolicies/{policy['id']}/categories")
    return [[category["name"]] for category in categories if category["name"] != UNDEFINED_CATEGORY]


def port_rows(fmc, notes):
    rows = []
    for obj in fmc.get_all("object/icmpv4objects"):
        if not is_user_defined(obj):
            continue
        if obj["name"] == "PING" and str(obj.get("icmpType")) == "8":
            rows.append(["PING", None, None])
        else:
            notes.append(["Port", obj["name"], "ICMPv4 objects other than PING (echo request) are not supported"])
    for obj in fmc.get_all("object/protocolportobjects"):
        if is_user_defined(obj):
            rows.append([obj["name"], obj.get("protocol"), obj.get("port")])
    return rows


def port_group_rows(fmc):
    return [
        [group["name"], ",".join(obj["name"] for obj in group.get("objects", []))]
        for group in fmc.get_all("object/portobjectgroups")
        if is_user_defined(group)
    ]


def host_network_rows(fmc):
    rows = []
    for obj_type, path in (("Host", "object/hosts"), ("Network", "object/networks"), ("Range", "object/ranges")):
        for obj in fmc.get_all(path):
            if is_user_defined(obj):
                rows.append([obj_type, obj["name"], obj.get("value"), cell(obj.get("description"))])
    return rows


def network_group_rows(fmc, notes):
    members = {}
    for group in fmc.get_all("object/networkgroups"):
        if not is_user_defined(group):
            continue
        if group.get("literals"):
            literals = ", ".join(literal.get("value", "?") for literal in group["literals"])
            notes.append(["NetworkGroup", group["name"], f"Literal values are not exported: {literals}"])
        members[group["name"]] = [obj["name"] for obj in group.get("objects", [])]

    # Nested groups must come after the groups they contain
    rows = []
    pending = dict(members)
    while pending:
        ready = [name for name, objects in pending.items() if not any(obj in pending for obj in objects)]
        for name in ready or list(pending):
            rows.append([name, ",".join(pending.pop(name))])
    return rows


def ha_form(fmc, notes):
    """HA sheet values and the device used for EtherChannel and subinterfaces ({id, name} or None)."""
    devices = fmc.get_all("devices/devicerecords")
    device_names = {device["id"]: device["name"] for device in devices}
    pairs = fmc.get_all("devicehapairs/ftddevicehapairs")

    if not pairs:
        device = choose(devices, "device")
        if device is None:
            notes.append(["HA", "-", "No devices on FMC"])
            return [], None
        notes.append(["HA", device["name"], "No HA pair - only the device for EtherChannel and subinterfaces (B3)"])
        return [[None], [device["name"]]], {"id": device["id"], "name": device["name"]}

    pair = fmc.get(f"devicehapairs/ftddevicehapairs/{choose(pairs, 'HA pair')['id']}")
    primary, secondary = pair["primary"], pair["secondary"]
    primary_name = device_names.get(primary["id"], primary.get("name"))
    bootstrap = pair.get("ftdHABootstrap", {})
    lan = bootstrap.get("lanFailover", {})
    stateful = lan if bootstrap.get("useSameLinkForFailovers") else bootstrap.get("statefulFailover", {})
    if not lan:
        notes.append(["HA", pair["name"], "FMC did not return failover link settings"])

    def link(settings):
        return [[settings.get("logicalName")], [settings.get("interfaceObject", {}).get("name")],
                [settings.get("activeIP")], [settings.get("standbyIP")], [settings.get("subnetMask")]]

    values = [[pair["name"]], [primary_name], [device_names.get(secondary["id"], secondary.get("name"))]]
    return values + link(lan) + link(stateful), {"id": primary["id"], "name": primary_name}


def etherchannel_form(fmc, device, zone_names, notes):
    """EtherChannel sheet values and all EtherChannels of the device."""
    if device is None:
        return [], []
    etherchannels = sorted(
        fmc.get_all(f"devices/devicerecords/{device['id']}/etherchannelinterfaces"),
        key=lambda etherchannel: etherchannel.get("etherChannelId", 0),
    )
    if not etherchannels:
        return [], []
    etherchannel = etherchannels[0]
    for other in etherchannels[1:]:
        notes.append(["EtherChannel", other["name"], "The sheet holds one EtherChannel - not exported"])
    return [
        [etherchannel.get("etherChannelId")],
        [etherchannel.get("ifname")],
        [interface["name"] for interface in etherchannel.get("selectedInterfaces", [])],
        [zone_names.get(etherchannel.get("securityZone", {}).get("id"))],
    ], etherchannels


def subinterface_rows(fmc, device, etherchannels, zone_names, notes):
    if device is None:
        return []
    etherchannel_names = {etherchannel["name"] for etherchannel in etherchannels}
    rows = []
    for sub in fmc.get_all(f"devices/devicerecords/{device['id']}/subinterfaces"):
        sub_name = f"{sub.get('name')}.{sub.get('subIntfId')}"
        if sub.get("name") not in etherchannel_names:
            notes.append(["SubInterfaces", sub_name, "Not on an EtherChannel - not supported"])
            continue
        static = sub.get("ipv4", {}).get("static")
        if not static:
            notes.append(["SubInterfaces", sub_name, "No static IPv4 address - not supported"])
            continue
        if sub.get("subIntfId") != sub.get("vlanId"):
            notes.append(["SubInterfaces", sub_name, f"Import uses VLAN {sub.get('vlanId')} as subinterface ID"])
        rows.append([
            sub["name"], sub.get("vlanId"), sub.get("ifname"), static.get("address"), static.get("netmask"),
            zone_names.get(sub.get("securityZone", {}).get("id")),
        ])
    return rows
