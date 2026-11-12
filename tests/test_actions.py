import shutil

import pytest
from openpyxl import load_workbook

from conftest import TEMPLATE
from fmc_setup import actions
from fmc_setup.client import SetupError
from fmc_setup.workbook import SetupWorkbook


def test_security_zones(fmc, workbook):
    actions.add_security_zones(fmc, workbook)
    assert [p["payload"]["name"] for p in fmc.posts] == ["Zone_Inside", "Zone_Outside", "Zone_DMZ"]
    assert all(p["path"] == "object/securityzones" for p in fmc.posts)


def test_access_policy(fmc, workbook):
    actions.add_access_policy(fmc, workbook)
    assert fmc.posts[0]["payload"] == {
        "type": "AccessPolicy", "name": "Example_ACP", "defaultAction": {"action": "BLOCK"}
    }


def test_categories_go_to_mandatory_section(fmc, workbook):
    actions.add_categories(fmc, workbook)
    assert fmc.posts[0]["path"] == "policy/accesspolicies/id-Example_ACP/categories"
    assert fmc.posts[0]["params"] == {"section": "mandatory"}


def test_unknown_policy_raises(fmc, workbook):
    fmc.inventory["policy/accesspolicies"] = []
    with pytest.raises(SetupError, match="Example_ACP"):
        actions.add_categories(fmc, workbook)


def test_ports_ping_is_icmp_object(fmc, workbook):
    actions.add_ports(fmc, workbook)
    assert fmc.posts[0] == {
        "path": "object/icmpv4objects", "params": None,
        "payload": {"type": "ICMPV4Object", "name": "PING", "icmpType": "8"},
    }
    assert fmc.posts[1]["payload"] == {
        "type": "ProtocolPortObject", "name": "LDAP_TCP-389", "protocol": "TCP", "port": "389"
    }


def test_port_groups(fmc, workbook):
    actions.add_port_groups(fmc, workbook)
    members = fmc.posts[0]["payload"]["objects"]
    assert len(members) == 8
    assert {m["type"] for m in members} == {"ProtocolPortObject"}


def test_hosts_networks_endpoints_and_description(fmc, workbook):
    actions.add_hosts_networks(fmc, workbook)
    paths = [p["path"] for p in fmc.posts]
    assert paths.count("object/hosts") == 5
    assert "object/networks" in paths and "object/ranges" in paths
    assert fmc.posts[0]["payload"]["description"] == "Domain controller 1"
    assert "description" not in fmc.posts[3]["payload"]


def test_network_group_members_keep_their_type(fmc, workbook):
    actions.add_network_groups(fmc, workbook)
    assert {m["type"] for m in fmc.posts[0]["payload"]["objects"]} == {"Host"}


def test_access_rules(fmc, workbook):
    actions.add_access_rules(fmc, workbook)
    rules = {p["payload"]["name"]: p for p in fmc.posts}
    assert set(rules) == {"DC-DC", "CLIENTS-TO-DC", "CLIENTS-TO-WEB", "PING-PRINTERS"}

    dc = rules["DC-DC"]
    assert dc["params"] == {"category": "ACTIVE_DIRECTORY"}
    assert dc["payload"]["destinationPorts"]["objects"][0]["type"] == "PortObjectGroup"

    ping = rules["PING-PRINTERS"]["payload"]
    assert "sourceNetworks" not in ping  # "Any"
    assert ping["destinationNetworks"]["objects"][0]["type"] == "NetworkGroup"
    assert ping["destinationPorts"]["objects"][0]["type"] == "ICMPV4Object"


def test_access_rule_action_from_column_m(fmc, tmp_path, capsys):
    path = tmp_path / "action-workbook.xlsx"
    shutil.copy(TEMPLATE, path)
    wb = load_workbook(path)
    sheet = wb["ACP"]
    sheet["M2"] = "BLOCK"   # DC-DC
    sheet["M3"] = "bogus"   # CLIENTS-TO-DC - invalid, rule is skipped
    sheet["M4"] = None      # CLIENTS-TO-WEB - empty, defaults to ALLOW
    wb.save(path)

    actions.add_access_rules(fmc, SetupWorkbook(path))
    rules = {p["payload"]["name"]: p["payload"] for p in fmc.posts}
    assert rules["DC-DC"]["action"] == "BLOCK"
    assert rules["CLIENTS-TO-WEB"]["action"] == "ALLOW"
    assert "CLIENTS-TO-DC" not in rules
    assert "invalid action 'BOGUS'" in capsys.readouterr().out


def test_access_rule_with_missing_object_is_skipped(fmc, workbook, capsys):
    fmc.inventory["object/networkaddresses"] = [
        o for o in fmc.inventory["object/networkaddresses"] if o["name"] != "WEB-SRV"
    ]
    actions.add_access_rules(fmc, workbook)
    assert "CLIENTS-TO-WEB" not in {p["payload"]["name"] for p in fmc.posts}
    assert "WEB-SRV" in capsys.readouterr().out


def test_ha(fmc, workbook, monkeypatch):
    monkeypatch.setenv("FMC_HA_SHARED_KEY", "secret")
    monkeypatch.setattr("builtins.input", lambda _: "Y")
    actions.add_ha(fmc, workbook)
    payload = fmc.posts[0]["payload"]
    bootstrap = payload["ftdHABootstrap"]
    assert payload["primary"] == {"id": "id-FTD-1"} and payload["secondary"] == {"id": "id-FTD-2"}
    assert bootstrap["sharedKey"] == "secret"
    assert bootstrap["useSameLinkForFailovers"] is False
    assert bootstrap["statefulFailover"]["logicalName"] == "STATE-LINK"
    assert bootstrap["statefulFailover"]["useIPv6Address"] is False


def test_ha_cancelled(fmc, workbook, monkeypatch):
    monkeypatch.setattr("builtins.input", lambda _: "N")
    actions.add_ha(fmc, workbook)
    assert fmc.posts == []


def test_etherchannel(fmc, workbook):
    actions.add_etherchannel(fmc, workbook)
    payload = fmc.posts[0]["payload"]
    assert fmc.posts[0]["path"] == "devices/devicerecords/id-FTD-1/etherchannelinterfaces"
    assert [i["name"] for i in payload["selectedInterfaces"]] == ["Ethernet1/7", "Ethernet1/8"]
    assert payload["etherChannelId"] == 1


def test_subinterfaces(fmc, workbook):
    actions.add_subinterfaces(fmc, workbook)
    assert [p["payload"]["vlanId"] for p in fmc.posts] == [10, 20]
    assert fmc.posts[1]["payload"]["ipv4"]["static"] == {"address": "198.51.100.1", "netmask": "26"}
