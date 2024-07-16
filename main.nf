#!/usr/bin/env/ nextflow
include {Spotiflow_run} from './workflow/workflow_peak_calling.nf'

// minimal parameter set
params.ome_zarr = ''
params.out_dir = ''
params.rna_spot_size = [5, 7] // the rna spot size in pixels to be tested for decoding
params.anchor_ch_indexes = 1 // anchor channel index, starts from 0
params.prob_threshold = 0.6 // the probability threshold for decoding restults to keep
params.whitehat = 'True' // whether to use whitehat filter for spot enhancement
params.peak_profile_cleanup = 'True'  // whether to clean up the peak profile by removing the background and infeasing the peaks
params.channel_map = '' // the channel map for the codebook, e.g. "{A: c01 Alexa 647, G: c02 Alexa 488, C: c03 Cy3, T: c04 Cy5}"
params.codebook_sep = "," // the separator for the codebook

params.peak_profile = ''
params.peak_location = ''

// needed when decoding
params.taglist_name = "taglist.csv"
params.channel_info_name = "channel_info.csv"
params.codebook = ""
params.chunk_size = 99999999 //3000000

params.anchor_peaks_tsv = "" // if avaiable peaks were detected by Synquant

params.max_n_worker = 28

params.trackpy_percentile = [85, 90]
params.trackpy_separation = 2
params.trackpy_search_range = 5

params.gmm_sif = "/lustre/scratch126/cellgen/team283/imaging_sifs/gmm_decode.sif"


process Codebook_conversion {
    debug true

    label "single_cpu"
    label "small_mem"

    container "${ workflow.containerEngine == 'singularity' && !task.ext.singularity_pull_docker_container ?
        params.gmm_sif:
        'bioinfotongli/decoding:latest'}"

    storeDir params.out_dir + "/codebook_metadata"

    input:
    file(codebook)
    val(channel_map)
    val(sep)

    output:
    path "taglist.csv", emit: taglist_name
    path "channel_info.csv", emit: channel_info_name
    /*path "channel_info.pickle", emit: channel_infos*/

    script:
    """
    codebook_convert.py -csv_file ${codebook} -channel_map "${channel_map}" -sep "${sep}"
    """
}


process Get_meatdata {
    debug true

    label "single_cpu"
    label "small_mem"

    container "${ workflow.containerEngine == 'singularity' && !task.ext.singularity_pull_docker_container ?
        params.gmm_sif:
        'bioinfotongli/decoding:latest'}"

    storeDir params.out_dir + "/codebook_metadata"
    /*publishDir params.out_dir + "/decoding_metadata", mode:"copy"*/

    input:
    path(taglist_name)
    path(channel_info_name)

    output:
    path "barcodes_01.npy", emit: barcodes
    path "gene_names.npy", emit: gene_names
    path "channel_info.pickle", emit: channel_infos

    script:
    """
    get_metadata.py -auxillary_file_dir ./  -taglist_name ${taglist_name} -channel_info_name ${channel_info_name}
    """
}


process Enhance_spots {
    debug true

    container "${ workflow.containerEngine == 'singularity' && !task.ext.singularity_pull_docker_container ?
        params.gmm_sif:
        'bioinfotongli/decoding:latest'}"
    containerOptions "${ workflow.containerEngine == 'singularity' ? '--nv':'--gpus all'}"
    storeDir params.out_dir + "/enhanced_anchor_channels"
    /*publishDir params.out_dir + "/anchor_spots", mode:"copy"*/

    input:
    path zarr
    val anchor_ch_index
    each rna_spot_size
    val whitehat

    output:
    tuple val(rna_spot_size), val(stem), path("${stem}_spot_enhanced_diam_${rna_spot_size}"), emit:ch_with_peak_img

    script:
    stem = file(zarr).baseName
    """
    export CUPY_CACHE_DIR=/tmp/
    helper.py enhance_all --diam ${rna_spot_size} --zarr_in ${zarr}/0 --stem ${stem} --whitehat ${whitehat} --anchor_ch_index ${anchor_ch_index}
    """
}


