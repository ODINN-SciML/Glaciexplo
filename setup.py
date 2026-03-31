from setuptools import setup, find_packages

setup(
    name="glaciexplo",
    version="0.1.0",
    description="Data exploration tools for glaciers",
    author="girodlis",
    python_requires=">=3.9",
    install_requires=[
        "oggm==1.6.2",
        "matplotlib==3.10.8",
        "numpy==2.4.3",
        "pandas==3.0.1",
        "geopandas",
        "xarray==2026.2.0",
        "scipy==1.17.1",
        "folium==0.20.0",
        "shapely==2.1.2",
        "salem==0.3.11",
        "scikit-learn",
        "tables",
        "rasterio"
    ],
    extras_require={
        "dev": [
            "ipykernel",
            "pytest",
        ],
    },
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    include_package_data=True,
)
