#!/usr/bin/env python3
"""Summarize the existing ten-column FEVIR BLASTx output by viral family."""

import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import json
import math
from pathlib import Path
import re
import sys
import tempfile

from build_protein_family_map import FIELDS as MAP_FIELDS, canonical_accession, sha256

SCHEMA = 1
MAP_STATUSES = {"assigned", "nonviral", "no_family_rank", "unknown_taxid",
                "ambiguous_name", "ambiguous_taxonomy", "unresolved_name", "missing_organism"}
CONTIG_FIELDS = ["contig_id", "contig_length_nt", "status", "family_taxid", "family",
                 "candidate_families", "reported_hsp_count", "retained_hsp_count",
                 "reported_subject_count", "retained_subject_count", "aligned_span_nt",
                 "aligned_span_percent", "best_retained_evalue", "best_retained_bitscore",
                 "subject_ids", "taxonomy_statuses", "taxonomy_sources"]
FAMILY_FIELDS = ["family", "family_taxid", "contig_count", "total_contig_nt",
                 "aligned_span_nt", "best_evalue", "best_bitscore", "contig_ids"]


def fasta_lengths(path):
    lengths, current = {}, None
    with open(path, encoding="utf-8") as handle:
        for number, raw in enumerate(handle, 1):
            line = raw.strip()
            if not line:
                continue
            if line.startswith(">"):
                if not line[1:].strip():
                    raise ValueError(f"{path}:{number}: empty FASTA header")
                current = line[1:].split()[0]
                if current in lengths:
                    raise ValueError(f"Duplicate FASTA identifier: {current}")
                lengths[current] = 0
            elif current is None:
                raise ValueError(f"{path}:{number}: sequence before FASTA header")
            else:
                if any(char.isspace() for char in line):
                    raise ValueError(f"{path}:{number}: whitespace inside a sequence line")
                lengths[current] += len(line)
    if any(length == 0 for length in lengths.values()):
        raise ValueError("FASTA contains an empty sequence")
    return lengths


def read_hits(path, lengths):
    hits, unique, duplicates = defaultdict(list), set(), 0
    with open(path, encoding="utf-8") as handle:
        for number, raw in enumerate(handle, 1):
            if not raw.strip() or raw.startswith("#"):
                continue
            fields = raw.rstrip("\r\n").split("\t")
            if len(fields) != 10:
                raise ValueError(f"{path}:{number}: expected FEVIR's 10 BLASTx columns, got {len(fields)}")
            query, subject, title = fields[:3]
            if query not in lengths:
                raise ValueError(f"{path}:{number}: BLAST query absent from FASTA: {query}")
            if not subject:
                raise ValueError(f"{path}:{number}: empty subject accession")
            identity, aa_length = float(fields[3]), int(fields[4])
            evalue, bitscore = float(fields[5]), float(fields[6])
            query_length, start, end = map(int, fields[7:])
            if not all(math.isfinite(x) for x in (identity, evalue, bitscore)):
                raise ValueError(f"{path}:{number}: non-finite BLAST value")
            if not (0 <= identity <= 100 and evalue >= 0 and bitscore > 0 and aa_length > 0):
                raise ValueError(f"{path}:{number}: invalid BLAST numeric value")
            if query_length != lengths[query] or not (1 <= start <= query_length and 1 <= end <= query_length):
                raise ValueError(f"{path}:{number}: BLAST coordinates/length disagree with FASTA")
            # Ignore exact duplicate rows; distinct HSPs are retained.
            signature = tuple(fields)
            if signature in unique:
                duplicates += 1
                continue
            unique.add(signature)
            title_hash = hashlib.sha256(title.strip().encode("utf-8")).hexdigest()
            hits[query].append({"subject": subject, "key": (canonical_accession(subject), title_hash),
                                "aa_length": aa_length, "evalue": evalue, "bitscore": bitscore,
                                "start": min(start, end), "end": max(start, end)})
    return hits, duplicates


