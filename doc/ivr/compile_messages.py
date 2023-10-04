#!/usr/bin/env python3

import csv
from pathlib import Path
import re
from typing import Dict, Optional, Sequence

import xlsxwriter
import yaml


POINT_ID = re.compile(r"^talkingPoints\.points\.([0-9]+)\.")
POINT_PREFIX = "talkingPoints.points."


csv.register_dialect("fully_quoted", quoting=csv.QUOTE_NONNUMERIC)


def load_messages(path: Path):
    with path.open(newline="") as stream:
        reader = csv.DictReader(stream)
        rows = {
            row["ID"]: {
                col: "" if val is None else val
                for col, val in row.items()
                if col != "ID"
            }
            for row in reader
        }
    langs = tuple(
        lang
        for lang in next(iter(rows.values())).keys()
        if lang != "Comment"
    )
    return rows, langs


def load_arguments(path: Path, langs: Sequence[str]):
    def point(strings: Dict[str, Dict[str, str]], num: int, lang: str):
        pre = f"{POINT_PREFIX}{num}."
        return (
            strings[f"{pre}title"][lang] +
            ": " +
            strings[f"{pre}body"][lang]
        )

    with path.open() as stream:
        yaml_dict = yaml.load(stream, yaml.Loader)
    strings = yaml_dict["l10n"]["frontend_strings"]
    # Collect talking point IDs.
    ids = set(
        int(match[1])
        for key in strings
        if (match := POINT_ID.match(key))
    )
    args = {
        f"argument_{num}": {
            lang: point(strings, num, lang)
            for lang in langs
        }
        for num in ids
    }
    return args


def write_csv(path: Path, rows):
    fields = ("ID",) + tuple(next(iter(rows.values())).keys())
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fields, dialect="fully_quoted")
        writer.writeheader()
        for id, vals in rows.items():
            writer.writerow({ "ID": id, **vals })


def write_xlsx(path: Path, rows):
    fields = ("ID",) + tuple(next(iter(rows.values())).keys())
    with xlsxwriter.Workbook(path) as workbook:
        bold = workbook.add_format({"bold": True})
        sheet = workbook.add_worksheet("DearMEP IVR")
        for pos, field in enumerate(fields):
            sheet.write_string(0, pos, field, bold)
        for rownum, (id, row) in enumerate(rows.items(), 1):
            sheet.write_string(rownum, 0, id, bold)
            for field, text in row.items():
                if len(text):
                    sheet.write_string(rownum, fields.index(field), text)
        sheet.freeze_panes(1, 1)
        sheet.autofit()


def run(repo_root: Optional[Path] = None):
    if not repo_root:
        repo_root = Path(__file__).parent.parent.parent
    ivr_dir = repo_root / "doc" / "ivr"
    dearmep_dir = repo_root / "server" / "dearmep"

    msgs, langs = load_messages(ivr_dir / "messages.csv")
    args = load_arguments(dearmep_dir / "example-config.yaml", langs)

    combined = { **msgs, **args }

    write_csv(ivr_dir / "combined.csv", combined)
    write_xlsx(ivr_dir / "combined.xlsx", combined)


if __name__ == "__main__":
    run()
