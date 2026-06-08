import os
import rasterio
import numpy as np
import geopandas as gpd
from rasterio.mask import mask
from scipy.ndimage import uniform_filter


def calculate_spatial_mean(band, size=3):
    """
    Calculate the spatial neighborhood mean of monthly water recurrence (MR)
    for each pixel using a size x size window, properly ignoring invalid values.

    This function computes the average MR value within a 3x3 spatial
    neighborhood centered on each pixel. Invalid values (NaN, negative, or
    values exceeding 100 for MR percentage data) are excluded from the mean
    calculation. This ensures that nodata pixels do not bias the spatial mean.

    The paper specifies a 3x3 neighborhood for Step 4 spatial consistency
    correction. The original gapfilling.py used a 5x5 window (radius=2);
    this implementation uses 3x3 as described in the paper.

    :param band: Input 2D numpy array (e.g., monthly recurrence values 0-100).
    :param size: Window size for the spatial neighborhood (default: 3 for 3x3).
    :return: 2D array of spatial neighborhood mean values.
    """
    # Identify valid pixels: non-NaN, non-negative, and within valid MR range (0-100)
    valid_mask = ~np.isnan(band.astype(float)) & (band.astype(float) >= 0) & (band.astype(float) <= 100)

    # Replace invalid pixels with 0 for summation, and compute the count of
    # valid pixels in each neighborhood separately
    band_filled = np.where(valid_mask, band.astype(float), 0.0)
    valid_count = uniform_filter(valid_mask.astype(float), size=size, mode='constant', cval=0)
    sum_band = uniform_filter(band_filled, size=size, mode='constant', cval=0)

    # Compute mean by dividing sum by valid count; avoid division by zero
    mean_band = np.where(valid_count > 0, sum_band / valid_count, 0.0)
    return mean_band


