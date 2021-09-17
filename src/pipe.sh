#doit lire et recuperer tout les parametres dans $chemin/pipe.config
chemin=${1%/*}
prefix=${1##*/}
echo "working dir: " $chemin
run=$(grep "run=" $chemin/pipe.config | cut -d"=" -f2)
reads_length=$(grep "reads_length=" $chemin/pipe.config | cut -d"=" -f2)
prescripteur1=$(grep "prescripteur=" $chemin/pipe.config | cut -d"=" -f2 | cut -d"_" -f1)
prescripteur2=$(grep "prescripteur=" $chemin/pipe.config | cut -d"=" -f2 | cut -d"_" -f2)
type_de_sample=$(grep "type_de_sample=" $chemin/pipe.config | cut -d"=" -f2)
bioinf1=$(grep "bioinf=" $chemin/pipe.config | cut -d"=" -f2 | cut -d"_" -f1)
bioinf2=$(grep "bioinf=" $chemin/pipe.config | cut -d"=" -f2 | cut -d"_" -f2)
dbHuman=$(grep "db_human=" $chemin/pipe.config | cut -d"=" -f2)
dbVirus=$(grep "db_virus=" $chemin/pipe.config | cut -d"=" -f2)
black_list=$(grep "black_list=" $chemin/pipe.config | cut -d"=" -f2)
ref=$(grep "ref=" $chemin/pipe.config | cut -d"=" -f2)
colors=$(grep "colors=" $chemin/pipe.config | cut -d"=" -f2)
mappeur=$(grep "mappeur=" $chemin/pipe.config | cut -d"=" -f2)

if [ -z "$run" ]; then

run="not provided"

fi

if [ -z "$reads_length" ]; then

reads_length="not provided"

fi

if [ -z "$prescripteur1" ]; then

prescripteur1="not provided"

fi

if [ -z "$type_de_sample" ]; then

type_de_sample="not provided"

fi

if [ -z "$bioinf" ]; then

bioinf="not provided"

fi

if [ -z "$mappeur" ]; then

mappeur="snap"

fi

echo "                                                  
 ########  ########  ##:  :##   ######   ######:  
 ########  ########  ##    ##   ######   #######  
 ##        ##        :##  ##:     ##     ##   :## 
 ##        ##        :##  ##:     ##     ##    ## 
 ##        ##         ##..##      ##     ##   :## 
 #######   #######    ##::##      ##     #######: 
 #######   #######    ##::##      ##     ######   
 ##        ##         :####:      ##     ##   ##. 
 ##        ##         .####.      ##     ##   ##  
 ##        ##          ####       ##     ##   :## 
 ##        ########    ####     ######   ##    ##:
 ##        ########     ##      ######   ##    ###
"

echo "RUN CONFIG:
run : $run
reads_length : $reads_length
prescripteur : $prescripteur1 $prescripteur2
type_de_sample : $type_de_sample
bioinf : $bioinf1 $bioinf2 
mappeur : $mappeur

__Path to files__
HUMAN DataBase: $dbHuman
VIRAL DataBase: $dbVirus
Black list: $black_list
Sequences info: $ref
Colors file: $colors"

##bash asign.sh

> run.log

#echo "END=false" >> run.log
#check=$(grep "END=" run.log | cut -d "=" -f2)

#while [ $(echo $check) != "true" ] ;
#  do sleep 1m ;
#    echo -n "-";
#    check=$(grep "END=" run.log | cut -d "=" -f2);
#  done;

# bash map  contre cdv  &

echo "_________________"
adapteur=/home/florian/myTools/Trimmomatic-0.36/TruSeqNexteraAdaptersAll.fa

bash src/paired.sh $1 db/NC_001921/ 1  $chemin/CDV_$prefix >> run.log 2>> run.log  &

bash src/adaptr $1 10 $adapteur >> run.log 2>> run.log  &

wait

echo "Reads filtrées"

#lancer le denovo en parallele
bash src/Pro.sh 1 /home/florian/Documents/VIRAL-HTS-1/denovo/db_/Viral_protein_database/C063gt100-RVDBv12.2-prot.fasta $prefix $chemin >> run.log 2>> run.log &

echo "Denovo lancé en parallele"

python3 src/metrics.py $chemin/CDV_$prefix db/NC_001921/ref.csv  SAFia-HUGv0.2/files/black_list.txt  SAFia-HUGv0.2/files/colors.txt  76

echo "map contre virosaurus"

bash src/paired.sh $1_tr_dup_fl db/database/ 10  $chemin/$prefix >> run.log 2>> run.log

python3 src/metrics.py $1 db/ref.csv  SAFia-HUGv0.2/files/black_list.txt  SAFia-HUGv0.2/files/colors.txt  76
echo "generation du rapport"
bash src/mkMd.sh $1 $chemin $prefix

echo "end"
