## Image-based spatial transcritomics RNA spot decoding workflow 

This workflow includes:
- Raw image enchancement with [White Tophat filtering](https://scikit-image.org/docs/stable/api/skimage.morphology.html#skimage.morphology.white_tophat)
- Peak-calling with [TrackPy](http://soft-matter.github.io/trackpy/dev/generated/trackpy.locate.html#trackpy.locate)
- PoSTcode decoding:
    ![plot](./PoSTcode.png)
    which is a method for decoding image-based spatial transcriptomics based on a re-parametrised matrix-variate Gaussian mixture model,

Prerequisite:
- Nextflow
- Docker/singularity

Usage (TODO):

```bash
NXF_OPTS='-Dleveldb.mmap=false' NXF_VER=23.10.1 \
    nextflow -trace nextflow.executor run BioinfoTongLI/workflow-decoding -r master \
        -profile local \
        -params-file decoding.yaml
```
An example of the parameter input file is 
```yaml
codebook : [codebook.csv]
out_dir : [output folder]
ome_zarr : [ome-zarr path of a registered multicycle multichannel stack]
channel_map : "{'Cy5':'A','AF488':'G','Cy3':'C','Atto425':'T','AF750':'T'}"
rna_spot_size : [5]
anchor_ch_indexes : 1
prob_threshold : 0.9
trackpy_percentile : [90]
trackpy_separation : 3
codebook_sep : ','
```