"""Convert CSV files to JSON and JSON files to CSV.

Console usage:
    python csv_json.py                      # asks for a file, then what to do
    python csv_json.py nairobi_cities.csv   # converts straight away

The convert functions can also be imported, e.g. by a future interface:
    from csv_json import csv_to_json, json_to_csv
"""
import sys
import csv
import json
from pathlib import Path


class ConversionError(Exception):
    """Raised when a file cannot be converted."""


# ---------- CSV -> JSON ----------

def _parse_value(value):
    """Turn CSV text into a number where that is safe, otherwise keep it as text."""
    text = value.strip()
    if text == "":
        return None
    # Keep values like phone numbers or IDs ("0712...") as text
    if len(text) > 1 and text[0] == "0" and text[1] != ".":
        return value
    try:
        return int(text)
    except ValueError:
        pass
    try:
        return float(text)
    except ValueError:
        return value


def read_csv(path, convert_numbers=True):
    """Read a CSV file into a list of dicts, one per row."""
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            raise ConversionError(f"{path} is empty or has no header row.")
        rows = []
        for row in reader:
            row.pop(None, None)  # extra cells that have no header
            if convert_numbers:
                row = {k: _parse_value(v) if v is not None else None for k, v in row.items()}
            rows.append(row)
    return rows


def csv_to_json(csv_path, json_path=None, convert_numbers=True, overwrite=False):
    """Convert a CSV file to a JSON file. Returns the path of the new file."""
    csv_path = Path(csv_path)
    json_path = Path(json_path) if json_path else csv_path.with_suffix(".json")
    if json_path.exists() and not overwrite:
        raise FileExistsError(json_path)

    rows = read_csv(csv_path, convert_numbers)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(rows, f, indent=2, ensure_ascii=False)
    return json_path


# ---------- JSON -> CSV ----------

def _flatten(obj, prefix=""):
    """Flatten nested dicts into one level: {"a": {"b": 1}} -> {"a.b": 1}."""
    flat = {}
    for key, value in obj.items():
        name = f"{prefix}.{key}" if prefix else str(key)
        if isinstance(value, dict):
            flat.update(_flatten(value, name))
        elif isinstance(value, list):
            flat[name] = json.dumps(value, ensure_ascii=False)
        else:
            flat[name] = value
    return flat


def read_json_records(path):
    """Read a JSON file and return it as a list of flat dicts (rows)."""
    with open(path, encoding="utf-8-sig") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError as e:
            raise ConversionError(f"{path} is not valid JSON: {e}") from None

    # Accept {"items": [...]} style files by using the first list inside them
    if isinstance(data, dict):
        lists = [v for v in data.values() if isinstance(v, list)]
        data = lists[0] if len(lists) == 1 else [data]

    if not isinstance(data, list):
        raise ConversionError("JSON must be a list of objects (or an object) to become a CSV.")
    if not data:
        raise ConversionError(f"{path} contains no records.")

    rows = []
    for item in data:
        rows.append(_flatten(item) if isinstance(item, dict) else {"value": item})
    return rows


def json_to_csv(json_path, csv_path=None, overwrite=False):
    """Convert a JSON file to a CSV file. Returns the path of the new file."""
    json_path = Path(json_path)
    csv_path = Path(csv_path) if csv_path else json_path.with_suffix(".csv")
    if csv_path.exists() and not overwrite:
        raise FileExistsError(csv_path)

    rows = read_json_records(json_path)

    # Columns in the order they first appear across all rows
    columns = list(dict.fromkeys(key for row in rows for key in row))

    # utf-8-sig so Excel shows accents and symbols correctly
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: "" if v is None else v for k, v in row.items()})
    return csv_path


# ---------- Console ----------

CONVERTERS = {
    ".csv": ("JSON", csv_to_json),
    ".json": ("CSV", json_to_csv),
}


def ask(prompt):
    try:
        return input(prompt).strip()
    except (EOFError, KeyboardInterrupt):
        print()
        sys.exit(0)


def ask_for_file():
    while True:
        text = ask("Path to a .csv or .json file (or 'q' to quit): ").strip('"').strip("'")
        if text.lower() in ("q", "quit", "exit"):
            sys.exit(0)
        path = Path(text).expanduser()
        if not path.is_file():
            print(f"  File not found: {path}")
        elif path.suffix.lower() not in CONVERTERS:
            print("  Only .csv and .json files are supported.")
        else:
            return path


def convert_interactively(path):
    target, convert = CONVERTERS[path.suffix.lower()]

    choice = ask(f"Convert {path.name} to {target}? [Y/n]: ").lower()
    if choice not in ("", "y", "yes"):
        print("  Skipped.")
        return

    try:
        out = convert(path)
    except FileExistsError as e:
        if ask(f"  {Path(str(e)).name} already exists. Overwrite? [y/N]: ").lower() not in ("y", "yes"):
            print("  Skipped.")
            return
        out = convert(path, overwrite=True)
    except (ConversionError, csv.Error, UnicodeDecodeError) as e:
        print(f"  Could not convert: {e}")
        return

    print(f"  Saved {out}")


def main():
    files = [Path(arg) for arg in sys.argv[1:]]
    if files:
        for path in files:
            if not path.is_file() or path.suffix.lower() not in CONVERTERS:
                print(f"Skipping {path}: not an existing .csv or .json file.")
                continue
            convert_interactively(path)
        return

    print("CSV <-> JSON converter")
    while True:
        convert_interactively(ask_for_file())
        if ask("Convert another file? [y/N]: ").lower() not in ("y", "yes"):
            break


if __name__ == "__main__":
    main()
