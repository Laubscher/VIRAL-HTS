#!/usr/bin/env python3
"""Suppress competing usual-name groups within each family without independent covered bases.

The dominant (family, virus/usual_name) group in each family is exempt. Other
groups must satisfy their original per-accession threshold with templates not
shared with any accession in the dominant group. all_hits is unchanged.
"""
import argparse
import csv
from collections import defaultdict

from filter_secondary_by_family import covered_intervals, union_length


def load_thresholds(path):
    result = {}
    if not path:
        return result
    with open(path, encoding='utf-8') as handle:
        for line in handle:
            if line.strip() and not line.startswith('#'):
                fields = line.replace(',', '\t').split('\t')
                result[fields[0]] = int(fields[1])
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--sam', required=True, help='Family-filtered SAM used for metrics')
    p.add_argument('--all-hits', required=True)
    p.add_argument('--best-hits', required=True)
    p.add_argument('--read-length', required=True, type=int)
    p.add_argument('--accession-thresholds')
    args = p.parse_args()
    thresholds = load_thresholds(args.accession_thresholds)
    with open(args.all_hits, newline='', encoding='utf-8') as handle:
        all_rows = list(csv.DictReader(handle, delimiter='\t'))
    with open(args.best_hits, newline='', encoding='utf-8') as handle:
        reader = csv.DictReader(handle, delimiter='\t')
        columns = reader.fieldnames
        best_rows = list(reader)
    if not columns:
        raise ValueError('Missing best_hits header')
    # Group means (family, virus/usual_name), NOT the taxonomy species column.
    # Score each group by its best accession, without adding reference coverages.
    group_best = {}
    for row in all_rows:
        key = (row['family'], row['virus'])
        score = (int(row['covered_nt']), float(row['median_depth']), int(row['reads']))
        if (key not in group_best or score > group_best[key][0]
                or (score == group_best[key][0] and row['accession'] < group_best[key][1]['accession'])):
            group_best[key] = (score, row)
    dominant = {}
    for (fam, virus), (score, row) in group_best.items():
        if (fam not in dominant or score > dominant[fam][0]
                or (score == dominant[fam][0] and virus < dominant[fam][1])):
            dominant[fam] = (score, virus)

    # Every alignment to any accession of the dominant usual-name group counts as shared support.
    # Do not exempt competing accessions merely because their taxonomy species matches the dominant accession.
    ref_groups = {row['accession']: (row['family'], row['virus']) for row in all_rows}
    dominant_templates = defaultdict(set)
    alignments = defaultdict(list)
    with open(args.sam, encoding='utf-8') as handle:
        for line in handle:
            if line.startswith('@'):
                continue
            fields = line.rstrip('\n').split('\t')
            if len(fields) < 11:
                raise ValueError('Malformed SAM record')
            flag = int(fields[1])
            if flag & (0x4 | 0x800):
                continue
            ref, qname = fields[2], fields[0]
            alignments[ref].append((qname, covered_intervals(fields[3], fields[5])))
            group = ref_groups.get(ref)
            if group and dominant.get(group[0], (None, None))[1] == group[1]:
                dominant_templates[group[0]].add(qname)

    independent_coverage = {}
    for row in all_rows:
        fam = row['family']
        if fam not in dominant or row['virus'] == dominant[fam][1]:
            continue
        independent_coverage[row['accession']] = union_length([
            span for qname, spans in alignments[row['accession']]
            if qname not in dominant_templates[fam] for span in spans
        ])

    minimum = max(3 * args.read_length, 300)
    independent_groups = set()
    for row in all_rows:
        accession = row['accession']
        if accession not in independent_coverage:
            continue
        accession_key = accession.split(':', 1)[0]
        required = max(minimum, thresholds.get(accession_key, -1) + 1)
        if independent_coverage[accession] >= required:
            independent_groups.add((row['family'], row['virus']))

    retained = []
    for row in best_rows:
        fam = row['family']
        if (fam not in dominant or row['virus'] == dominant[fam][1]
                or (fam, row['virus']) in independent_groups):
            retained.append(row)
    # Replacement only after successful parsing/computation.
    import os
    import tempfile
    folder = os.path.dirname(os.path.abspath(args.best_hits))
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', newline='', dir=folder, delete=False) as handle:
        temp = handle.name
        writer = csv.DictWriter(handle, fieldnames=columns, delimiter='\t')
        writer.writeheader()
        writer.writerows(retained)
    os.replace(temp, args.best_hits)


if __name__ == '__main__':
    main()
