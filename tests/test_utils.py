from glaciexplo import utils
import geopandas as gpd


def test_get_oggm_version():
    """Test that the get_oggm_version function returns a non-empty string."""
    version = utils.get_oggm_version()
    assert isinstance(version, str), "The version should be a string."
    assert version, "The version string should not be empty."


def test_get_gdf_file():
    """Test that the get_gdf_file function returns a valid GeoDataFrame."""
    # Get a sample glacier dataframe for a specific region
    gdf = utils.get_gdf_file(11, version="62")
    assert isinstance(gdf, gpd.GeoDataFrame), "The output should be a GeoDataFrame."
    assert len(gdf) > 0, "The GeoDataFrame should contain at least one glacier."


def test_init_glaciers_from_oggm():
    """Test that the init_glaciers_from_oggm function initializes glacier directories correctly."""
    # Get a sample glacier dataframe for a specific region
    gdf = utils.get_gdf_file(11, version="62")

    # Initialize glacier directories with a small subset of glaciers to avoid long processing times
    subset_gdf = gdf.head(5)  # Use only the first 5 glaciers for testing
    try:
        gdirs = utils.init_glaciers_from_oggm(subset_gdf, workspace_path="c")
        assert isinstance(
            gdirs, list
        ), "The output should be a list of glacier directories."
        assert len(gdirs) == len(
            subset_gdf
        ), "The number of glacier directories should match the number of glaciers in the subset."
    except Exception as e:
        assert False, f"Initialization failed with an exception: {e}"
