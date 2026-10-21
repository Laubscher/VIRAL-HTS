#!/usr/bin/env python3
"""Summarize the existing ten-column FEVIR BLASTx output by viral family."""

import argparse
from collections import Counter, defaultdict
from contextlib import ExitStack
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile

from build_protein_family_map import FIELDS as MAP_FIELDS, canonical_accession, sha256

SCHEMA = 1
MAP_STATUSES = {"assigned", "nonviral", "no_family_rank", "unknown_taxid",
                "ambiguous_name", "ambiguous_taxonomy", "unresolved_name", "missing_organism"}
NCBI_MAP_FIELDS = {"protein_accession", "protein_source", "nucleotide_accession",
                   "nucleotide_source", "description", "organism_hint", "resolved_accession",
                   "taxid", "scientific_name", "family", "lookup_status", "taxonomy_status"}
NCBI_LOOKUP_STATUSES = {"ok", "version_changed", "not_found", "no_taxid", "not_checked"}
NCBI_TAXONOMY_STATUSES = {"resolved", "non_viral_taxon", "no_family_rank", "not_found", "not_checked"}
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


def ncbi_map_row(row, path, number):
    """Adapt the export from fevir_ncbi_families.py without inventing family TaxIDs."""
    for field in ("protein_accession", "protein_source", "nucleotide_accession", "nucleotide_source"):
        value = row[field]
        if not value or "|" in value or any(char.isspace() for char in value):
            raise ValueError(f"{path}:{number}: invalid RVDB identifier field: {field}")
    if any(char in row["description"] for char in "\t\r\n") or not row["description"]:
        raise ValueError(f"{path}:{number}: invalid RVDB description")
    lookup, taxonomy = row["lookup_status"], row["taxonomy_status"]
    if lookup not in NCBI_LOOKUP_STATUSES or taxonomy not in NCBI_TAXONOMY_STATUSES:
        raise ValueError(f"{path}:{number}: invalid NCBI lookup/taxonomy status")
    family = row["family"]
    if taxonomy == "resolved" and not family:
        raise ValueError(f"{path}:{number}: resolved taxonomy without a family name")
    if taxonomy != "resolved" and family:
        raise ValueError(f"{path}:{number}: family name conflicts with taxonomy status")
    if lookup not in {"ok", "version_changed"} and family:
        raise ValueError(f"{path}:{number}: family name without a resolved protein lookup")
    if lookup in {"ok", "version_changed"}:
        if not row["taxid"].isdigit() or int(row["taxid"]) <= 0 or not row["resolved_accession"]:
            raise ValueError(f"{path}:{number}: resolved protein without a valid accession/taxid")
    if lookup == "ok" and row["resolved_accession"] != row["protein_accession"]:
        raise ValueError(f"{path}:{number}: lookup marked ok for a different protein accession")

    # These fields retain the complete original FASTA title. Keep its exact
    # fingerprint check; a matching accession alone is not enough.
    title = "|".join(("acc", row["protein_source"], row["protein_accession"],
                      row["nucleotide_source"], row["nucleotide_accession"], row["description"]))
    title_hash = hashlib.sha256(title.strip().encode("utf-8")).hexdigest()
    status = "unknown_taxid"
    if lookup == "ok":
        status = {"resolved": "assigned", "non_viral_taxon": "nonviral",
                  "no_family_rank": "no_family_rank"}.get(taxonomy, "unknown_taxid")
    # A changed protein version is retained as incomplete taxonomy. It does
    # not establish a lookup for the exact sequence used by this database.
    source = "ncbi_protein_accession"
    if lookup != "ok":
        source += "+lookup_" + lookup
    if taxonomy in {"not_found", "not_checked"}:
        source += "+taxonomy_" + taxonomy
    return dict(row, subject_id=title.split()[0], title_sha256=title_hash,
                taxids=row["taxid"], family_taxid="",
                family=family if status == "assigned" else "", status=status,
                source=source, organism=row["organism_hint"])


