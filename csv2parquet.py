"""Convert a CSV to Parquet and emit a matching Athena CREATE EXTERNAL TABLE DDL.

Usage:
    python csv2parquet.py input.csv
    python csv2parquet.py input.csv -o out/ -t my_table
"""

import argparse
import sys
from pathlib import Path

import pandas as pd


PANDAS_TO_ATHENA = {
    "int64": "BIGINT",
    "Int64": "BIGINT",
    "int32": "INT",
    "Int32": "INT",
    "int16": "SMALLINT",
    "int8": "TINYINT",
    "float64": "DOUBLE",
    "float32": "FLOAT",
    "bool": "BOOLEAN",
    "boolean": "BOOLEAN",
    "datetime64[ns]": "TIMESTAMP",
    "object": "STRING",
    "string": "STRING",
}


def athena_type(pandas_dtype) -> str:
    name = str(pandas_dtype)
    if name.startswith("datetime64"):
        return "TIMESTAMP"
    return PANDAS_TO_ATHENA.get(name, "STRING")


def build_ddl(table: str, dtypes: "pd.Series") -> str:
    columns = ",\n  ".join(
        f"`{col}` {athena_type(dt)}" for col, dt in dtypes.items()
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
    df.to_parquet(parquet_path, compression="snappy", index=False)
    sql_path.write_text(build_ddl(table, df.dtypes))

    print(f"wrote {parquet_path} ({len(df)} rows, {len(df.columns)} cols)")
    print(f"wrote {sql_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