def load_map(path, wanted):
    mapping, known_ids, family_names = {}, set(), {}
    if path is None:
        return mapping, known_ids, None
    provenance = {"path": str(path.resolve()), "sha256": sha256(path)}
    wanted_titles = {key[1] for key in wanted}
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        if not reader.fieldnames or not set(MAP_FIELDS).issubset(reader.fieldnames):
            raise ValueError("Invalid family map header; use build_protein_family_map.py")
        for number, row in enumerate(reader, 2):
            if None in row or any(row.get(name) is None for name in MAP_FIELDS):
                raise ValueError(f"{path}:{number}: malformed family map row")
            key = (canonical_accession(row["subject_id"]), row["title_sha256"])
            ordinal = re.fullmatch(r"BL_ORD_ID:[0-9]+", row["subject_id"]) is not None
            known_ids.add(key[0])
            if key not in wanted and not (ordinal and key[1] in wanted_titles):
                continue
            if row["status"] not in MAP_STATUSES:
                raise ValueError(f"{path}:{number}: invalid taxonomy status")
            if row["status"] == "assigned":
                if not row["family_taxid"].isdigit() or int(row["family_taxid"]) <= 0 or not row["family"]:
                    raise ValueError(f"{path}:{number}: assigned family without valid name/taxid")
                family_id = row["family_taxid"]
                if family_id in family_names and family_names[family_id] != row["family"]:
                    raise ValueError(f"Conflicting names for family taxid {family_id}")
                family_names[family_id] = row["family"]
            if key in mapping and mapping[key] != row:
                raise ValueError(f"Conflicting family map rows for {key[0]}")
            mapping[key] = row
            if ordinal:
                # For databases built without -parse_seqids, %a is BL_ORD_ID:n,
                # while BLASTx sacc can be the original FASTA identifier.
                # The FULL unchanged title includes that identifier. Match its
                # fingerprint, never just an organism name or protein keyword.
                title_key = (None, key[1])
                title_row = dict(row, source=row["source"] + "+ordinal_title")
                old = mapping.get(title_key)
                comparison = ("status", "taxids", "family_taxid", "family")
                if old and any(old[field] != title_row[field] for field in comparison):
                    title_row.update(status="ambiguous_taxonomy", taxids="", family_taxid="", family="",
                                     source="conflicting_ordinal_titles")
                mapping[title_key] = title_row
    sidecar = Path(str(path) + ".json")
    if sidecar.is_file():
        metadata = json.loads(sidecar.read_text(encoding="utf-8"))
        if metadata.get("mapping_sha256") != provenance["sha256"]:
            raise ValueError(f"Family map and its provenance JSON disagree: {path}")
        provenance["build"] = metadata
    return mapping, known_ids, provenance


def union_span(hits):
    total, previous_end = 0, 0
    for start, end in sorted((hit["start"], hit["end"]) for hit in hits):
        total += max(0, end - max(start, previous_end + 1) + 1)
        previous_end = max(previous_end, end)
    return total


