#!/bin/bash

re='^[0-9]+$'

# $1 nb CPU

ls *R1*.fastq | cut -d "_" -f 1,2,3 > listFaStQ

for i in $( cat listFaStQ); do

  bash assembl.sh $(echo $i) $1

  cat scaffold_$(echo $i).fa | tr "\n" "!" > scaffold_$(echo $i).fa.temp

  sed -i "s/>/\n/g" scaffold_$(echo $i).fa.temp

  for j in $(cat scaffold_$(echo $i).fa.temp); do

    if [ ${#j} -gt 2010 ]

      then

      echo $(echo ">"$j |  cut -d "!" -f1 ) >> scaffold2_$(echo $i).fa
      echo $(echo $j |  cut -d "!" -f2 ) >> scaffold2_$(echo $i).fa

    fi

  done

  BLASTDB=$2
  blastx -query scaffold2_$(echo $i).fa -db $BLASTDB -num_threads $1 -evalue 1 -num_descriptions 3 -num_alignments 3 > $(echo $i)_blast.txt 

  cat $(echo $i)_blast.txt | tr "\n" "\t" > $(echo $i)_blast.txt.temp

  sed -i "s/Query=/\n/g" $(echo $i)_blast.txt.temp

  cut -f 1,3,6,7 $(echo $i)_blast.txt.temp > $(echo $i)_blast.tsv

  rm $(echo $i)_blast.txt.temp

  for j in $( cat $(echo $i)_blast.tsv|sed "s/[\t]*//g"|sed "s/[ ]*//g" ); do

    BITSCORE1=$( echo $j | cut -d "." -f 5 | cut -d "e" -f 1 )

    BITSCORE2=$( echo $j | cut -d "]" -f 2 | cut -d "e" -f 1 | cut -d "." -f 1 )
    
    if [[ $BITSCORE1 =~ $re ]] 

      then

      if [ $BITSCORE1 -gt 999 ]

        then

        echo ">"$(echo $j) >> $(echo $i).results

        grep $(echo $j | cut -d "L" -f 1)"!" scaffold_$(echo $i).fa.temp | cut -d "!" -f 2 >> $(echo $i).results

      fi 

    fi 

    if [[ $BITSCORE2 =~ $re ]]

      then

      if [ $BITSCORE2 -gt 999 ]

        then

	echo ">"$(echo $j) >> $(echo $i).results

        grep $(echo $j | cut -d "L" -f 1)"!" scaffold_$(echo $i).fa.temp | cut -d "!" -f 2 >> $(echo $i).results

      fi

    fi
  
  done

  rm scaffold_$i.fa.temp
 
done
