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


def max_image_size(image):
    # Get the current device
    device = torch.cuda.current_device()

    # Get available memory in bytes
    available_memory = torch.cuda.get_device_properties(device).total_memory - torch.cuda.memory_allocated(device)

    # Get the size of the data type in bytes
    dtype_size = np.dtype(image.dtype).itemsize

    # Calculate the maximum number of pixels that can fit into the available memory
    max_pixels = available_memory / dtype_size

    # The maximum size of a square image is the square root of the maximum number of pixels
    max_size = int(math.sqrt(max_pixels))

    return max_size


def spotiflow_call(block, block_info, model_name, edge):
    model = Spotiflow.from_pretrained(model_name)
    print(block_info)
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
        with open(f'peaks_Y{y_min_str}_X{x_min_str}.csv', 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['y', 'x'])  # write column names
            writer.writerows(peaks)
        del peaks, _
    return block


def main(image_path:str, ch_index:int=2, model_name:str="general", depth:int = 10):
    hyperstack = AICSImage(image_path)
    print(hyperstack.dims)

    with Client(processes=True, threads_per_worker=1, n_workers=1): #memory_limit='20GB'):
        for t in range(hyperstack.dims.T):
            img = hyperstack.get_image_dask_data("ZYX", T=t, C=ch_index)
            img = np.max(img, axis=0)
            print(img.shape)
            # Get the maximum size of the image that can fit into GPU memory (WIP)
            # max_size = max_image_size(img)
            # print(max_size)
            # img = img.rechunk((max_size, max_size))
            img = img.rechunk((2000, 2000))

            # Predict
            points = img.map_overlap(
                spotiflow_call,
                model_name=model_name,
                depth=depth,
                edge=depth,
                dtype=np.float16
            )
            points.compute()


if __name__ == "__main__":
    options = {
        "run" : main,
        "version" : "0.0.1"
    }
    fire.Fire(options)
