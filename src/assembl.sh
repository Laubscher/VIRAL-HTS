#!/bin/bash

/home/florian/idba-master/bin/fq2fa --merge $1/$2_R1_001.fastq $1/$2_R2_001.fastq $1/$2.fa                        # create a merged sorted file with the two pairs reads that follow each other.

idba_ud --pre_correction --num_threads $3 --step 20 --mink 21 --maxk 100 -r $1/$2.fa -o $1/$2_out

if [ -e $1/$2_out/scaffold.fa ]                                                               # It's may that idba-ud can not make scafold from contig-*.fa file, when it's happend it cause and error
    then                                                                                   # The contig files have to be used instead of the scaffold.fa files. 
    mv $1/$2_out/scaffold.fa $1/scaffold_$2.fa
    else                                             
    mv $1/$2_out/contig-100.fa $1/scaffold_$2.fa                                                # if happend here we used the contig-100.fa file instead of the scafold.fa
    sed -i s/length_.*$//g $1/scaffold_$2.fa                                                  # change to the header of the file to correspond to the format of scaffold.fa
    sed -i s/contig-100_/scaffold_/g $1/scaffold_$2.fa
    sed -i s"/[ ]//"g $1/scaffold_$2.fa
fi
rm -r $1/$2_out/
rm $1/$2.fa
