#!/usr/bin/env/ nextflow

process Spotiflow_call_peaks {
    debug false 

    label "gpu_normal"

    container 'bioinfotongli/decoding:spotiflow'
    containerOptions "${workflow.containerEngine == 'singularity' ? '--nv':'--gpus all'}"
    storeDir params.out_dir

    input:
    tuple val(meta), path(img)

    output:
    tuple val(meta), path("peaks_Y*_X*.csv"), emit: peaks

    script:
    def args = task.ext.args ?: ''
    """
    Spotiflow_call_peaks.py run \
        -image_path ${img} \
        ${args}
    """
}


process Spotiflow_merge_peaks {
    debug true
    cache true

    container 'bioinfotongli/decoding:spotiflow'
    storeDir params.out_dir

    input:
    tuple val(meta), path(csvs)

    output:
    tuple val(meta), path("merged_peaks.wkt"), emit: merged_peaks

    script:
    def args = task.ext.args ?: ''
    """
    Spotiflow_post_process.py run \
        ${args} \
        ${csvs} \
    """
}

workflow Spotiflow_run {
    take:
    zarrs

    main:
    Spotiflow_call_peaks(zarrs)
    Spotiflow_merge_peaks(Spotiflow_call_peaks.out.peaks.collect())
}