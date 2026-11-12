"""Menu options. Every option takes the FMC client and the setup workbook."""

import os
import time

from fmc_setup.client import SetupError, report
from fmc_setup.console import read_secret
from fmc_setup.objects import by_name, ref, resolve
from fmc_setup.workbook import cell, data_rows, split_names


def get_acp_name(workbook):
    name = cell(workbook.sheet("ACP")["A2"].value)
    if not name:
        raise SetupError("Access Control Policy name is missing in sheet ACP, cell A2")
    return name


def get_policy_id(fmc, workbook):
    acp_name = get_acp_name(workbook)
    for policy in fmc.get_all("policy/accesspolicies"):
        if policy["name"] == acp_name:
            return policy["id"]
    raise SetupError(f"Access Control Policy '{acp_name}' does not exist on FMC")


def ensure_access_policy(fmc, workbook):
    """Access Control Policy ID for ACP!A2, creating it on FMC with the default action BLOCK if missing."""
    try:
        return get_policy_id(fmc, workbook)
    except SetupError:
        acp_name = get_acp_name(workbook)
        print(f"Access Control Policy '{acp_name}' does not exist on FMC - creating it.")
        response = fmc.post(
            "policy/accesspolicies",
            {"type": "AccessPolicy", "name": acp_name, "defaultAction": {"action": "BLOCK"}},
        )
        if not report(response, f"{acp_name} has been added to FMC."):
            raise SetupError(f"Could not create Access Control Policy '{acp_name}'") from None
        return response.json()["id"]


def get_primary_fw(fmc, workbook):
    """Primary firewall of the HA pair (sheet HA, cell B3)."""
    fw_name = cell(workbook.sheet("HA")["B3"].value)
    devices = by_name(fmc.get_all("devices/devicerecords"))
    if fw_name not in devices:
        raise SetupError(f"{fw_name} does not exist on FMC")
    print(f"{fw_name} ID: {devices[fw_name]['id']}")
    return devices[fw_name]


def wait_for_registration(fmc, task_id, device_name, timeout=300, interval=10):
    """Polls an FMC task until it succeeds, fails, or `timeout` seconds pass.

    NOTE: the exact task status endpoint/values were not verified against a live FMC -
    adjust the `status` values below if your FMC version reports registration differently.
    """
    print(f"Waiting for {device_name} registration to complete (this can take a few minutes)...")
    elapsed = 0
    while elapsed < timeout:
        response = fmc.request("GET", f"job/taskstatuses/{task_id}")
        if response.status_code == 200:
            status = response.json().get("status")
            if status in ("Success", "COMPLETED"):
                print(f"{device_name} has been registered successfully.")
                return
            if status in ("Failed", "FAILED"):
                print(f"{device_name} registration failed: {response.json()}")
                return
        time.sleep(interval)
        elapsed += interval
    print(f"{device_name} registration is still in progress after {timeout}s - check the FMC UI.")


def register_devices(fmc, workbook):
    print("Registering new FTD devices from the xlsx")
    policy_id = ensure_access_policy(fmc, workbook)
    reg_key = os.environ.get("FMC_REG_KEY") or read_secret(
        "FTD registration key (configured on the device with 'configure manager add'): "
    )
    for name, host in data_rows(workbook.sheet("Devices"), 2):
        payload = {
            "type": "Device",
            "name": name,
            "hostName": host,
            "regKey": reg_key,
            "license_caps": ["BASE"],
            "accessPolicy": {"id": policy_id, "type": "AccessPolicy"},
        }
        response = fmc.post("devices/devicerecords", payload)
        if not report(response, f"{name} registration has been submitted to FMC."):
            continue
        task_id = response.json().get("metadata", {}).get("task", {}).get("id")
        if task_id:
            wait_for_registration(fmc, task_id, name)
        else:
            print(f"{name} - no task ID returned by FMC, check the FMC UI for registration progress.")


