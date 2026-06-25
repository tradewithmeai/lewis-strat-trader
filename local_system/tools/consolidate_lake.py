#!/usr/bin/env python3
"""
Memory-safe, crash-safe, idempotent crypto-lake consolidation.

Merges the many per-minute parquet files the live collector writes for a day
into a single `consolidated.parquet`, so the backtest harness (which reads only
low-file-count "backfill" days) keeps seeing recent data instead of stopping at
the last consolidated day.

Why this exists rather than crypto-lake-rs `tools/archive.py consolidate`:
  - archive.py reuses ONE DuckDB connection across all partitions; on a small-RAM
    box the connection's memory accumulates until the kernel OOM-kills it
    (observed 2026-06-24 on the 5.7 GiB VPS). Here every partition gets a FRESH
    connection capped at 512 MB, so memory cannot accumulate.
  - This merges the existing consolidated.parquet back in and DEDUPES on
    window_start, so a late backfill that drops a few files into an
    already-consolidated day cannot lose or duplicate data.
  - Writes via .tmp + rename-before-delete, so an interrupt can never leave a day
    invisible to the backtester.

Run niced / IO-idle / MemoryMax-capped under systemd (see lake-consolidate.timer).

Usage: consolidate_lake.py [DAYS_OLDER]
  DAYS_OLDER (default 2): only consolidate day-partitions strictly older than
  (today - DAYS_OLDER), leaving the most recent day(s) raw so collector backfill
  can settle first.
"""
import os
import sys
from datetime import date, timedelta
from pathlib import Path

import duckdb

LAKE = Path(os.environ.get("LAKE_ROOT", os.path.expanduser("~/crypto-lake-rs/data/parquet")))
DAYS_OLDER = int(sys.argv[1]) if len(sys.argv) > 1 else 2
CUTOFF = date.today() - timedelta(days=DAYS_OLDER)
MEM = "512MB"
CONS = "consolidated.parquet"


def targets():
    """Yield day-dirs older than CUTOFF that hold >1 parquet file (i.e. not yet,
    or no longer, a single consolidated file)."""
    for ex in sorted(p for p in LAKE.iterdir() if p.is_dir()):
        for sym in sorted(p for p in ex.iterdir() if p.is_dir()):
            for y in sorted(sym.glob("year=*")):
                for m in sorted(y.glob("month=*")):
                    for d in sorted(m.glob("day=*")):
                        try:
                            pd = date(int(y.name[5:]), int(m.name[6:]), int(d.name[4:]))
                        except ValueError:
                            continue
                        if pd >= CUTOFF:
                            continue
                        # *.parquet does not match the *.parquet.tmp work file
                        if len(list(d.glob("*.parquet"))) > 1:
                            yield d


def _merge(src_glob, out_path):
    """Merge all parquet matching src_glob into out_path, deduping on window_start.
    Fresh connection, 512 MB cap. Returns row count."""
    con = duckdb.connect()
    try:
        con.execute(f"SET memory_limit='{MEM}'")
        con.execute("SET threads TO 1")
        con.execute(
            f"COPY (SELECT * FROM read_parquet('{src_glob}') "
            f"QUALIFY row_number() OVER (PARTITION BY window_start ORDER BY window_start) = 1 "
            f"ORDER BY window_start) "
            f"TO '{out_path}' (FORMAT PARQUET, COMPRESSION 'zstd')"
        )
        return con.execute(f"SELECT count(*) FROM read_parquet('{out_path}')").fetchone()[0]
    finally:
        con.close()


def main():
    tl = list(targets())
    print(f"targets: {len(tl)} day-partitions older than {CUTOFF} (cap {MEM}/partition)", flush=True)
    done = errs = 0
    for d in tl:
        cons = d / CONS
        tmp = d / (CONS + ".tmp")
        gall = str(d).replace("\\", "/") + "/*.parquet"
        out = str(tmp).replace("\\", "/")
        try:
            if tmp.exists():
                tmp.unlink()
            try:
                n = _merge(gall, out)               # include existing consolidated.parquet; dedupe
            except Exception:
                # a corrupt partial consolidated.parquet from a prior interrupt can
                # break the read — drop it and rebuild from the raw per-minute files
                if cons.exists():
                    cons.unlink()
                if tmp.exists():
                    tmp.unlink()
                n = _merge(gall, out)
            if n <= 0:
                raise RuntimeError("empty consolidated output")
            tmp.rename(cons)                          # atomic: new full file in place FIRST
            for f in d.glob("*.parquet"):             # then drop the per-minute originals
                if f.name != CONS:
                    f.unlink()
            done += 1
            if done % 20 == 0:
                print(f"  ...{done}/{len(tl)}", flush=True)
        except Exception as e:
            errs += 1
            try:
                if tmp.exists():
                    tmp.unlink()
            except Exception:
                pass
            print(f"  ERROR {d}: {e}", flush=True)
    print(f"DONE processed={done} errors={errs} of {len(tl)} targets", flush=True)


if __name__ == "__main__":
    main()
