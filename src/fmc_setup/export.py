"""Export of Access Control Policies to CSV."""

import csv
import re
from pathlib import Path

from fmc_setup.objects import by_name
from fmc_setup.workbook import split_names

CSV_HEADER = [
    "#", "name", "sourceZones", "destZones", "sourceNetworks", "destNetworks", "sourcePorts", "destPorts",
    "URL", "APP", "VLAN", "Action", "Enable", "ipsPolicy", "variableSet", "filePolicy", "logBegin", "logEnd",
    "sendEventsToFMC", "syslogConfig", "TimeRangeObject", "Comments",
]


def export_policy_to_csv(fmc, workbook, output_dir="."):
    policies = fmc.get_all("policy/accesspolicies")
    print("ACP available in the domain: ")
    for policy in policies:
        print("\tName: ", policy["name"])
    answer = input(
        "Enter the ACP Name (case sensitive) if you want specific ACP to export "
        "(multiple values should be comma separated). By default all the ACP would be exported, "
        "press return for default behaviour: "
    )
    if answer.strip():
        by_policy_name = by_name(policies)
        selected = []
        for name in split_names(answer):
            if name in by_policy_name:
                selected.append(by_policy_name[name])
            else:
                print(f"ACP {name} does not exist on FMC")
    else:
        selected = policies

    for policy in selected:
        rules = fmc.get_all(f"policy/accesspolicies/{policy['id']}/accessrules")
        path = Path(output_dir) / (re.sub(r'[\\/:*?"<>|]', "_", policy["name"]) + ".csv")
        write_rules_csv(path, rules)
        print(f"File is at: {path}")


def write_rules_csv(path, rules):
    with open(path, "w", newline="", encoding="utf-8") as policy_file:
        writer = csv.writer(policy_file)
        writer.writerow(CSV_HEADER)
        for pos, rule in enumerate(rules, start=1):
            print(f"Writing rule #{pos} to CSV...")
            writer.writerow([pos, rule["name"]] + rule_csv_fields(rule))


def rule_csv_fields(rule):
    """CSV columns of one access rule (without position and name)."""

    def joined(values):
        values = [str(v) for v in values]
        return ";".join(values) if values else "Any"

    def zones(key):
        return joined(o["name"] for o in rule.get(key, {}).get("objects", []))

    def networks(key):
        container = rule.get(key, {})
        return joined(
            [o["name"] for o in container.get("objects", [])]
            + [literal["value"] for literal in container.get("literals", [])]
        )

    def ports(key):
        container = rule.get(key, {})
        return joined(
            [o["name"] for o in container.get("objects", [])]
            + [
                literal.get("port") or literal.get("icmpType") or literal["type"]
                for literal in container.get("literals", [])
            ]
        )

    def name_of(key):
        return rule.get(key, {}).get("name", "NULL")

    urls = rule.get("urls", {})
    url = (
        [u["category"]["name"] for u in urls.get("urlCategoriesWithReputation", [])]
        + [u["url"] for u in urls.get("literals", [])]
        + [u["name"] for u in urls.get("objects", [])]
    )

    app = []
    for values in rule.get("applications", {}).values():
        for item in values:
            app += [tag["name"] for tag in item.get("tags", [])]
            if "Application" in item.get("type", ""):
                app.append(item["name"])

    vlans = rule.get("vlanTags", {})
    vlan = [v["startTag"] for v in vlans.get("literals", [])] + [v["name"] for v in vlans.get("objects", [])]

    comments = [c.get("comment", "") for c in rule.get("commentHistoryList", [])]

    return [
        zones("sourceZones"), zones("destinationZones"),
        networks("sourceNetworks"), networks("destinationNetworks"),
        ports("sourcePorts"), ports("destinationPorts"),
        joined(url), joined(app), joined(vlan),
        rule["action"], rule["enabled"],
        name_of("ipsPolicy"), name_of("variableSet"), name_of("filePolicy"),
        rule.get("logBegin", "NULL"), rule.get("logEnd", "NULL"), rule.get("sendEventsToFMC", "NULL"),
        rule.get("enableSyslog", "NULL"),
        ";".join(t["name"] for t in rule.get("timeRangeObjects", [])) or "NULL",
        ";".join(comments) if comments else "Not Applicable",
    ]
