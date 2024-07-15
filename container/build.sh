#! /bin/sh
#
# build.sh
# Copyright (C) 2023 Tong LI <tongli.bioinfo@proton.me>
#
# Distributed under terms of the BSD-3 license.
#

#TAG="latest"
TAG="spotiflow"
docker build -t bioinfotongli/decoding:$TAG .
docker push bioinfotongli/decoding:$TAG
