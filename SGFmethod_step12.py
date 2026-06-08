import os
import rasterio
import numpy as np


def repair_water_pixels(tif_path, ywch_path, mwr_path):
    """
    Apply Steps 1 and 2 of the Stepwise Gap-Filling (SGF) method to fill gap
    pixels in the Monthly Water History (MWH) dataset.

    Step 1: Long-term water attribute constraint based on YWCH dataset
        For each gap pixel in the monthly MWH image:
        (1) If the corresponding YWCH pixel is permanent water, the pixel is
            directly filled as water.
        (2) If the YWCH pixel is not-water, the pixel is directly filled as
            not-water.
        (3) If the YWCH pixel is seasonal water, the pixel is marked as
            "potentially water" for further judgment in subsequent steps.

    Step 2: Monthly water recurrence correction based on MWR dataset
        For each potentially water pixel from Step 1:
        (1) If monthly recurrence (MR) = 100%, the pixel is classified as water.
        (2) If MR = 0% (with valid observations), the pixel is classified as
            not-water.
        (3) Pixels with 0% < MR < 100% retain the potentially water attribute
            and enter Step 3 (temporal neighborhood judgment).

    Pixel encoding (JRC MWH original):
        0 = No data / gap
        1 = Not water
        2 = Water (original observation)

    Pixel encoding (after Step 0 re-encoding):
        0 = No data / gap
        1 = Not water
        2 = Potentially water (seasonal water from YWCH, to be further classified)
        3 = Water (confirmed)

    :param tif_path: Path to the current monthly MWH TIF file.
    :param ywch_path: Path to the corresponding annual YWCH reference TIF file.
    :param mwr_path: Path to the corresponding monthly MWR reference TIF file.
    """
    with rasterio.open(tif_path, 'r+') as tif:
        water_band = tif.read(1)

        # ----------------------------------------------------------------
        # Pre-step: Re-encode original water observations from 2 to 3
        # The original JRC MWH encoding uses 2 for water observations.
        # We re-encode water as 3 so that value 2 becomes available for
        # the "potentially water" classification introduced in Step 1.
        # After this step: 0=gap, 1=not-water, 3=confirmed water.
        # ----------------------------------------------------------------
        water_band = np.where(water_band == 2, 3, water_band)

        # ----------------------------------------------------------------
        # Step 1: Long-term water attribute constraint based on YWCH dataset
        #
        # For gap pixels (water=0) in the monthly MWH image, the annual YWCH
        # classification provides long-term water stability constraints to
        # define the inherent water attribute of each pixel:
        #   - YWCH permanent water (3) indicates the pixel is stably water
        #     throughout all valid non-gap observations of the year -> fill as water
        #   - YWCH not-water (1) indicates no water occurrence in the entire
        #     year -> fill as not-water
        #   - YWCH seasonal water (2) typically corresponds to lake marginal
        #     zones with dynamic water changes and seasonal water bodies
        #     frequently obscured by clouds or snow-ice -> mark as potentially
        #     water for subsequent multi-dimensional rules
        #   - YWCH no-data (0) is rare; these pixels remain as gap and will
        #     be handled in later steps
        # ----------------------------------------------------------------
        with rasterio.open(ywch_path) as ywch:
            ywch_water_band = ywch.read(1)

            mask_gap = water_band == 0

            # YWCH permanent water -> confirmed water
            water_band = np.where(mask_gap & (ywch_water_band == 3), 3, water_band)
            # YWCH not-water -> not-water
            water_band = np.where(mask_gap & (ywch_water_band == 1), 1, water_band)
            # YWCH seasonal water -> potentially water (needs further judgment)
            water_band = np.where(mask_gap & (ywch_water_band == 2), 2, water_band)
            # YWCH no-data -> keep as gap (0), will be handled in Steps 3-4

        # ----------------------------------------------------------------
        # Step 2: Monthly water recurrence correction based on MWR dataset
        #
        # To further eliminate the uncertainty of residual seasonal water gap
        # pixels that cannot be confirmed in Step 1, the month-specific MWR
        # value (0-100%) is introduced for secondary judgment of all
        # potentially water pixels.
        #   - MR = 100%: the pixel has been observed as water in the same
        #     month throughout its entire water period -> classified as water
        #   - MR = 0% (with valid observations): the pixel shows no water
        #     recurrence record in the target month throughout the entire
        #     observation period -> classified as not-water
        #   - 0% < MR < 100%: the pixel retains the potentially water
        #     attribute and enters Step 3 (temporal neighborhood judgment)
        #
        # The has_observations flag (MWR band 2) indicates whether the pixel
        # has valid observations. MR rules only apply when has_observations=1.
        # When has_observations=0, the MR value is not meaningful, and the
        # pixel remains as potentially water (2) for Step 3 processing.
        # ----------------------------------------------------------------
        with rasterio.open(mwr_path) as mwr:
            has_observations = mwr.read(2)    # 0=no observations, 1=has observations
            monthly_recurrence = mwr.read(1)  # 0-100 (%)

            mask_potentially_water = water_band == 2

            # MR = 100% with valid observations -> confirmed water
            water_band = np.where(
                mask_potentially_water
                & (has_observations == 1)
                & (monthly_recurrence == 100),
                3, water_band)

            # MR = 0% with valid observations -> not-water
            # (the pixel shows no water recurrence in this month across all years,
            #  while water presence can be detected in other months of the year)
            water_band = np.where(
                mask_potentially_water
                & (has_observations == 1)
                & (monthly_recurrence == 0),
                1, water_band)

            # Pixels with 0% < MR < 100% or no observations remain as
            # potentially water (2) and will be processed in Steps 3-4

        # Save the updated water_band back to the TIF file
        tif.write(water_band, 1)


def process_tifs(folder_path, ywch_folder, mwr_folder):
    """
    Process all MWH TIF files in the folder, applying Steps 1 and 2 of the
    SGF method.

    The input MWH files should use the standard JRC encoding:
        0 = No data / gap, 1 = Not water, 2 = Water

    After processing, the output encoding becomes:
        0 = No data / gap (remaining unclassified)
        1 = Not water
        2 = Potentially water (to be further classified in Steps 3-4)
        3 = Water (confirmed)

    :param folder_path: Directory containing input MWH TIF files.
    :param ywch_folder: Directory containing annual YWCH reference TIF files.
                        Expected naming: TP_{year}.tif
    :param mwr_folder: Directory containing monthly MWR reference TIF files.
                       Expected naming: TP_{month}MR.tif
    """
    tif_files = sorted([f for f in os.listdir(folder_path) if f.endswith('.tif')])
    for tif_file in tif_files:
        tif_path = os.path.join(folder_path, tif_file)
        # Extract year and month from the filename
        # Expected filename format: TP_{year}_{month}.tif
        year = tif_file.split('_')[1][:4]
        month = tif_file.split('_')[2][:2]
        ywch_path = os.path.join(ywch_folder, f'TP_{year}.tif')
        mwr_path = os.path.join(mwr_folder, f'TP_{month}MR.tif')

        print(f"Processing (Steps 1-2): {tif_file}")
        repair_water_pixels(tif_path, ywch_path, mwr_path)


# Example usage
if __name__ == '__main__':
    folder_path = r'F:\TP_MWH_original'
    ywch_folder = r'F:\TP_YWCH'
    mwr_folder = r'F:\TP_MR'

    process_tifs(folder_path, ywch_folder, mwr_folder)
