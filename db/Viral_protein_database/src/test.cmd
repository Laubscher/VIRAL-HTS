
# pour dégrossir rapidement les résultats (détéction de faux pos) ~ Tout ce qui n'est pas TTV :
grep ">" *res* | grep -v "hypo" | grep -v "ORF1" | grep -v "Orf1"

# dans la database tous ce qui n'as pas (Vv-)irus dans le nom
grep ">" C063gt100-RVDBv12.2-prot.fasta | cut -d "[" -f 2 | cut -d "]" -f 1 | grep -v irus | sort | uniq

