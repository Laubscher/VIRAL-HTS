#!/usr/bin/env bash
set -euo pipefail

source "$ROOT_DIR/lib/common.sh"

for program in "$SAMTOOLS" "$MINIMAP2" "$BEDTOOLS" "$PYTHON"; do
    require_program "$program"
done

for file in "$VIROSAURUS_FASTA" "$VIROSAURUS_METADATA"; do
    require_file "$file"
done

if [[ "$SKIP_PREPROCESSING" -eq 0 ]]; then
    for program in "$JAVA_BIN" "$CD_HIT_DUP"; do
        require_program "$program"
    done
    ADAPTER_FILE="$ADAPTERS_FASTA"
    [[ "$READ_LAYOUT" != single ]] || ADAPTER_FILE="$ADAPTERS_FASTA_SE"
    for file in "$TRIMMOMATIC_JAR" "$ADAPTER_FILE"; do
        require_file "$file"
    done
fi

if [[ "$SKIP_HOST_DEPLETION" -eq 0 ]]; then
    require_program "$SNAP_ALIGNER"
    while IFS= read -r database; do
        [[ -d "$database" ]] || die "SNAP index directory not found: $database"
        for index_file in Genome GenomeIndex GenomeIndexHash OverflowTable; do
            [[ -f "$database/$index_file" && -r "$database/$index_file" ]] \
                || die "Incomplete or unreadable SNAP index: $database/$index_file"
        done
    done < "$HOST_DB_LIST"
fi

if [[ -n "$ACCESSION_THRESHOLDS" ]]; then
    require_file "$ACCESSION_THRESHOLDS"
fi

if [[ "$SKIP_DENOVO" -eq 0 ]]; then
    for program in "$FQ2FA" "$IDBA_UD" "$BLASTX" "$BLASTDBCMD"; do
        require_program "$program"
    done
    if [[ "$READ_LAYOUT" == single ]]; then
        IDBA_HELP="$("$IDBA_UD" 2>&1 || true)"
        [[ "$IDBA_HELP" == *"--single"* ]] || die "Single-end requires the supplied IDBA-UD with --single support: $IDBA_UD"
    fi
    "$BLASTDBCMD" -db "\"$RVDB_PROTEIN_DB\"" -dbtype prot -info \
        > "$SAMPLE_DIR/logs/rvdb.info.txt" \
        || die "Cannot open the indexed protein BLAST database: $RVDB_PROTEIN_DB"
fi

log "Dependencies and reference paths checked"
