#!/bin/bash

# cleanDatabase2.sh [fileName] [database.fasta]
# do not run several instance in the same directory
#"extrem" setting
# outputfile --> dont change the input file
cp $2 .out

# if <= 100 AA rm entry
grep -v ">" .out > temp.fasta
for n in $(cat temp.fasta);do if [ $(echo $n | wc -c) -le 100 ] ;then echo $n >> temp2.fasta ;fi ; done   
for m in $(cat temp2.fasta); do grep -B1 $m .out >> temp3.fasta ; done
sed -i "/--/d" temp3.fasta
sed -i "s/\[//" temp3.fasta
sed -i "s/\]//" temp3.fasta
for o in $(cat temp3.fasta| cut -d "|" -f 3); do sed -i "/$o/d" .out ; done
rm temp.fasta
rm temp2.fasta
rm temp3.fasta

for i in $(cat $1); do grep -A1 $i $2 >> temp.fasta ; done
sed -i "/\[/d" temp.fasta
sed -i "/--/d" temp.fasta
for j in $(cat temp.fasta); do sed -i "/$j/d" .out ; done
for k in $(cat $1); do sed -i "/$k/d" .out ; done
rm temp.fasta

# rm sequence with motifs XX (hardcoded)

grep -B1 XX .out > temp.fasta
sed -i "/--/d" temp.fasta
sed -i "s/\[//" temp.fasta
sed -i "s/\]//" temp.fasta
for l in $(cat temp.fasta| cut -d "|" -f 3); do sed -i "/$l/d" .out ; done   # cut -d " " -f 1 should also works and be compatible for all fasta (?)

mv .out $2.out
rm temp.fasta
