from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import folium
import matplotlib.patheffects as path_effects
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import rasterio
import rasterio.merge
import requests
import salem
from mpl_toolkits.axes_grid1 import make_axes_locatable
from oggm import cfg
from oggm import utils as oggm_utils

from glaciexplo import utils, slope, thickness, velocity

# Public, no-auth elevation tiles (Tilezen/Joerd "elevation-tiles-prod"),
# used for the regional overview background. oggm.utils.get_topo_file's own
# sources either need credentials (NASADEM) or point to hosts that turned
# out unreliable/blocked in testing (COPDEM, SRTM); its MAPZEN source hits
# the same bucket but over a now-rejected plain http:// URL.
_OVERVIEW_DEM_TILE_URL = "https://s3.amazonaws.com/elevation-tiles-prod/geotiff"

# Reference cities shown on the regional overview, as (lon, lat).
_OVERVIEW_CITIES = {
    "Grenoble": (5.7245, 45.1885),
    "Geneva": (6.1432, 46.2044),
    "Milan": (9.1900, 45.4642),
    "Turin": (7.6869, 45.0703),
    "Innsbruck": (11.4041, 47.2692),
}


def glaciers_location(gdf, outlines=False):
    """Create an interactive map of glaciers using Folium."""

    # Calculate the mean latitude and longitude for centering the map
    mean_lat = gdf["CenLat"].mean()
    mean_lon = gdf["CenLon"].mean()

    # Create a Folium map centered on the mean location
    glacier_map = folium.Map(location=[mean_lat, mean_lon], zoom_start=6)

    # Add markers for each glacier
    for _, row in gdf.iterrows():
        folium.Marker(
            location=[row["CenLat"], row["CenLon"]],
            tooltip=f"RGI ID: {row['RGIId']}<br>Mean slope: {row['Slope']:.2f}°<br>Area: {row['Area']:.2f}km2",
        ).add_to(glacier_map)
        if outlines:
            folium.GeoJson(
                data=gdf.geometry,
                name="Glacier Outlines",
                style_function=lambda x: {
                    "fillColor": "#00ffff",
                    "color": "black",
                    "weight": 1,
                    "fillOpacity": 0.5,
                },
            ).add_to(glacier_map)

    return glacier_map


def plot_title(gdir, label):
    """Build the shared '<RGI id> — <label>' title used across all glacier plots."""

    return f"{gdir.rgi_id} — {label}"


def _fetch_overview_dem_tile(zone, cache_dir):
    local_path = cache_dir / zone.replace("/", "_")
    if not local_path.exists():
        r = requests.get(f"{_OVERVIEW_DEM_TILE_URL}/{zone}", timeout=30)
        r.raise_for_status()
        local_path.write_bytes(r.content)
    return str(local_path)


def _download_overview_dem_tiles(lon_ex, lat_ex, dx_meter):
    """Download (and locally cache) the elevation tiles covering an extent."""

    zones = oggm_utils.mapzen_zone(lon_ex, lat_ex, dx_meter=dx_meter)

    cache_dir = Path(cfg.PATHS["tmp_dir"]) / "glaciexplo_overview_dem"
    cache_dir.mkdir(parents=True, exist_ok=True)

    with ThreadPoolExecutor(max_workers=16) as pool:
        tile_paths = list(
            pool.map(lambda z: _fetch_overview_dem_tile(z, cache_dir), zones)
        )

    return tile_paths


def plot_glacier_overview(gdir, ax=None, extent_m=550_000):
    """Plot a regional overview map (Swiss Alps) with the glacier outline.

    Uses the same salem shaded-relief style as plot_dem_slope/plot_velocity,
    but on a regional grid centered on the glacier rather than its own local
    (cropped) domain, since the glacier's own gridded_data only covers its
    immediate surroundings. The background DEM is downloaded from the public
    Tilezen/Joerd elevation tiles (no credentials needed).

    Args:
        gdir: Glacier directory.
        ax: Matplotlib axis to plot on (optional).
        extent_m: Width/height in meters of the regional view (default 550 km).
    """

    grid = salem.mercator_grid(
        center_ll=(gdir.cenlon, gdir.cenlat), extent=(extent_m, extent_m), ny=900
    )
    smap = salem.Map(grid, ny=900, countries=False)

    lon_min, lon_max, lat_min, lat_max = grid.extent_in_crs(crs=salem.wgs84)
    dem_paths = _download_overview_dem_tiles(
        (lon_min, lon_max), (lat_min, lat_max), dx_meter=grid.dx
    )

    mosaic, transform = rasterio.merge.merge(dem_paths)
    with rasterio.open(dem_paths[0]) as src:
        profile = src.profile
    profile.update(height=mosaic.shape[1], width=mosaic.shape[2], transform=transform)

    cache_dir = Path(cfg.PATHS["tmp_dir"]) / "glaciexplo_overview_dem"
    mosaic_path = str(cache_dir / f"mosaic_{gdir.rgi_id}_{extent_m}.tif")
    with rasterio.open(mosaic_path, "w", **profile) as dst:
        dst.write(mosaic)

    smap.set_topography(mosaic_path, relief_factor=3.0)

    created_fig = False
    if ax is None:
        f, ax = plt.subplots(figsize=(9, 9))
        created_fig = True

    smap.set_shapefile(
        gdir.read_shapefile("outlines"), edgecolor="orange", facecolor="none", linewidth=0.25
    )
    smap.plot(ax=ax)

    city_lons, city_lats = zip(*_OVERVIEW_CITIES.values())
    xx, yy = smap.grid.transform(np.array(city_lons), np.array(city_lats), crs=salem.wgs84)
    ax.scatter(xx, yy, marker="o", s=25, facecolor="black", edgecolor="white", linewidth=0.5)

    x_lo, x_hi = ax.get_xlim()
    x_mid = (x_lo + x_hi) / 2
    for name, x, y in zip(_OVERVIEW_CITIES, xx, yy):
        on_right = x > x_mid
        label = ax.annotate(
            name,
            (x, y),
            xytext=(-5 if on_right else 5, 4),
            textcoords="offset points",
            ha="right" if on_right else "left",
            fontsize=9,
            color="black",
            clip_on=False,
        )
        label.set_path_effects(
            [path_effects.withStroke(linewidth=2.5, foreground="white")]
        )

    ax.set_title(plot_title(gdir, "Regional overview (French Alps)"))
    if created_fig:
        plt.show()


