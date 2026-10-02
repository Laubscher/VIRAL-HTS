#!/usr/bin/env bash
set -euo pipefail

source "$ROOT_DIR/lib/common.sh"

WORK="$SAMPLE_DIR/work/02_host_depletion"
RESULTS="$SAMPLE_DIR/results/reads"
SNAP_ARGS=()
if [[ "${SNAP_USE_HUGE_PAGES:-0}" -eq 1 ]]; then SNAP_ARGS+=(-hp); fi
mkdir -p "$RESULTS"
mapfile -t HOST_DATABASES < "$HOST_DB_LIST"
if ((${#HOST_DATABASES[@]})); then mkdir -p "$WORK"; fi

INPUT_R1="$(<"$SAMPLE_DIR/work/preprocessed_r1.path")"
INPUT_R2=""
if [[ "$READ_LAYOUT" == paired ]]; then
    INPUT_R2="$(<"$SAMPLE_DIR/work/preprocessed_r2.path")"
fi

deplete_database() {
    local label="$1"
    local database="$2"
    local input_r1="$3"
    local input_r2="$4"
    local output_r1="$5"
    local output_r2="$6"
    local bam="$WORK/${SAMPLE}.${label}.bam"
    local unmapped="$WORK/${SAMPLE}.${label}.unmapped.bam"
    local sorted="$WORK/${SAMPLE}.${label}.unmapped.name_sorted.bam"

    if [[ ! -s "$input_r1" ]]; then
        log "Host depletion: no reads to process against $label"
        : > "$output_r1"
        if [[ "$READ_LAYOUT" == paired ]]; then : > "$output_r2"; fi
        return
    fi
    log "Host depletion: $label against $database"
    if [[ "$READ_LAYOUT" == single ]]; then
        "$SNAP_ALIGNER" single "$database" "$input_r1" \
            -t "$THREADS" -d 16 "${SNAP_ARGS[@]}" -f -x -E u -mrl 50 -o "$bam"
        "$SAMTOOLS" view -uh -f 0x04 -o "$unmapped" "$bam"

        "$SAMTOOLS" fastq -n "$unmapped" > "$output_r1"
        return
    fi
    "$SNAP_ALIGNER" paired "$database" "$input_r1" "$input_r2" \
        -t "$THREADS" -d 16 "${SNAP_ARGS[@]}" -f -x -E u -F b -mrl 50 -o "$bam"


    "$SAMTOOLS" view -uh -f 0x04 -o "$unmapped" "$bam"
    "$SAMTOOLS" sort -@ "$THREADS" -n "$unmapped" -o "$sorted"
    "$SAMTOOLS" fastq -n \
        -1 "$output_r1" -2 "$output_r2" \
        -0 /dev/null -s /dev/null "$sorted"
}

FINAL_R1="$INPUT_R1"
FINAL_R2="$INPUT_R2"
for index in "${!HOST_DATABASES[@]}"; do
    printf -v label 'host_%03d' "$((index + 1))"
    NEXT_R1="$WORK/${SAMPLE}.${label}.filtered.R1.fastq"
    NEXT_R2="$WORK/${SAMPLE}.${label}.filtered.R2.fastq"
    if (( index + 1 == ${#HOST_DATABASES[@]} )); then
        NEXT_R1="$WORK/${SAMPLE}.host_depleted.R1.fastq"
        NEXT_R2="$WORK/${SAMPLE}.host_depleted.R2.fastq"
    fi
    deplete_database "$label" "${HOST_DATABASES[$index]}" \
        "$FINAL_R1" "$FINAL_R2" "$NEXT_R1" "$NEXT_R2"
    FINAL_R1="$NEXT_R1"
    FINAL_R2="$NEXT_R2"
done

if [[ "$READ_LAYOUT" == paired ]]; then
    gzip -c "$FINAL_R1" > "$RESULTS/${SAMPLE}.filtered.R1.fastq.gz"
    gzip -c "$FINAL_R2" > "$RESULTS/${SAMPLE}.filtered.R2.fastq.gz"
else
    gzip -c "$FINAL_R1" > "$RESULTS/${SAMPLE}.filtered.SE.fastq.gz"
fi

if ((${#HOST_DATABASES[@]})); then
    "$PYTHON" "$ROOT_DIR/lib/append_host_stats.py" \
        --stats "$SAMPLE_DIR/results/preprocessing_stats.tsv" \
        --deduplicated-r1 "$INPUT_R1" \
        --host-depleted-r1 "$FINAL_R1" \
        --layout "$READ_LAYOUT"
    printf 'host_depletion\tcompleted\nhost_database_count\t%s\n' "${#HOST_DATABASES[@]}" \
        >> "$SAMPLE_DIR/results/preprocessing_stats.tsv"
else
    printf 'host_depletion\tskipped\nhost_database_count\t0\n' \
        >> "$SAMPLE_DIR/results/preprocessing_stats.tsv"
fi

printf '%s\n' "$FINAL_R1" > "$SAMPLE_DIR/work/host_depleted_r1.path"
if [[ "$READ_LAYOUT" == paired ]]; then
    printf '%s\n' "$FINAL_R2" > "$SAMPLE_DIR/work/host_depleted_r2.path"
fi

if ((${#HOST_DATABASES[@]})); then
    log "Host depletion completed (${#HOST_DATABASES[@]} SNAP databases)"
else
    log "Host depletion skipped: no --host-db supplied; using trimmed, deduplicated reads"
fi
