# SystemsEarthIO: Geospatial Optimisation & Environmental Screening

For Hack & Hire SystemEarth. A decision-specific geospatial processing architecture designed to reduce environmental raster storage, accelerate plot-level queries, and provide independent satellite-derived evidence for supplier due diligence verification.

Google Slide: [Link](https://docs.google.com/presentation/d/1Up0p4dgxFiEKyoSYRHse_NvAEED1zXUd/edit?slide=id.p2#slide=id.p2)

## Architecture

The Streamlit dashboard brings together two complementary pipelines:

1. **Supplier records:** CSV + farm GeoJSON → `process_data.py` → `optimized_plots.parquet` → DuckDB queries in `query_engine.py`.
2. **Environmental observations:** Hansen rasters + farm polygons → separate offline analysis → `dashboard_integrated.geojson` → the dashboard's Hansen section.

Selecting a plot runs the supplier baseline and optimised queries, then displays precomputed Hansen results for the same plot ID. Streamlit does not run the raster analysis live. The existing map colours and benchmark cards use the supplier pipeline.

## Supplier-record optimisation

`process_data.py` joins `GeoJSON.ProductionPlace` to `CSV.a3_plot_id`, retaining six of the CSV's 35 attributes for the selected outputs: plot ID, area and four status fields. The other 29 attributes are excluded from this compact representation, not declared unnecessary for all due diligence.

The four statuses are packed into one `uint8` column:

| Bit value | Source field | Meaning when set |
|---|---|---|
| `1` | `i1_eudr_status` | Supplier declares compliant |
| `2` | `c5_deforestation_final_status` | Supplier declares deforestation-free |
| `4` | `d1_strict_protected_area_spatial_analysis_result` | Supplier reports no strict protected-area overlap |
| `8` | `c2_deforestation_spatial_analysis_result` | Supplier reports a spatial deforestation indication |

For this sample, `7` represents the first three flags; `15` additionally includes a spatial alert. Bitwise AND operations reconstruct the selected statuses.

The output contains four columns: `a3_plot_id`, `a7_size_of_plot_ha`, `compliance_bitmask` and `geometry`. Areas use `float32`; geometry uses WKB in GeoParquet. Zstandard compression and `index=False` reduce storage. A persistent DuckDB connection queries the Parquet file without repeating the CSV/GeoJSON join.

This preserves the selected categorical outputs and the sample's areas rounded to two decimals, rather than every original field or full numeric precision.

## Hansen analysis and raster optimisation

The separate raster workflow uses `treecover2000`, `lossyear` and `datamask`. It samples farm polygons to calculate six outputs: sampled pixels, land pixels, canopy-threshold fraction, post-2020 loss flag, earliest post-2020 loss year and water fraction.

The selected optimisation replaces exact canopy percentages with:

```python
binary_cover = (cover >= 10).astype(np.uint8)
```

The binary canopy raster preserves the fixed ≥10% query but cannot recover original percentages or support arbitrary new thresholds. It uses a byte per pixel before file compression. Loss-year and land/water rasters remain unchanged. An earlier three-layer `uint16` packing experiment increased compressed storage by 24.57% and was rejected.

Supplier comparison uses **2021–2023** loss; additional environmental observations use **2021–2025**. These time windows must remain distinct.

`dashboard_integrated.geojson` stores the resulting observations and supplier details as **plain GeoJSON**. It has no compliance bitmask and is not processed by the existing Parquet optimiser. Its precomputed results are cached by Streamlit. Compressing this additional dashboard dataset would require extending the ingestion and query code while retaining both sources' meanings.

## Validation and benchmark scope

Checks against the supplied files confirmed:

- All 17 plot IDs, geometries, areas and copied supplier details agree across the source and integrated files.
- The actual pandas bitmask expression and decoding functions reproduce all five supplier outputs for all 17 plots: twelve masks are `7`, five are `15`.
- All Hansen properties required by the dashboard exist; stored flags, counts, fractions, years and comparison labels are internally consistent.
- **9 plots have matching indicators; 8 differ:** 3 have Hansen loss without a supplier indication, and 5 have a supplier indication without Hansen loss in 2021–2023. These are review candidates, not confirmed compliance violations.

Earlier project measurements are retained below as **reported benchmarks, not rerun measurements**:

| Pipeline | Reported storage result | Reported query result |
|---|---|---|
| Supplier CSV + GeoJSON → GeoParquet | >32% reduction on the sample | 10–30× faster retrieval |
| Three original → optimised rasters | 1,031,083 → 422,941 bytes; 58.98% reduction | Median 60.84 → 47.11 ms; 1.29× faster |

The canopy layer alone reportedly shrank by 86.08%. Raster testing reportedly matched all six outputs across 17 plots. The raster files and processing scripts are absent from this supplied snapshot, so those claims cannot be reproduced from the integrated GeoJSON. Parquet compression and DuckDB timings were also not rerun in this review.

The integrated GeoJSON is 16,817 bytes of additional dashboard data. Supplier benchmark cards exclude it and the rasters; neither pipeline's percentage describes total application storage. Small, warm-cache benchmarks do not establish production-scale performance.

## Setup Instructions
1. Clone the repository and navigate into the folder.
2. Create a virtual environment: `python -m venv venv`
3. Activate the environment:
   - Mac/Linux: `source venv/bin/activate`
   - Windows: `venv\Scripts\activate`
4. Install dependencies: `pip install -r requirements.txt`
5. Preprocess the data
   - Generate mock data: `python generate_mock_data.py`
   - Preprocess sample data: `python process_data.py`. Ensure csv and geojson file are in `source/`.

   Preprocessing creates `optimized_plots.parquet`. Recomputing Hansen observations additionally requires the separate raster scripts, source rasters and their dependencies.

6. Run the app: `streamlit run app.py`


## Limitations

The year-2000 canopy layer and illustrative threshold are not a validated 2020 forest baseline. Tree-cover loss alone is not a deforestation determination. The independent module does not analyse protected-area boundaries. Preserve source data for audit and broader queries.

Two dashboard presentation issues remain: the sidebar says 30 excluded CSV columns instead of 29, and individual fidelity cells are hardcoded as “Match” although the overall comparison is calculated.
