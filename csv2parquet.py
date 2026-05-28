"""Convert a CSV to Parquet and emit a matching Athena CREATE EXTERNAL TABLE DDL.

Usage:
    python csv2parquet.py input.csv
    python csv2parquet.py input.csv -o out/ -t my_table
"""

import argparse
import re
import sys
from datetime import date, datetime
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq
from pyarrow import types


ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
US_DATE_RE = re.compile(r"^\d{1,2}/\d{1,2}/\d{4}$")
NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")


def normalize_column_names(df: "pd.DataFrame") -> dict:
    """In-place: rename columns to snake_case ascii. Returns the rename map.

    Lowercase, replace any run of non-alphanumeric characters with a single
    underscore, trim leading/trailing underscores. Also strips a leading
    UTF-8 BOM if pandas didn't already.
    """
    rename = {}
    for col in df.columns:
        cleaned = col.lstrip("﻿").strip().lower()
        cleaned = NON_ALNUM_RE.sub("_", cleaned).strip("_")
        if not cleaned:
            cleaned = "unnamed"
        rename[col] = cleaned
    df.rename(columns=rename, inplace=True)
    return rename


def strip_string_values(df: "pd.DataFrame") -> None:
    """In-place: trim leading/trailing whitespace on every string-typed column.

    Leaves NaN as NaN. Empty strings stay empty. Casing is preserved.
    """
    for col in df.columns:
        if df[col].dtype != object:
            continue
        df[col] = df[col].map(lambda v: v.strip() if isinstance(v, str) else v)


def downcast_integer_floats(df: "pd.DataFrame") -> None:
    """In-place: convert float columns to nullable Int64 when every non-null
    value is a whole number. Empty columns are left untouched (no signal to
    downcast). Uses pandas' nullable Int64 so NaN-bearing columns survive.
    """
    for col in df.columns:
        if df[col].dtype.kind != "f":
            continue
        non_null = df[col].dropna()
        if non_null.empty:
            continue
        if (non_null % 1 == 0).all():
            df[col] = df[col].astype("Int64")


def _parse_date(value: str):
    """Parse a single date string in YYYY-MM-DD or M/D/YYYY format.
    Returns a datetime.date or None if the value is not a string.
    """
    if not isinstance(value, str):
        return None
    if ISO_DATE_RE.match(value):
        return date.fromisoformat(value)
    if US_DATE_RE.match(value):
        return datetime.strptime(value, "%m/%d/%Y").date()
    return None


def convert_date_columns(df: "pd.DataFrame") -> None:
    """In-place: convert object columns whose non-null values all match a
    supported date format (YYYY-MM-DD or US-style M/D/YYYY) into Python date
    objects, so pyarrow writes them as date32 (Athena DATE).

    Strict mode: a single non-parseable value blocks conversion. If a column
    looks date-like (>=50% of non-null values parse) but has bad cells, the
    bad values are printed with their original CSV line numbers and the
    column stays as STRING so no data is silently lost.

    Using Python date (not pandas datetime64[ns]) preserves out-of-range
    sentinels like 9999-12-31 that overflow pandas' nanosecond timestamps.
    """
    for col in df.columns:
        if df[col].dtype != object:
            continue
        non_null = df[col].dropna()
        if non_null.empty:
            continue
        matches = non_null.map(
            lambda v: isinstance(v, str) and bool(ISO_DATE_RE.match(v) or US_DATE_RE.match(v))
        )
        if matches.all():
            df[col] = df[col].map(lambda v: _parse_date(v) if isinstance(v, str) else None)
            continue
        if matches.mean() < 0.5:
            continue
        bad = non_null[~matches]
        print(
            f"warning: column {col!r} looks date-like "
            f"({matches.sum()}/{len(non_null)} parse OK) but {len(bad)} bad cell(s) found; "
            f"keeping as STRING. Fix the source and re-run."
        )
        for idx, val in bad.head(20).items():
            print(f"         line {idx + 2}: {val!r}")
        if len(bad) > 20:
            print(f"         ... and {len(bad) - 20} more")


def athena_type(arrow_type) -> str:
    if types.is_int8(arrow_type):
        return "TINYINT"
    if types.is_int16(arrow_type):
        return "SMALLINT"
    if types.is_int32(arrow_type):
        return "INT"
    if types.is_int64(arrow_type):
        return "BIGINT"
    if types.is_float32(arrow_type):
        return "FLOAT"
    if types.is_float64(arrow_type):
        return "DOUBLE"
    if types.is_boolean(arrow_type):
        return "BOOLEAN"
    if types.is_timestamp(arrow_type):
        return "TIMESTAMP"
    if types.is_date(arrow_type):
        return "DATE"
    if types.is_decimal(arrow_type):
        return f"DECIMAL({arrow_type.precision},{arrow_type.scale})"
    return "STRING"


def build_ddl(table: str, schema: "pq.ParquetSchema") -> str:
    columns = ",\n  ".join(
        f"`{field.name}` {athena_type(field.type)}" for field in schema
    )
    return (
        f"CREATE EXTERNAL TABLE IF NOT EXISTS `{table}` (\n"
        f"  {columns}\n"
        f")\n"
        f"STORED AS PARQUET\n"
        f"LOCATION 's3://<FILL-ME-IN>/'\n"
        f"TBLPROPERTIES ('parquet.compression'='SNAPPY');\n"
    )


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert a CSV to Parquet and emit an Athena DDL."
    )
    parser.add_argument("input", type=Path, help="Path to the input CSV file.")
    parser.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        default=None,
        help="Directory for .parquet and .sql outputs (default: alongside input).",
    )
    parser.add_argument(
        "-t",
        "--table",
        type=str,
        default=None,
        help="Athena table name (default: input filename stem).",
    )
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)

    if not args.input.is_file():
        print(f"error: input not found: {args.input}", file=sys.stderr)
        return 1

    output_dir = args.output_dir or args.input.parent
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = args.input.stem
    table = args.table or stem
    parquet_path = output_dir / f"{stem}.parquet"
    sql_path = output_dir / f"{stem}.sql"

    df = pd.read_csv(args.input)

    rename = normalize_column_names(df)
    renamed = [(old, new) for old, new in rename.items() if old != new]
    if renamed:
        print(f"renamed {len(renamed)} column(s):")
        for old, new in renamed:
            print(f"  {old!r} -> {new!r}")

    strip_string_values(df)

    original_rows = len(df)
    df = df.dropna(how="all")
    dropped = original_rows - len(df)
    if dropped:
        print(f"dropped {dropped} fully-empty row(s)")
    downcast_integer_floats(df)
    convert_date_columns(df)
    df.to_parquet(parquet_path, compression="snappy", index=False)
    schema = pq.read_schema(parquet_path)
    sql_path.write_text(build_ddl(table, schema))

    print(f"wrote {parquet_path} ({len(df)} rows, {len(df.columns)} cols)")
    print(f"wrote {sql_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