process Call_peaks_in_anchor {
    debug true

    container "${ workflow.containerEngine == 'singularity' && !task.ext.singularity_pull_docker_container ?
        params.gmm_sif:
        'bioinfotongli/decoding:latest'}"
    storeDir params.out_dir + "/anchor_spots"
    /*publishDir params.out_dir + "/anchor_spots", mode:"copy"*/

    input:
    tuple val(rna_spot_size), val(stem), file(anchor_zarr)
    val(anchor_ch_index)
    each percentile
    each separation
    each search_range

    output:
    tuple val(rna_spot_size), path("${stem}_detected_peaks_diam_${rna_spot_size}_percentile_${percentile}_sep_${separation}_search_range_${search_range}.tsv"), emit: peaks_from_anchor_chs

    script:
    """
    helper.py call_peaks --zarr_in ${anchor_zarr}/0/${anchor_ch_index} --stem ${stem} --diam ${rna_spot_size} --tp_percentile ${percentile} --peak_separation ${separation} --tp_search_range ${search_range}
    """
}


process Extract_peak_intensities {
    debug true

    container "${ workflow.containerEngine == 'singularity' && !task.ext.singularity_pull_docker_container ?
        params.gmm_sif:
        'bioinfotongli/decoding:latest'}"

    storeDir params.out_dir + "/peak_intensities"
    /*publishDir params.out_dir + "/peak_intensities", mode:"copy"*/

    input:
    tuple val(rna_spot_size), path(peaks), val(stem), path(imgs), path(channel_info)

    output:
    tuple val(new_stem), file("${new_stem}_extracted_peak_intensities.npy"), file("${new_stem}_peak_locs.csv"), emit: peaks_for_preprocessing

    script:
    new_stem = peaks.baseName
    def args = task.ext.args ?: ''
    """
    extract_peak_intensities.py --raw_zarr ${imgs}/0 \
        --peaks ${peaks} \
        --stem ${new_stem} \
        --channel_info ${channel_info} \
        --peak_radius ${rna_spot_size} \
        ${args}
    """
}


process Preprocess_peak_profiles {
    debug true

    label "single_cpu"

    container "${ workflow.containerEngine == 'singularity' && !task.ext.singularity_pull_docker_container ?
        params.gmm_sif:
        'bioinfotongli/decoding:latest'}"
    containerOptions "${ workflow.containerEngine == 'singularity' ? '--nv':'--gpus all'}"

    storeDir params.out_dir + "/preprocessed_peak_intensities"
    /*publishDir params.out_dir + "/preprocessed_peak_intensities", mode:"copy"*/

    input:
    tuple val(stem), file(profiles), file(peak_locations)
    val(cleanup)

    output:
    tuple val(stem), file("${stem}_filtered_peak_intensities.npy"), file("${stem}_filtered_peak_locs.csv"), emit: peaks_for_decoding

    script:
    """
    export CUPY_CACHE_DIR=/tmp/
    preprocess_peak_profiles.py --profiles ${profiles} --stem ${stem} --spot_loc ${peak_locations} --cleanup ${cleanup}
    """
}


process Decode_peaks {
    debug true

    label "single_cpu"

    container "${ workflow.containerEngine == 'singularity' && !task.ext.singularity_pull_docker_container ?
        params.gmm_sif:
        'bioinfotongli/decoding:latest'}"
    containerOptions "${ workflow.containerEngine == 'singularity' ? '--nv':'--gpus all'}"

    storeDir params.out_dir + "decoded"
    /*publishDir params.out_dir + "/decoded", mode:"copy"*/

    input:
    tuple val(stem), file(spot_profile), file(spot_loc), file(barcodes_f), file(gene_names_f), file(channel_info_f)
    val(chunk_size)

    output:
    tuple val(stem), path("${stem}_decoded_df.tsv"), emit:decoded_peaks
    path "${stem}_decode_out_parameters.pickle" optional true

    script:
    """
    decode.py --spot_profile ${spot_profile} --spot_loc ${spot_loc} --barcodes_01 ${barcodes_f} --gene_names ${gene_names_f} --channels_info ${channel_info_f} --stem ${stem} --chunk_size ${chunk_size}
    """
}

