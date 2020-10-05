#!/usr/bin/env Rscript
#Purpose: To make report from a tsv
#Project: SAfia, pipeline "FeVIR"
#Usage: graphics.r prefix

library(gplots)     # to make plot
library(readr)      # to import tsv
library(gridExtra)  # to make table
library(ggrepel)    # to avoid overlapping label

prefix <- commandArgs(trailingOnly = TRUE)  # the only option prefix

out= paste(c(prefix[1],".pdf"), collapse='')
pdf(out,width=14.85,height=10.5) # A4 "parameters"

file1= paste(c(prefix[1],"_best.tsv"), collapse='') # get the tsv data (best virus for each virus name).
doc <- read_delim(file1, "\t", escape_double = FALSE, trim_ws = TRUE)

data <- doc[rev(order(doc$`Reads`)),]  # sort by reads
data$Colors <- NULL # get rid off colors
data$Species <- NULL # get rid off sp names

# the plot
ggplot(doc, aes(y= `Depth(Median)`, x= `% Segment coverage`, label=`Virus`), margin=TRUE)+
  geom_point(size=0.001*(doc$`Coverage`),color=doc$Colors,alpha=0.5)+geom_point(size=0.001*(doc$`Segment length`),color=doc$Colors,alpha=0.2)  +geom_text_repel(aes(label=`Virus`),color=doc$Colors)+ scale_x_continuous(breaks = c(0,20,40,60,80,100), minor_breaks= c(10,30,50,70,90))+ expand_limits(x=c(0,100), y=c(1, 1000))+ scale_y_log10(minor_breaks=NULL, breaks = c(1,10,100,1000,10000,100000))+labs(title=prefix[1])
#+ annotation_logticks(base = 10, sides = "l", scaled = TRUE)

# the table, create an empty graph with nothing and add the table
ggplot() + theme_bw() + theme(line = element_blank(), text = element_blank()) + annotation_custom(grob = tableGrob(data))

dev.off()
