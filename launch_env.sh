#!/usr/bin/env bash

export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export VECLIB_MAXIMUM_THREADS=1

export ATHENA_HOST='ws://op.caminfo.cn:7776'
export API_HOST='http://op.caminfo.cn:7777'
export MAPBOX_TOKEN='sk.eyJ1IjoibWF3ZWl5dXdlaXdlaSIsImEiOiJjbG15NHN1dDMwdWc5MmxwaDdkZ3Z5dHNyIn0.pk06qTKkAZyBC1Z37v8i0A'
export QCOM_PRIORITY=12

if [ -z "$AGNOS_VERSION" ]; then
  export AGNOS_VERSION="16"
fi

export STAGING_ROOT="/data/safe_staging"
