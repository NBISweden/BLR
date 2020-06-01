#!/bin/bash
set -xeuo pipefail

uname
samtools --version
bowtie2 --version
minimap2 --version
cutadapt --version
starcode --version
snakemake --version
blr --version
picard MarkDuplicates --version || true
ema

if [[ $(uname) == Darwin ]]; then
  md5="md5 -r"
else
  md5=md5sum
fi

pushd blr-testdata
bwa index chr1mini.fasta
bowtie2-build chr1mini.fasta chr1mini.fasta > /dev/null
samtools faidx chr1mini.fasta
test -f chr1mini.dict || gatk CreateSequenceDictionary -R chr1mini.fasta
popd

pytest -v tests/

# Test full run on BLR library.
rm -rf outdir-bowtie2
blr init --r1=blr-testdata/blr_reads.1.fastq.gz -l blr outdir-bowtie2
blr config \
    --file outdir-bowtie2/blr.yaml \
    --set genome_reference ../blr-testdata/chr1mini.fasta \
    --set dbSNP ../blr-testdata/dbSNP.chr1mini.vcf.gz \
    --set reference_variants ../blr-testdata/HG002_GRCh38_GIAB_highconf.chr1mini.vcf \
    --set phasing_ground_truth ../blr-testdata/HG002_GRCh38_GIAB_highconf_triophased.chr1mini.vcf \
    --set max_molecules_per_bc 1 \
    --set heap_space 1

cd outdir-bowtie2
blr run
m=$(samtools view mapped.sorted.tag.bcmerge.mkdup.mol.filt.bam | $md5 | cut -f1 -d" ")
test $m == b7c6fc6489dc59dd72e985ef8522e2e1

# Cut away columns 2 and 3 as these change order between linux and osx
m2=$(cut -f1,4- mapped.sorted.tag.bcmerge.mkdup.mol.filt.phase | $md5 | cut -f1 -d" ")
test $m2 == e6c512bfeb7cb1b230a9320f22c32937
