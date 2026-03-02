## TP_monthly_surface_water
This repository contains the core code for generating the Tibetan Plateau (TP) 30-m gap-free monthly surface water dataset (2000–2021) used in the research article:
**"Landsat-Derived Gap-Free Monthly 30-m Dataset (2000–2021) Unraveling Intra-Annual Surface Water Dynamics on the Tibetan Plateau"**

## Code Description

The scripts enable downloading and reconstructing the original JRC Global Surface Water datasets (MWH/YWCH/MWR) via Google Earth Engine (GEE) and Python, implementing the Stepwise Gap-Filling (SGF) method proposed in the study.

GEE_download_JRCMWH_code.txt：GEE-based data downloading, Open in GEE Code Editor: Includes image collection filtering, clipping (to TP boundary), and export functions for the initial JRC MWH dataset.
SGFmethod_step12.py:	SGF method (Steps 1 & 2), Run in Python: Reads locally downloaded initial data, executes Step 1 (YWCH-based classification) and Step 2 (MWR-based inference) of the gap-filling process.
SGFmethod_step34.py:	SGF method (Steps 3 & 4),	Run in Python: Reads the intermediate dataset from Steps 1&2, executes Step 3 (adjacent month MWH reference) and Step 4 (remaining gap handling) to generate the final gap-free dataset.

## Output
The reconstructed surface water dataset is saved in GeoTIFF format (EPSG:4326 coordinate system) with pixel values:
1: Not water
3: Water
The dataset can be opened, visualized, and analyzed using software such as QGIS, ArcGIS, or GDAL.

## Licence
Dataset Licence
The Tibetan Plateau 30-m gap-free monthly surface water dataset (2000–2021) associated with this code is made available under the Creative Commons Zero v1.0 Universal (CC0 1.0) licence. You are free to copy, modify, distribute, and use the dataset for any purpose (commercial or non-commercial), without attribution or permission.
Dataset repository: https://doi.org/10.5281/zenodo.13910635
Dataset citation: Liu, Z., Zhu, D., Wang, L., Yao, Q., & Li, D. (2024). Monthly 30-m Surface Water Dataset of the Tibetan Plateau from 2000 to 2021 [Dataset]. Zenodo. https://doi.org/10.5281/zenodo.13910635

## Code Licence
All code in this repository (.txt and .py files) is released under the Creative Commons Zero v1.0 Universal (CC0 1.0) licence. You may reuse, modify, and redistribute the code without restriction, provided that the original research article is cited when the code is used in academic work.

## Requirements
For GEE code: Google Earth Engine account (https://earthengine.google.com/)
For Python scripts: Python 3.7+, libraries including gdal, numpy, pandas, rasterio
