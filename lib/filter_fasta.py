#!/usr/bin/env python3
import argparse


def records(path):
    header = None
    sequence = []
    with open(path, encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith(">"):
                if header is not None:
                    yield header, "".join(sequence)
                header = line
                sequence = []
            else:
                if header is None:
                    raise ValueError(f"Sequence found before FASTA header in {path}")
                sequence.append(line)
    if header is not None:
        yield header, "".join(sequence)


parser = argparse.ArgumentParser()
parser.add_argument("--input", required=True)
parser.add_argument("--minimum-length", required=True, type=int)
parser.add_argument("--output", required=True)
args = parser.parse_args()

with open(args.output, "w", encoding="utf-8") as output:
    for header, sequence in records(args.input):
        if len(sequence) >= args.minimum_length:
            output.write(f"{header}\n")
            for start in range(0, len(sequence), 80):
                output.write(sequence[start:start + 80] + "\n")

