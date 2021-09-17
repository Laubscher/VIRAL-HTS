#!/bin/bash
# $1 chemin+prefix
#$2 chemin
#$3 nom/prefix
#$4  num d'analyse
#  nom du run ngs
# prescripteur
#  prescripteur
#  type de sample
#  Florian
#  Laubscher

chemin=$2

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

if [ -z "$bioinf1" ]; then
bioinf1="Florian"
fi

if [ -z "$bioinf2" ]; then
bioinf2="Laubscher"
fi

while getopts ":h" opt; do
	case $opt in
                 h)  
                       echo "Usage : mkMd.sh  options(-h display this help) [prefix] [num d'analyse] [nom du run ngs] [prescripteur] [prescripteur] [type de sample] [bioinformaticien] [bioinformaticien]"
                       exit 0
                       ;;

		\?)
			echo "Unknown option $OPTARG" >&2
			;;
	esac
done

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

total=$(echo $(wc -l $1_R1_001.fastq ) | cut -d" " -f1)

total=$(expr $total / 2 )
unique=$(echo $(wc -l $1_tr_dup_R1_001.fastq) | cut -d" " -f1)

unique=$(expr $unique / 2 )

noHuman=$(echo  $(wc -l $1_tr_dup_R1_001.fastq) | cut -d" " -f1)
noHuman=$(expr $noHuman / 2 )

> $chemin/generatedReport.md


#echo "# Header" >> $chemin/generatedReport.md
echo "![](./Pictures/HUG_LOGO_POS-324x115.jpg)">> $chemin/generatedReport.md
echo "" >> $chemin/generatedReport.md
echo "Nom de l'échantillon: "$3  >> $chemin/generatedReport.md
echo "" >> $chemin/generatedReport.md
echo "Numéro de run: "$run >> $chemin/generatedReport.md
echo "" >> $chemin/generatedReport.md
echo "Numéro de l'Analyse: "$4 >> $chemin/generatedReport.md
echo "" >> $chemin/generatedReport.md
echo "Type d'échantillon: "$type_de_sample  >> $chemin/generatedReport.md
echo "" >> $chemin/generatedReport.md
echo "Date du rapport:
"$(date +'%d/%m/%Y')  >> $chemin/generatedReport.md
echo "" >> $chemin/generatedReport.md
echo "Préscripteur: "$prescripteur1" "$prescripteur2  >> $chemin/generatedReport.md
echo "" >> $chemin/generatedReport.md
echo -n "Analysé par: "$bioinf1" "$bioinf2   >> $chemin/generatedReport.md
echo "[^2]"   >> $chemin/generatedReport.md

cat $chemin/CDV*_best.tsv | cut -f1,2,3,4,5,6,7,8 --output-delimiter ","  | sed "s/^\ *//g" | sed "s/ /$/g" > $chemin/CDV_best.csv

#get cdv reads
for line in $(cat $chemin/CDV_best.csv); do if [ $(echo $line |cut -f1 -d ",") != Virus ]; then CDV=$(echo $line | cut -f4 -d ",")  ; fi ; done

#ratio cdv / total
CDVratio=$(echo 'print(round('$CDV'/'$total'*100, 3))' | python3)

#$(($CDV/$total \* 100 ))
echo "
###reads:

total | unique/filtré | CDV total | % CDV
:---------------|:---------------|:---------------|:---------------|" >> $chemin/generatedReport.md
echo $total" | "$unique" | "$CDV" | "$CDVratio" |" >> $chemin/generatedReport.md

cat $1_best.tsv | cut -f1,2,3,4,5,6,7,8 --output-delimiter ","  | sed "s/^\ *//g" | sed "s/ /$/g" > $1_best.csv

echo "

###(na)[^1] Virus relevants détéctés par metagénomique:
(Coverage >= 300 bp)

Virus | % coverage | Depth(Median) | Reads |
:---------------|:---------------|:---------------|:---------------|" >> $chemin/generatedReport.md

for line in $(cat $1_best.csv); do if [ $(echo $line |cut -f1 -d ",") != Virus ]; then echo $line | cut -f1,2,3,4 -d "," --output-delimiter "|"   ; fi ; done  >> $chemin/generatedReport.md

echo "

###Détails virus:

Virus | Coverage | length(reference) | Acession number |
:---------------|:---------------|:---------------|:---------------|" >> $chemin/generatedReport.md

for line in $(cat $1_best.csv); do if [ $(echo $line |cut -f1 -d ",") != Virus ]; then echo $line | cut -f1,5,6,8 -d "," --output-delimiter "|"  ; fi ; done   >> $chemin/generatedReport.md

echo "

###Control:

Virus | % coverage | Depth(Median) | Reads |
:---------------|:---------------|:---------------|:---------------|" >> $chemin/generatedReport.md

for line in $(cat $chemin/CDV_best.csv); do if [ $(echo $line |cut -f1 -d ",") != Virus ]; then echo $line | cut -f1,2,3,4 -d "," --output-delimiter "|"   ; fi ; done  >> $chemin/generatedReport.md

echo "

[^1]:(na) analyse non accréditée

[^2]:Version logiciel; Pipeline: FEVIR-SAFIA [Version 0.1]: T.Junier & F.Laubscher, Mapper: VIRUS_MATCH [HUG VERSION=1.0]: (c) N.Guex & C.Iseli, Database: Virosaurus90 [20180906]: (c) P.Lemercier & A.Gleize,
Dependences: BASH [4.2.46(2)-release] Python [3.5.2] R [3.4.2].

"  >> $chemin/generatedReport.md

sed -i "s/\\$/\\ /g" $chemin/generatedReport.md

#pandoc -o output.pdf -f markdown -t latex generatedReport.md

#pandoc -o output.docx -f markdown -t docx report.markdown

pandoc -o $chemin/output.odt -f markdown -t odt $chemin/generatedReport.md