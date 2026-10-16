#!/usr/bin/env python3
"""Prepare an offline BLAST subject-to-viral-family table (Python stdlib only)."""

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import csv
import hashlib
import json
from pathlib import Path
import re
import sys

SCHEMA = 1
NAME_CLASSES = {"scientific name", "synonym", "equivalent name"}
FIELDS = ["subject_id", "title_sha256", "taxids", "family_taxid", "family",
          "status", "source", "organism"]


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def organism_name(title):
    # Only the terminal organism bracket of an ordinary RVDB/NCBI title.
    # Multiple deflines must not be silently reduced to the last organism.
    if "\x01" in title or " >" in title or "<>" in title:
        return ""
    match = re.search(r"\[([^\[\]]+)\]\s*$", title)
    return match.group(1).strip() if match else ""


def normalized_name(name):
    return " ".join(name.split()).casefold()


def canonical_accession(accession):
    # BLASTx sacc omits versions whereas blastdbcmd %a can retain them.
    if re.fullmatch(r"[A-Za-z]{1,6}_?[0-9]+\.[0-9]+", accession):
        return accession.rsplit(".", 1)[0]
    return accession


def subjects(path):
    with open(path, encoding="utf-8") as handle:
        for number, raw in enumerate(handle, 1):
            if not raw.strip():
                continue
            fields = raw.rstrip("\r\n").split("\t")
            if len(fields) != 3 or not fields[0].strip():
                raise ValueError(f"{path}:{number}: expected subject_id<TAB>taxid<TAB>title")
            accession, raw_taxids, title = (part.strip() for part in fields)
            if raw_taxids in {"", "N/A", "NA", "0"}:
                taxids = []
            else:
                parts = re.split(r"[;,]", raw_taxids)
                if not all(part.strip().isdigit() for part in parts):
                    raise ValueError(f"{path}:{number}: invalid taxid: {raw_taxids}")
                taxids = sorted({int(part) for part in parts if int(part) > 0})
            yield accession, taxids, title


def dump_rows(path):
    with open(path, encoding="utf-8") as handle:
        for raw in handle:
            if raw.strip():
                yield [field.strip() for field in raw.split("|")]


