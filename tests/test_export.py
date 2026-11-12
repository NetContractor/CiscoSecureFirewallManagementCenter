import csv

from fmc_setup.export import CSV_HEADER, rule_csv_fields, write_rules_csv

RULE = {
    "name": "WEB",
    "action": "ALLOW",
    "enabled": True,
    "sourceZones": {"objects": [{"name": "Zone_Inside"}]},
    "sourceNetworks": {"objects": [{"name": "CLIENTS-NET"}], "literals": [{"value": "192.0.2.1"}]},
    "destinationPorts": {"objects": [{"name": "HTTPS"}], "literals": [{"type": "PortLiteral", "port": "8443"}]},
    "commentHistoryList": [{"comment": "first, with comma"}],
    "logBegin": True,
}


def test_rule_fields():
    fields = rule_csv_fields(RULE)
    assert len(fields) == len(CSV_HEADER) - 2
    assert fields[0] == "Zone_Inside"
    assert fields[1] == "Any"
    assert fields[2] == "CLIENTS-NET;192.0.2.1"
    assert fields[5] == "HTTPS;8443"
    assert fields[-1] == "first, with comma"


def test_csv_is_readable(tmp_path):
    path = tmp_path / "policy.csv"
    write_rules_csv(path, [RULE])
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    assert rows[0] == CSV_HEADER
    assert rows[1][1] == "WEB"
    assert rows[1][-1] == "first, with comma"