def plot_dem_slope(gdir, ax=None):
    """Plot the slope of the DEM for a glacier."""

    ds = utils.get_ds(gdir)
    slope_masked = slope.get_dem_slope(gdir)

    smap = ds.salem.get_map(countries=False)
    smap.set_shapefile(gdir.read_shapefile("outlines"))
    smap.set_topography(ds.topo.data)

    created_fig = False
    if ax is None:
        f, ax = plt.subplots(figsize=(9, 9))
        created_fig = True

    smap.set_cmap("viridis")
    smap.set_data(slope_masked)
    smap.plot(ax=ax)
    smap.append_colorbar(ax=ax, label="Slope (degrees)")

    ax.set_title(plot_title(gdir, "Surface slope"))
    if created_fig:
        plt.show()


def plot_domain(gdir, ax=None):
    """Plot the glacier domain: outline over the terrain (elevation)."""

    ds = utils.get_ds(gdir)

    smap = ds.salem.get_map(countries=False)
    smap.set_shapefile(gdir.read_shapefile("outlines"))
    smap.set_data(ds.topo.data)

    created_fig = False
    if ax is None:
        f, ax = plt.subplots(figsize=(9, 9))
        created_fig = True

    smap.set_cmap("terrain")
    smap.plot(ax=ax)
    smap.append_colorbar(ax=ax, label="Altitude (m)")

    ax.set_title(plot_title(gdir, "Glacier domain"))
    if created_fig:
        plt.show()


def plot_glacier_grid(gdir, ax=None, step=3, highlight_index=None, scale_km=1.0):
    """Plot the glacier outline (filled) with a regular grid of sample points inside it.

    Mimics classic glaciological sampling-grid figures: the outline is filled,
    a red dot is drawn on every `step`-th DEM grid cell that falls inside the
    glacier mask, one point is highlighted and labelled "A", and a scale bar
    is added.

    Args:
        gdir: Glacier directory.
        ax: Matplotlib axis to plot on (optional).
        step: Take every `step`-th grid cell in each direction.
        highlight_index: index (into the flattened list of in-glacier points)
            of the point to label "A". Defaults to the point closest to the
            centroid of the sampled points.
        scale_km: length of the scale bar, in km.
    """

    ds = utils.get_ds(gdir)
    mask = ds.glacier_mask.values

    smap = ds.salem.get_map(countries=False)
    smap.set_shapefile(
        gdir.read_shapefile("outlines"), facecolor="#f5f0c9", edgecolor="black", linewidth=1
    )

    created_fig = False
    if ax is None:
        f, ax = plt.subplots(figsize=(7, 9))
        created_fig = True

    smap.plot(ax=ax)

    jj, ii = np.meshgrid(
        np.arange(0, mask.shape[0], step), np.arange(0, mask.shape[1], step), indexing="ij"
    )
    inside = mask[jj, ii].astype(bool)
    jj, ii = jj[inside], ii[inside]

    xx, yy = smap.grid.transform(ds.x.values[ii], ds.y.values[jj], crs=gdir.grid.proj)
    ax.scatter(xx, yy, s=35, facecolor="#d94b3f", edgecolor="black", linewidth=0.5, zorder=5)

    if len(xx):
        if highlight_index is None:
            cx, cy = xx.mean(), yy.mean()
            highlight_index = np.argmin((xx - cx) ** 2 + (yy - cy) ** 2)
        hx, hy = xx[highlight_index], yy[highlight_index]
        ax.annotate(
            "A",
            (hx, hy),
            xytext=(hx - 25, hy - 25),
            fontsize=12,
            color="black",
            arrowprops=dict(arrowstyle="-", color="grey", lw=0.8),
            zorder=6,
        )

    xlim, ylim = ax.get_xlim(), ax.get_ylim()
    bar_len = scale_km * 1000 / abs(smap.grid.dx)
    bx0 = xlim[0] + 0.06 * (xlim[1] - xlim[0])
    by0 = ylim[0] + 0.06 * (ylim[1] - ylim[0])
    ax.plot([bx0, bx0 + bar_len], [by0, by0], color="black", lw=2, solid_capstyle="butt")
    ax.text(
        bx0 + bar_len / 2,
        by0 + 0.02 * (ylim[1] - ylim[0]),
        f"{scale_km:g} km",
        ha="center",
        va="bottom",
        fontsize=10,
    )

    ax.set_title(plot_title(gdir, "Sampling grid"))
    if created_fig:
        plt.show()


