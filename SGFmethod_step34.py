import os
import rasterio
import numpy as np
import geopandas as gpd
from rasterio.mask import mask

def repair_water_pixels(tif_path, prev_tif_path, next_tif_path, mwr_path, glake_shp_path):
    with rasterio.open(tif_path, 'r+') as tif:
        water_band = tif.read(1)

        # Step 1: Process water=2 pixels
        with rasterio.open(mwr_path) as mwr:
            has_observations = mwr.read(2)
            monthly_recurrence = mwr.read(1)
            with rasterio.open(prev_tif_path) as prev_tif:
                prev_water_band = prev_tif.read(1)
            with rasterio.open(next_tif_path) as next_tif:
                next_water_band = next_tif.read(1)

            water_band = np.where(
                (water_band == 2) & (has_observations == 1) & (monthly_recurrence >= 50) &
                ((prev_water_band == 3) | (next_water_band == 3)), 3, water_band)

            water_band = np.where(
                (water_band == 2) & (has_observations == 1) & (monthly_recurrence < 50) &
                ((prev_water_band == 3) & (next_water_band == 3)), 3, water_band)

            water_band = np.where(water_band == 2, 0, water_band)


        # Step 2: Process water=0 pixels
        water_band = np.where(
            (water_band == 0) & ((prev_water_band == 3) | (next_water_band == 3)), 3, water_band)

        water_band = np.where(water_band == 0, 1, water_band)

        tif.write(water_band, 1)

        # Step 3: Assign nodata to pixels outside the TibetanPlateau boundary
        gdf = gpd.read_file(glake_shp_path)
        shapes = [feature["geometry"] for feature in gdf.iterfeatures()]
        water_band, _ = mask(tif, shapes, filled=True, nodata=255)
        water_band = water_band[0,:,:]
        tif.meta.update({"nodata": 255})


        # Save the updated water_band back to the TIF file
        tif.write(water_band, 1)

def process_tifs(folder_path, mwr_folder, glake_shp_path):
    tif_files = sorted([f for f in os.listdir(folder_path) if f.endswith('.tif')])
    for i in range(1, len(tif_files) - 1):
        tif_path = os.path.join(folder_path, tif_files[i])
        prev_tif_path = os.path.join(folder_path, tif_files[i - 1])
        next_tif_path = os.path.join(folder_path, tif_files[i + 1])
        month = tif_files[i].split('_')[2][:2]  # Extract the month from the file name
        mwr_path = os.path.join(mwr_folder, f'TP_{month}MR.tif')

        print(f"正在处理：{tif_files[i]}")
        repair_water_pixels(tif_path, prev_tif_path, next_tif_path, mwr_path, glake_shp_path)



# 使用示例
folder_path = r'F:\TP_MWH_after_step12'
mwr_folder = r'F:\TP_MR_merge'
glake_shp_path = r'F:\TibetanPlateau.shp'

process_tifs(folder_path, mwr_folder, glake_shp_path)