def build(args):
    paths = {name: args.taxdump / name for name in ("nodes.dmp", "names.dmp", "merged.dmp")}
    for path in paths.values():
        if not path.is_file():
            raise ValueError(f"Taxonomy file missing: {path}")
    outputs = [args.output, Path(str(args.output) + ".json")]
    for path in outputs:
        if path.exists():
            raise ValueError(f"Output already exists: {path}; use a new output name")

    wanted_names, input_count = set(), 0
    for _, ids, title in subjects(args.subjects):
        input_count += 1
        if not ids:
            wanted_names.add(normalized_name(organism_name(title)))
    if not input_count:
        raise ValueError("Empty subject export; check the blastdbcmd command before building a map")
    wanted_names.discard("")
    print("[taxonomy] Reading NCBI nodes and family ranks", file=sys.stderr)
    parents, families = {}, set()
    for row in dump_rows(paths["nodes.dmp"]):
        taxid, parent = int(row[0]), int(row[1])
        parents[taxid] = parent
        if row[2] == "family":
            families.add(taxid)
    if 1 not in parents or 10239 not in parents:
        raise ValueError("NCBI root (1) or Viruses (10239) missing from nodes.dmp")
    merged = {int(row[0]): int(row[1]) for row in dump_rows(paths["merged.dmp"])}
    names_to_ids, family_names = defaultdict(set), {}
    for row in dump_rows(paths["names.dmp"]):
        taxid, name, category = int(row[0]), row[1], row[3]
        if category == "scientific name" and taxid in families:
            family_names[taxid] = name
        key = normalized_name(name)
        if key in wanted_names and category in NAME_CLASSES:
            names_to_ids[key].add(taxid)

    def current_id(taxid):
        seen = set()
        while taxid in merged:
            if taxid in seen:
                raise ValueError(f"Cycle in merged.dmp at taxid {taxid}")
            seen.add(taxid)
            taxid = merged[taxid]
        return taxid

    lineage_cache = {}

    def classify(taxid):
        taxid = current_id(taxid)
        if taxid in lineage_cache:
            return lineage_cache[taxid]
        node, family, viral, seen = taxid, None, False, set()
        while node not in seen:
            seen.add(node)
            viral |= node == 10239
            if node in families and family is None:
                family = node
            if node not in parents:
                result = ("unknown_taxid", None)
                break
            parent = parents[node]
            if parent == node:
                if node != 1:
                    raise ValueError(f"Unexpected self-parent in nodes.dmp: {node}")
                if not viral:
                    result = ("nonviral", None)
                elif family is None:
                    result = ("no_family_rank", None)
                elif family not in family_names:
                    raise ValueError(f"Scientific name missing for family taxid {family}")
                else:
                    result = ("assigned", family)
                break
            node = parent
        else:
            raise ValueError(f"Cycle in nodes.dmp at taxid {node}")
        lineage_cache[taxid] = result
        return result

    counts, sources, seen_subjects = Counter(), Counter(), {}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_name(args.output.name + ".tmp")
    try:
        with temporary.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=FIELDS, delimiter="\t", lineterminator="\n")
            writer.writeheader()
            for accession, ids, title in subjects(args.subjects):
                organism = organism_name(title)
                source = "embedded_taxid" if ids else "exact_name"
                status, family = "unresolved_name", None
                if not ids:
                    ids = sorted({current_id(t) for t in names_to_ids.get(normalized_name(organism), set())})
                    if len(ids) > 1:
                        status = "ambiguous_name"
                    elif not organism:
                        status = "missing_organism"
                if ids and status != "ambiguous_name":
                    ids = sorted({current_id(t) for t in ids})
                    resolved = {classify(taxid) for taxid in ids}
                    if len(resolved) == 1:
                        status, family = next(iter(resolved))
                    else:
                        status = "ambiguous_taxonomy"
                title_hash = hashlib.sha256(title.encode("utf-8")).hexdigest()
                record = dict(zip(FIELDS, [accession, title_hash, ";".join(map(str, ids)),
                                          family or "", family_names.get(family, ""),
                                          status, source, organism]))
                key = (accession, title_hash)
                signature = tuple(record.values())
                if key in seen_subjects:
                    if seen_subjects[key] != signature:
                        raise ValueError(f"Conflicting taxonomy for the same subject/title: {accession}")
                    continue
                seen_subjects[key] = signature
                writer.writerow(record)
                counts[status] += 1
                sources[source] += 1
        temporary.replace(args.output)
    finally:
        temporary.unlink(missing_ok=True)

    report = {"schema_version": SCHEMA, "created_utc": datetime.now(timezone.utc).isoformat(),
              "taxonomy_label": args.taxonomy_label, "protein_database_label": args.database_label,
              "subjects": {"path": str(args.subjects.resolve()), "sha256": sha256(args.subjects)},
              "taxonomy_files": {name: {"path": str(path.resolve()), "sha256": sha256(path)}
                                 for name, path in paths.items()},
              "mapping_sha256": sha256(args.output), "subject_count": sum(counts.values()),
              "status_counts": dict(counts), "source_counts": dict(sources),
              "name_matching": "Exact normalized scientific name, synonym or equivalent name; unique taxid only",
              "viral_ancestor_taxid": 10239}
    outputs[1].write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"[taxonomy] {sum(counts.values())} subjects: {dict(counts)}", file=sys.stderr)
    print(f"[taxonomy] Table: {args.output}", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--subjects", type=Path, required=True,
                        help="blastdbcmd -entry all -outfmt $'%%a\\t%%T\\t%%t' output")
    parser.add_argument("--taxdump", type=Path, required=True,
                        help="Directory containing NCBI nodes.dmp, names.dmp and merged.dmp")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--taxonomy-label", required=True, help="Date/release of the saved NCBI taxonomy")
    parser.add_argument("--database-label", required=True, help="Exact protein database name/version")
    args = parser.parse_args()
    try:
        build(args)
    except (OSError, ValueError, IndexError, csv.Error) as exc:
        parser.exit(2, f"ERROR: {exc}\n")


if __name__ == "__main__":
    main()