def plot_thickness_coverage(gdir, ax=None):
    """
    Plot the thickness data from GlaThIDA for a glacier.

    Args:
        gdir: Glacier directory.

    Returns:
        None
    """

    ds = utils.get_ds(gdir)
    df_gtd = pd.read_csv(gdir.get_filepath("glathida_data"))
    percentage, n_ij_grid = thickness.glacier_thickness_coverage(gdir)

    smap = ds.salem.get_map(countries=False)
    smap.set_shapefile(gdir.read_shapefile("outlines"))

    created_fig = False
    if ax is None:
        f, ax = plt.subplots(figsize=(9, 9))
        created_fig = True

    smap.plot(ax=ax)

    xx, yy = smap.grid.transform(
        df_gtd["x_proj"].values, df_gtd["y_proj"].values, crs=gdir.grid.proj
    )
    sc = ax.scatter(xx, yy, c=df_gtd["thickness"], cmap="viridis", s=10)
    cax = make_axes_locatable(ax).append_axes("right", size="5%", pad=0.5)
    plt.colorbar(sc, cax=cax, label="Thickness (m)")

    ax.set_title(
        plot_title(
            gdir,
            f"GlaThiDa thickness coverage ({percentage:.1f}%, {n_ij_grid} pts)",
        )
    )
    if created_fig:
        plt.show()


def plot_velocity(gdir, ax=None):
    """
    Plot the velocity data for a glacier.

    Args:
        gdir: Glacier directory.

    Returns:
        None
    """
    ds = utils.get_ds(gdir)
    # get the velocity data
    u = ds.millan_vx.where(ds.glacier_mask)
    v = ds.millan_vy.where(ds.glacier_mask)
    ws = ds.millan_v.where(ds.glacier_mask)

    smap = ds.salem.get_map(countries=False)
    smap.set_shapefile(gdir.read_shapefile("outlines"))
    smap.set_topography(ds.topo.data)

    # get the axes ready
    created_fig = False
    if ax is None:
        f, ax = plt.subplots(figsize=(9, 9))
        created_fig = True

    # Quiver only every N grid point
    us = u[1::3, 1::3]
    vs = v[1::3, 1::3]

    smap.set_data(ws)
    smap.set_cmap("Blues")
    smap.plot(ax=ax)
    smap.append_colorbar(ax=ax, label="ice velocity (m yr$^{-1}$)")

    # transform their coordinates to the map reference system and plot the arrows
    xx, yy = smap.grid.transform(us.x.values, us.y.values, crs=gdir.grid.proj)
    xx, yy = np.meshgrid(xx, yy)
    qu = ax.quiver(xx, yy, us.values, vs.values)
    ax.quiverkey(qu, 0.82, 0.97, 10, "10 m yr$^{-1}$", labelpos="E", coordinates="axes")
    ax.set_title(plot_title(gdir, "Ice velocity (Millan et al., 2022)"))
    if created_fig:
        plt.show()


def merge_glacier_data(gdirs, gdf, slope_threshold=20):
    """Generate a merged GeoDataFrame containing:
        - glacier information,
        - thickness coverage,
        - percentage of glacier surface with slope above threshold,
        - velocity errors for glaciers.

    Args:
        gdirs: list of GlacierDirectory objects.
        gdf: GeoDataFrame with glacier information (must contain 'RGIId' column).
        slope_threshold: slope threshold in degrees to calculate the percentage of glacier surface above it.

    Returns:
        GeoDataFrame.
    """
    data_thick = thickness.create_df_thickness_coverage(gdirs)
    data_vel = velocity.create_df_velocity_errors(gdirs)
    data_slope = slope.create_df_slope_above(gdirs, threshold=slope_threshold)

    # verify that the 'RGIId' column exists in all DataFrames
    for df in [gdf, data_thick, data_vel, data_slope]:
        if "RGIId" not in df.columns:
            raise ValueError(
                "All DataFrames must contain an 'RGIId' column for merging."
            )

    gdf_merged = gdf.merge(data_thick, on="RGIId", how="left")
    gdf_merged = gdf_merged.merge(data_slope, on="RGIId", how="left")
    gdf_merged = gdf_merged.merge(data_vel, on="RGIId", how="left")

    return gdf_merged
