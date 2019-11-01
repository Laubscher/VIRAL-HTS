#!/bin/bash

NAME=$(echo $1 |rev |cut -d "/" -f 1 | rev) 
OUTPUT=$(echo $4)
TEMPNAME=$(echo $OUTPUT/$NAME)
CPU=$(echo $2)
VIRUSDB=$(echo $3)

TIME=$(date +%s)

tagdust -t $CPU -dust 16 -1 R:N <(gzip -dc $1_R1_001.fastq.gz) <(gzip -dc $1_R2_001.fastq.gz) -o $TEMPNAME

rm $(echo $TEMPNAME)_logfile.txt $(echo $TEMPNAME)_un_READ1.fq $(echo $TEMPNAME)_un_READ2.fq
  
echo "unziping/Low-Complexity Filtering :"$(($(date +%s) - $TIME))" sec."
TIME=$(date +%s)

mv $(echo $TEMPNAME)_READ1.fq $(echo $TEMPNAME)_R1_001.fastq

mv $(echo $TEMPNAME)_READ2.fq $(echo $TEMPNAME)_R2_001.fastq


TIME=$(date +%s)

bash virus_mapping $TEMPNAME $VIRUSDB $CPU 

echo "Virus Mapping :"$(($(date +%s) - $TIME))" sec."
TIME=$(date +%s)

python3 metrics.py $TEMPNAME $(echo $3)/ref.txt black_list.txt colors.txt

echo "Metrics Calculating :"$(($(date +%s) - $TIME))" sec."

TIME=$(date +%s)

Rscript	graphics.r $TEMPNAME 1>/dev/null

echo "PDF :"$(($(date +%s) - $TIME))" sec." 

rm $(echo $TEMPNAME)_R1_001.fastq $(echo $TEMPNAME)_R2_001.fastq

rm $(echo $TEMPNAME)*.bam
exit 0