def load_map(path, wanted):
    mapping, known_ids, family_names = {}, set(), {}
    if path is None:
        return mapping, known_ids, None
    provenance = {"path": str(path.resolve()), "sha256": sha256(path)}
    wanted_titles = {key[1] for key in wanted}
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        if not reader.fieldnames or len(set(reader.fieldnames)) != len(reader.fieldnames):
            raise ValueError("Invalid family map header: empty or duplicate column names")
        if set(MAP_FIELDS).issubset(reader.fieldnames):
            ncbi_format, required_fields = False, MAP_FIELDS
        elif NCBI_MAP_FIELDS.issubset(reader.fieldnames):
            ncbi_format, required_fields = True, NCBI_MAP_FIELDS
            provenance.update(format="fevir_ncbi_families", family_identifier="exact_family_name",
                              family_taxid_available=False,
                              subject_matching="Exact reconstructed RVDB subject and full title SHA256",
                              changed_protein_versions="Retained as incomplete taxonomy")
        else:
            raise ValueError("Invalid family map header; expected the export from "
                             "build_protein_family_map.py or fevir_ncbi_families.py")
        for number, row in enumerate(reader, 2):
            if None in row or any(row.get(name) is None for name in required_fields):
                raise ValueError(f"{path}:{number}: malformed family map row")
            if ncbi_format:
                row = ncbi_map_row(row, path, number)
            key = (canonical_accession(row["subject_id"]), row["title_sha256"])
            ordinal = re.fullmatch(r"BL_ORD_ID:[0-9]+", row["subject_id"]) is not None
            known_ids.add(key[0])
            if key not in wanted and not (ordinal and key[1] in wanted_titles):
                continue
            if row["status"] not in MAP_STATUSES:
                raise ValueError(f"{path}:{number}: invalid taxonomy status")
            if row["status"] == "assigned":
                if not ncbi_format:
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


def family_filenames(family_rows):
    """Keep ordinary family names readable and safely disambiguate other names."""
    names, bases = {}, defaultdict(list)
    reserved = {"CON", "PRN", "AUX", "NUL"}
    reserved.update(f"{prefix}{number}" for prefix in ("COM", "LPT") for number in range(1, 10))
    for row in family_rows:
        key = (row["family_taxid"], row["family"])
        family = row["family"]
        digest = hashlib.sha256((key[0] + "\0" + family).encode("utf-8")).hexdigest()[:16]
        if re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,99}", family) and family.upper() not in reserved:
            base = family
        else:
            stem = re.sub(r"[^A-Za-z0-9_-]+", "_", family).strip("_-")[:80] or "family"
            base = f"{stem}__{digest}"
        names[key] = base
        bases[base.casefold()].append(key)
    # This also separates different native TaxIDs that share a family name.
    for keys in bases.values():
        if len(keys) > 1:
            for key in keys:
                digest = hashlib.sha256((key[0] + "\0" + key[1]).encode("utf-8")).hexdigest()[:16]
                names[key] += "__" + digest
    filenames = {key: name + ".fasta" for key, name in names.items()}
    if len({name.casefold() for name in filenames.values()}) != len(filenames):
        raise ValueError("Unable to create distinct family FASTA filenames")
    return filenames


def check_family_directory(directory, table, inputs, outputs, force):
    """Only replace files that the previous family TSV identifies as our export."""
    resolved = directory.resolve()
    if directory.is_symlink():
        raise ValueError(f"Family FASTA directory must not be a symlink: {directory}")
    for path in inputs | {output.resolve() for output in outputs}:
        if path == resolved or resolved in path.parents:
            raise ValueError(f"Family FASTA directory would contain an input or summary file: {directory}")
    if not directory.exists():
        return
    if not directory.is_dir():
        raise ValueError(f"Family FASTA path is not a directory: {directory}")
    if not force:
        raise ValueError(f"Family FASTA directory already exists: {directory}; use --force to replace its export")
    existing = list(directory.iterdir())
    if not existing:
        return
    if not table.is_file():
        raise ValueError(f"Cannot replace a nonempty family directory without its previous family TSV: {table}")
    owned = set()
    with table.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        required = set(FAMILY_FIELDS) | {"fasta_file"}
        if (not reader.fieldnames or len(reader.fieldnames) != len(set(reader.fieldnames))
                or not required.issubset(reader.fieldnames)):
            raise ValueError(f"Previous family TSV does not identify its exported FASTA files: {table}")
        for row in reader:
            if None in row or any(row.get(field) is None for field in required):
                raise ValueError(f"Malformed previous family TSV: {table}")
            relative = Path(row["fasta_file"])
            target = table.parent / relative
            if (not row["fasta_file"] or relative.is_absolute()
                    or target.resolve().parent != resolved or target.suffix != ".fasta"):
                raise ValueError(f"Previous family TSV points outside the family export: {row['fasta_file']}")
            if target.name in owned:
                raise ValueError(f"Previous family TSV repeats an exported filename: {target.name}")
            owned.add(target.name)
    for path in existing:
        if path.name not in owned or path.is_symlink() or not path.is_file():
            raise ValueError(f"Refusing to replace an unrecognized entry in the family directory: {path}")


