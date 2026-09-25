#!/bin/bash

# rmLessThan50AA.sh [database.fasta]
# do not run several instance in the same directory

# outputfile --> dont change the input file
cp $1 .out



# if <= 50 AA rm entry
grep -v ">" .out > temp.fasta
for n in $(cat temp.fasta);do if [ $(echo $n | wc -c) -le 50 ] ;then echo $n >> temp2.fasta ;fi ; done   
for m in $(cat temp2.fasta); do grep -B1 $m .out >> temp3.fasta ; done
sed -i "/--/d" temp3.fasta
sed -i "s/\[//" temp3.fasta
sed -i "s/\]//" temp3.fasta
for o in $(cat temp3.fasta| cut -d "|" -f 3); do sed -i "/$o/d" .out ; done  # cut -d " " -f 1 should also works and be compatible for all fasta (?)
rm temp.fasta
rm temp2.fasta
rm temp2.fasta

mv .out $1.out
