#!/usr/bin/python3

'''
Sample Pegasus workflow for searching the SRA database
'''

import argparse
import logging
import os
import shutil
import sys
import time

from Pegasus.api import *

logging.basicConfig(level=logging.ERROR)
BASE_DIR = os.path.abspath(os.path.dirname(__file__))

# need to know where Pegasus is installed for notifications
pegasus_plan_path = shutil.which('pegasus-plan')
PEGASUS_HOME = "/scratch/rzogg/miniconda/envs/100genome/lib/python3.10/site-packages/Pegasus"

#PEGASUS_HOME = os.path.dirname(os.path.dirname(PEGASUS_HOME))

def add_merge_jobs(wf, parents):
    '''
    an upside down triangle of merge jobs to merge a set of bam
    files into a final tarball.
    parents is a list of jobs, for which all outputs will be
    in the resulting tarball
    '''

    start_time = time.time()

    max_parents = 25
    final_job = False
    level = 1
    while len(parents) > 1:
        children = []
        if len(parents) <= max_parents:
            final_job = True
        chunks = [parents[i:i + max_parents] for i in range(0, len(parents), max_parents)]
        job_count = 0
        for chunk in chunks:
            job_count += 1
            j = Job('merge')
            wf.add_jobs(j)
            # outputs
            out_file = File('results-l{}-j{}.tar.gz'.format(level, job_count))
            if final_job:
                out_file = File('results.tar.gz')
            j.add_outputs(out_file, stage_out=final_job)
            j.add_args(out_file)
            # inputs and parent deps
            for parent in chunk:
                j.add_inputs(*parent.get_outputs())
                j.add_args(*parent.get_outputs())
            wf.add_dependency(j, parents=chunk)
            children.append(j)
        # next round
        level += 1
        parents = children
        
        end_time = time.time()
        print(f"Merging time: {end_time - start_time:3f} seconds")

    
def generate_wf():
    '''
    Main function that parses arguments and generates the pegasus
    workflow
    '''

    parser = argparse.ArgumentParser(description="generate a pegasus workflow")
    parser.add_argument('--sra-id-list', dest='sra_id_list', default=None, required=True,
                        help='Specifies list of SRA IDs to include in the search')
    parser.add_argument('--reference', dest='reference', default=None, required=True,
                        help='Specifies the fasta file to use as a reference for the searc')
    args = parser.parse_args(sys.argv[1:])
    
    start_time = time.time()

    wf = Workflow('sra-search')
    tc = TransformationCatalog()
    rc = ReplicaCatalog()
    
    # --- Properties ----------------------------------------------------------
    
    # set the concurrency limit for the download jobs, and send some extra usage
    # data to the Pegasus developers
    props = Properties()
    props['dagman.fasterq-dump.maxjobs'] = '20'
    props['pegasus.catalog.workflow.amqp.url'] = 'amqp://friend:donatedata@msgs.pegasus.isi.edu:5672/prod/workflows'
    props.write() 
    
    # --- Event Hooks ---------------------------------------------------------

    # get emails on all events at the workflow level
    wf.add_shell_hook(EventType.ALL, '{}/share/pegasus/notification/email'.format(PEGASUS_HOME))
    
    # --- Transformations -----------------------------------------------------
    
    container = Container(
                   'sra-search',
                   Container.SINGULARITY,
                   'docker://pegasus/sra-search:latest'
                )
    tc.add_containers(container)

    bowtie2_build = Transformation(
                       'bowtie2-build',
                       site='incontainer',
                       container=container,
                       pfn='/opt/bowtie2-2.2.9/bowtie2-build',
                       is_stageable=False
                    )


    bowtie2_build.add_profiles(Namespace.CONDOR, key='request_memory', value='1 GB')

    tc.add_transformations(bowtie2_build)

    bowtie2 = Transformation(
                  'bowtie2',
                  site='local',
                  container=container,
                  pfn=BASE_DIR + '/tools/bowtie2_wrapper',
                  is_stageable=True
              )
      
    bowtie2.add_profiles(Namespace.CONDOR, key='request_memory', value='2 GB')
    tc.add_transformations(bowtie2)
    
    fasterq_dump = Transformation(
                      'fasterq-dump',
                       site='local',
                       container=container,
                       pfn=BASE_DIR + '/tools/fasterq_dump_wrapper',
                       is_stageable=True
                     )
      
    fasterq_dump.add_profiles(Namespace.CONDOR, key='request_memory', value='1 GB')
    # this one is used to limit the number of concurrent downloads
    fasterq_dump.add_profiles(Namespace.DAGMAN, key='category', value='fasterq-dump')
    tc.add_transformations(fasterq_dump)

    merge = Transformation(
                'merge',
                site='local',
                container=container,
                pfn=BASE_DIR + '/tools/merge',
                is_stageable=True
            )
    
    merge.add_condor_profile(request_memory='1 GB')
    tc.add_transformations(merge)

    # --- Workflow -----------------------------------------------------

    # keep track of bam files, so we can merge them into a single tarball at
    # the end
    to_merge = []

    # set up reference file and what files needs to be generated by the index job
    ref_main = File('reference.fna')
    rc.add_replica('local', 'reference.fna', os.path.abspath(args.reference))
    ref_files = []
    for filename in ['reference.1.bt2', 'reference.2.bt2', 'reference.3.bt2', 'reference.4.bt2',
                     'reference.rev.1.bt2', 'reference.rev.2.bt2']:
        ref_files.append(File(filename))

    # index the reference file
    index_job = Job('bowtie2-build')
    index_job.add_args('reference.fna', 'reference')
    index_job.add_inputs(ref_main)
    index_job.add_outputs(*ref_files, stage_out=False)
    wf.add_jobs(index_job)

    # create jobs for each SRA ID
    fh = open(args.sra_id_list)
    for line in fh:
        sra_id = line.strip()
        if len(sra_id) < 5:
            continue

        # files for this id
        fastq_1 = File('{}_1.fastq'.format(sra_id))
        fastq_2 = File('{}_2.fastq'.format(sra_id))

        # download job
        j = Job('fasterq-dump')
        j.add_args('--split-files', sra_id)
        j.add_outputs(fastq_1, fastq_2, stage_out=False)
        wf.add_jobs(j)

        # bowtie2 job
        bam = File('{}.bam'.format(sra_id))
        bam_index = File('{}.bam.bai'.format(sra_id))
        j = Job('bowtie2')
        j.add_args(sra_id)
        j.add_inputs(*ref_files, fastq_1, fastq_2)
        j.add_outputs(bam, bam_index, stage_out=False)
        wf.add_jobs(j)
        
        # keep track of jobs and outputs for merging
        to_merge.append(j)
    
    add_merge_jobs(wf, to_merge)

    try:
        wf.add_transformation_catalog(tc)
        wf.add_replica_catalog(rc)
        
        wf.plan(submit=True)

        end_time = time.time()
        print(f"Total workflow execution time: {end_time - start_time:.2f} seconds")

    except PegasusClientError as e:
        print(e.output)


if __name__ == '__main__':
    generate_wf()

