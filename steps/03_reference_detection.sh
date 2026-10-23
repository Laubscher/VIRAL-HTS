#!/usr/bin/env bash
set -euo pipefail

source "$ROOT_DIR/lib/common.sh"

WORK="$SAMPLE_DIR/work/03_reference_detection"
RESULTS="$SAMPLE_DIR/results/reference_detection"
MAPPING_RESULTS="$RESULTS/mapping"
mkdir -p "$WORK" "$MAPPING_RESULTS"
INPUT_R1="$(<"$SAMPLE_DIR/work/host_depleted_r1.path")"
READ_INPUTS=("$INPUT_R1")
LAYOUT_ARGS=()
if [[ "$READ_LAYOUT" == paired ]]; then
    READ_INPUTS+=("$(<"$SAMPLE_DIR/work/host_depleted_r2.path")")
else
    # Explicitly prevent pairing adjacent records with matching names.
    LAYOUT_ARGS+=(--frag=no)
fi
SAM="$WORK/${SAMPLE}.virosaurus.sam"
FILTERED_SAM="$WORK/${SAMPLE}.virosaurus.family_filtered.sam"
BAM="$WORK/${SAMPLE}.virosaurus.bam"
SORTED_BAM="$WORK/${SAMPLE}.virosaurus.sorted.bam"
COUNTS="$WORK/${SAMPLE}.read_counts.tsv"
BEDGRAPH="$MAPPING_RESULTS/${SAMPLE}.coverage.bga"
if [[ -s "$INPUT_R1" ]]; then
    log "Reference detection: mapping reads against Virosaurus 2023 ($READ_LAYOUT)"
    "$MINIMAP2" -t "$THREADS" -ax sr --secondary=yes "${LAYOUT_ARGS[@]}" "$VIROSAURUS_FASTA" "${READ_INPUTS[@]}" > "$SAM"
    "$PYTHON" "$ROOT_DIR/lib/filter_secondary_by_family.py" \
        --metadata "$VIROSAURUS_METADATA" --input "$SAM" --output "$FILTERED_SAM"
    "$SAMTOOLS" view -S -b -F 4 "$FILTERED_SAM" > "$BAM"
    # Count distinct read ends per accession, avoiding repeated secondary mappings and the unreliable TLEN=0 of secondary alignments.
    "$SAMTOOLS" view -F 4 "$BAM" \
        | awk 'BEGIN {OFS="\t"} {mate=(int($2/64)%2)?"1":((int($2/128)%2)?"2":"S"); print $1,$3,mate}' \
        | LC_ALL=C sort -u \
        | cut -f2 \
        | LC_ALL=C sort \
        | uniq -c \
        | awk 'BEGIN {OFS="\t"} {print $2,$1}' > "$COUNTS"
    "$SAMTOOLS" sort -@ "$THREADS" "$BAM" -o "$SORTED_BAM"
    "$BEDTOOLS" genomecov -ibam "$SORTED_BAM" -bga > "$BEDGRAPH"
else
    log "Reference detection: no reads remain after preprocessing and host depletion"
    : > "$COUNTS"
    : > "$BEDGRAPH"
fi
METRIC_ARGS=(
    --bedgraph "$BEDGRAPH"
    --read-counts "$COUNTS"
    --metadata "$VIROSAURUS_METADATA"
    --read-length "$READ_LENGTH"
    --all-output "$MAPPING_RESULTS/${SAMPLE}.all_hits.tsv"
    --best-output "$RESULTS/${SAMPLE}.best_hits.tsv"
)
if [[ -n "$ACCESSION_THRESHOLDS" ]]; then
    METRIC_ARGS+=(--accession-thresholds "$ACCESSION_THRESHOLDS")
fi

"$PYTHON" "$ROOT_DIR/lib/compute_metrics.py" "${METRIC_ARGS[@]}"
# Remove within-family species calls lacking independent coverage; preserve in all_hits.
COMPETITION_ARGS=(
    --sam "$FILTERED_SAM"
    --all-hits "$MAPPING_RESULTS/${SAMPLE}.all_hits.tsv"
    --best-hits "$RESULTS/${SAMPLE}.best_hits.tsv"
    --read-length "$READ_LENGTH"
)
if [[ -n "$ACCESSION_THRESHOLDS" ]]; then
    COMPETITION_ARGS+=(--accession-thresholds "$ACCESSION_THRESHOLDS")
fi
if [[ -s "$INPUT_R1" ]]; then
    "$PYTHON" "$ROOT_DIR/lib/filter_competing_species.py" "${COMPETITION_ARGS[@]}"
fi

log "Reference detection completed"
