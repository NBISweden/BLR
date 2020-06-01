from pathlib import Path
import pysam
import pytest
import dnaio

from blr.cli.init import init
from blr.cli.run import run
from blr.cli.config import change_config
from blr.utils import get_bamtag

TESTDATA_BLR_READ1 = Path("testdata/blr_reads.1.fastq.gz")
TESTDATA_BLR_READ2 = Path("testdata/blr_reads.2.fastq.gz")
TESTDATA_TENX_READ1 = Path("testdata/tenx_reads.1.fastq.gz")
TESTDATA_TENX_READ2 = Path("testdata/tenx_reads.2.fastq.gz")
TESTDATA_TENX_BARCODES = str(Path("testdata/tenx_barcode_whitelist.txt").absolute())
TESTDATA_STLFR_READ1 = Path("testdata/stlfr_reads.1.fastq.gz")
TESTDATA_STLFR_READ2 = Path("testdata/stlfr_reads.2.fastq.gz")
TESTDATA_STLFR_BARCODES = str(Path("testdata/stlfr_barcodes.txt").absolute())
DEFAULT_CONFIG = "blr.yaml"
REFERENCE_GENOME = str(Path("testdata/chr1mini.fasta").absolute())
REFERENCE_VARIANTS = str(Path("testdata/HG002_GRCh38_GIAB_highconf.chr1mini.vcf").absolute())
DB_SNP = str(Path("testdata/dbSNP.chr1mini.vcf.gz").absolute())


def count_bam_alignments(path):
    with pysam.AlignmentFile(path) as af:
        n = 0
        for _ in af:
            n += 1
    return n


def count_fastq_reads(path):
    with dnaio.open(path) as f:
        n = 0
        for _ in f:
            n += 1
    return n


def count_bam_tags(path, tag):
    with pysam.AlignmentFile(path, 'rb') as af:
        n = 0
        for r in af.fetch(until_eof=True):
            if get_bamtag(r, tag):
                n += 1
    return n


def bam_has_tag(path, tag):
    with pysam.AlignmentFile(path) as file:
        for alignment in file:
            if alignment.has_tag(tag):
                return True

    return False


def test_init(tmpdir):
    init(tmpdir / "analysis", TESTDATA_BLR_READ1, "blr")


def test_config(tmpdir):
    workdir = tmpdir / "analysis"
    init(workdir, TESTDATA_BLR_READ1, "blr")
    change_config(workdir / "blr.yaml", [("read_mapper", "bwa")])


def test_trim_blr(tmpdir):
    workdir = tmpdir / "analysis"
    init(workdir, TESTDATA_BLR_READ1, "blr")
    change_config(
        workdir / DEFAULT_CONFIG,
        [("library_type", "blr")]
    )
    trimmed = ["trimmed.barcoded.1.fastq.gz", "trimmed.barcoded.2.fastq.gz"]
    run(workdir=workdir, targets=trimmed)
    assert count_fastq_reads(trimmed[0]) <= count_fastq_reads(TESTDATA_BLR_READ1)
    assert count_fastq_reads(trimmed[1]) <= count_fastq_reads(TESTDATA_BLR_READ2)


def test_trim_tenx(tmpdir):
    workdir = tmpdir / "analysis"
    init(workdir, TESTDATA_TENX_READ1, "10x")
    change_config(
        workdir / DEFAULT_CONFIG,
        [("barcode_whitelist", TESTDATA_TENX_BARCODES)]
    )
    trimmed = ["trimmed.barcoded.1.fastq.gz", "trimmed.barcoded.2.fastq.gz"]
    run(workdir=workdir, targets=trimmed)
    for raw, trimmed in zip((TESTDATA_TENX_READ1, TESTDATA_TENX_READ2), trimmed):
        assert count_fastq_reads(raw) == count_fastq_reads(Path(workdir / trimmed))


def test_trim_stlfr(tmpdir):
    workdir = tmpdir / "analysis"
    init(workdir, TESTDATA_STLFR_READ1, "stlfr")
    change_config(
        workdir / DEFAULT_CONFIG,
        [("stlfr_barcodes", TESTDATA_STLFR_BARCODES)]
    )
    trimmed = ["trimmed.barcoded.1.fastq.gz", "trimmed.barcoded.2.fastq.gz"]
    run(workdir=workdir, targets=trimmed)
    for raw, trimmed in zip((TESTDATA_STLFR_READ1, TESTDATA_STLFR_READ2), trimmed):
        assert count_fastq_reads(raw) >= count_fastq_reads(Path(workdir / trimmed))