process Filter_decoded_peaks {
    debug true

    label "single_cpu"

    container "${ workflow.containerEngine == 'singularity' && !task.ext.singularity_pull_docker_container ?
        params.gmm_sif:
        'bioinfotongli/decoding:latest'}"
    containerOptions "${ workflow.containerEngine == 'singularity' ? '--nv':'--gpus all'}"

    storeDir params.out_dir + "filtered_decoded"

    input:
    tuple val(stem), path(decoded_peaks)
    each prob_thre

    output:
    tuple val(stem), path("${stem}_decoded_df_prob_thresholded_${prob_thre}.tsv")

    script:
    """
    filter_decoded_peaks.py --stem ${stem} --transcripts ${decoded_peaks} --prob_threshold ${prob_thre}
    """
}


process Heatmap_plot {
    debug true
    container "${ workflow.containerEngine == 'singularity' && !task.ext.singularity_pull_docker_container ?
        params.gmm_sif:
        'gitlab-registry.internal.sanger.ac.uk/tl10/gmm-decoding:latest'}"

    publishDir params.out_dir + "/plots", mode:"copy"

    input:
    path(decoded_df)
    /*file decode_out_parameters_f from decode_out_parameters*/
    /*file channel_info_f from channel_info_for_plot*/

    output:
    path("*.png")

    script:
    """
    do_plots.py --decoded_df $decoded_df
    #-decode_out_params decode_out_parameters_f -channels_info {channel_info_f}
    """
}


workflow {
    Codebook_conversion(Channel.fromPath(params.codebook), params.channel_map, params.codebook_sep)
    Get_meatdata(Codebook_conversion.out.taglist_name, Codebook_conversion.out.channel_info_name)
    peak_calling()
    Extract_peak_intensities(
        peak_calling.out.peaks_and_enhanced_raw.combine(Get_meatdata.out.channel_infos)
    )
    Preprocess_peak_profiles(Extract_peak_intensities.out.peaks_for_preprocessing, params.peak_profile_cleanup)
    for_decoding = Preprocess_peak_profiles.out.peaks_for_decoding
        .combine(Get_meatdata.out.barcodes)
        .combine(Get_meatdata.out.gene_names)
        .combine(Get_meatdata.out.channel_infos)
    Decode_peaks(for_decoding, params.chunk_size)
    Filter_decoded_peaks(Decode_peaks.out.decoded_peaks, params.prob_threshold)
    /*Heatmap_plot(Decode_peaks.out[0])*/
}

workflow peak_calling {
    Enhance_spots(params.ome_zarr, params.anchor_ch_indexes, channel.from(params.rna_spot_size), params.whitehat)
    if (params.anchor_peaks_tsv != "") {
        peaks = Channel.from([[params.rna_spot_size, params.anchor_peaks_tsv]])
    } else {
        Call_peaks_in_anchor(Enhance_spots.out.ch_with_peak_img, params.anchor_ch_indexes,
            channel.from(params.trackpy_percentile),
            channel.from(params.trackpy_separation),
            channel.from(params.trackpy_search_range)
        )
        peaks = Call_peaks_in_anchor.out.peaks_from_anchor_chs
    }
    peaks.combine(Enhance_spots.out.ch_with_peak_img)
        .map{it -> [it[0], it[1], it[3], it[4]]}
        .set{peaks_and_enhanced_raw}
        /*.view()*/

    emit:
    peaks_and_enhanced_raw = peaks_and_enhanced_raw
}

workflow Decode {
    params.proj_code = "" // the project code for the data, e.g SM_BRA
    Codebook_conversion(Channel.fromPath(params.codebook), params.channel_map, params.codebook_sep)
    Get_meatdata(Codebook_conversion.out.taglist_name, Codebook_conversion.out.channel_info_name)

    for_decoding = channel.from(params.proj_code).combine(channel.fromPath(params.peak_profile))
        .combine(channel.fromPath(params.peak_location))
        .combine(Get_meatdata.out.barcodes)
        .combine(Get_meatdata.out.gene_names)
        .combine(Get_meatdata.out.channel_infos)
    /*for_decoding.view()*/
    Decode_peaks(for_decoding, params.chunk_size)
    Filter_decoded_peaks(Decode_peaks.out.decoded_peaks, params.prob_threshold)
}


workflow Spotiflow {
    Spotiflow_run(channel.from(params.ome_zarr).combine(channel.from(params.ch_ind)))
}