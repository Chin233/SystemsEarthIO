# Independent Hansen Environmental Analysis & Raster Optimisation Engine

For Hack & Hire SystemEarth. A decision-specific geospatial processing architecture designed to reduce environmental raster storage, accelerate plot-level queries, and provide independent satellite-derived evidence for supplier due diligence verification.

## 🎯 Problem Statement

SystemEarth collects farm plot boundaries and supplier-submitted due diligence reports to evaluate sustainability and regulatory risks.

However, supplier declarations alone do not establish whether the underlying environmental observations support those declarations.

Independent geospatial analysis is needed to identify tree-cover loss and other environmental conditions affecting individual farm plots.

At the same time, environmental raster datasets can contain millions of pixels and attributes that may not all be necessary for a specific query.

Our contribution addresses two related problems:

1. **Independent Environmental Screening:** Query publicly available Hansen forest-change datasets against customer farm polygons and compare observations with supplier declarations.
2. **Decision-Specific Raster Optimisation:** Reduce the amount of environmental data stored for predefined queries while preserving their outputs.

The objective is to demonstrate more efficient environmental data processing and better-informed due diligence review, not to automatically determine EUDR compliance.

---

## ⚡ Core Optimisation & Analysis Techniques

### 1. Environmental Layer Analysis & Attribute Selection

Three Hansen Global Forest Change raster layers were obtained and cropped to the region containing 17 customer farm plots in Thailand.

| Raster Layer | Original Information | Treatment |
|---|---|---|
| `treecover2000` | Canopy-cover percentage (0–100%) in 2000 | Simplified for a fixed-threshold query |
| `lossyear` | Year of detected tree-cover loss | Preserved |
| `datamask` | Land and permanent-water classification | Preserved |

Each raster contains **1,061,333 pixels** at approximately 30 m spatial resolution.

**Layer-selection rationale:**

- Exact canopy-cover percentages are unnecessary for the specific query of whether canopy cover meets a fixed threshold.
- Loss-year information must remain available for temporal analysis.
- Land/water classification must remain available to distinguish land observations from permanent water.
- Source rasters should remain available for auditing and queries requiring information discarded by the optimized representation.

The prototype uses an illustrative 10% canopy-cover threshold. This is not a complete EUDR forest classification, and `treecover2000` is not a validated forest baseline for 31 December 2020.

### 2. Lossless Multi-Layer Bit-Packing Experiment

We initially tested combining all three raster attributes into a single `uint16` representation.

| Attribute | Values | Bits Required |
|---|---|---:|
| Loss year | 0–25 | 5 |
| Canopy-cover percentage | 0–100 | 7 |
| Land/water indicator | 1–2 | 1 |
| **Total** | | **13 bits** |

The implementation used a 16-bit integer per pixel.

All three original attributes were reconstructed exactly after decoding.

**Experimental results:**

- Original compressed raster storage: 1,031,083 bytes.
- Bit-packed compressed raster storage: 1,284,464 bytes.
- Storage increased by **24.57%**.

**Engineering finding:** Reducing the uncompressed bit depth does not guarantee better compressed storage. Combining attributes can disrupt patterns exploited by DEFLATE compression.

This approach was not selected for the final prototype.

### 3. Decision-Specific Binary Raster Encoding

Instead of preserving exact canopy-cover percentages, we investigated storing only the output of a predefined canopy-cover threshold query.

**Original representation:**

`treecover2000` stores integer canopy-cover percentages between 0 and 100.

**Optimized representation:**

```python
binary_cover = (cover >= 10).astype(np.uint8)
```

Each pixel is represented as:

| Encoded Value | Meaning |
|---|---|
| `1` | Canopy cover ≥10% in 2000 |
| `0` | Canopy cover below 10% in 2000 |

The optimized architecture retains three separate raster layers:

- `treecover_binary_10.tif`
- `lossyear_thailand.tif`
- `datamask_thailand.tif`

The loss-year and data-mask rasters remain unchanged.

**Single-layer storage results:**

| Representation | Compressed Size |
|---|---:|
| Original canopy-cover raster | 706,517 bytes |
| Binary canopy-cover raster | 98,375 bytes |
| **Storage reduction** | **86.08%** |

This transformation is decision-preserving for the fixed threshold, but is not lossless with respect to the original canopy-cover percentages.

### 4. Multi-Layer Plot Query Engine

The raster query engine processes farm polygons using GeoPandas, Rasterio and NumPy.

**Processing pipeline:**

1. Load the 17 customer farm polygons from GeoJSON.
2. Align polygon coordinates with the raster coordinate reference system.
3. Extract pixels selected by each polygon.
4. Use `datamask` to distinguish land and water pixels.
5. Calculate canopy-threshold results for sampled land pixels.
6. Identify tree-cover loss recorded during 2021–2025.
7. Return plot-level environmental summaries.

**Query outputs:**

| Output | Description |
|---|---|
| `sampled_pixels` | Number of raster pixels sampled |
| `land_pixels` | Number of sampled land pixels |
| `treecover_threshold_fraction` | Fraction of sampled land pixels meeting the illustrative 10% canopy threshold |
| `loss_after_2020` | Whether any sampled land pixel has recorded loss during 2021–2025 |
| `first_loss_year_after_2020` | Earliest recorded post-2020 loss year |
| `water_pixel_fraction` | Fraction of sampled pixels classified as permanent water |

The original and optimized query implementations use the same polygon sampling conventions and return the same output schema.

### 5. Independent Hansen Analysis & Supplier Comparison

Beyond storage optimisation, the pipeline independently analyzes tree-cover loss and compares it against supplier-submitted due diligence indications.

