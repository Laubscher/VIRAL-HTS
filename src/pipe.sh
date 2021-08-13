#doit lire et recuperer tout les parametres dans pipe.config
run=$(grep "run=" pipe.config | cut -d"=" -f2)
reads_length=$(grep "reads_length=" pipe.config | cut -d"=" -f2)
prescripteur1=$(grep "prescripteur=" pipe.config | cut -d"=" -f2 | cut -d"_" -f1)
prescripteur2=$(grep "prescripteur=" pipe.config | cut -d"=" -f2 | cut -d"_" -f2)
type_de_sample=$(grep "type_de_sample=" pipe.config | cut -d"=" -f2)
bioinf1=$(grep "bioinf=" pipe.config | cut -d"=" -f2 | cut -d"_" -f1)
bioinf2=$(grep "bioinf=" pipe.config | cut -d"=" -f2 | cut -d"_" -f2)
dbHuman=$(grep "db_human=" pipe.config | cut -d"=" -f2)
dbVirus=$(grep "db_virus=" pipe.config | cut -d"=" -f2)
black_list=$(grep "black_list=" pipe.config | cut -d"=" -f2)
ref=$(grep "ref=" pipe.config | cut -d"=" -f2)
colors=$(grep "colors=" pipe.config | cut -d"=" -f2)
mappeur=$(grep "mappeur=" pipe.config | cut -d"=" -f2)

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

echo "END=false" >> run.log
check=$(grep "END=" run.log | cut -d "=" -f2)

while [ $(echo $check) != "true" ] ;
  do sleep 1m ;
    echo -n "-";
    check=$(grep "END=" run.log | cut -d "=" -f2);
  done;


#sed -i "s/END=false/END=true/" run.log


#bash filter.sh $1 4 RNA
#bash paire.sh $1 db/database/ 4 $1
#python3 metrics.py $1 db/ref.csv  SAFia-HUGv0.2/files/black_list.txt  SAFia-HUGv0.2/files/colors.txt  76
