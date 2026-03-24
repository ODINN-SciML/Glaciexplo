from oggm.core import gis
import numpy as np
import pandas as pd

from src.utils import get_ds


def get_dem_slope(gdir):
    """
    Get the slope of the DEM for a glacier.

    Args:
        gdir: Glacier directory.

    Returns:
        np.ndarray: Slope of the DEM for the glacier.
    """

    dem = gis.read_geotiff_dem(gdir)
    sy, sx = np.gradient(dem, gdir.grid.dx)

    ds = get_ds(gdir)
    glacier_mask = ds.glacier_mask

    slope = np.arctan(np.sqrt(sx**2 + sy**2))
    slope_masked = np.where(glacier_mask, np.degrees(slope), np.nan)

    return slope_masked


def glacier_slope_above(gdir, threshold=20):
    """
    Calculate the percentage of the glacier area with slope above a threshold.

    Args:
        gdir: Glacier directory.
        threshold: Slope threshold in degrees.

    Returns:
        float: Percentage of glacier area with slope above the threshold.
    """

    slope_masked = get_dem_slope(gdir)
    glacier_mask = ~np.isnan(slope_masked)
    total_area = np.sum(glacier_mask)
    if total_area == 0:
        percentage = 0.0
    else:
        above_threshold = np.sum((slope_masked > threshold) & glacier_mask)
        percentage = above_threshold / total_area * 100
    return percentage


def create_df_slope_above(gdirs, threshold=20):
    """
    Create a DataFrame with the percentage of glacier area with slope above a threshold for each glacier.

    Args:
        gdirs (list): List of glacier directories.
        threshold (float): Slope threshold in degrees.

    Returns:
        pd.DataFrame: DataFrame with the percentage of glacier area with slope above the threshold for each glacier.
    """

    percent_slope_above_list = []
    for gdir in gdirs:
        percentage = glacier_slope_above(gdir, threshold)
        percent_slope_above_list.append(
            {"RGIId": gdir.rgi_id, "percent_slope_above": percentage}
        )

    df_slope_coverage = pd.DataFrame(percent_slope_above_list)
    return df_slope_coverage
