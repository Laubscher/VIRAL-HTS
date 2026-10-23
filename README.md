Copyright (C) 2020 Thomas Junier and Florian Laubscher

# FEVIR
Viral detection from high-throughput sequencing data

### FEVIR v1.0.0
```text
+ Single-end (SE) support
+ De novo contig preclassification by viral family
```
### Container

```bash
docker build --platform linux/amd64 -t fevir:1.0.0 .
docker save -o fevir-1.0.0.tar fevir:1.0.0
singularity build --force fevir-1.0.0.sif docker-archive:fevir-1.0.0.tar
```
### Usage
```bash
  fevir.sh -1 reads_R1.fastq[.gz] -2 reads_R2.fastq[.gz] -s SAMPLE [options]
  fevir.sh -U reads.fastq[.gz] -s SAMPLE [options]

Reference detection, IDBA-UD assembly and RVDB-prot BLASTx.
Input reads are used unchanged unless --preprocess is supplied.

Input (choose one layout):
  -1 FILE      Paired-end Illumina R1 FASTQ (requires -2)
  -2 FILE      Paired-end Illumina R2 FASTQ (requires -1)
  -U FILE      Single-end Illumina FASTQ (cannot be combined with -1/-2)

Required:
  -s NAME      Sample name

Options:
  -o DIR       Output root (default: ./fevir_output)
  -c FILE      Configuration file (default: config/config.sh)
  -t INT       Threads (default from configuration)
  -l INT       Original read length (default from configuration)
  -k           Keep intermediate files
  --preprocess Enable adapter/quality trimming and deduplication
  --host-db DIR
               Prebuilt SNAP index directory (repeatable, requires --preprocess).
               Filter remaining reads against each index in the supplied order.
               Without --host-db, no host depletion is performed. No FASTA indexing.
  -P           Explicitly skip all preprocessing (the default; legacy alias)
  -D           Skip de novo assembly and BLASTx
  -h           Show this help
```