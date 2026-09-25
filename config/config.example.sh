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
#HUMAN_GENOME_DB="$FEVIR_DIR/db/GRCh38_p14_genome" 
HUMAN_GENOME_DB="$FEVIR_DIR/db/moreHuman" # for local test
#HUMAN_TRANSCRIPTOME_DB="$FEVIR_DIR/db/gencode_v43_transcripts"
HUMAN_TRANSCRIPTOME_DB="$FEVIR_DIR/db/moreHuman"
HUMAN_EXTRA_DB="$FEVIR_DIR/db/moreHuman"
VIROSAURUS_FASTA="$FEVIR_DIR/db/virosaurus2023/Virosaurus2023.fasta"
VIROSAURUS_METADATA="$FEVIR_DIR/db/virosaurus2023/ref.txt"
RVDB_PROTEIN_DB="$FEVIR_DIR/db/Viral_protein_database/C063gt100-RVDBv12.2-prot.fasta"

# Optional accession-specific minimum covered-nucleotide thresholds.
# Format: accession<TAB>minimum_covered_nt
# Leave empty to disable.
ACCESSION_THRESHOLDS=""

# Defaults 75-bp workflow.
DEFAULT_THREADS=20
DEFAULT_READ_LENGTH=75
MIN_CONTIG_LENGTH=1000
LONG_CONTIG_LENGTH=40000
BLAST_EVALUE=1
BLAST_MAX_TARGETS=3
IDBA_MINK=21
IDBA_MAXK=75
IDBA_STEP=20