def write_family_fastas(fasta, directory, grouped, filenames):
    """Copy complete assigned records, keeping source headers and sequence order."""
    directory.mkdir()
    selected = {}
    for key, rows in grouped.items():
        for row in rows:
            selected[row["contig_id"]] = (filenames[key], row["contig_length_nt"])
    seen, handle, current, length = set(), None, None, 0

    def close_record():
        if handle is not None:
            handle.close()
            if length != selected[current][1]:
                raise ValueError(f"FASTA changed while exporting contig: {current}")

    try:
        with fasta.open(encoding="utf-8") as source:
            for raw in source:
                line = raw.strip()
                if not line:
                    continue
                if line.startswith(">"):
                    close_record()
                    handle, current, length = None, line[1:].split()[0], 0
                    if current in selected:
                        if current in seen:
                            raise ValueError(f"Duplicate FASTA identifier while exporting: {current}")
                        seen.add(current)
                        handle = (directory / selected[current][0]).open("a", encoding="utf-8", newline="\n")
                        handle.write(line + "\n")
                elif handle is not None:
                    handle.write(line + "\n")
                    length += len(line)
        close_record()
    finally:
        if handle is not None:
            handle.close()
    if seen != set(selected):
        raise ValueError("FASTA changed while exporting: assigned contigs are missing")


def publish_outputs(pairs):
    """Stage all outputs first and restore earlier outputs if publication fails."""
    changed, backups = [], []
    try:
        for source, target in pairs:
            previous = None
            if target.exists() or target.is_symlink():
                backup = Path(tempfile.mkdtemp(prefix=".denovo-previous-", dir=target.parent))
                backups.append(backup)
                previous = backup / "previous"
                target.replace(previous)
            item = [target, previous, False]
            changed.append(item)
            source.replace(target)
            item[2] = True
    except OSError as original:
        failures = []
        for target, previous, installed in reversed(changed):
            try:
                if installed:
                    if target.is_dir() and not target.is_symlink():
                        shutil.rmtree(target)
                    else:
                        target.unlink()
                if previous is not None:
                    previous.replace(target)
            except OSError as rollback_error:
                failures.append(str(rollback_error))
        if failures:
            locations = ", ".join(str(path) for path in backups)
            raise OSError(f"Output publication failed; recovery copies retained in {locations}: {'; '.join(failures)}") from original
        for backup in backups:
            shutil.rmtree(backup)
        raise
    for backup in backups:
        shutil.rmtree(backup)


