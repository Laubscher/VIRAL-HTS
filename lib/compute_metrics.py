#!/usr/bin/env python3
import argparse
import csv
from collections import defaultdict


def weighted_value(values, index):
    seen = 0
    for depth, length in sorted(values):
        if seen + length > index:
            return depth
        seen += length
    return 0.0


def weighted_median(values):
    total = sum(length for _, length in values)
    if total == 0:
        return 0.0
    if total % 2:
        return float(weighted_value(values, total // 2))
    left = weighted_value(values, total // 2 - 1)
    right = weighted_value(values, total // 2)
    return (left + right) / 2.0


def load_metadata(path):
    metadata = {}
    with open(path, encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            fields = next(csv.reader([line]))
            if len(fields) < 2:
                continue
            accession = fields[0].lstrip(">")
            metadata[accession] = {
                "virus": fields[1],
                "family": fields[2] if len(fields) > 2 else "",
                "species": fields[-1] if len(fields) > 2 else fields[1],
            }
    return metadata


def load_thresholds(path):
    thresholds = {}
    if not path:
        return thresholds
    with open(path, encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            fields = line.replace(",", "\t").split("\t")
            thresholds[fields[0]] = int(fields[1])
    return thresholds


parser = argparse.ArgumentParser()
parser.add_argument("--bedgraph", required=True)
parser.add_argument("--read-counts", required=True)
parser.add_argument("--metadata", required=True)
parser.add_argument("--read-length", required=True, type=int)
parser.add_argument("--accession-thresholds")
parser.add_argument("--all-output", required=True)
parser.add_argument("--best-output", required=True)
args = parser.parse_args()

metadata = load_metadata(args.metadata)
custom_thresholds = load_thresholds(args.accession_thresholds)
read_counts = defaultdict(int)
with open(args.read_counts, encoding="utf-8") as handle:
    for line in handle:
        if line.strip():
            accession, count = line.rstrip("\n").split("\t")[:2]
            read_counts[accession] = int(count)

coverage = defaultdict(int)
genome_lengths = defaultdict(int)
positive_intervals = defaultdict(list)
with open(args.bedgraph, encoding="utf-8") as handle:
    for line in handle:
        if not line.strip():
            continue
        accession, start, end, depth = line.rstrip("\n").split("\t")[:4]
        start, end = int(start), int(end)
        depth_value = float(depth)
        genome_lengths[accession] = max(genome_lengths[accession], end)
        if depth_value > 0:
            interval_length = end - start
            coverage[accession] += interval_length
            positive_intervals[accession].append((depth_value, interval_length))

rows = []
for accession in sorted(coverage):
    covered = coverage[accession]
    if covered == 0:
        continue
    info = metadata.get(accession, {"virus": accession, "family": "", "species": accession})
    length = genome_lengths[accession]
    rows.append({
        "virus": info["virus"],
        "percent_coverage": round(covered / length * 100, 3) if length else 0.0,
        "median_depth": weighted_median(positive_intervals[accession]),
        "reads": read_counts[accession],
        "covered_nt": covered,
        "reference_length": length,
        "species": info["species"],
        "family": info["family"],
        "accession": accession,
    })

columns = ["virus", "percent_coverage", "median_depth", "reads", "covered_nt",
           "reference_length", "species", "family", "accession"]
with open(args.all_output, "w", encoding="utf-8", newline="") as handle:
    writer = csv.DictWriter(handle, fieldnames=columns, delimiter="\t")
    writer.writeheader()
    writer.writerows(rows)

minimum_covered_nt = max(3 * args.read_length, 300)
grouped = defaultdict(list)
for row in rows:
    accession_key = row["accession"].split(":", 1)[0]
    accession_minimum = custom_thresholds.get(accession_key, -1) + 1
    required = max(minimum_covered_nt, accession_minimum)
    if row["covered_nt"] >= required:
        grouped[row["virus"]].append(row)

best_rows = []
for virus in sorted(grouped):
    candidates = grouped[virus]
    candidates.sort(
        key=lambda row: (-row["covered_nt"], -row["median_depth"], -row["reads"], row["accession"])
    )
    best_rows.append(candidates[0])

with open(args.best_output, "w", encoding="utf-8", newline="") as handle:
    writer = csv.DictWriter(handle, fieldnames=columns, delimiter="\t")
    writer.writeheader()
    writer.writerows(best_rows)

