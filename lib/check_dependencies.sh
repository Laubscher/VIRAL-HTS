#!/usr/bin/env bash
set -euo pipefail

source "$ROOT_DIR/lib/common.sh"

for program in "$JAVA_BIN" "$CD_HIT_DUP" "$SNAP_ALIGNER" "$SAMTOOLS" \
               "$MINIMAP2" "$BEDTOOLS" "$PYTHON"; do
    require_program "$program"
done

ADAPTER_FILE="$ADAPTERS_FASTA"
[[ "$READ_LAYOUT" != single ]] || ADAPTER_FILE="$ADAPTERS_FASTA_SE"
for file in "$TRIMMOMATIC_JAR" "$ADAPTER_FILE" "$VIROSAURUS_FASTA" \
            "$VIROSAURUS_METADATA"; do
    require_file "$file"
done

for database in "$HUMAN_GENOME_DB" "$HUMAN_TRANSCRIPTOME_DB" "$HUMAN_EXTRA_DB"; do
    require_path "$database"
done

if [[ -n "$ACCESSION_THRESHOLDS" ]]; then
    require_file "$ACCESSION_THRESHOLDS"
fi

log "Dependencies and reference paths checked"
