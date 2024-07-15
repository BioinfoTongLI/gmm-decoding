#! /usr/bin/env python3
# -*- coding: utf-8 -*-
# vim:fenc=utf-8
#
# Copyright © 2023 Tong LI <tongli.bioinfo@proton.me>
"""

"""
from typing import List, Tuple
import fire
import numpy as np
import dask.dataframe as dd
from shapely.geometry import Point, MultiPoint
from shapely.ops import unary_union


def main(*csvs, peak_radius: float = 1.5):
    df = dd.read_csv(csvs).compute()
    print(df.shape)
    points= []
    for coord in df.values:
        points.append(Point(coord[1], coord[0]))
    # Create a buffer around each point
    buffers = [point.buffer(peak_radius) for point in points]

    # Merge overlapping buffers
    merged = unary_union(buffers)

    peaks = MultiPoint([g.centroid for g in merged.geoms])
    print(len(peaks.geoms))

    # Dump the merged multipolygon in WKT format
    with open("merged_peaks.wkt", "w") as file:
        file.write(peaks.wkt)


if __name__ == "__main__":
    options = {
        "run" : main,
        "version" : "0.0.1"
    }
    fire.Fire(options)
