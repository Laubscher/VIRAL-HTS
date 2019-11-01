#!/bin/bash

fq2fa --merge $(echo $1)_R1_001.fastq $(echo $1)_R2_001.fastq $1.fa                        # create a merged sorted file with the two pairs reads that follow each other.

idba_ud --pre_correction --num_threads $2 --step 20 --mink 21 --maxk 100 -r $1.fa -o $1_out

if [ -e $1_out/scaffold.fa ]                                                               # It's may that idba-ud can not make scafold from contig-*.fa file, when it's happend it cause and error
    then                                                                                   # The contig files have to be used instead of the scaffold.fa files. 
    mv $1_out/scaffold.fa scaffold_$1.fa
    else                                             
    mv $1_out/contig-100.fa scaffold_$1.fa                                                 # if happend here we used the contig-100.fa file instead of the scafold.fa
    sed -i s/length_.*$//g scaffold_$1.fa                                                  # change to the header of the file to correspond to the format of scaffold.fa
    sed -i s/contig-100_/scaffold_/g scaffold_$1.fa               
    sed -i s"/[ ]//"g scaffold_$1.fa    

fi
rm -r $(echo $1)_out/                                                                  
rm $(echo $1).fa                                                                           