def configure_interfaces(fmc, workbook):
    print("Configuring interfaces from the xlsx")
    devices = by_name(fmc.get_all("devices/devicerecords"))
    zones = by_name(fmc.get_all("object/securityzones"))

    # Columns: A device name, B physical interface, C logical name, D IP address, E netmask, F security zone, G enabled
    for device_name, interface_name, ifname, ip_address, netmask, zone_name, enabled in data_rows(
        workbook.sheet("Interfaces"), 7
    ):
        label = ifname or interface_name
        if device_name not in devices:
            print(f"{device_name} does not exist on FMC - {label} skipped.")
            continue
        enabled = (enabled or "TRUE").upper()
        if enabled not in ("TRUE", "FALSE"):
            print(f"{label} skipped - invalid Enabled value '{enabled}' (expected TRUE or FALSE).")
            continue
        if zone_name not in zones:
            print(f"{zone_name} does not exist on FMC - {label} skipped.")
            continue

        device = devices[device_name]
        interfaces = by_name(fmc.get_all(f"devices/devicerecords/{device['id']}/physicalinterfaces"))
        if interface_name not in interfaces:
            print(f"{interface_name} does not exist on {device_name} - {label} skipped.")
            continue

        interface = interfaces[interface_name]
        interface.update({
            "ifname": ifname,
            "enabled": enabled == "TRUE",
            "securityZone": {"id": zones[zone_name]["id"], "type": "SecurityZone"},
            "ipv4": {"static": {"address": ip_address, "netmask": netmask}},
        })
        response = fmc.put(
            f"devices/devicerecords/{device['id']}/physicalinterfaces/{interface['id']}", interface
        )
        report(response, f"Interface {interface_name} ({ifname}) has been configured on {device_name}.")


def add_security_zones(fmc, workbook):
    print("Adding Security Zones to FMC from the xlsx")
    for (name,) in data_rows(workbook.sheet("SecurityZones"), 1):
        response = fmc.post(
            "object/securityzones", {"type": "SecurityZone", "name": name, "interfaceMode": "ROUTED"}
        )
        report(response, f"{name} has been added to FMC.")


def add_access_policy(fmc, workbook):
    acp_name = get_acp_name(workbook)
    print(acp_name)
    response = fmc.post(
        "policy/accesspolicies",
        {"type": "AccessPolicy", "name": acp_name, "defaultAction": {"action": "BLOCK"}},
    )
    report(response, f"{acp_name} has been added to FMC.")


def add_categories(fmc, workbook):
    policy_id = get_policy_id(fmc, workbook)
    print("Adding Categories to FMC from the xlsx")
    for (name,) in data_rows(workbook.sheet("Categories"), 1):
        response = fmc.post(
            f"policy/accesspolicies/{policy_id}/categories",
            {"type": "Category", "name": name},
            params={"section": "mandatory"},
        )
        report(response, f"{name} has been added to FMC.")


def add_ports(fmc, workbook):
    print("Adding new port from the xlsx")
    for name, protocol, port in data_rows(workbook.sheet("Port"), 3):
        if name == "PING":
            response = fmc.post(
                "object/icmpv4objects", {"type": "ICMPV4Object", "name": "PING", "icmpType": "8"}
            )
        else:
            response = fmc.post(
                "object/protocolportobjects",
                {"type": "ProtocolPortObject", "name": name, "protocol": protocol, "port": port},
            )
        report(response, f"{name} has been added to FMC.")


def add_port_groups(fmc, workbook):
    ports = by_name(fmc.get_all("object/protocolportobjects"))
    icmp = by_name(fmc.get_all("object/icmpv4objects"))
    print("Adding new port group from the xlsx")
    for group_name, members in data_rows(workbook.sheet("PortGroup"), 2):
        objects, missing = resolve(split_names(members or ""), ports, icmp)
        if missing:
            print(f"WARNING: {group_name} - following ports do not exist on FMC: {', '.join(missing)}")
        if not objects:
            print(f"{group_name} skipped - no existing port objects.")
            continue
        response = fmc.post(
            "object/portobjectgroups",
            {"type": "PortObjectGroup", "name": group_name, "objects": objects},
        )
        report(response, f"{', '.join(o['name'] for o in objects)} has been added to {group_name}")


