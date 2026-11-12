from pathlib import Path

import pytest

from fmc_setup.workbook import SetupWorkbook

TEMPLATE = Path(__file__).resolve().parent.parent / "examples" / "fmc-setup-template.xlsx"


class FakeResponse:
    def __init__(self, status_code, body):
        self.status_code = status_code
        self._body = body
        self.text = str(body)

    def json(self):
        return self._body


def objects(obj_type, names):
    return [{"type": obj_type, "id": f"id-{name}", "name": name} for name in names]


class FakeFMC:
    """FMC client double: GET collections come from `inventory`, POST requests are recorded."""

    def __init__(self, inventory=None, post_status=201):
        self.inventory = inventory or {}
        self.post_status = post_status
        self.posts = []

    def get_all(self, path):
        return self.inventory.get(path, [])

    def request(self, method, path, **kwargs):
        return FakeResponse(200, {"items": []})

    def post(self, path, payload, params=None):
        self.posts.append({"path": path, "params": params, "payload": payload})
        return FakeResponse(self.post_status, dict(payload, id="new-id"))


@pytest.fixture
def workbook():
    return SetupWorkbook(TEMPLATE)


@pytest.fixture
def inventory():
    """FMC content matching the template workbook, as if options 0-6 were already run."""
    hosts = objects("Host", ["DC1", "DC2", "WEB-SRV", "PRINTER-01", "PRINTER-02"])
    return {
        "policy/accesspolicies": objects("AccessPolicy", ["Example_ACP"]),
        "object/securityzones": objects("SecurityZone", ["Zone_Inside", "Zone_Outside", "Zone_DMZ"]),
        "object/networkaddresses": hosts + objects("Network", ["CLIENTS-NET"]) + objects("Range", ["LAB-RANGE"]),
        "object/networkgroups": objects("NetworkGroup", ["PRINTERS"]),
        "object/protocolportobjects": objects(
            "ProtocolPortObject",
            ["LDAP_TCP-389", "KERBEROS_TCP-88", "KERBEROS_UDP-88", "DNS_TCP-53", "DNS_UDP-53", "SMB_TCP-445",
             "RPC_ENDPOINT_MAPPER_TCP-135", "RPC-49152-65535", "HTTPS"],
        ),
        "object/icmpv4objects": objects("ICMPV4Object", ["PING"]),
        "object/portobjectgroups": objects("PortObjectGroup", ["AD_PORTS"]),
        "devices/devicerecords": objects("Device", ["FTD-1", "FTD-2"]),
        "devices/devicerecords/id-FTD-1/physicalinterfaces": objects(
            "PhysicalInterface", ["GigabitEthernet0/6", "GigabitEthernet0/7", "Ethernet1/7", "Ethernet1/8"]
        ),
        "devices/devicerecords/id-FTD-1/etherchannelinterfaces": objects("EtherChannelInterface", ["Port-channel1"]),
    }


@pytest.fixture
def fmc(inventory):
    return FakeFMC(inventory)
