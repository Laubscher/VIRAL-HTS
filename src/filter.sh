#!/bin/bash

# HUMAN filter

if [ -z "$*" ]; then 
echo "Arguments are missing"

fi

DB=$3   #PATH to database
DB=db/RNA38
DISPLAY="GRChXX_pXX genome"

if [ -z "$2" ]; then
CPU=12
else
CPU=$2
fi

while getopts ":h" opt; do
	case $opt in
                 h)  
                       echo "Usage : ffilter -options(-h display this help) [fastqPrefix] [nb of cpu] [database]"
                       exit 0
                       ;;

		\?)
			echo "Unknown option $OPTARG" >&2
			;;
	esac
done

snap-aligner paired $DB $(echo $1)_R1_001.fastq $(echo $1)_R2_001.fastq -t $CPU -d 16 -hp -f -x -F u -mrl 50 -o $1.bam

samtools view -uh -o $1.2.bam -f 0x04 $1.bam
samtools sort -@ $CPU -n $1.2.bam -o $1.bam.sorted

samtools fastq -1 $1_fl_R1_001.fastq -2 $1_fl_R2_001.fastq -0 /dev/null -s /dev/null -n $1.bam.sorted

#cleaning
rm $(echo $1).bam
rm $(echo $1).2.bam
rm $(echo $1).bam.sorted



exit 0
