#!/usr/bin/env python3
import argparse


def count_reads(path: str) -> int:
    lines = 0
    with open(path, "rb") as handle:
        for _ in handle:
            lines += 1
    if lines % 4:
        raise ValueError(f"Invalid FASTQ line count in {path}: {lines}")
    return lines // 4


parser = argparse.ArgumentParser()
parser.add_argument("--stats", required=True)
parser.add_argument("--deduplicated-r1", required=True)
parser.add_argument("--host-depleted-r1", required=True)
parser.add_argument("--layout", choices=("paired", "single"), default="paired")
args = parser.parse_args()

before = count_reads(args.deduplicated_r1)
after = count_reads(args.host_depleted_r1)
removed_percent = round(((before - after) / before * 100), 3) if before else 0.0

with open(args.stats, "a", encoding="utf-8") as handle:
    unit = "read_pairs" if args.layout == "paired" else "reads"
    handle.write(f"host_depleted_{unit}\t{after}\n")
    handle.write(f"host_removed_percent\t{removed_percent}\n")