The supplier's CSV identifies Hansen Tree Cover Loss 2021–2023 as its spatial analysis layer.

Our implementation checks whether any sampled land pixel within each farm polygon has a recorded Hansen loss year between 2021 and 2023.

The results are joined using:

`GeoJSON.ProductionPlace` ↔ `CSV.a3_plot_id`

**Comparison results:**

| Indicator Comparison | Number of Plots |
|---|---:|
| Same binary flag | 9 |
| Different binary flag | 8 |
| **Total** | **17** |

**Example: Plot P-0001**

| Attribute | Result |
|---|---|
| Supplier-reported deforestation indication | No |
| Independent Hansen tree-cover-loss detection | Yes |
| Loss pixels (2021–2023) | 38 |
| Earliest detected post-2020 loss year | 2022 |
| Comparison outcome | Further investigation recommended |

The eight differences are not confirmed compliance discrepancies.

They may arise from different analysis thresholds, dataset versions, spatial sampling methods or the distinction between tree-cover loss and regulatory deforestation.

The comparison is intended to identify **review candidates**, not automatically override supplier declarations.

---

## 📊 Evaluation & Benchmark Summary

| Evaluation Pillar | Original Raster Architecture | Optimized Raster Architecture | Result |
|---|---|---|---|
| **Storage Footprint** | Three compressed GeoTIFFs totaling 1,031,083 bytes | Binary canopy-cover raster plus unchanged loss-year and data-mask rasters totaling 422,941 bytes | **58.98% reduction** |
| **Query Performance** | Median 60.84 ms | Median 47.11 ms | **1.29× preliminary speedup** |
| **Result Fidelity** | Reference environmental query outputs | Identical outputs across all 17 plots | **100% agreement for six defined outputs** |

### Evaluation Methodology

- The same 17 customer polygons were queried using both representations.
- All six defined environmental outputs were compared.
- Raster values were validated using exact equality checks.
- Query latency was measured over repeated local executions.

**Limitations of the benchmark:**

- The dataset covers a relatively small geographic region.
- Only 17 customer plots were evaluated.
- Repeated queries largely reflect warm-cache behavior.
- The speedup may not generalize to larger datasets or different hardware.
- Matching the six environmental outputs does not establish full EUDR decision fidelity.

---

## 🌍 Business Value for SystemEarth

### 1. Independent Evidence for Due Diligence Review

The existing dashboard retrieves supplier-submitted due diligence information.

This module adds independently calculated environmental observations, allowing reviewers to compare what suppliers reported with satellite-derived evidence.

**Business benefit:** SystemEarth can identify plots where submitted declarations and independent environmental indicators differ, supporting targeted follow-up.

### 2. More Efficient Environmental Data Storage

The optimized representation stores only the information needed for a predefined canopy-threshold query rather than retaining every original canopy-cover percentage in the fast query layer.

**Business benefit:** Reduced storage requirements for this type of repeated environmental query.

### 3. Faster Plot-Level Environmental Queries

The optimized rasters achieved a preliminary 1.29× median query speedup on the tested workload.

**Business benefit:** Potentially lower processing time for repeated plot checks, subject to validation at production scale.

### 4. Transparent, Evidence-Based Review

The dashboard presents supplier declarations, Hansen observations, detected loss-pixel counts and mitigation information together.

**Business benefit:** Reviewers can inspect the basis for a flagged difference rather than receiving an unexplained compliance verdict.

### 5. Reproducible Engineering Evaluation

The processing pipeline includes separate scripts for raster inspection, encoding experiments, query fidelity and performance benchmarking.

**Business benefit:** The representation can be tested and refined as new environmental datasets and decision requirements are introduced.

---

## 🔗 Dashboard Integration

The environmental analysis was integrated into the team's Streamlit dashboard using:

`dashboard_integrated.geojson`

The file contains 17 farm polygons and associated supplier and environmental attributes.

The dashboard's **Independent Hansen Environmental Analysis** section displays:

- Supplier-reported deforestation indication.
- Independent Hansen loss detection during 2021–2023.
- Number of sampled loss pixels.
- Agreement or difference between binary indicators.
- Additional environmental observations.
- Supplier mitigation and declared final status.

The integration was tested locally using P-0001, P-0004 and P-0016.

**Implementation note:** The dashboard currently displays precomputed results from GeoJSON. The environmental raster query engine runs separately and is not invoked live by Streamlit.

---

## ⚠️ Limitations & Future Development

The prototype demonstrates environmental data optimisation and independent screening, not complete EUDR compliance verification.

Current limitations:

1. The canopy-cover layer represents the year 2000, not the regulatory cut-off of 31 December 2020.
2. Tree-cover loss is not necessarily deforestation, because forest-to-agriculture conversion must also be considered.
3. The illustrative 10% canopy threshold does not implement the complete regulatory forest definition.
4. Protected-area and restricted-use-area layers have not yet been independently incorporated.
5. The binary canopy representation cannot reconstruct original canopy percentages.
6. The supplier comparison uses simplified indicators and may not reproduce the supplier's original analysis methodology.
7. The 17-plot benchmark does not establish production-scale performance.

Future development could incorporate a validated 2020 forest baseline, agricultural land-use conversion data, additional environmental layers and larger-scale benchmarks.

---

## Conclusion

This module extends the existing SystemEarth application in two ways:

**Environmental Data Optimisation:** Demonstrating that decision-specific raster simplification can reduce storage while preserving predefined plot-level outputs.

**Independent Environmental Screening:** Providing satellite-derived observations that can be compared with supplier-submitted due diligence information.

Together, these capabilities support more efficient geospatial analysis and more transparent, evidence-informed supplier review.