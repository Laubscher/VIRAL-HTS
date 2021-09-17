#!/bin/bash

re='^[0-9]+$'

# $1 nb CPU

i=$3   #prefix
chemin=$4

#ls *R1*.fastq | cut -d "_" -f 1,2,3 > listFaStQ

  bash src/assembl.sh $chemin $i $1

  cat $chemin/scaffold_$(echo $i).fa | tr "\n" "!" > $chemin/scaffold_$(echo $i).fa.temp

  sed -i "s/>/\n/g" $chemin/scaffold_$(echo $i).fa.temp

  for j in $(cat $chemin/scaffold_$(echo $i).fa.temp); do

    if [ ${#j} -gt 2010 ]

      then

      echo $(echo ">"$j |  cut -d "!" -f1 ) >> $chemin/scaffold2_$(echo $i).fa
      echo $(echo $j |  cut -d "!" -f2 ) >> $chemin/scaffold2_$(echo $i).fa

    fi

  done

  BLASTDB=$2
  blastx -query $chemin/scaffold2_$(echo $i).fa -db $BLASTDB -num_threads $1 -evalue 1 -num_descriptions 3 -num_alignments 3 > $chemin/$(echo $i)_blast.txt

  cat $chemin/$(echo $i)_blast.txt | tr "\n" "\t" > $chemin/$(echo $i)_blast.txt.temp

  sed -i "s/Query=/\n/g" $chemin/$(echo $i)_blast.txt.temp

  cut -f 1,3,6,7 $chemin/$(echo $i)_blast.txt.temp > $chemin/$(echo $i)_blast.tsv

  rm $chemin/$(echo $i)_blast.txt.temp

  for j in $( cat $chemin/$(echo $i)_blast.tsv|sed "s/[\t]*//g"|sed "s/[ ]*//g" ); do

    BITSCORE1=$( echo $j | cut -d "." -f 5 | cut -d "e" -f 1 )

    BITSCORE2=$( echo $j | cut -d "]" -f 2 | cut -d "e" -f 1 | cut -d "." -f 1 )
    
    if [[ $BITSCORE1 =~ $re ]] 

      then

      if [ $BITSCORE1 -gt 999 ]

        then

        echo ">"$(echo $j) >> $chemin/$(echo $i).results

        grep $(echo $j | cut -d "L" -f 1)"!" $chemin/scaffold_$(echo $i).fa.temp | cut -d "!" -f 2 >> $chemin/$(echo $i).results

      fi 

    fi 

    if [[ $BITSCORE2 =~ $re ]]

      then

      if [ $BITSCORE2 -gt 999 ]

        then

	echo ">"$(echo $j) >> $chemin/$(echo $i).results

        grep $(echo $j | cut -d "L" -f 1)"!" $chemin/scaffold_$(echo $i).fa.temp | cut -d "!" -f 2 >> $chemin/$(echo $i).results

      fi

    fi
  
  done

  rm $chemin/scaffold_$i.fa.temp
 