def repair_water_pixels(tif_path, prev_tif_path, next_tif_path, mwr_path, glake_shp_path):
    """
    Apply Steps 3 and 4 of the Stepwise Gap-Filling (SGF) method to classify
    remaining potentially water pixels and achieve complete gap-filling.

    Step 3: Temporal neighborhood similarity inference
        After Steps 1-2, more than 99.8% of all pixels have been clearly
        classified. For the tiny proportion (< 0.2%) of highly ambiguous
        potentially water pixels that remain (0% < MR < 100%), temporal
        neighborhood similarity judgment with strict non-overlapping unequal
        threshold rules is applied:
        (1) If MR < 50% AND at least one adjacent monthly pixel (previous or
            next month) is not-water, the target pixel is classified as
            not-water.
        (2) If MR >= 50% AND at least one adjacent monthly pixel is water,
            the target pixel is classified as water.
        (3) The remaining ambiguous gap pixels, including those with missing
            values in adjacent months (i.e., invalid neighborhood observations),
            cannot be determined via temporal rules and are forwarded to Step 4
            for spatial neighborhood correction.

    Step 4: Spatial neighborhood consistency correction
        For the few ambiguous residual gap pixels that cannot be classified
        via temporal neighborhood inference, spatial neighborhood consistency
        analysis is adopted for final confirmation based on the spatial
        continuity characteristics of surface water bodies:
        - Calculate the average monthly water recurrence value of the 3x3
          spatial neighborhood centered on the target pixel.
        - Pixels are classified as water when their neighborhood-averaged
          water recurrence is no less than 50%, with either MR >= 50% or
          valid water identification from adjacent monthly observations.
        - Otherwise, pixels are classified as not-water.

    After Steps 3-4, all gap and potentially water pixels should be classified
    as either water (3) or not-water (1), achieving complete binary
    classification. Pixels outside the Tibetan Plateau boundary are then
    assigned nodata (255).

    Pixel encoding (input from Steps 1-2 output):
        0 = No data / gap (remaining from Step 1, e.g., YWCH no-data)
        1 = Not water
        2 = Potentially water (0% < MR < 100%, from Step 2)
        3 = Water (confirmed)

    :param tif_path: Path to the current monthly MWH TIF file (after Steps 1-2).
    :param prev_tif_path: Path to the previous month's MWH TIF file.
    :param next_tif_path: Path to the next month's MWH TIF file.
    :param mwr_path: Path to the corresponding monthly MWR reference TIF file.
    :param glake_shp_path: Path to the Tibetan Plateau boundary shapefile.
    """
    with rasterio.open(tif_path, 'r+') as tif:
        water_band = tif.read(1)

        # Read MWR data (monthly recurrence and observation flag)
        with rasterio.open(mwr_path) as mwr:
            has_observations = mwr.read(2)    # 0=no observations, 1=has observations
            monthly_recurrence = mwr.read(1)  # 0-100 (%)

        # Read adjacent month water data for temporal neighborhood inference
        with rasterio.open(prev_tif_path) as prev_tif:
            prev_water_band = prev_tif.read(1)
        with rasterio.open(next_tif_path) as next_tif:
            next_water_band = next_tif.read(1)

        # ----------------------------------------------------------------
        # Step 3: Temporal neighborhood similarity inference
        #
        # For potentially water pixels (water=2) with 0% < MR < 100%,
        # apply strict non-overlapping unequal threshold rules based on
        # temporal dynamic continuity of water variations.
        #
        # The has_observations flag is checked to ensure MR values are
        # meaningful. Pixels without valid observations (has_observations=0)
        # skip Step 3 and are forwarded directly to Step 4.
        # ----------------------------------------------------------------

        mask_potentially_water = water_band == 2

        # Rule 1: MR < 50% AND at least one adjacent month is not-water
        #          -> classified as not-water
        # This rule identifies pixels with low water recurrence that are
        # confirmed as not-water by temporal neighborhood observations.
        water_band = np.where(
            mask_potentially_water
            & (has_observations == 1)
            & (monthly_recurrence < 50)
            & ((prev_water_band == 1) | (next_water_band == 1)),
            1, water_band)

        # Update the mask after Rule 1
        mask_potentially_water = water_band == 2

        # Rule 2: MR >= 50% AND at least one adjacent month is water
        #          -> classified as water
        # This rule identifies pixels with high water recurrence that are
        # confirmed as water by temporal neighborhood observations.
        water_band = np.where(
            mask_potentially_water
            & (has_observations == 1)
            & (monthly_recurrence >= 50)
            & ((prev_water_band == 3) | (next_water_band == 3)),
            3, water_band)

        # Remaining potentially water pixels (including those without valid
        # observations or with invalid neighborhood observations) are
        # forwarded to Step 4 for spatial neighborhood correction.

        # ----------------------------------------------------------------
        # Step 4: Spatial neighborhood consistency correction
        #
        # For the few ambiguous residual gap pixels that cannot be classified
        # via temporal neighborhood inference, spatial neighborhood consistency
        # analysis is adopted for final confirmation.
        #
        # Calculate the average MR of the 3x3 spatial neighborhood centered
        # on each target pixel. Pixels are classified as water when:
        #   (1) neighborhood-averaged MR >= 50%
        #   AND
        #   (2) either MR >= 50% OR at least one adjacent month is water
        # Otherwise, pixels are classified as not-water.
        #
        # This spatial correction effectively eliminates unreasonable
        # classification results of isolated residual gap pixels caused by
        # extreme terrain shadows and sporadic cloud interference.
        # ----------------------------------------------------------------

        # Calculate spatial mean of monthly recurrence using 3x3 neighborhood
        mr_spatial_mean = calculate_spatial_mean(monthly_recurrence, size=3)

        # Apply spatial neighborhood rule to remaining potentially water pixels
        mask_potentially_water = water_band == 2

        water_band = np.where(
            mask_potentially_water
            & (mr_spatial_mean >= 50)
            & ((monthly_recurrence >= 50) | (prev_water_band == 3) | (next_water_band == 3)),
            3, water_band)

        # Remaining potentially water pixels that fail the spatial rule
        # -> classified as not-water
        mask_potentially_water = water_band == 2
        water_band = np.where(mask_potentially_water, 1, water_band)

        # Handle remaining gap pixels (water=0) that had no YWCH data
        # These are rare pixels where YWCH also had no data.
        # Apply the same spatial neighborhood rule for final classification.
        mask_gap = water_band == 0
        water_band = np.where(
            mask_gap
            & (mr_spatial_mean >= 50)
            & ((monthly_recurrence >= 50) | (prev_water_band == 3) | (next_water_band == 3)),
            3, water_band)
        # Remaining gap pixels -> not-water
        mask_gap = water_band == 0
        water_band = np.where(mask_gap, 1, water_band)

        # Save the classified result before boundary clipping
        tif.write(water_band, 1)

        # ----------------------------------------------------------------
        # Boundary assignment: Set pixels outside the Tibetan Plateau
        # boundary to nodata (255)
        #
        # This step masks out pixels that fall outside the study area
        # boundary defined by the Tibetan Plateau shapefile. Only pixels
        # within the boundary retain their water/not-water classification.
        # ----------------------------------------------------------------
        gdf = gpd.read_file(glake_shp_path)
        shapes = [feature["geometry"] for feature in gdf.iterfeatures()]
        water_band, _ = mask(tif, shapes, filled=True, nodata=255)
        water_band = water_band[0, :, :]
        tif.meta.update({"nodata": 255})

        # Save the final result with boundary clipping applied
        tif.write(water_band, 1)


