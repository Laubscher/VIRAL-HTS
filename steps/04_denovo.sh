#!/usr/bin/env bash
set -euo pipefail

source "$ROOT_DIR/lib/common.sh"

WORK="$SAMPLE_DIR/work/04_denovo"
RESULTS="$SAMPLE_DIR/results/denovo"
ASSEMBLY_RESULTS="$RESULTS/assembly"
LOGS="$SAMPLE_DIR/logs"
mkdir -p "$WORK" "$ASSEMBLY_RESULTS" "$LOGS"

INPUT_R1="$(<"$SAMPLE_DIR/work/host_depleted_r1.path")"
ASSEMBLY_DIR="$WORK/idba_ud"
READ_FASTA="$WORK/${SAMPLE}.reads.fasta"
ASSEMBLY="$ASSEMBLY_RESULTS/${SAMPLE}.assembly.fasta"
CONTIGS="$ASSEMBLY_RESULTS/${SAMPLE}.contigs.min${MIN_CONTIG_LENGTH}.fasta"
LONG_CONTIGS="$ASSEMBLY_RESULTS/${SAMPLE}.contigs.min${LONG_CONTIG_LENGTH}.fasta"
BLAST="$ASSEMBLY_RESULTS/${SAMPLE}.blastx.tsv"
VIRAL_CONTIGS="$ASSEMBLY_RESULTS/${SAMPLE}.viral_contigs.fasta"

summarize_families() {
    local summary_args=(--fasta "$CONTIGS" --blast "$BLAST"
        --output-prefix "$RESULTS/$SAMPLE"
        --families-dir "$RESULTS/families"
        --details-dir "$ASSEMBLY_RESULTS"
        --no-summary-json
        --max-evalue "$DENOVO_FAMILY_EVALUE"
        --blast-max-targets "$BLAST_MAX_TARGETS")
    if [[ -f "$RVDB_FAMILY_MAP" ]]; then
        summary_args+=(--taxonomy-map "$RVDB_FAMILY_MAP")
    else
        log "De novo family map absent: $RVDB_FAMILY_MAP; writing contig audit without family assignments"
    fi
    "$PYTHON" "$ROOT_DIR/lib/summarize_denovo_families.py" "${summary_args[@]}"
}

if [[ ! -s "$INPUT_R1" ]]; then
    for output in "$ASSEMBLY" "$CONTIGS" "$LONG_CONTIGS" "$BLAST" "$VIRAL_CONTIGS"; do
        : > "$output"
    done
    printf 'metric\tvalue\nreads\t0\nbases\t0\nminimum_read_length\t0\nmaximum_read_length\t0\n' \
        > "$LOGS/${SAMPLE}.input_stats.tsv"
    log "De novo: no reads remain after host depletion"
    summarize_families
    exit 0
fi

IDBA_ARGS=()
CHECK_ARGS=(--r1 "$INPUT_R1")
if [[ "$READ_LAYOUT" == paired ]]; then
    INPUT_R2="$(<"$SAMPLE_DIR/work/host_depleted_r2.path")"
    CHECK_ARGS+=(--r2 "$INPUT_R2")
else
    IDBA_ARGS+=(--single)
fi
IDBA_HELP="$("$IDBA_UD" 2>&1 || true)"
READ_LIMIT_PATTERN='fasta read file \(<=([0-9]+)\)'
[[ "$IDBA_HELP" =~ $READ_LIMIT_PATTERN ]] || die "Cannot determine the IDBA-UD read-length limit"
"$PYTHON" "$ROOT_DIR/lib/check_assembly_reads.py" "${CHECK_ARGS[@]}" \
    --maximum-length "${BASH_REMATCH[1]}" --output "$LOGS/${SAMPLE}.input_stats.tsv"

if [[ "$READ_LAYOUT" == paired ]]; then
    log "De novo: interleaving paired FASTQ into FASTA"
    "$FQ2FA" --merge "$INPUT_R1" "$INPUT_R2" "$READ_FASTA"
else
    log "De novo: converting single-end FASTQ into FASTA"
    "$FQ2FA" "$INPUT_R1" "$READ_FASTA"
fi

log "De novo: IDBA-UD assembly ($READ_LAYOUT)"
"$IDBA_UD" "${IDBA_ARGS[@]}" --pre_correction --num_threads "$THREADS" \
    --step "$IDBA_STEP" --mink "$IDBA_MINK" --maxk "$IDBA_MAXK" \
    -r "$READ_FASTA" -o "$ASSEMBLY_DIR"

if [[ "$READ_LAYOUT" == paired && -s "$ASSEMBLY_DIR/scaffold.fa" ]]; then
    cp "$ASSEMBLY_DIR/scaffold.fa" "$ASSEMBLY"
elif [[ -f "$ASSEMBLY_DIR/contig.fa" ]]; then
    cp "$ASSEMBLY_DIR/contig.fa" "$ASSEMBLY"
    if [[ "$READ_LAYOUT" == paired ]]; then
        log "De novo: no nonempty scaffold output; retaining contigs"
    fi
elif [[ -f "$ASSEMBLY_DIR/contig-${IDBA_MAXK}.fa" ]]; then
    cp "$ASSEMBLY_DIR/contig-${IDBA_MAXK}.fa" "$ASSEMBLY"
else
    die "IDBA-UD finished without an assembly file: $ASSEMBLY_DIR"
fi

"$PYTHON" "$ROOT_DIR/lib/filter_fasta.py" \
    --input "$ASSEMBLY" --minimum-length "$MIN_CONTIG_LENGTH" --output "$CONTIGS"
"$PYTHON" "$ROOT_DIR/lib/filter_fasta.py" \
    --input "$ASSEMBLY" --minimum-length "$LONG_CONTIG_LENGTH" --output "$LONG_CONTIGS"

if [[ ! -s "$CONTIGS" ]]; then
    : > "$BLAST"
    : > "$VIRAL_CONTIGS"
    log "De novo: no contig reached ${MIN_CONTIG_LENGTH} nt; BLASTx skipped"
    summarize_families
    exit 0
fi

log "De novo: BLASTx against $RVDB_PROTEIN_DB"
"$BLASTX" -query "$CONTIGS" -db "\"$RVDB_PROTEIN_DB\"" \
    -num_threads "$THREADS" -evalue "$BLAST_EVALUE" \
    -max_target_seqs "$BLAST_MAX_TARGETS" \
    -outfmt '6 qseqid sacc stitle pident length evalue bitscore qlen qstart qend' \
    -out "$BLAST"

"$PYTHON" "$ROOT_DIR/lib/extract_blast_hits.py" \
    --fasta "$CONTIGS" --blast "$BLAST" --output "$VIRAL_CONTIGS"

summarize_families
log "De novo analysis completed"
