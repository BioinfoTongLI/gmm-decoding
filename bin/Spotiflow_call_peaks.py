#! /usr/bin/env python3
# -*- coding: utf-8 -*-
# vim:fenc=utf-8
#
# Copyright © 2024 Tong LI <tongli.bioinfo@proton.me>
"""

"""
import fire
from aicsimageio import AICSImage
import numpy as np
from spotiflow.model import Spotiflow
from dask.distributed import Client
import torch
import numpy as np
import math
import csv
import os


def spotiflow_call(block, block_info, model_name, edge, final_dir, ch_index):
    model = Spotiflow.from_pretrained(model_name)
    # print(block_info)
    try:
        y_min = block_info[None]["array-location"][0][0]
        x_min = block_info[None]["array-location"][1][0]
        
        y_chunk_loc = block_info[None]["chunk-location"][0]
        x_chunk_loc = block_info[None]["chunk-location"][1]
    except:
        pass
    peaks, _  = model.predict(block)
    if len(peaks) > 0:
        peaks[:, 0] += y_min - y_chunk_loc * 2 * edge
        peaks[:, 1] += x_min - x_chunk_loc * 2 * edge

        # Serialize peaks to disk
        y_min_str = str(y_min).zfill(5)  # pad with zeros for consistent file names
        x_min_str = str(x_min).zfill(5)

        # Serialize peaks to disk as CSV
        with open(f"{final_dir}/ch_{ch_index}_peaks_Y{y_min_str}_X{x_min_str}.csv", 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['y', 'x'])  # write column names
            writer.writerows(peaks)
        del peaks, _
    return block


def main(image_path:str, out_dir:str,
         ch_ind:int=2, model_name:str="general",
         depth:int = 10, chunk_size:int=2000):
    hyperstack = AICSImage(image_path)
    print(hyperstack.dims)

    # Create the output directory if it doesn't exist
    final_dir = f"{out_dir}_ch_{ch_ind}"
    if not os.path.exists(final_dir):
        os.makedirs(final_dir)

    with Client(processes=True, threads_per_worker=1, n_workers=1): #memory_limit='20GB'):
        for t in range(hyperstack.dims.T):
            img = hyperstack.get_image_dask_data("ZYX", T=t, C=ch_ind)
            img = np.max(img, axis=0)
            img = img.rechunk((chunk_size, chunk_size))

            # Predict
            points = img.map_overlap(
                spotiflow_call,
                model_name=model_name,
                depth=depth,
                edge=depth,
                final_dir=final_dir,
                ch_index=ch_ind,
                dtype=np.float16
            )
            _ = points.compute()


if __name__ == "__main__":
    options = {
        "run" : main,
        "version" : "0.0.1"
    }
    fire.Fire(options)
