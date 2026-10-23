#!/usr/bin/env python3
"""Keep secondary SAM mappings only for the coverage winner in each family.

Usage: filter_secondary_by_family.py --metadata ref.txt --input raw.sam --output filtered.sam
Primary and supplementary alignments are retained unchanged.  Secondary hits are
kept only if their accession wins on primary + eligible secondary covered bases within its family,
and all primary mappings for the read/template belong to that same family.
"""
import argparse
import csv
import re
from collections import defaultdict

CIGAR_RE = re.compile(r"(\d+)([MIDNSHP=X])")


def covered_intervals(pos, cigar):
    at = int(pos) - 1
    intervals = []
    for length_str, op in CIGAR_RE.findall(cigar):
        length = int(length_str)
        if op in "M=X":
            intervals.append((at, at + length))
        if op in "MDN=X":
            at += length
    return intervals


def union_length(intervals):
    end = 0
    total = 0
    for start, stop in sorted(intervals):
        if stop > end:
            total += stop - max(start, end)
            end = stop
    return total


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--metadata", required=True)
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    families = {}
    with open(args.metadata, encoding="utf-8") as handle:
        for line in handle:
            if line.strip() and not line.startswith("#"):
                row = next(csv.reader([line]))
                if len(row) >= 3:
                    families[row[0].lstrip(">")] = row[2]

    def family(ref):
        return families.get(ref) or "__unknown__:" + ref

    template_primary_families = defaultdict(set)
    # Establish primary family assignments first, across both mates of each template.
    with open(args.input, encoding="utf-8") as handle:
        for line in handle:
            if line.startswith("@"):
                continue
            fields = line.rstrip("\n").split("\t")
            if len(fields) < 11:
                raise ValueError("Malformed SAM record")
            flag = int(fields[1])
            if not flag & (0x4 | 0x100 | 0x800):
                template_primary_families[fields[0]].add(family(fields[2]))

    # Score (couverture) accessions using primary mappings AND eligible secondary mappings.
    # Cross-family secondary mappings must never affect the winner selection.
    intervals = defaultdict(list)
    with open(args.input, encoding="utf-8") as handle:
        for line in handle:
            if line.startswith("@"):
                continue
            fields = line.rstrip("\n").split("\t")
            flag = int(fields[1])
            if flag & (0x4 | 0x800):
                continue
            ref = fields[2]
            fam = family(ref)
            if flag & 0x100 and template_primary_families.get(fields[0]) != {fam}:
                continue
            intervals[ref].extend(covered_intervals(fields[3], fields[5]))

    winner = {}
    for ref, spans in intervals.items():
        fam = family(ref)
        score = union_length(spans)
        if fam not in winner or score > winner[fam][0] or (score == winner[fam][0] and ref < winner[fam][1]):
            winner[fam] = (score, ref)

    with open(args.input, encoding="utf-8") as source, open(args.output, "w", encoding="utf-8") as output:
        for line in source:
            if line.startswith("@"):
                output.write(line)
                continue
            fields = line.rstrip("\n").split("\t")
            flag = int(fields[1])
            if not flag & 0x100:
                output.write(line)
                continue
            if flag & (0x4 | 0x800):
                continue
            ref = fields[2]
            fam = family(ref)
            if (winner.get(fam, (None, None))[1] == ref
                    and template_primary_families.get(fields[0]) == {fam}):
                output.write(line)


if __name__ == "__main__":
    main()
