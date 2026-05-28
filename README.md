# csv_to_parquet_enabler

A tiny CLI that converts a CSV file into a Snappy-compressed Parquet file and emits a matching **Athena `CREATE EXTERNAL TABLE` DDL**. The S3 `LOCATION` is left as a placeholder (`s3://<FILL-ME-IN>/`) so you can paste in your bucket/prefix after uploading.

## Why

If your workflow is "CSV → Parquet → upload to S3 → run Athena DDL," this tool handles the first and third steps so you only have to do the upload yourself.

You install this **once**, and then run `csv2parquet some_file.csv` from any directory on your machine — no need to copy the script around.

## Requirements

- Python 3.9+
- `pandas`, `pyarrow` (installed automatically)

## Install

```bash
git clone https://github.com/yogi-dpi/csv_to_parquet_enabler.git
cd csv_to_parquet_enabler

python -m venv .venv
source .venv/bin/activate          # macOS/Linux
# .venv\Scripts\activate           # Windows PowerShell

pip install -e .
```

`pip install -e .` installs the package in editable mode and puts a `csv2parquet` command on your PATH (active whenever the venv is activated).

> **Want it always available without activating a venv?** Install into your user environment instead: `pip install --user .` (run from the cloned repo). Then `csv2parquet` works from any shell.

### Reactivating in a new shell session

> **Note:** If you used the venv install above, you must reactivate it in every new terminal session before `csv2parquet` will be found. You do **not** need to reinstall — the venv persists on disk.
>
> Two equivalent options:
>
> ```bash
> # Option 1 — activate by absolute path (works from any directory)
> source ~/Documents/repository/csv_to_parquet_extractor/.venv/bin/activate
> ```
>
> ```bash
> # Option 2 — cd into the repo first, then activate by relative path
> cd ~/Documents/repository/csv_to_parquet_extractor
> source .venv/bin/activate
> ```
>
> Once activated, run `csv2parquet` from whatever folder your CSV lives in. Run `deactivate` when you're done.
>
> This step is **not** needed if you installed with `pip install --user .` — that install is always on PATH.

## Usage

After installing, run from **any folder** that contains a CSV:

```bash
# In whatever directory your CSV lives
cd ~/data/2026-q1
csv2parquet sales.csv
# → writes sales.parquet and sales.sql right next to sales.csv
```

```bash
# Custom output directory and Athena table name
csv2parquet sales.csv -o build/ -t sales_2026
```

### CLI flags

| Flag | Description | Default |
|---|---|---|
| `<input.csv>` | Path to the CSV file | required |
| `-o`, `--output-dir` | Where to write the `.parquet` and `.sql` | same directory as the input |
| `-t`, `--table` | Athena table name in the DDL | input filename (without extension) |

### Quick smoke-test with the included sample

```bash
csv2parquet sample.csv
```

## What you get

Running `csv2parquet sample.csv` produces two files alongside the input:

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

The tool reads the Parquet file's schema (via pyarrow) and maps types to Athena/Hive types:

| Parquet / Arrow type | Athena type |
|---|---|
| `int64` | `BIGINT` |
| `int32` | `INT` |
| `int16` | `SMALLINT` |
| `int8` | `TINYINT` |
| `double` | `DOUBLE` |
| `float` | `FLOAT` |
| `bool` | `BOOLEAN` |
| `timestamp` | `TIMESTAMP` |
| `date32` / `date64` | `DATE` |
| `decimal128(p,s)` | `DECIMAL(p,s)` |
| anything else | `STRING` |

The DDL is generated from the actual Parquet schema, so it always matches what Athena will see when reading the file.

## Don't want to install? Run the script directly

If you'd rather not install anything, you can still run the script directly with an absolute path — no copy needed:

```bash
python /path/to/csv_to_parquet_enabler/csv2parquet.py /any/folder/data.csv
```

You'll need `pandas` and `pyarrow` available in whichever Python you invoke (`pip install -r requirements.txt`).

## Scope (intentional)

- **Local files only.** No S3 reads, no AWS auth.
- **No partitioning.** One CSV → one Parquet file.
- **Column names preserved verbatim** (wrapped in backticks in the DDL).

If you need partitioning, S3 reads, or batch globbing, open an issue.

## License

MIT — see [LICENSE](LICENSE).
