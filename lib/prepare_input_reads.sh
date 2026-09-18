#!/usr/bin/env bash
set -euo pipefail

source "$ROOT_DIR/lib/common.sh"

WORK="$SAMPLE_DIR/work/00_input"
RESULTS="$SAMPLE_DIR/results/reads"
mkdir -p "$WORK" "$RESULTS"

log "Preprocessing and host depletion skipped (-P): using input reads unchanged"
LABEL=SE
if [[ "$READ_LAYOUT" == paired ]]; then LABEL=R1; fi
INPUT_R1="$WORK/${SAMPLE}.input.${LABEL}.fastq"
open_fastq "$R1" > "$INPUT_R1"
CHECK_ARGS=(--r1 "$INPUT_R1")
if [[ "$READ_LAYOUT" == paired ]]; then
    INPUT_R2="$WORK/${SAMPLE}.input.R2.fastq"
    open_fastq "$R2" > "$INPUT_R2"
    CHECK_ARGS+=(--r2 "$INPUT_R2")
fi

"$PYTHON" "$ROOT_DIR/lib/check_assembly_reads.py" "${CHECK_ARGS[@]}" \
    --output "$SAMPLE_DIR/results/input_stats.tsv"

awk -F '\t' -v layout="$READ_LAYOUT" '
    BEGIN {OFS="\t"; print "metric", "value"}
    $1 == "reads" {
        if (layout == "paired") print "raw_read_pairs", $2 / 2
        else print "raw_reads", $2
    }
    END {print "preprocessing", "skipped"; print "host_depletion", "skipped"}
' "$SAMPLE_DIR/results/input_stats.tsv" > "$SAMPLE_DIR/results/preprocessing_stats.tsv"

gzip -c "$INPUT_R1" > "$RESULTS/${SAMPLE}.input.${LABEL}.fastq.gz"
printf '%s\n' "$INPUT_R1" > "$SAMPLE_DIR/work/host_depleted_r1.path"
if [[ "$READ_LAYOUT" == paired ]]; then
    gzip -c "$INPUT_R2" > "$RESULTS/${SAMPLE}.input.R2.fastq.gz"
    printf '%s\n' "$INPUT_R2" > "$SAMPLE_DIR/work/host_depleted_r2.path"
fi
