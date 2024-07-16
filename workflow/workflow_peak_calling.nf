#!/usr/bin/env/ nextflow

process Spotiflow_call_peaks {
    debug false 

    label "gpu_normal"

    container 'bioinfotongli/decoding:spotiflow'
    containerOptions "${workflow.containerEngine == 'singularity' ? '--nv':'--gpus all'}"
    storeDir params.out_dir

    input:
    tuple val(meta), path(img), val(ch_ind)
    
    output:
    tuple val(meta), path("${meta.id[0]}_ch_${ch_ind}/ch_${ch_ind}_peaks_Y*_X*.csv"), val(ch_ind), emit: peaks

    script:
    def args = task.ext.args ?: ''
    """
    Spotiflow_call_peaks.py run \
        -image_path ${img} \
        -out_dir ${meta.id[0]} \
        --ch_ind ${ch_ind} \
        ${args}
    """
}


process Spotiflow_merge_peaks {
    debug true

    container 'bioinfotongli/decoding:spotiflow'
    storeDir params.out_dir

    input:
    tuple val(meta), path(csvs), val(ch_ind)

    output:
    tuple val(meta), path("${meta.id[0]}_merged_peaks_ch_${ch_ind}.wkt"), val(ch_ind), emit: merged_peaks

    script:
    def args = task.ext.args ?: ''
    """
    Spotiflow_post_process.py run \
        ${csvs} \
        --ch_ind ${ch_ind} \
        --prefix ${meta.id[0]} \
        ${args} \
    """
}

workflow Spotiflow_run {
    take:
    zarrs

    main:
    Spotiflow_call_peaks(zarrs)
    Spotiflow_merge_peaks(Spotiflow_call_peaks.out.peaks)
}