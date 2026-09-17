#!/usr/bin/env python3
import argparse
from pathlib import Path


def count_reads(path: str) -> int:
    lines = 0
    with open(path, "rb") as handle:
        for _ in handle:
            lines += 1
    if lines % 4:
        raise ValueError(f"Invalid FASTQ line count in {path}: {lines}")
    return lines // 4


parser = argparse.ArgumentParser()
parser.add_argument("--raw-r1", required=True)
parser.add_argument("--trimmed-r1", required=True)
parser.add_argument("--deduplicated-r1", required=True)
parser.add_argument("--output", required=True)
parser.add_argument("--layout", choices=("paired", "single"), default="paired")
args = parser.parse_args()

unit = "read_pairs" if args.layout == "paired" else "reads"
values = {
    f"raw_{unit}": count_reads(args.raw_r1),
    f"quality_retained_{unit}": count_reads(args.trimmed_r1),
    f"deduplicated_{unit}": count_reads(args.deduplicated_r1),
}

output = Path(args.output)
output.parent.mkdir(parents=True, exist_ok=True)
with output.open("w", encoding="utf-8") as handle:
    handle.write("metric\tvalue\n")
    for metric, value in values.items():
        handle.write(f"{metric}\t{value}\n")
