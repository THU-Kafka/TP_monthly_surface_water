import os
import rasterio
import numpy as np


def repair_water_pixels(tif_path, ywch_path, mwr_path):
    with rasterio.open(tif_path, 'r+') as tif:
        water_band = tif.read(1)

        # Step 0: Set water=2 pixels to water=3
        water_band = np.where(water_band == 2, 3, water_band)

        # Step 1: Use YWCH reference file
        with rasterio.open(ywch_path) as ywch:
            ywch_water_band = ywch.read(1)
            mask_0_1 = (water_band == 0) | (water_band == 1)
            water_band = np.where(mask_0_1 & (ywch_water_band == 3), 3, water_band)
            water_band = np.where(mask_0_1 & (ywch_water_band == 1), 1, water_band)
            water_band = np.where(mask_0_1 & (ywch_water_band == 2), 2, water_band)
            water_band = np.where(mask_0_1 & (ywch_water_band == 0), 0, water_band)

        # Step 2: Use MWR reference file
        with rasterio.open(mwr_path) as mwr:
            has_observations = mwr.read(2)
            monthly_recurrence = mwr.read(1)
            mask_2 = water_band == 2
            water_band = np.where(mask_2 & (has_observations == 1) & (monthly_recurrence == 0), 1, water_band)
            water_band = np.where(mask_2 & (has_observations == 1) & (monthly_recurrence == 100), 3, water_band)

        # Save the updated water_band back to the TIF file
        tif.write(water_band, 1)

def process_tifs(folder_path, ywch_folder, mwr_folder):
    tif_files = sorted([f for f in os.listdir(folder_path) if f.endswith('.tif')])
    for tif_file in tif_files:
        tif_path = os.path.join(folder_path, tif_file)
        year = tif_file.split('_')[1][:4]  # Extract the year from the file name
        month = tif_file.split('_')[2][:2]  # Extract the month from the file name
        ywch_path = os.path.join(ywch_folder, f'TP_{year}.tif')
        mwr_path = os.path.join(mwr_folder, f'TP_{month}MR.tif')

        print(f"正在处理：{tif_file}")
        repair_water_pixels(tif_path, ywch_path, mwr_path)


# 使用示例
folder_path = r'F:\TP_MWH_original'
ywch_folder = r'F:\TP_YWCH'
mwr_folder = r'F:\TP_MR'

process_tifs(folder_path, ywch_folder, mwr_folder)
