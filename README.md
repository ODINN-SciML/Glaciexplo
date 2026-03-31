# Glaciexplo

This small package provides tools and methods to facilitate the selection of glaciers for modeling studies.
It focuses on location, mean slope, area, availability of thickness measurements (e.g., from GlaThiDa), and reliable surface velocity data (from Millan et al., 2022).

## Installation

It is recommended to install **Glaciexplo** in a dedicated Python environment.

For example, with `conda`:

```bash
conda create -n glaciexplo python=3.11
conda activate glaciexplo
```

Then install the package in editable mode to be able to makes changes:
```bash
pip install -e .
```
If you want the support of ipykernel to run notebook, you can install the extra dependencies with:
```bash
pip install -e '.[dev]'
```

## References

- Le Meur, E., Gagliardini, O., Zwinger, T., & Ruokolainen, J. (2004). Glacier flow modelling: A comparison of the Shallow Ice Approximation and the full-stokes solution. Comptes Rendus Physique, 5(7), 709–722.
- Millan, R., Mouginot, J., Rabatel, A., & Morlighem, M. (2022). Ice velocity and thickness of the world’s glaciers. Nature Geoscience, 15(2), 124–129.

## License

Distributed under the MIT License. See [`LICENSE`](./LICENSE) for more information.
