#!/usr/bin/env python3
import argparse
from itertools import zip_longest


def reads(path, maximum):
    with open(path, encoding="ascii") as source:
        number = 0
        while True:
            header = source.readline()
            if not header:
                return
            number += 1
            sequence = source.readline().rstrip("\r\n")
            plus = source.readline()
            quality = source.readline().rstrip("\r\n")
            if not header.startswith("@") or not plus.startswith("+") or not sequence or len(sequence) != len(quality):
                raise ValueError(f"Invalid FASTQ record {number}: {path}")
            if maximum is not None and len(sequence) > maximum:
                raise ValueError(f"Read {number} has {len(sequence)} bases; IDBA-UD limit is {maximum}: {path}")
            words = header[1:].split()
            if not words:
                raise ValueError(f"Missing read name at record {number}: {path}")
            name = words[0]
            if name.endswith(("/1", "/2")):
                name = name[:-2]
            yield name, len(sequence)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--r1", required=True)
    parser.add_argument("--r2")
    parser.add_argument("--maximum-length", type=int)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    count = total = maximum = 0
    minimum = None
    inputs = reads(args.r1, args.maximum_length)
    if args.r2:
        records = zip_longest(inputs, reads(args.r2, args.maximum_length))
    else:
        records = ((read,) for read in inputs)
    for group in records:
        if any(read is None for read in group):
            raise ValueError("Paired FASTQ files have different numbers of reads")
        if len(group) == 2 and group[0][0] != group[1][0]:
            raise ValueError(f"Paired FASTQ names differ: {group[0][0]} / {group[1][0]}")
        for _, length in group:
            count += 1
            total += length
            maximum = max(maximum, length)
            minimum = length if minimum is None else min(minimum, length)
    with open(args.output, "w") as out:
        out.write("metric\tvalue\n")
        for name, value in (("reads", count), ("bases", total), ("minimum_read_length", minimum or 0),
                            ("maximum_read_length", maximum)):
            out.write(f"{name}\t{value}\n")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError) as error:
        raise SystemExit(str(error))
