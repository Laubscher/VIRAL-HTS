#!/usr/bin/env python3
import argparse


parser = argparse.ArgumentParser()
parser.add_argument("--fasta", required=True)
parser.add_argument("--blast", required=True)
parser.add_argument("--output", required=True)
args = parser.parse_args()

hit_ids = set()
with open(args.blast, encoding="utf-8") as handle:
    for line in handle:
        if line.strip():
            hit_ids.add(line.split("\t", 1)[0])

header = None
sequence = []
with open(args.fasta, encoding="utf-8") as source, open(args.output, "w", encoding="utf-8") as output:
    def emit():
        if header is not None and header[1:].split()[0] in hit_ids:
            output.write(header + "\n")
            joined = "".join(sequence)
            for start in range(0, len(joined), 80):
                output.write(joined[start:start + 80] + "\n")

    for raw_line in source:
        line = raw_line.strip()
        if line.startswith(">"):
            emit()
            header = line
            sequence = []
        elif line:
            sequence.append(line)
    emit()

