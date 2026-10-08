import csv
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Point:
    values: list[float]
    mode: str


def load_points(csv_path: str | Path, default_mode: str) -> list[Point]:
    """Load six-value rows. Headers may use x1..x6 or j1..j6."""
    path = Path(csv_path)
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise ValueError("CSV must have a header row")

        names = {name.strip().lower(): name for name in reader.fieldnames}
        value_columns = _find_value_columns(names)
        mode_column = names.get("mode")
        points = []
        for line_number, row in enumerate(reader, start=2):
            try:
                values = [float(row[column]) for column in value_columns]
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError(f"Invalid point at CSV line {line_number}") from exc
            mode = (row.get(mode_column, "") if mode_column else "").strip()
            points.append(Point(values, mode or default_mode))

    if not points:
        raise ValueError("CSV contains no movement points")
    return points


def _find_value_columns(names: dict[str, str]) -> list[str]:
    for prefix in ("x", "j", "p", "value"):
        columns = [names.get(f"{prefix}{index}") for index in range(1, 7)]
        if all(columns):
            return columns
    raise ValueError("CSV needs x1..x6, j1..j6, p1..p6, or value1..value6 columns")
