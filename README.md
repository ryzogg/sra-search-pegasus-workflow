# SRA Search Pegasus Workflow

Pegasus workflow which downloads and aligns SRA data, using SRA Toolkit,
Samtools and Bowtie2

SRA Tools, samtools and Bowtie2 are all included in a single Docker
container defined in `Dockerfile` and available in the Docker Hub under
`pegasus/sra-search`. The workflow is setup up to use that container
but execute it via Singularity as that maybe a more common container
runtime on HPC machines. The container runtime used can easily be
changed in the workflow definition.

The number of concurrent downloads is limited with a DAGMan
category profile.

The output bam/bai files are merged into a single tarball which is
the final output of the workflow.

To submit a workflow, run:

    ./sra-search.py --sra-id-list tests/10/sra_ids.txt --reference tests/10/crassphage.fna
    


