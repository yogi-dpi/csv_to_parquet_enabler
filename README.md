# csv_to_parquet_enabler

A tiny CLI that converts a CSV file into a Snappy-compressed Parquet file and emits a matching **Athena `CREATE EXTERNAL TABLE` DDL**. The S3 `LOCATION` is left as a placeholder (`s3://<FILL-ME-IN>/`) so you can paste in your bucket/prefix after uploading.

## Why

If your workflow is "CSV → Parquet → upload to S3 → run Athena DDL," this tool handles the first and third steps so you only have to do the upload yourself.

## Requirements

- Python 3.8+
- `pandas`, `pyarrow` (installed via `requirements.txt`)

## Install

```bash
git clone https://github.com/yogi-dpi/csv_to_parquet_enabler.git
cd csv_to_parquet_enabler

python -m venv .venv
source .venv/bin/activate          # macOS/Linux
# .venv\Scripts\activate           # Windows PowerShell

pip install -r requirements.txt
```

## Usage

```bash
# Basic — writes sample.parquet and sample.sql next to the input
python csv2parquet.py sample.csv

# Custom output directory and Athena table name
python csv2parquet.py data/sales.csv -o build/ -t sales_2026
```

### CLI flags

| Flag | Description | Default |
|---|---|---|
| `<input.csv>` | Path to the CSV file | required |
| `-o`, `--output-dir` | Where to write the `.parquet` and `.sql` | same directory as the input |
| `-t`, `--table` | Athena table name in the DDL | input filename (without extension) |

## What you get

Running `python csv2parquet.py sample.csv` produces two files:

**`sample.parquet`** — Snappy-compressed columnar data, Athena-ready.

**`sample.sql`** — DDL like:

```sql
CREATE EXTERNAL TABLE IF NOT EXISTS `sample` (
  `order_id` BIGINT,
  `customer_name` STRING,
  `amount` DOUBLE,
  `is_paid` BOOLEAN,
  `order_date` STRING
)
STORED AS PARQUET
LOCATION 's3://<FILL-ME-IN>/'
TBLPROPERTIES ('parquet.compression'='SNAPPY');
```

Replace `s3://<FILL-ME-IN>/` with the S3 prefix you upload the Parquet file to, then run the DDL in Athena.

## Type mapping

The tool infers types via pandas and maps them to Athena/Hive types:

| Pandas dtype | Athena type |
|---|---|
| `int64` | `BIGINT` |
| `int32` | `INT` |
| `float64` | `DOUBLE` |
| `float32` | `FLOAT` |
| `bool` | `BOOLEAN` |
| `datetime64[ns]` | `TIMESTAMP` |
| `object` (anything else) | `STRING` |

If pandas reads a column as `object` (e.g., a date that wasn't auto-parsed), it lands as `STRING` in the DDL. Cast in your Athena queries as needed.

## Scope (intentional)

- **Local files only.** No S3 reads, no AWS auth.
- **No partitioning.** One CSV → one Parquet file.
- **Column names preserved verbatim** (wrapped in backticks in the DDL).

If you need partitioning, S3 reads, or batch globbing, open an issue.

## License

MIT — see [LICENSE](LICENSE).