def summarize(args):
    details_prefix = args.details_dir / args.output_prefix.name if args.details_dir else args.output_prefix
    outputs = [Path(str(args.output_prefix) + ".denovo_families.tsv"),
               Path(str(details_prefix) + ".denovo_contigs.tsv")]
    if not args.no_summary_json:
        outputs.append(Path(str(details_prefix) + ".denovo_summary.json"))
    inputs = {args.fasta.resolve(), args.blast.resolve()}
    if args.taxonomy_map:
        inputs.add(args.taxonomy_map.resolve())
    for path in outputs:
        if path.resolve() in inputs:
            raise ValueError(f"An output would overwrite an input: {path}")
        if path.exists() and not args.force:
            raise ValueError(f"Output already exists: {path}; use --force to replace generated outputs")
        if path.is_dir():
            raise ValueError(f"Expected a summary file, found a directory: {path}")
    if len({path.resolve() for path in outputs}) != len(outputs):
        raise ValueError("Summary output paths overlap")
    if args.families_dir:
        check_family_directory(args.families_dir, outputs[0], inputs, outputs, args.force)
    lengths = fasta_lengths(args.fasta)
    hits, duplicate_count = read_hits(args.blast, lengths)
    wanted = {hit["key"] for group in hits.values() for hit in group}
    mapping, known_ids, provenance = load_map(args.taxonomy_map, wanted)
    contig_rows, grouped, counts = [], defaultdict(list), Counter()

    for contig, length in lengths.items():
        reported = hits.get(contig, [])
        retained = [hit for hit in reported if hit["evalue"] <= args.max_evalue
                    and hit["aa_length"] >= args.min_alignment_aa]
        annotations, families = [], {}
        for hit in retained:
            annotation = mapping.get(hit["key"]) or mapping.get((None, hit["key"][1]))
            if annotation is None:
                status = "map_unavailable" if args.taxonomy_map is None else (
                    "title_mismatch" if canonical_accession(hit["subject"]) in known_ids else "subject_unmapped")
                annotation = {"status": status, "source": ""}
            annotations.append(annotation)
            if annotation["status"] == "assigned":
                family_id, family = annotation["family_taxid"], annotation["family"]
                # The NCBI export supplies family names but no family TaxIDs.
                # Never merge distinct families under the same empty TaxID.
                family_key = ("taxid", family_id) if family_id else ("name", family)
                families[family_key] = (family_id, family)
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
            family_id, family = next(iter(families.values()))
        elif statuses == {"nonviral"}:
            status = "nonviral"
        else:
            status = "incomplete_taxonomy"
        span = union_span(retained)
        row = {"contig_id": contig, "contig_length_nt": length, "status": status,
               "family_taxid": family_id, "family": family,
               "candidate_families": ";".join(f"{name}|{taxid}" for taxid, name in sorted(families.values())),
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
    family_fields = FAMILY_FIELDS
    filenames = {}
    if args.families_dir:
        filenames = family_filenames(family_rows)
        family_fields = FAMILY_FIELDS + ["fasta_file"]
        for row in family_rows:
            path = args.families_dir / filenames[(row["family_taxid"], row["family"])]
            row["fasta_file"] = Path(os.path.relpath(path.resolve(), outputs[0].parent.resolve())).as_posix()
    report = {"schema_version": SCHEMA, "assignment_rule": "All qualifying reported hits must resolve to one viral family",
              "parameters": {"max_evalue": args.max_evalue, "min_alignment_aa": args.min_alignment_aa,
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
    if args.families_dir:
        report["family_fastas"] = {"directory": str(args.families_dir.resolve()),
                                  "family_count": len(family_rows),
                                  "contig_count": sum(len(rows) for rows in grouped.values()),
                                  "selection": "Complete source FASTA records with status assigned"}
    with ExitStack() as stack:
        temporary = {}

        def staging_parent(parent):
            resolved = parent.resolve()
            if resolved not in temporary:
                parent.mkdir(parents=True, exist_ok=True)
                temporary[resolved] = Path(stack.enter_context(
                    tempfile.TemporaryDirectory(prefix=".denovo-summary-", dir=parent)))
            return temporary[resolved]

        staged = [staging_parent(path.parent) / f"summary-{number}" for number, path in enumerate(outputs)]
        for path, fields, rows in [(staged[0], family_fields, family_rows), (staged[1], CONTIG_FIELDS, contig_rows)]:
            with path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t", lineterminator="\n")
                writer.writeheader()
                writer.writerows(rows)
        if not args.no_summary_json:
            staged[2].write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        pairs = list(zip(staged, outputs))
        if args.families_dir:
            staged_families = staging_parent(args.families_dir.parent) / "family-fastas"
            write_family_fastas(args.fasta, staged_families, grouped, filenames)
            pairs.append((staged_families, args.families_dir))
        publish_outputs(pairs)
    print(f"[denovo families] {len(family_rows)} candidate families; contig statuses: {dict(counts)}", file=sys.stderr)
    if args.taxonomy_map is None:
        print("[denovo families] No taxonomy map supplied: no family assignments were inferred", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fasta", type=Path, required=True, help="The contigs submitted to BLASTx")
    parser.add_argument("--blast", type=Path, required=True, help="Unmodified ten-column FEVIR BLASTx TSV")
    parser.add_argument("--taxonomy-map", type=Path, help="Table from build_protein_family_map.py or fevir_ncbi_families.py; omit to audit without assigning families")
    parser.add_argument("--output-prefix", type=Path, required=True)
    parser.add_argument("--families-dir", type=Path, help="Export complete assigned contigs as one FASTA per family")
    parser.add_argument("--details-dir", type=Path, help="Directory for the contig table and optional summary JSON")
    parser.add_argument("--no-summary-json", action="store_true", help="Do not write the summary JSON")
    parser.add_argument("--max-evalue", type=float, default=1e-5)
    parser.add_argument("--min-alignment-aa", type=int, default=50)
    parser.add_argument("--blast-max-targets", type=int, default=0, help="Original BLAST target cap, 0 if unknown")
    parser.add_argument("--force", action="store_true", help="Replace summary files and a recognized family FASTA export")
    args = parser.parse_args()
    if not math.isfinite(args.max_evalue) or args.max_evalue <= 0 or args.min_alignment_aa < 1 or args.blast_max_targets < 0:
        parser.error("Require finite max-evalue > 0, min-alignment-aa >= 1, blast-max-targets >= 0")
    try:
        summarize(args)
    except (OSError, ValueError, csv.Error) as exc:
        parser.exit(2, f"ERROR: {exc}\n")


if __name__ == "__main__":
    main()
