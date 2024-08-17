#! /usr/bin/env python
# -*- coding: utf-8 -*-
# vim:fenc=utf-8

import fire
from pandas import DataFrame
from shapely import from_wkt
from pathlib import Path
import os

VERSION = "0.0.1"


def load_wkts_as_table(wkt_files:list):
    names, ys, xs = [], [], []
    for wkt_file in wkt_files:
        with open(wkt_file, 'r') as f:
            for g in from_wkt(f.read()).geoms:
                names.append(Path(wkt_file).stem)
                ys.append(g.y)
                xs.append(g.x)
    return {"feature_name": names, "Y": ys, "X": xs}


def main(*wkt_files: list, prefix:str):
    tab = DataFrame(load_wkts_as_table(wkt_files))
    tab["instance_id"] = tab.index + 1
    tab.set_index("instance_id", inplace=True)
    tab['x_int'] = tab['X'].astype(int)
    tab['y_int'] = tab['Y'].astype(int)
    os.mkdir(prefix)
    tab.to_csv(f"{prefix}/peaks.csv")


if __name__ == "__main__":
    options = {
        'run': main,
        'version' : VERSION
    }
    fire.Fire(options)