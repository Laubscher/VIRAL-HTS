#!/usr/bin/env bash

FEVIR_DIR="${ROOT_DIR:-$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)}"

# Software
JAVA_BIN="java"
TRIMMOMATIC_JAR="$FEVIR_DIR/bin/trimmomatic-0.36.jar"
CD_HIT_DUP="$FEVIR_DIR/bin/cd-hit-dup"
SNAP_ALIGNER="$FEVIR_DIR/bin/snap-aligner"
SAMTOOLS="samtools"
MINIMAP2="$FEVIR_DIR/bin/minimap2"
BEDTOOLS="bedtools"
PYTHON="python3"
FQ2FA="$FEVIR_DIR/bin/fq2fa"
IDBA_UD="$FEVIR_DIR/bin/idba_ud"
BLASTX="blastx"
BLASTDBCMD="blastdbcmd"

FEVIR_MODULES=()
SNAP_USE_HUGE_PAGES=0

# Reference databases
ADAPTERS_FASTA="$FEVIR_DIR/db/fasta/TruSeqNexteraAdaptersAll.fa"
# Optional single-end adapter file. Empty uses ADAPTERS_FASTA.
ADAPTERS_FASTA_SE=""
# Host indexes are external: --preprocess --host-db /path/to/snap_index
# Repeat --host-db for additional indexes. No host database is selected by default.
VIROSAURUS_FASTA="$FEVIR_DIR/db/virosaurus2023/Virosaurus2023.fasta"
VIROSAURUS_METADATA="$FEVIR_DIR/db/virosaurus2023/ref.txt"
RVDB_PROTEIN_DB="$FEVIR_DIR/db/Viral_protein_database/C063gt100-RVDBv12.2-prot.fasta"
# If absent, contig files are still written, without family assignments.
RVDB_FAMILY_MAP="${RVDB_PROTEIN_DB}.families.tsv"

# Optional accession-specific minimum covered-nucleotide thresholds.
# Format: accession<TAB>threshold (covered_nt must be strictly greater).
# Leave empty to disable.
ACCESSION_THRESHOLDS="$FEVIR_DIR/files/black_list.txt"

# Defaults 75-bp workflow.
DEFAULT_THREADS=20
DEFAULT_READ_LENGTH=75
MIN_CONTIG_LENGTH=1000
LONG_CONTIG_LENGTH=40000
BLAST_EVALUE=1
BLAST_MAX_TARGETS=3
DENOVO_FAMILY_EVALUE=1
IDBA_MINK=21
IDBA_MAXK=75
IDBA_STEP=20
