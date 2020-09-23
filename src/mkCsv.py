import glob
#recover file name in a list

fileList=glob.glob("*best.tsv")

newLine= []
for file in fileList:
      f=open(file,"r")
      for line in f:
          line=line.rstrip()
          if line.split("\t")[0] != 'Virus':  # X_D,Lx-rxx,virus,%
            newLine.append(file.split("_")[0]+"_"+file.split("_")[1]+","+file.split("_")[-2].split(".")[0]+","+line.split("\t")[0]+","+line.split("\t")[1]+","+line.split("\t")[2]+","+line.split("\t")[3]+","+line.split("\t")[4]+","+line.split("\t")[5]+","+line.split("\t")[7])
      f.close()

# write the csv

f = open("fevir.csv", "w")

for line in newLine:
    f.write( line+"\n")
f.close()

fe=open("fevir.csv","r")
header=open("header.txt","r")
Tableau=open("Tableau.csv","r")

newLine= []
dicoFamily={}
dicoTableau={}

for line in header:
  line=line.rstrip()
  dicoFamily[line.split(",")[0].split(">")[1]]=  line.split(",")[2] 
header.close()

for line in Tableau:
  line=line.rstrip()
  dicoTableau["_".join(line.split(",")[2].split("-"))]=line.split(",")[0] + ","+line.split(",")[1]
  dicoTableau["_".join(line.split(",")[3].split("-"))]=line.split(",")[0] + ","+line.split(",")[1]
  dicoTableau["_".join(line.split(",")[4].split("-"))]=line.split(",")[0] + ","+line.split(",")[1]

Tableau.close()

for line in fe:
  line=line.rstrip()
  newLine.append(dicoTableau[line.split(",")[0]]+","+ dicoFamily[line.split(",")[-1]]+ "," + line)
fe.close()

# write the csv
f = open("Fevir2.csv", "w")

f.write("sample,date,family,library_ID,run_lane,virus,%_coverage,depth,mapped_reads,covered_(bp),genome_(bp),genome_ID")

for line in newLine:
    f.write("\n" + line)
f.close()
fe=open("Fevir2.csv","r")
sampleDico ={}
virusNameSet= set()
for line in fe:

  
  
  virusNameSet.add(line.split(",")[5])


fe.close()
fe=open("Fevir2.csv","r")

for line in fe:
  if line.split(",")[0] != "sample" :
    line= line.rstrip()
    sampleName = line.split(",")[3]+"_"+line.split(",")[4]
    virusNameDico = {}
    for virusName in virusNameSet:
        virusNameDico[virusName]= 0
    sampleDico[sampleName] = virusNameDico

fe.close()
fe=open("Fevir2.csv","r")
for line in fe:
  if line.split(",")[0] != "sample" :
    sampleName = line.split(",")[3]+"_"+line.split(",")[4]
    sampleDico[sampleName][line.split(",")[5]] += int(line.split(",")[8])

    # get the correspondence with lane and sampleName
fe.close()

fe=open("Fevir2.csv","r")
laneDico = {}
for line in fe:
  if line.split(",")[0] != "sample" :
        sampleName = line.split(",")[3]+"_"+line.split(",")[4]
        lane = line.split(",")[4]
        laneDico[sampleName] = lane


    # dico for max lane value per virusName
fe.close()
laneMaxDico={}
for lane in laneDico.values():
    virusNameDico = {}
    for virusName in virusNameSet:
        virusNameDico[virusName]= 0
    laneMaxDico[lane] = virusNameDico


# get the max(reads) for one lane per virus
keys=sorted(sampleDico.keys())
for sample in keys:
    for otherSample in keys:
        if laneDico[sample] == laneDico[otherSample]:

            for virusName in virusNameSet:
                if sampleDico[sample][virusName] > laneMaxDico[laneDico[sample]][virusName]:
                    laneMaxDico[laneDico[sample]][virusName] = sampleDico[sample][virusName]

newLine=[]

fe=open("Fevir2.csv","r")
for line in fe:
  if line.split(",")[0] != "sample" :
    line= line.rstrip()
    sample = line.split(",")[3]+"_"+line.split(",")[4]
    virus = line.split(",")[5]
    maxRead =laneMaxDico[laneDico[sample]][virus]
    print(maxRead)
    read = sampleDico[sample][virus]
    print(read)
    if read != 0 :
      if read/maxRead < 0.01:
        newLine.append(line+",True")
      else:
        newLine.append(line+",False")
    else:
        newLine.append(line+",N/A")

newLine2=[]
for line in newLine:
  virus = line.split(",")[5]
  if virus == '"background"'
     newLine2.append(line+",True")
  else:
     newLine2.append(line+",False")

fe.close()
f = open("Fevir3.csv", "w")
f.write("sample,date,family,library_ID,run_lane,virus,%_coverage,depth,mapped_reads,covered_(bp),genome_(bp),genome_ID,IndexHopping,background")

for line in newLine2:
    f.write("\n" + line)
f.close()
