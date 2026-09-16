#!/usr/bin/env bash
set -euo pipefail

source "$ROOT_DIR/lib/common.sh"

WORK="$SAMPLE_DIR/work/03_reference_detection"
RESULTS="$SAMPLE_DIR/results/reference_detection"
mkdir -p "$WORK" "$RESULTS"

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
BAM="$WORK/${SAMPLE}.virosaurus.bam"
SORTED_BAM="$WORK/${SAMPLE}.virosaurus.sorted.bam"
COUNTS="$WORK/${SAMPLE}.read_counts.tsv"
BEDGRAPH="$RESULTS/${SAMPLE}.coverage.bedgraph"

if [[ -s "$INPUT_R1" ]]; then
    log "Reference detection: mapping reads against Virosaurus 2023 ($READ_LAYOUT)"
    "$MINIMAP2" -t "$THREADS" -ax sr "${LAYOUT_ARGS[@]}" "$VIROSAURUS_FASTA" "${READ_INPUTS[@]}" > "$SAM"
    "$SAMTOOLS" view -S -b "$SAM" > "$BAM"

    # Count unique read/reference/template-length tuples as in the historical pipeline.
    "$SAMTOOLS" view -F 4 "$BAM" \
        | cut -f1,3,9 \
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
    --all-output "$RESULTS/${SAMPLE}.all_hits.tsv"
    --best-output "$RESULTS/${SAMPLE}.detected_viruses.tsv"
)
if [[ -n "$ACCESSION_THRESHOLDS" ]]; then
    METRIC_ARGS+=(--accession-thresholds "$ACCESSION_THRESHOLDS")
fi

"$PYTHON" "$ROOT_DIR/bin/compute_metrics.py" "${METRIC_ARGS[@]}"

log "Reference detection completed"