def process_tifs(folder_path, mwr_folder, glake_shp_path):
    """
    Process all MWH TIF files in the folder, applying Steps 3 and 4 of the
    SGF method.

    The input files should be the output of Steps 1-2 (SGFmethod_step12.py)
    with the following pixel encoding:
        0 = No data / gap (remaining from Step 1)
        1 = Not water
        2 = Potentially water (0% < MR < 100%, from Step 2)
        3 = Water (confirmed)

    After processing, all pixels within the Tibetan Plateau boundary are
    classified as either water (3) or not-water (1). Pixels outside the
    boundary are set to nodata (255).

    Note: The first and last files in the time series are skipped because
    they lack both adjacent month neighbors required for temporal
    neighborhood inference. These files may need separate handling using
    Step 4 (spatial neighborhood only) or single-neighbor temporal rules.

    :param folder_path: Directory containing MWH TIF files (output from Steps 1-2).
    :param mwr_folder: Directory containing monthly MWR reference TIF files.
                       Expected naming: TP_{month}MR.tif
    :param glake_shp_path: Path to the Tibetan Plateau boundary shapefile.
    """
    tif_files = sorted([f for f in os.listdir(folder_path) if f.endswith('.tif')])
    # Skip the first and last files as they lack both temporal neighbors
    for i in range(1, len(tif_files) - 1):
        tif_path = os.path.join(folder_path, tif_files[i])
        prev_tif_path = os.path.join(folder_path, tif_files[i - 1])
        next_tif_path = os.path.join(folder_path, tif_files[i + 1])
        # Extract month from filename: expected format TP_{year}_{month}.tif
        month = tif_files[i].split('_')[2][:2]
        mwr_path = os.path.join(mwr_folder, f'TP_{month}MR.tif')

        print(f"Processing (Steps 3-4): {tif_files[i]}")
        repair_water_pixels(tif_path, prev_tif_path, next_tif_path, mwr_path, glake_shp_path)


# Example usage
if __name__ == '__main__':
    folder_path = r'F:\TP_MWH_after_step12'
    mwr_folder = r'F:\TP_MR_merge'
    glake_shp_path = r'F:\TibetanPlateau.shp'

    process_tifs(folder_path, mwr_folder, glake_shp_path)
