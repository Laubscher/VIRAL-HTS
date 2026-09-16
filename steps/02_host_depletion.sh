#!/usr/bin/env bash
set -euo pipefail

source "$ROOT_DIR/lib/common.sh"

WORK="$SAMPLE_DIR/work/02_host_depletion"
RESULTS="$SAMPLE_DIR/results/reads"
mkdir -p "$WORK" "$RESULTS"

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
    log "Host depletion: mapping against $label"
    if [[ "$READ_LAYOUT" == single ]]; then
        "$SNAP_ALIGNER" single "$database" "$input_r1" \
            -t "$THREADS" -d 16 -hp -f -x -E u -mrl 50 -o "$bam"
        "$SAMTOOLS" view -uh -f 0x04 -o "$unmapped" "$bam"

        "$SAMTOOLS" fastq -n "$unmapped" > "$output_r1"
        return
    fi
    "$SNAP_ALIGNER" paired "$database" "$input_r1" "$input_r2" \
        -t "$THREADS" -d 16 -hp -f -x -E u -F b -mrl 50 -o "$bam"


    "$SAMTOOLS" view -uh -f 0x04 -o "$unmapped" "$bam"
    "$SAMTOOLS" sort -@ "$THREADS" -n "$unmapped" -o "$sorted"
    "$SAMTOOLS" fastq -n \
        -1 "$output_r1" -2 "$output_r2" \
        -0 /dev/null -s /dev/null "$sorted"
}

GENOME_R1="$WORK/${SAMPLE}.no_genome.R1.fastq"
GENOME_R2="$WORK/${SAMPLE}.no_genome.R2.fastq"
TRANSCRIPTOME_R1="$WORK/${SAMPLE}.no_transcriptome.R1.fastq"
TRANSCRIPTOME_R2="$WORK/${SAMPLE}.no_transcriptome.R2.fastq"
FINAL_R1="$WORK/${SAMPLE}.host_depleted.R1.fastq"
FINAL_R2="$WORK/${SAMPLE}.host_depleted.R2.fastq"

deplete_database "GRCh38.p14" "$HUMAN_GENOME_DB" \
    "$INPUT_R1" "$INPUT_R2" "$GENOME_R1" "$GENOME_R2"
deplete_database "GENCODE.v43" "$HUMAN_TRANSCRIPTOME_DB" \
    "$GENOME_R1" "$GENOME_R2" "$TRANSCRIPTOME_R1" "$TRANSCRIPTOME_R2"
deplete_database "moreHuman.2023" "$HUMAN_EXTRA_DB" \
    "$TRANSCRIPTOME_R1" "$TRANSCRIPTOME_R2" "$FINAL_R1" "$FINAL_R2"

if [[ "$READ_LAYOUT" == paired ]]; then
    gzip -c "$FINAL_R1" > "$RESULTS/${SAMPLE}.filtered.R1.fastq.gz"
    gzip -c "$FINAL_R2" > "$RESULTS/${SAMPLE}.filtered.R2.fastq.gz"
else
    gzip -c "$FINAL_R1" > "$RESULTS/${SAMPLE}.filtered.SE.fastq.gz"
fi

"$PYTHON" "$ROOT_DIR/bin/append_host_stats.py" \
    --stats "$SAMPLE_DIR/results/preprocessing_stats.tsv" \
    --deduplicated-r1 "$INPUT_R1" \
    --host-depleted-r1 "$FINAL_R1" \
    --layout "$READ_LAYOUT"

printf '%s\n' "$FINAL_R1" > "$SAMPLE_DIR/work/host_depleted_r1.path"
if [[ "$READ_LAYOUT" == paired ]]; then
    printf '%s\n' "$FINAL_R2" > "$SAMPLE_DIR/work/host_depleted_r2.path"
fi

log "Host depletion completed"
