OUTPUT=Cluster.fa

cat $1 > $OUTPUT
bash mkFasta.sh $1
for HEADER in $( grep ">" $OUTPUT); do
    grep -A1 $(echo $HEADER | cut -d ">" -f 2| cut -d "," -f 1) $OUTPUT > $(echo $HEADER | cut -d ">" -f 2 | cut -d "," -f 1).fa
       rm *$(echo $HEADER | cut -d ">" -f 2| cut -d "," -f 1)*.fasta
       for i in $(ls *.fasta); do

          cat $(echo $i $(echo $HEADER | cut -d ">" -f 2 | cut -d "," -f 1).fa) > file_bash_alignement_inProgress.fas

          SAME=$(muscle -in file_bash_alignement_inProgress.fas -clw -quiet | grep -o "*" | wc -l)

          LEN=$(muscle -in file_bash_alignement_inProgress.fas -msf -quiet  | grep MSF | cut -d " " -f4)

          PTC_IDENT=$(echo $(calc $SAME/$LEN*100) | cut -d "." -f 1 | cut -d " " -f 3 )
          if [ $PTC_IDENT -gt 79 ]
          then    

            CLST_TESTED=$(echo $HEADER | cut -d ","  -f2)
            CLST_FASTA=$(echo $i | cut -d "_" -f 1,2)_
            
            if [ $CLST_TESTED != $CLST_FASTA ]
            then
              
              echo $(echo $HEADER | cut -d ">" -f 2)" :"
              echo $PTC_IDENT "% identity with" $(echo $i | cut -d "." -f 1)
              echo

              
              if [ $(echo $CLST_TESTED | cut -d "_" -f 2 ) -gt $(echo $i | cut -d "_" -f 2) ]
              then
                sed -i s/$CLST_FASTA/$CLST_TESTED/ $OUTPUT 2>/dev/null
              else
                sed -i s/$CLST_TESTED/$CLST_FASTA/ $OUTPUT 2>/dev/null
              fi 

            fi
          fi
       rm  file_bash_alignement_inProgress.fas
       
       done
    rm  $(echo $HEADER | cut -d ">" -f 2 | cut -d "," -f 1).fa
done