def add_hosts_networks(fmc, workbook):
    print("Adding new host, network or range from the xlsx")
    endpoints = {"Host": "object/hosts", "Network": "object/networks", "Range": "object/ranges"}
    for obj_type, name, value, description in data_rows(workbook.sheet("HostNetwork"), 4):
        if obj_type not in endpoints:
            print(f"{name} skipped - unsupported object type '{obj_type}' (Host, Network or Range expected).")
            continue
        payload = {"type": obj_type, "name": name, "value": value}
        if description:
            payload["description"] = description
        report(fmc.post(endpoints[obj_type], payload), f"{name} has been added to FMC.")


def add_network_groups(fmc, workbook):
    addresses = by_name(fmc.get_all("object/networkaddresses"))
    groups = by_name(fmc.get_all("object/networkgroups"))
    print("Adding new network group from the xlsx")
    for group_name, members in data_rows(workbook.sheet("NetworkGroup"), 2):
        objects, missing = resolve(split_names(members or ""), addresses, groups)
        if missing:
            print(f"WARNING: {group_name} - following objects do not exist on FMC: {', '.join(missing)}")
        if not objects:
            print(f"{group_name} skipped - no existing network objects.")
            continue
        response = fmc.post(
            "object/networkgroups", {"type": "NetworkGroup", "name": group_name, "objects": objects}
        )
        if report(response, f"{', '.join(o['name'] for o in objects)} has been added to {group_name}"):
            # Group created here can be used as a member of the next groups
            groups[group_name] = response.json()


def add_access_rules(fmc, workbook):
    policy_id = get_policy_id(fmc, workbook)
    zones = by_name(fmc.get_all("object/securityzones"))
    addresses = by_name(fmc.get_all("object/networkaddresses"))
    network_groups = by_name(fmc.get_all("object/networkgroups"))
    ports = by_name(fmc.get_all("object/protocolportobjects"))
    icmp = by_name(fmc.get_all("object/icmpv4objects"))
    port_groups = by_name(fmc.get_all("object/portobjectgroups"))

    def network_lookups(obj_type):
        if obj_type == "NetworkGroup":
            return network_groups, addresses
        return addresses, network_groups

    def service_lookups(obj_type):
        if obj_type == "Service":
            return ports, icmp, port_groups
        return port_groups, ports, icmp

    # Columns: A ACP name, B rule number, C category, D rule name, E SRC zone, F DST zone,
    # G SRC type, H SRC, I DST type, J DST, K service type, L service, M action (ALLOW/BLOCK)
    for row in data_rows(workbook.sheet("ACP"), 13, key_column=1):
        (_, _, category, rule_name, src_zone, dst_zone,
         src_type, src_net, dst_type, dst_net, service_type, service, action) = row
        if not rule_name:
            print(f"Rule number {row[1]} skipped - access rule name is empty.")
            continue

        action = (action or "ALLOW").upper()
        if action not in ("ALLOW", "BLOCK"):
            print(f"Access rule {rule_name} skipped - invalid action '{action}' (expected ALLOW or BLOCK).")
            continue

        rule = {
            "type": "AccessRule",
            "name": rule_name,
            "action": action,
            "enabled": True,
            "sendEventsToFMC": True,
            "logFiles": False,
            "logBegin": True,
            "logEnd": False,
        }
        conditions = (
            ("sourceZones", src_zone, (zones,)),
            ("destinationZones", dst_zone, (zones,)),
            ("sourceNetworks", src_net, network_lookups(src_type)),
            ("destinationNetworks", dst_net, network_lookups(dst_type)),
            ("destinationPorts", service, service_lookups(service_type)),
        )
        missing = []
        for field, value, lookups in conditions:
            # Empty cell or "Any" - condition is not set in the rule
            if value is None or value.lower() == "any":
                continue
            objects, not_found = resolve(split_names(value), *lookups)
            missing += [name for name in not_found if name not in missing]
            rule[field] = {"objects": objects}
        if missing:
            # Rule without these objects would be wider than expected - do not create it
            print(f"Access rule {rule_name} skipped - following objects do not exist on FMC: {', '.join(missing)}")
            continue

        response = fmc.post(
            f"policy/accesspolicies/{policy_id}/accessrules",
            rule,
            params={"category": category} if category else None,
        )
        if report(response, "Following access rule has been added:"):
            print()
            print(f"Category name: {category}")
            print(f"Access rule: {rule_name}")
            print(f"Action: {action}")
            print(f"Source zone: {src_zone}")
            print(f"Source host/network/group: {src_net}")
            print(f"Destination zone: {dst_zone}")
            print(f"Destination host/network/group: {dst_net}")
            print(f"Port: {service}")
        else:
            print(f"Access rule: {rule_name}")
        print()


