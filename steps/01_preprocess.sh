#!/usr/bin/env bash
set -euo pipefail

source "$ROOT_DIR/lib/common.sh"

WORK="$SAMPLE_DIR/work/01_preprocess"
RESULTS="$SAMPLE_DIR/results/reads"
LOGS="$SAMPLE_DIR/logs"
mkdir -p "$WORK" "$RESULTS" "$LOGS"

RAW_R1="$WORK/${SAMPLE}.raw.R1.fastq"
RAW_R2="$WORK/${SAMPLE}.raw.R2.fastq"
ADAPTER_R1="$WORK/${SAMPLE}.adapter_trimmed.R1.fastq"
ADAPTER_R2="$WORK/${SAMPLE}.adapter_trimmed.R2.fastq"
QUALITY_R1="$WORK/${SAMPLE}.quality_trimmed.R1.fastq"
QUALITY_R2="$WORK/${SAMPLE}.quality_trimmed.R2.fastq"
DEDUP_R1="$WORK/${SAMPLE}.deduplicated.R1.fastq"
DEDUP_R2="$WORK/${SAMPLE}.deduplicated.R2.fastq"

log "Preprocessing: decompressing input FASTQ files"
open_fastq "$R1" > "$RAW_R1"
if [[ "$READ_LAYOUT" == paired ]]; then
    open_fastq "$R2" > "$RAW_R2"
fi

if [[ "$READ_LAYOUT" == paired ]]; then
    log "Preprocessing: trimming TruSeq/Nextera adapters with Trimmomatic 0.36"
    "$JAVA_BIN" -jar "$TRIMMOMATIC_JAR" PE \
        -threads "$THREADS" \
        "$RAW_R1" "$RAW_R2" \
        "$ADAPTER_R1" "$WORK/adapter.unpaired.R1.fastq" \
        "$ADAPTER_R2" "$WORK/adapter.unpaired.R2.fastq" \
        "ILLUMINACLIP:${ADAPTERS_FASTA}:1:30:7:1:true" MINLEN:65

    log "Preprocessing: quality trimming with Trimmomatic 0.36"
    "$JAVA_BIN" -jar "$TRIMMOMATIC_JAR" PE \
        -threads "$THREADS" \
        "$ADAPTER_R1" "$ADAPTER_R2" \
        "$QUALITY_R1" "$WORK/quality.unpaired.R1.fastq" \
        "$QUALITY_R2" "$WORK/quality.unpaired.R2.fastq" \
        MAXINFO:40:0.3 LEADING:10 TRAILING:10 MINLEN:65
else
    log "Preprocessing: trimming single-end adapters with Trimmomatic 0.36"
    "$JAVA_BIN" -jar "$TRIMMOMATIC_JAR" SE -threads "$THREADS" \
        "$RAW_R1" "$ADAPTER_R1" \
        "ILLUMINACLIP:${ADAPTERS_FASTA_SE}:1:30:7" MINLEN:65

    log "Preprocessing: single-end quality trimming with Trimmomatic 0.36"
    "$JAVA_BIN" -jar "$TRIMMOMATIC_JAR" SE -threads "$THREADS" \
        "$ADAPTER_R1" "$QUALITY_R1" \
        MAXINFO:40:0.3 LEADING:10 TRAILING:10 MINLEN:65
fi

if [[ ! -s "$QUALITY_R1" ]]; then
    log "Preprocessing: no reads remain after trimming"
    : > "$DEDUP_R1"
    if [[ "$READ_LAYOUT" == paired ]]; then : > "$DEDUP_R2"; fi
elif [[ "$READ_LAYOUT" == paired ]]; then
    log "Preprocessing: removing duplicate read pairs with cd-hit-dup 4.6.8"
    "$CD_HIT_DUP" \
        -i "$QUALITY_R1" -i2 "$QUALITY_R2" \
        -o "$DEDUP_R1" -o2 "$DEDUP_R2"
else
    log "Preprocessing: removing single-end duplicates with cd-hit-dup 4.6.8"
    "$CD_HIT_DUP" -i "$QUALITY_R1" -o "$DEDUP_R1"
fi

"$PYTHON" "$ROOT_DIR/lib/fastq_stats.py" \
    --raw-r1 "$RAW_R1" \
    --trimmed-r1 "$QUALITY_R1" \
    --deduplicated-r1 "$DEDUP_R1" \
    --layout "$READ_LAYOUT" \
    --output "$LOGS/preprocessing_stats.tsv"

export PREPROCESSED_R1="$DEDUP_R1"
printf '%s\n' "$PREPROCESSED_R1" > "$SAMPLE_DIR/work/preprocessed_r1.path"
if [[ "$READ_LAYOUT" == paired ]]; then
    printf '%s\n' "$DEDUP_R2" > "$SAMPLE_DIR/work/preprocessed_r2.path"
fi

log "Preprocessing completed"