def summarize(args):
    suffixes = [".denovo_families.tsv", ".denovo_contigs.tsv", ".denovo_summary.json"]
    outputs = [Path(str(args.output_prefix) + suffix) for suffix in suffixes]
    inputs = {args.fasta.resolve(), args.blast.resolve()}
    if args.taxonomy_map:
        inputs.add(args.taxonomy_map.resolve())
    for path in outputs:
        if path.resolve() in inputs:
            raise ValueError(f"An output would overwrite an input: {path}")
        if path.exists() and not args.force:
            raise ValueError(f"Output already exists: {path}; --force replaces summary files only")
    lengths = fasta_lengths(args.fasta)
    hits, duplicate_count = read_hits(args.blast, lengths)
    wanted = {hit["key"] for group in hits.values() for hit in group}
    mapping, known_ids, provenance = load_map(args.taxonomy_map, wanted)
    contig_rows, grouped, counts = [], defaultdict(list), Counter()

    for contig, length in lengths.items():
        reported = hits.get(contig, [])
        retained = [hit for hit in reported if hit["evalue"] <= args.max_evalue]
        annotations, families = [], {}
        for hit in retained:
            annotation = mapping.get(hit["key"]) or mapping.get((None, hit["key"][1]))
            if annotation is None:
                status = "map_unavailable" if args.taxonomy_map is None else (
                    "title_mismatch" if canonical_accession(hit["subject"]) in known_ids else "subject_unmapped")
                annotation = {"status": status, "source": ""}
            annotations.append(annotation)
            if annotation["status"] == "assigned":
                families[annotation["family_taxid"]] = annotation["family"]
        statuses = {item["status"] for item in annotations}
        family_id, family = "", ""
        if not reported:
            status = "no_blast_hit"
        elif not retained:
            status = "below_thresholds"
        elif len(families) > 1 or (families and "nonviral" in statuses) or statuses & {"ambiguous_name", "ambiguous_taxonomy"}:
            status = "ambiguous"
        elif statuses == {"assigned"} and len(families) == 1:
            status = "assigned"
            family_id, family = next(iter(families.items()))
        elif statuses == {"nonviral"}:
            status = "nonviral"
        else:
            status = "incomplete_taxonomy"
        span = union_span(retained)
        row = {"contig_id": contig, "contig_length_nt": length, "status": status,
               "family_taxid": family_id, "family": family,
               "candidate_families": ";".join(f"{name}|{taxid}" for taxid, name in sorted(families.items())),
               "reported_hsp_count": len(reported), "retained_hsp_count": len(retained),
               "reported_subject_count": len({hit["subject"] for hit in reported}),
               "retained_subject_count": len({hit["subject"] for hit in retained}),
               "aligned_span_nt": span, "aligned_span_percent": round(100 * span / length, 3),
               "best_retained_evalue": min((hit["evalue"] for hit in retained), default=""),
               "best_retained_bitscore": max((hit["bitscore"] for hit in retained), default=""),
               "subject_ids": ";".join(sorted({hit["subject"] for hit in retained})),
               "taxonomy_statuses": ";".join(sorted(statuses)),
               "taxonomy_sources": ";".join(sorted({item["source"] for item in annotations if item["source"]}))}
        counts[status] += 1
        contig_rows.append(row)
        if status == "assigned":
            grouped[(family_id, family)].append(row)

    family_rows = []
    for (family_id, family), rows in grouped.items():
        family_rows.append({"family": family, "family_taxid": family_id, "contig_count": len(rows),
                            "total_contig_nt": sum(row["contig_length_nt"] for row in rows),
                            "aligned_span_nt": sum(row["aligned_span_nt"] for row in rows),
                            "best_evalue": min(row["best_retained_evalue"] for row in rows),
                            "best_bitscore": max(row["best_retained_bitscore"] for row in rows),
                            "contig_ids": ";".join(sorted(row["contig_id"] for row in rows))})
    family_rows.sort(key=lambda row: (-row["contig_count"], -row["aligned_span_nt"], row["family"]))
    report = {"schema_version": SCHEMA, "assignment_rule": "All qualifying reported hits must resolve to one viral family",
              "parameters": {"max_evalue": args.max_evalue,
                             "blast_max_targets": args.blast_max_targets},
              "inputs": {"fasta": {"path": str(args.fasta.resolve()), "sha256": sha256(args.fasta)},
                         "blast": {"path": str(args.blast.resolve()), "sha256": sha256(args.blast)}},
              "taxonomy_map": provenance, "contig_count": len(lengths),
              "family_count": len(family_rows), "status_counts": dict(sorted(counts.items())),
              "exact_duplicate_blast_rows_ignored": duplicate_count,
              "contigs_reaching_reported_target_limit": sum(
                  row["reported_subject_count"] >= args.blast_max_targets for row in contig_rows
              ) if args.blast_max_targets else None,
              "limitations": ["Candidate family assignment, not confirmation of viral origin or clinical detection.",
                              "Consensus is restricted to hits present in BLAST output; omitted targets cannot be assessed.",
                              "Thresholds are initial reporting choices, not validated diagnostic cutoffs.",
                              "Contig counts are not read counts, genome counts or abundance estimates.",
                              "Aligned span is a union of query-coordinate intervals, including gaps; total contig length includes unaligned sequence."]}
    args.output_prefix.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".denovo-summary-", dir=args.output_prefix.parent) as temporary:
        staged = [Path(temporary) / path.name for path in outputs]
        for path, fields, rows in [(staged[0], FAMILY_FIELDS, family_rows), (staged[1], CONTIG_FIELDS, contig_rows)]:
            with path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t", lineterminator="\n")
                writer.writeheader()
                writer.writerows(rows)
        staged[2].write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        for source, target in zip(staged, outputs):
            source.replace(target)
    print(f"[denovo families] {len(family_rows)} candidate families; contig statuses: {dict(counts)}", file=sys.stderr)
    if args.taxonomy_map is None:
        print("[denovo families] No taxonomy map supplied: no family assignments were inferred", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fasta", type=Path, required=True, help="The contigs submitted to BLASTx")
    parser.add_argument("--blast", type=Path, required=True, help="Unmodified ten-column FEVIR BLASTx TSV")
    parser.add_argument("--taxonomy-map", type=Path, help="Table from build_protein_family_map.py; omit to audit without assigning families")
    parser.add_argument("--output-prefix", type=Path, required=True)
    parser.add_argument("--max-evalue", type=float, default=1e-5)
    parser.add_argument("--blast-max-targets", type=int, default=0, help="Original BLAST target cap, 0 if unknown")
    parser.add_argument("--force", action="store_true", help="Replace only the three summary files")
    args = parser.parse_args()
    if not math.isfinite(args.max_evalue) or args.max_evalue <= 0 or args.blast_max_targets < 0:
        parser.error("Require finite max-evalue > 0, blast-max-targets >= 0")
    try:
        summarize(args)
    except (OSError, ValueError, csv.Error) as exc:
        parser.exit(2, f"ERROR: {exc}\n")


if __name__ == "__main__":
    main()
