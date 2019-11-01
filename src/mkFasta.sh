
for i in $(cat $1) ; do chain=$i ; if [ ${chain:0:1} == ">" ] ; then cluster=$(echo $i | cut -d ">" -f2 | cut -d "," -f2)","$(echo $i | cut -d ">" -f2 | cut -d "," -f1); echo $chain > $(echo $cluster).fasta ; else echo $chain >> $(echo $cluster).fasta ; fi ; done
