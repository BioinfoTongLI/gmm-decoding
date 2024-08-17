#!/usr/bin/env/ nextflow

process Spotiflow_call_peaks {
    debug false 

    label "gpu_normal"

    container 'bioinfotongli/decoding:spotiflow'
    containerOptions "${workflow.containerEngine == 'singularity' ? '--nv':'--gpus all'}"
    publishDir params.out_dir

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
    publishDir params.out_dir

    input:
    tuple val(meta), path(csvs), val(ch_ind)

    output:
    tuple val(meta), path("${meta.id[0]}_merged_peaks_ch_${ch_ind}.wkt"), emit: merged_peaks

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


process Spotiflow_merge_channels {
    debug true

    container 'bioinfotongli/decoding:spotiflow'
    publishDir params.out_dir, mode: 'copy'

    input:
    tuple val(meta), path(wkts)

    output:
    tuple val(meta), path("${meta.id}/peaks.csv"), emit: merged_channels

    script:
    def args = task.ext.args ?: ''
    """
    merge_wkts.py run \
        --prefix ${meta.id} \
        ${wkts} \
        ${args} \
    """
}

workflow Spotiflow_run {
    take:
    zarrs

    main:
    Spotiflow_call_peaks(zarrs)
    Spotiflow_merge_peaks(Spotiflow_call_peaks.out.peaks)
    Spotiflow_merge_channels(Spotiflow_merge_peaks.out.merged_peaks.groupTuple())

    emit:
    Spotiflow_merge_channels.out.merged_channels
}