def add_ha(fmc, workbook):
    sheet = workbook.sheet("HA")
    labels = (
        "HA Name", "HA Primary firewall", "HA Secondary firewall", "HA Link Name", "HA Interface",
        "HA Primary IP", "HA Secondary IP", "HA Subnet Mask", "HA State Link", "HA State Interface",
        "HA State Primary IP", "HA State Secondary IP", "HA State Subnet Mask",
    )
    ha = {label: cell(sheet[f"B{row}"].value) for row, label in enumerate(labels, start=2)}

    devices = by_name(fmc.get_all("devices/devicerecords"))
    for key in ("HA Primary firewall", "HA Secondary firewall"):
        if ha[key] not in devices:
            raise SetupError(f"{ha[key]} does not exist on FMC")
        print(f"{ha[key]} ID: {devices[ha[key]]['id']}")
    primary = devices[ha["HA Primary firewall"]]
    secondary = devices[ha["HA Secondary firewall"]]

    print("Checking pending FMC changes")
    response = fmc.request(
        "GET", f"deployment/deployabledevices/{primary['id']}/pendingchanges", params={"expanded": "true"}
    )
    if response.status_code == 200 and response.json().get("items"):
        print(f"{primary['name']} has pending changes. Please deploy them first before further proceeding.")
        return
    print("FMC has no pending changes")

    for label, value in ha.items():
        print(f"{label}: {value}")
    if input("Do you want to proceed (Y/N): ").strip().upper() != "Y":
        print("HA has not been added.")
        return

    interfaces = by_name(fmc.get_all(f"devices/devicerecords/{primary['id']}/physicalinterfaces"))
    for key in ("HA Interface", "HA State Interface"):
        if ha[key] not in interfaces:
            raise SetupError(f"{ha[key]} does not exist on {primary['name']}")
        print(f"{ha[key]} ID: {interfaces[ha[key]]['id']}")

    shared_key = os.environ.get("FMC_HA_SHARED_KEY") or read_secret("HA encryption shared key: ")

    def failover_link(interface, logical_name, active_ip, standby_ip, mask):
        return {
            "useIPv6Address": False,
            "subnetMask": mask,
            "interfaceObject": ref(interfaces[interface]),
            "logicalName": logical_name,
            "activeIP": active_ip,
            "standbyIP": standby_ip,
        }

    lan_failover = failover_link(
        ha["HA Interface"], ha["HA Link Name"], ha["HA Primary IP"], ha["HA Secondary IP"], ha["HA Subnet Mask"]
    )
    same_link = ha["HA Interface"] == ha["HA State Interface"]
    stateful_failover = lan_failover if same_link else failover_link(
        ha["HA State Interface"], ha["HA State Link"], ha["HA State Primary IP"],
        ha["HA State Secondary IP"], ha["HA State Subnet Mask"],
    )

    print("Adding HA to the FMC")
    payload = {
        "type": "DeviceHAPair",
        "name": ha["HA Name"],
        "primary": {"id": primary["id"]},
        "secondary": {"id": secondary["id"]},
        "ftdHABootstrap": {
            "isEncryptionEnabled": True,
            "encKeyGenerationScheme": "CUSTOM",
            "sharedKey": shared_key,
            "useSameLinkForFailovers": same_link,
            "lanFailover": lan_failover,
            "statefulFailover": stateful_failover,
        },
    }
    report(fmc.post("devicehapairs/ftddevicehapairs", payload), "High Availability has been created in FMC.")


