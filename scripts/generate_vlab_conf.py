#!/usr/bin/env python3

"""
Generates a vlab.conf file from a student spreadsheet (.xlsx).

Reads usernames from column A of the spreadsheet and creates a VLAB
configuration with 'ian' as overlord and each student allowed to use
the vlab_zybo board class.

Usage:
    ./generate_vlab_conf.py /path/to/students.xlsx -o vlab.conf
    ./generate_vlab_conf.py /path/to/students.xlsx -o vlab.conf --boards 210279777433 210279771877
"""

import argparse
import json
import sys

try:
    import openpyxl
except ImportError:
    print("Error: openpyxl is required. Install with: pip3 install openpyxl", file=sys.stderr)
    sys.exit(1)


def read_usernames(xlsx_path):
    """Read usernames from column A of the first sheet."""
    wb = openpyxl.load_workbook(xlsx_path, read_only=True, data_only=True)
    ws = wb.active
    usernames = []
    for row in ws.iter_rows(min_col=1, max_col=1, values_only=True):
        val = row[0]
        if val is not None:
            username = str(val).strip()
            if username:
                usernames.append(username)
    wb.close()
    return usernames


def generate_config(usernames, board_class, boards):
    """Build the vlab.conf dictionary."""
    users = {"ian": {"overlord": True}}
    for username in usernames:
        users[username] = {"allowedboards": [board_class]}

    boards_dict = {}
    for serial in boards:
        boards_dict[serial] = {"class": board_class, "type": "zybo", "reset": "true"}

    return {"users": users, "boards": boards_dict}


def main():
    parser = argparse.ArgumentParser(description="Generate vlab.conf from a student spreadsheet")
    parser.add_argument("spreadsheet", help="Path to the .xlsx file with student usernames in column A")
    parser.add_argument("-o", "--output", default="vlab.conf", help="Output file path (default: vlab.conf)")
    parser.add_argument("-c", "--board-class", default="vlab_zybo", help="Board class name (default: vlab_zybo)")
    parser.add_argument("--boards", nargs="*", default=[], metavar="SERIAL",
                        help="Board serial numbers to include")
    args = parser.parse_args()

    usernames = read_usernames(args.spreadsheet)
    if not usernames:
        print("Error: No usernames found in spreadsheet", file=sys.stderr)
        sys.exit(1)

    config = generate_config(usernames, args.board_class, args.boards)

    with open(args.output, "w") as f:
        json.dump(config, f, indent="\t")
        f.write("\n")

    print("Generated {} with {} students and {} boards -> {}".format(
        args.output, len(usernames), len(args.boards), args.output))


if __name__ == "__main__":
    main()
