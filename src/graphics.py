import folium
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


from src.slope import get_dem_slope
from src.thickness import glacier_thickness_coverage
from src.utils import get_ds


def glaciers_location(gdf):
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
            tooltip=f"RGI ID: {row['RGIId']}<br>Slope: {row['Slope']:.2f}<br>Area: {row['Area']:.2f}",
        ).add_to(glacier_map)

    return glacier_map


def plot_dem_slope(gdir, ax=None):
    """Plot the slope of the DEM for a glacier."""

    ds = get_ds(gdir)
    slope_masked = get_dem_slope(gdir)

    smap = ds.salem.get_map(countries=False)
    smap.set_shapefile(gdir.read_shapefile("outlines"))
    smap.set_topography(ds.topo.data)

    created_fig = False
    if ax is None:
        fig, ax = plt.subplots(figsize=(9, 9))
        created_fig = True

    smap.set_cmap("viridis")
    smap.set_data(slope_masked)
    smap.plot(ax=ax)
    smap.append_colorbar(ax=ax, label="Slope (degrees)")

    ax.set_title(f"Slope on the full glacier {gdir.rgi_id}")
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

    geom = gdir.read_shapefile("outlines")
    df_gtd = pd.read_csv(gdir.get_filepath("glathida_data"))
    percent_thickness_coverage = glacier_thickness_coverage(gdir)

    created_fig = False
    if ax is None:
        f, ax = plt.subplots(figsize=(9, 9))
        created_fig = True

    df_gtd.plot.scatter(
        x="x_proj", y="y_proj", c="thickness", cmap="viridis", s=10, ax=ax
    )
    geom.plot(ax=ax, facecolor="none", edgecolor="k")
    plt.title(
        f"Glacier: {gdir.rgi_id} - Thickness Coverage: {percent_thickness_coverage:.2f}%"
    )
    plt.xlabel("x_proj")
    plt.ylabel("y_proj")
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
    ds = get_ds(gdir)
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
    ax.set_title("Millan 2022 velocity")
    if created_fig:
        plt.show()
