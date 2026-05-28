"""Convert a CSV to Parquet and emit a matching Athena CREATE EXTERNAL TABLE DDL.

Usage:
    python csv2parquet.py input.csv
    python csv2parquet.py input.csv -o out/ -t my_table
"""

import argparse
import re
import sys
from datetime import date
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq
from pyarrow import types


ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


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


def convert_iso_date_columns(df: "pd.DataFrame") -> None:
    """In-place: convert object columns whose non-null values all match
    YYYY-MM-DD into Python date objects, so pyarrow writes them as date32.

    Using Python date (not pandas datetime64[ns]) preserves out-of-range
    sentinels like 9999-12-31 that overflow pandas' nanosecond timestamps.
    """
    for col in df.columns:
        if df[col].dtype != object:
            continue
        non_null = df[col].dropna()
        if non_null.empty:
            continue
        if not non_null.map(lambda v: isinstance(v, str) and bool(ISO_DATE_RE.match(v))).all():
            continue
        df[col] = df[col].map(lambda v: date.fromisoformat(v) if isinstance(v, str) else None)


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
    original_rows = len(df)
    df = df.dropna(how="all").reset_index(drop=True)
    dropped = original_rows - len(df)
    if dropped:
        print(f"dropped {dropped} fully-empty row(s)")
    downcast_integer_floats(df)
    convert_iso_date_columns(df)
    df.to_parquet(parquet_path, compression="snappy", index=False)
    schema = pq.read_schema(parquet_path)
    sql_path.write_text(build_ddl(table, schema))

    print(f"wrote {parquet_path} ({len(df)} rows, {len(df.columns)} cols)")
    print(f"wrote {sql_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