@pytest.mark.parametrize("read_mapper", ["bwa", "bowtie2", "minimap2", "ema"])
def test_mappers(tmpdir, read_mapper):
    workdir = tmpdir / "analysis"
    init(workdir, TESTDATA_BLR_READ1, "blr")
    change_config(
        workdir / DEFAULT_CONFIG,
        [("genome_reference", REFERENCE_GENOME), ("read_mapper", read_mapper)]
    )
    run(workdir=workdir, targets=["mapped.sorted.tag.bam"])
    n_input_fastq_reads = 2 * count_fastq_reads(Path(workdir / "trimmed_barcoded.1.fastq.gz"))
    assert n_input_fastq_reads <= count_bam_alignments(workdir / "mapped.sorted.tag.bam")


def test_final_compressed_reads_exist(tmpdir):
    workdir = tmpdir / "analysis"
    init(workdir, TESTDATA_BLR_READ1, "blr")
    change_config(
        workdir / DEFAULT_CONFIG,
        [("genome_reference", REFERENCE_GENOME)]
    )
    targets = ("reads.1.final.fastq.gz", "reads.2.final.fastq.gz")
    run(workdir=workdir, targets=targets)
    for filename in targets:
        assert Path(workdir / filename).exists()


def test_link_reference_variants(tmpdir):
    workdir = tmpdir / "analysis"
    init(workdir, TESTDATA_BLR_READ1, "blr")
    change_config(
        workdir / DEFAULT_CONFIG,
        [("genome_reference", REFERENCE_GENOME), ("reference_variants", REFERENCE_VARIANTS)]
    )
    target = "mapped.phaseinput.vcf"
    run(workdir=workdir, targets=[target])
    assert Path(workdir / target).is_symlink()


def test_BQSR(tmpdir):
    workdir = tmpdir / "analysis"
    init(workdir, TESTDATA_BLR_READ1, "blr")
    change_config(
        workdir / DEFAULT_CONFIG,
        [("genome_reference", REFERENCE_GENOME), ("dbSNP", DB_SNP), ("BQSR", "true"), ("reference_variants", "null"),
         ("variant_caller", "gatk")]
    )
    target = "mapped.sorted.tag.bcmerge.mkdup.mol.filt.BQSR.bam"
    run(workdir=workdir, targets=[target])
    assert Path(workdir / target).is_file()


@pytest.mark.parametrize("variant_caller", ["freebayes", "bcftools", "gatk"])
def test_call_variants(tmpdir, variant_caller):
    workdir = tmpdir / "analysis"
    init(workdir, TESTDATA_BLR_READ1, "blr")
    change_config(
        workdir / DEFAULT_CONFIG,
        [("genome_reference", REFERENCE_GENOME), ("reference_variants", "null"), ("variant_caller", variant_caller)]
    )
    target = "mapped.variants.called.vcf"
    run(workdir=workdir, targets=[target])
    assert Path(workdir / target).is_file()


def test_plot_figures(tmpdir):
    workdir = tmpdir / "analysis"
    init(workdir, TESTDATA_BLR_READ1, "blr")
    change_config(
        workdir / DEFAULT_CONFIG,
        [("genome_reference", REFERENCE_GENOME)]
    )
    target = "figures/mapped"
    run(workdir=workdir, targets=[target])
    assert Path(workdir / target).is_dir()


@pytest.mark.parametrize("haplotype_tool", ["blr", "whatshap"])
def test_haplotag(tmpdir, haplotype_tool):
    workdir = tmpdir / "analysis"
    init(workdir, TESTDATA_BLR_READ1, "blr")
    change_config(
        workdir / DEFAULT_CONFIG,
        [("genome_reference", REFERENCE_GENOME),
         ("reference_variants", "null")]
    )
    target = "mapped.calling.phased.bam"
    run(workdir=workdir, targets=[target])
    assert bam_has_tag(workdir / target, "HP")  # Check that tag HP have been added
    assert bam_has_tag(workdir / target, "PS")  # Check that tag PS have been added
    assert count_bam_tags((workdir / target), "PS") == count_bam_tags((workdir / target), "HP")  # Confirm same count.