def add_etherchannel(fmc, workbook):
    print("Adding EtherChannel")
    sheet = workbook.sheet("EtherChannel")
    etherchannel_id = cell(sheet["B2"].value)
    etherchannel_name = cell(sheet["B3"].value)
    # Selected interfaces - row 4, from column B to the right
    member_names = [name for name in (cell(c.value) for c in sheet[4][1:]) if name]
    zone_name = cell(sheet["B5"].value)

    primary = get_primary_fw(fmc, workbook)
    zones = by_name(fmc.get_all("object/securityzones"))
    if zone_name not in zones:
        raise SetupError(f"{zone_name} does not exist on FMC")
    interfaces = by_name(fmc.get_all(f"devices/devicerecords/{primary['id']}/physicalinterfaces"))
    members, missing = resolve(member_names, interfaces)
    if missing or not members:
        raise SetupError(
            f"Following interfaces do not exist on {primary['name']}: {', '.join(missing) or 'none selected'}"
        )

    payload = {
        "type": "EtherChannelInterface",
        "mode": "NONE",
        "selectedInterfaces": members,
        "etherChannelId": int(etherchannel_id),
        "lacpMode": "ACTIVE",
        "hardware": {"speed": "THOUSAND", "duplex": "FULL", "autoNegState": True},
        "nveOnly": False,
        "enabled": True,
        "MTU": 1500,
        "priority": 0,
        "managementOnly": False,
        "securityZone": {"id": zones[zone_name]["id"], "type": "SecurityZone"},
        "ifname": etherchannel_name,
        "enableSGTPropagate": True,
        "ipv4": {"static": {}},
    }
    response = fmc.post(f"devices/devicerecords/{primary['id']}/etherchannelinterfaces", payload)
    report(response, "Port channel has been created in FMC.")


def add_subinterfaces(fmc, workbook):
    print("Adding Subinterfaces")
    primary = get_primary_fw(fmc, workbook)
    zones = by_name(fmc.get_all("object/securityzones"))
    etherchannels = by_name(fmc.get_all(f"devices/devicerecords/{primary['id']}/etherchannelinterfaces"))

    # Columns: A Port-channel, B VLAN, C name, D IP address, E netmask, F security zone
    for etherchannel, vlan, name, ip_address, netmask, zone_name in data_rows(
        workbook.sheet("SubInterfaces"), 6
    ):
        if etherchannel not in etherchannels:
            print(f"{etherchannel} does not exist on {primary['name']} - {name} skipped.")
            continue
        if zone_name not in zones:
            print(f"{zone_name} does not exist on FMC - {name} skipped.")
            continue
        payload = {
            "type": "SubInterface",
            "name": etherchannel,
            "vlanId": int(vlan),
            "subIntfId": int(vlan),
            "enabled": True,
            "MTU": 1500,
            "managementOnly": False,
            "mode": "NONE",
            "securityZone": {"id": zones[zone_name]["id"], "type": "SecurityZone"},
            "ifname": name,
            "ipv4": {"static": {"address": ip_address, "netmask": netmask}},
        }
        response = fmc.post(f"devices/devicerecords/{primary['id']}/subinterfaces", payload)
        report(response, f"Subinterface {etherchannel}.{vlan} ({name}) has been created in FMC.")
