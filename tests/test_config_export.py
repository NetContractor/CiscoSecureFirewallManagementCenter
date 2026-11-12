from collections import defaultdict

import pytest
from openpyxl import load_workbook

from conftest import FakeResponse, objects
from fmc_setup import actions
from fmc_setup.config_export import (
    export_configuration,
    is_user_defined,
    network_group_rows,
    unsupported_rule_settings,
)
from fmc_setup.workbook import SetupWorkbook, cell, data_rows

SYSTEM = {"metadata": {"readOnly": {"state": True, "reason": "SYSTEM"}}}
ADDRESS_PATHS = ("object/hosts", "object/networks", "object/ranges")


class StatefulFMC:
    """FMC double that stores created objects, so the import can be followed by the export."""

    host = "fmc.example.com"

    def __init__(self):
        self.store = defaultdict(list)
        self.next_id = 0
        self.store["devices/devicerecords"] = objects("Device", ["FTD-1", "FTD-2"])
        self.store["devices/devicerecords/id-FTD-1/physicalinterfaces"] = objects(
            "PhysicalInterface", ["GigabitEthernet0/6", "GigabitEthernet0/7", "Ethernet1/7", "Ethernet1/8"]
        )
        self.store["object/protocolportobjects"] = [
            dict(SYSTEM, type="ProtocolPortObject", id="sys-https", name="HTTPS", protocol="TCP", port="443")
        ]

    def get_all(self, path):
        return list(self.store[path])

    def get(self, path):
        collection, _, obj_id = path.rpartition("/")
        return next(obj for obj in self.store[collection] if obj["id"] == obj_id)

    def request(self, method, path, **kwargs):
        return FakeResponse(200, {"items": []})

    def post(self, path, payload, params=None):
        self.next_id += 1
        obj = dict(payload, id=f"id{self.next_id}")
        if path.endswith("/accessrules"):
            obj["metadata"] = {"category": (params or {}).get("category")}
        if path.endswith("/etherchannelinterfaces"):
            obj["name"] = f"Port-channel{payload['etherChannelId']}"
        self.store[path].append(obj)
        if path in ADDRESS_PATHS:
            self.store["object/networkaddresses"].append(obj)
        return FakeResponse(201, obj)


def form_values(sheet, rows, columns):
    return [[cell(sheet.cell(row, column).value) for column in columns] for row in rows]


def acp_rows(sheet):
    rows = []
    for row in data_rows(sheet, 13, key_column=1):
        # Object type does not matter when the condition is Any
        for type_column in (6, 8, 10):
            if row[type_column + 1] is None or row[type_column + 1].lower() == "any":
                row[type_column], row[type_column + 1] = None, "Any"
        rows.append(row)
    return rows


def test_import_then_export_gives_the_same_workbook(workbook, tmp_path, monkeypatch):
    monkeypatch.setenv("FMC_HA_SHARED_KEY", "secret")
    monkeypatch.setattr("builtins.input", lambda _: "Y")
    fmc = StatefulFMC()
    for action in (actions.add_security_zones, actions.add_access_policy, actions.add_categories,
                   actions.add_ports, actions.add_port_groups, actions.add_hosts_networks,
                   actions.add_network_groups, actions.add_access_rules, actions.add_ha,
                   actions.add_etherchannel, actions.add_subinterfaces):
        action(fmc, workbook)

    exported = SetupWorkbook(export_configuration(fmc, workbook, output_dir=tmp_path))

    columns = {"SecurityZones": 1, "Categories": 1, "Port": 3, "PortGroup": 2, "HostNetwork": 4,
               "NetworkGroup": 2, "SubInterfaces": 6}
    for name, count in columns.items():
        assert list(data_rows(exported.sheet(name), count)) == list(data_rows(workbook.sheet(name), count)), name
    assert acp_rows(exported.sheet("ACP")) == acp_rows(workbook.sheet("ACP"))
    assert exported.sheet("ACP")["A2"].value == "Example_ACP"
    assert form_values(exported.sheet("HA"), range(2, 15), [2]) == form_values(workbook.sheet("HA"), range(2, 15), [2])
    assert (form_values(exported.sheet("EtherChannel"), range(2, 6), [2, 3])
            == form_values(workbook.sheet("EtherChannel"), range(2, 6), [2, 3]))
    assert load_workbook(exported.path).sheetnames == [
        "Readme", "ACP", "SecurityZones", "Categories", "Port", "PortGroup", "HA",
        "HostNetwork", "NetworkGroup", "EtherChannel", "SubInterfaces",
    ]


ALLOW_RULE = {
    "name": "r", "action": "ALLOW", "enabled": True,
    "sourceNetworks": {"objects": [{"type": "Host", "name": "A", "id": "1"}]},
    "variableSet": {"name": "Default-Set", "id": "v"}, "metadata": {"ruleIndex": 1},
}


@pytest.mark.parametrize(
    ("change", "problem"),
    [
        ({"action": "MONITOR"}, "action MONITOR"),
        ({"enabled": False}, "rule is disabled"),
        ({"destinationNetworks": {"literals": [{"value": "192.0.2.1"}]}}, "literal values in destinationNetworks"),
        ({"applications": {"applications": [{"name": "Facebook"}]}}, "applications condition"),
        ({"sourcePorts": {"objects": [{"name": "HTTP"}]}}, "sourcePorts condition"),
        ({"timeRangeObjects": [{"name": "Office hours"}]}, "timeRangeObjects condition"),
        ({"sourceNetworks": {"objects": [{"type": "Country", "name": "PL"}]}}, "objects of type Country"),
    ],
)
def test_rules_that_import_would_change_are_not_exported(change, problem):
    assert unsupported_rule_settings(ALLOW_RULE) == []
    problems = unsupported_rule_settings(dict(ALLOW_RULE, **change))
    assert any(problem in p for p in problems)


def test_block_action_is_exportable():
    assert unsupported_rule_settings(dict(ALLOW_RULE, action="BLOCK")) == []


def test_skipped_rule_is_listed_in_notes(tmp_path, monkeypatch):
    fmc = StatefulFMC()
    fmc.store["policy/accesspolicies"] = objects("AccessPolicy", ["P"])
    fmc.store["policy/accesspolicies/id-P/accessrules"] = [
        dict(ALLOW_RULE, name="ok", id="r1"), dict(ALLOW_RULE, name="deny", id="r2", action="BLOCK_RESET"),
    ]
    # No HA pair - the device for EtherChannel and subinterfaces is selected by name
    monkeypatch.setattr("builtins.input", lambda _: "FTD-1")
    exported = SetupWorkbook(export_configuration(fmc, None, output_dir=tmp_path))
    assert [row[3] for row in data_rows(exported.sheet("ACP"), 13, key_column=1)] == ["ok"]
    notes = list(data_rows(exported.sheet("ExportNotes"), 3))
    assert any(row[1] == "deny" and "action BLOCK_RESET" in row[2] for row in notes)


def test_system_objects_are_not_exported():
    assert is_user_defined({"name": "A"})
    assert not is_user_defined(SYSTEM)


def test_nested_network_groups_follow_their_members():
    class FMC:
        def get_all(self, path):
            return [
                {"name": "OUTER", "objects": [{"name": "INNER"}, {"name": "HOST"}]},
                {"name": "INNER", "objects": [{"name": "HOST"}], "literals": [{"value": "192.0.2.1"}]},
            ]

    notes = []
    assert network_group_rows(FMC(), notes) == [["INNER", "HOST"], ["OUTER", "INNER,HOST"]]
    assert notes == [["NetworkGroup", "INNER", "Literal values are not exported: 192.0.2.1"]]
