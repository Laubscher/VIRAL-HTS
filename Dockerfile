# syntax=docker/dockerfile:1
FROM ubuntu:22.04

RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
       ca-certificates python3 openjdk-17-jre-headless samtools bedtools ncbi-blast+ \
       bash coreutils findutils grep sed gawk gzip \
       libgomp1 libstdc++6 zlib1g libbz2-1.0 liblzma5 libncurses5 libtinfo5 libcurl4 \
    && rm -rf /var/lib/apt/lists/*

ENV PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/opt/fevir/bin" \
    LANG=C.UTF-8 LC_ALL=C.UTF-8 \
    PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 \
    FEVIR_CONTAINER_IMAGE=fevir:1.0.0
LABEL org.opencontainers.image.title="FEVIR" \
      org.opencontainers.image.version="1.0.0"

# Existing tools, sources and notices supplied with FEVIR.
COPY bin/ /opt/fevir/bin/
COPY vendor/idba/ /opt/fevir/vendor/idba/
COPY LICENSE NOTICE /opt/fevir/
COPY fevir.sh VERSION /opt/fevir/
COPY lib/ /opt/fevir/lib/
COPY steps/ /opt/fevir/steps/
COPY files/ /opt/fevir/files/
COPY config/ /opt/fevir/config/

RUN chmod -R a+rX /opt/fevir \
    && chmod a+rx /opt/fevir/fevir.sh \
       /opt/fevir/bin/cd-hit-dup /opt/fevir/bin/snap-aligner \
       /opt/fevir/bin/minimap2 /opt/fevir/bin/idba_ud /opt/fevir/bin/fq2fa \
    && mkdir -p /input /output \
    && chmod 1777 /output

# Viral references and adapters only. Host SNAP indexes are supplied at runtime.
COPY --chmod=0555 db/virosaurus2023/ /opt/fevir/db/virosaurus2023/
COPY --chmod=0555 db/Viral_protein_database/ /opt/fevir/db/Viral_protein_database/
COPY --chmod=0444 db/fasta/TruSeqNexteraAdaptersAll.fa /opt/fevir/db/fasta/TruSeqNexteraAdaptersAll.fa

USER 1000:1000
WORKDIR /output
ENTRYPOINT ["/bin/bash", "/opt/fevir/fevir.sh"]
CMD ["-h"]
