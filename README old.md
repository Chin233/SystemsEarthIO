# SystemsEarthIO: Geospatial Data Optimisation & Encoding Engine
For Hack&amp;Hire SystemsEarth. A compact, query-efficient geospatial encoding architecture designed to reproduce plot-level EUDR compliance decisions.

Google Slide: [Link](https://docs.google.com/presentation/d/1Up0p4dgxFiEKyoSYRHse_NvAEED1zXUd/edit?slide=id.p2#slide=id.p2)

## Setup Instructions
1. Clone the repository and navigate into the folder.
2. Create a virtual environment: `python -m venv venv`
3. Activate the environment:
   - Mac/Linux: `source venv/bin/activate`
   - Windows: `venv\Scripts\activate`
4. Install dependencies: `pip install -r requirements.txt`
5. Preprocess the data
   - Generate mock data: `python generate_mock_data.py`
   - Preprocess sample data: `python process_data.py`
6. Run the app: `streamlit run app.py`


## 🎯 Problem Statement

SystemEarth collects farm plot boundaries and supplier-submitted due diligence reports to evaluate sustainability and regulatory risks.

Sustainability and EUDR due diligence platforms must overlay multi-year, multi-layer geospatial datasets such as natural forest baselines (31 December 2020 cut-off), Hansen tree cover loss alerts, and protected area boundaries—against farm plot polygons. 

In the baseline workflow, evaluating a single farm plot requires parsing and joining fragmented files at runtime:
1. **Plot Geometries (`.geojson`):** Polygon boundaries for overlap analysis.
2. **Due Diligence Reports (`.csv`):** A wide, 35-column tabular file filled with repetitive text strings and administrative metadata.

Compliance decisions rarely require the entire raw dataset. They only require specific segments of decision-critical information delivered rapidly and with **100% decision fidelity**.

On top of that, supplier declarations alone do not establish whether the underlying environmental observations support those declarations.

Independent geospatial analysis is needed to identify tree-cover loss and other environmental conditions affecting individual farm plots.

As such, our solution mostly comprises of 2 parts:

1. **Independent Environmental Screening:** Query publicly available Hansen forest-change datasets against customer farm polygons and compare observations with supplier declarations.
2. **Decision-Specific Raster Optimisation:** Reduce the amount of environmental data stored for predefined queries while preserving their outputs.

## ⚡ Core Optimisation Technique for Decision-Specific Raster Optimisation

Our architecture (`process_data.py` + `query_engine.py`) compresses the multi-file baseline into a unified, bitmask-encoded columnar store through four primary optimisations:

### 1. Regulatory Layer Analysis & Schema Pruning
Guided by EUDR compliance rules, we audited all 35 columns of the raw due diligence dataset and pruned **29 non-essential administrative columns** (e.g., factory IDs, lot numbers, harvest dates, dry weight quotas, and verbose mitigation links). We retained only the 6 core attributes required to verify plot-level compliance:
* **Plot Identifier:** `a3_plot_id` (joined against GeoJSON `ProductionPlace`)
* **Plot Area (ha):** `a7_size_of_plot_ha`
* **Spatial Deforestation Alert (Hansen 2021–2023):** `c2_deforestation_spatial_analysis_result`
* **Final Deforestation Status:** `c5_deforestation_final_status`
* **Strict Protected Area Overlap:** `d1_strict_protected_area_spatial_analysis_result`
* **Overall EUDR Compliance Status:** `i1_eudr_status`

### 2. 1-Byte Bitmask Encoding (`uint8`)
Instead of storing repetitive string literals (such as `"a. No overlap with strict PA"` or `"b. Indication of deforestation"`) across thousands of rows, we pack the 4 binary compliance layers into a single **8-bit unsigned integer (`uint8`)** column named `compliance_bitmask`:

| Bit Position | Binary Value | Layer / Attribute | `1` (True) | `0` (False) |
| :--- | :---: | :--- | :--- | :--- |
| **Bit 0** | `1` (`2^0`) | `i1_eudr_status` | Compliant (`a.`) | Non-Compliant (`b.`) |
| **Bit 1** | `2` (`2^1`) | `c5_deforestation_final_status` | Deforestation-Free (`a.`) | Flagged (`b.`) |
| **Bit 2** | `4` (`2^2`) | `d1_strict_protected_area...` | No Strict PA Overlap (`a.`) | Overlap Detected (`b.`) |
| **Bit 3** | `8` (`2^3`) | `c2_deforestation_spatial...` | Spatial Alert Detected (`b.`) | No Indication (`a.`) |

* **Example:** A compliant plot with no deforestation alerts and no protected area overlap encodes all four layers into the integer **`7`** (`1 + 2 + 4 + 0`). A plot that triggered a Hansen spatial alert but passed final compliance after on-site mitigation encodes as **`15`** (`1 + 2 + 4 + 8`).
* **Zero-Cost Decoding:** At query time, bitwise `AND` operations (`bitmask & 1`, `bitmask & 8`, etc.) reconstruct the exact compliance outputs in nanoseconds.

### 3. Pre-Joined GeoParquet & Zstandard (`zstd`) Compression
* **Eliminating Runtime Joins:** The GeoJSON polygon layer and pruned CSV attributes are pre-merged during ingestion into a single **4-column dataset** (`a3_plot_id`, `a7_size_of_plot_ha`, `compliance_bitmask`, `geometry`).
* **Data Type Downcasting:** Plot area (`a7_size_of_plot_ha`) is downcast from 64-bit float (`float64`) to 32-bit float (`float32`), cutting numeric column memory in half while preserving hectare precision.
* **WKB Geometry & Zstandard Compression:** Polygon coordinates are serialized into compact Well-Known Binary (WKB) and written to disk using `compression="zstd"` with `index=False` to strip Pandas index bloat.

### 4. Persistent In-Memory OLAP Execution (DuckDB)
* **Zero-Boot Query Path:** Rather than instantiating a database connection or loading C++ spatial extensions on every query (which adds ~90 ms of overhead), `query_engine.py` maintains a persistent in-memory DuckDB instance (`CON = duckdb.connect(database=":memory:")`).
* **Predicate Pushdown:** DuckDB queries `optimized_plots.parquet` directly using vectorized SQL filtering (`WHERE a3_plot_id = ? LIMIT 1`), reading only the required byte ranges.

---

## 📊 Evaluation & Benchmark Summary

| Evaluation Pillar | Raw Baseline (`CSV` + `GeoJSON`) | Optimized Architecture (`Bitmask GeoParquet` + `DuckDB`) | Impact |
| :--- | :--- | :--- | :--- |
| **Storage Footprint** | Disjointed files (`18.81 KB` for 17 sample plots; 35 CSV columns + raw text GeoJSON) | Single `zstd` GeoParquet file (4 columns, 1-byte bitmask, WKB geometry) | **>32% reduction** on tiny samples; scales to **80%+ reduction** on multi-megabyte shipments |
| **Query Performance** | `~14 ms – 55 ms` (requires full file parsing & runtime DataFrame merge) | `~1 ms – 4 ms` (persistent DuckDB direct columnar lookup + bitwise decode) | **10x – 30x faster** single-plot retrieval |
| **Result Fidelity** | Baseline reference outputs | Bitwise-decoded outputs verified against raw layers across all 17 plots (80.5 ha) | **100% Decision Fidelity** across all compliance checks |

---