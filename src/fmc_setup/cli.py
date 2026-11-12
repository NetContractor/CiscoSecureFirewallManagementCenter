"""Command line interface and interactive menu."""

import argparse
import functools
import os
import sys

import requests

from fmc_setup import __version__, actions
from fmc_setup.client import FMCClient, SetupError
from fmc_setup.config_export import export_configuration
from fmc_setup.console import read_secret
from fmc_setup.export import export_policy_to_csv
from fmc_setup.workbook import SetupWorkbook

DEFAULT_WORKBOOK = "fmc-setup.xlsx"
DEFAULT_USERNAME = "admin"

MENU = (
    ("1", "Register new FTD devices from the xlsx", actions.register_devices),
    ("2", "Configure interfaces from the xlsx", actions.configure_interfaces),
    ("3", "Add security zones from the xlsx", actions.add_security_zones),
    ("4", "Add new Access Control Policy", actions.add_access_policy),
    ("5", "Add categories from the xlsx", actions.add_categories),
    ("6", "Add ports from the xlsx", actions.add_ports),
    ("7", "Add port groups from the xlsx", actions.add_port_groups),
    ("8", "Add host, network or range from the xlsx", actions.add_hosts_networks),
    ("9", "Add network group from the xlsx", actions.add_network_groups),
    ("10", "Add ACP from the xlsx", actions.add_access_rules),
    ("11", "Export policy to the csv", export_policy_to_csv),
    ("12", "Export FMC configuration to the xlsx", export_configuration),
    ("13", "Add HA", actions.add_ha),
    ("14", "Add Port-Channel", actions.add_etherchannel),
    ("15", "Add subinterface to Port-Channel", actions.add_subinterfaces),
    ("16", "END program", None),
)


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        prog="fmc-setup",
        description="Configure Cisco Secure Firewall Management Center (FMC) from an Excel workbook.",
    )
    parser.add_argument(
        "-w", "--workbook", default=os.environ.get("FMC_SETUP_WORKBOOK", DEFAULT_WORKBOOK),
        help=f"setup workbook (env FMC_SETUP_WORKBOOK, default: {DEFAULT_WORKBOOK})",
    )
    parser.add_argument("--host", default=os.environ.get("FMC_HOST"), help="FMC address (env FMC_HOST)")
    parser.add_argument("-u", "--username", default=os.environ.get("FMC_USER"), help="FMC user (env FMC_USER)")
    parser.add_argument(
        "--ca-cert", default=os.environ.get("FMC_CA_CERT"),
        help="CA bundle used to verify the FMC certificate (env FMC_CA_CERT). "
             "Without it the certificate is not verified.",
    )
    parser.add_argument("--output-dir", default=".", help="directory for CSV and xlsx export (default: current)")
    parser.add_argument(
        "-o", "--option", action="append", choices=[number for number, _, _ in MENU], metavar="NUMBER",
        help="run menu option(s) in the given order and exit instead of showing the menu",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser.parse_args(argv)


def connect(args):
    host = args.host or input("FMC address: ").strip()
    if not host:
        raise SetupError("FMC address is required")
    username = args.username or input(f"Username [{DEFAULT_USERNAME}]: ").strip() or DEFAULT_USERNAME
    password = os.environ.get("FMC_PASSWORD") or read_secret("Password: ")
    return FMCClient(host, username, password, verify=args.ca_cert or False)


def run_option(action, fmc, workbook):
    try:
        action(fmc, workbook)
    except SetupError as err:
        print(f"ERROR: {err}")
    except requests.RequestException as err:
        print("Error in connection --> " + str(err))


def print_menu():
    print()
    print("What would you like to do? Please select one of the following option: ")
    print()
    for number, description, _ in MENU:
        print(f"{number}. {description}")
    print()


def main(argv=None):
    try:
        run(parse_args(argv))
    except (KeyboardInterrupt, EOFError):
        print()
        sys.exit(130)


def run(args):
    workbook = SetupWorkbook(args.workbook)
    actions_by_number = {number: action for number, _, action in MENU}
    actions_by_number["11"] = functools.partial(export_policy_to_csv, output_dir=args.output_dir)
    actions_by_number["12"] = functools.partial(export_configuration, output_dir=args.output_dir)

    try:
        fmc = connect(args)
    except (SetupError, requests.RequestException) as err:
        print("Error in generating auth token --> " + str(err))
        sys.exit(1)

    if args.option:
        for number in args.option:
            action = actions_by_number[number]
            if action is None:
                break
            run_option(action, fmc, workbook)
        return

    while True:
        print_menu()
        selection = input("Please select option number: ").strip()
        if selection not in actions_by_number:
            print()
            print("Incorrect selection. Please try again.")
            continue
        action = actions_by_number[selection]
        if action is None:
            break
        run_option(action, fmc, workbook)


if __name__ == "__main__":
    main()
