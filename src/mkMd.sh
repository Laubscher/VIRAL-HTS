#$1 prefix
#$2 num d'analyse
#$3 nom du run ngs
#$4 prescripteur
#$5 prescripteur
#$6 type de sample
#$7 Florian
#$8 Laubscher

if [ -z "$7" ]; then
bioinf1="Florian"
else
bioinf1=$7
fi

if [ -z "$8" ]; then
bioinf2="Laubscher"
else
bioinf2=$8
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

> generatedReport.md

#echo "# Header" >> generatedReport.md
echo "![](./Pictures/HUG_LOGO_POS-324x115.jpg)">> generatedReport.md
echo "" >> generatedReport.md
echo "Nom de l'échantillon: "$1  >> generatedReport.md
echo "" >> generatedReport.md
echo "Numéro de run: "$3 >> generatedReport.md
echo "" >> generatedReport.md
echo "Numéro de l'Analyse: "$2 >> generatedReport.md
echo "" >> generatedReport.md
echo "Type d'échantillon: "$6  >> generatedReport.md
echo "" >> generatedReport.md
echo "Date du raport:
"$(date +'%d/%m/%Y')  >> generatedReport.md
echo "" >> generatedReport.md
echo "Préscripteur: "$4" "$5  >> generatedReport.md
echo "" >> generatedReport.md
echo -n "Analysé par: "$bioinf1" "$bioinf2   >> generatedReport.md
echo "[^2]"   >> generatedReport.md

cat $1_best.tsv | cut -f1,2,3,4,5,6,7,8 --output-delimiter ","  | sed "s/^\ *//g" | sed "s/ /$/g" > $1_best.csv

echo "
###(na)[^1] Virus relevants détéctés par metagénomique:
(Coverage >= 300 bp)

Virus | % coverage | Depth(Median) | Reads |
:---------------|:---------------|:---------------|:---------------|" >> generatedReport.md

for line in $(cat $1_best.csv); do if [ $(echo $line |cut -f1 -d ",") != Virus ]; then echo $line | cut -f1,2,3,4 -d "," --output-delimiter "|"   ; fi ; done  >> generatedReport.md

echo "

###Détails virus:

Virus | Coverage | length(reference) | Acession number |
:---------------|:---------------|:---------------|:---------------|" >> generatedReport.md

for line in $(cat $1_best.csv); do if [ $(echo $line |cut -f1 -d ",") != Virus ]; then echo $line | cut -f1,5,6,8 -d "," --output-delimiter "|"  ; fi ; done   >> generatedReport.md

# pour l'instant un seul cdv par run en tant que deuxième echantillions

cat CDV*_best.tsv | cut -f1,2,3,4,5,6,7,8 --output-delimiter ","  | sed "s/^\ *//g" | sed "s/ /$/g" > CDV_best.csv

echo "

###Control:

Virus | % coverage | Depth(Median) | Reads |
:---------------|:---------------|:---------------|:---------------|" >> generatedReport.md

for line in $(cat $1_best.csv); do if [ $(echo $line |cut -f1 -d ",") != Virus ]; then echo $line | cut -f1,2,3,4 -d "," --output-delimiter "|"   ; fi ; done  >> generatedReport.md

echo "

[^1]:(na) analyse non accréditée

[^2]:Version logiciel; Pipeline: FEVIR-SAFIA [Version 0.1]: T.Junier & F.Laubscher, Mapper: VIRUS_MATCH [HUG VERSION=1.0]: (c) N.Guex & C.Iseli, Database: Virosaurus90 [20180906]: (c) P.Lemercier & A.Gleize,
Dependences: BASH [4.2.46(2)-release] Python [3.5.2] R [3.4.2].

"  >> generatedReport.md

sed -i "s/\\$/\\ /g" generatedReport.md

#pandoc -o output.pdf -f markdown -t latex generatedReport.md

#pandoc -o output.docx -f markdown -t docx report.markdown

pandoc -o output.odt -f markdown -t odt generatedReport.md
