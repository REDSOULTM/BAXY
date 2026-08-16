Data-analysis rule: data_analysis(...) is local CSV/XLSX analysis with pandas + matplotlib. Actions: status, csv_profile, csv_describe, csv_query, csv_head, csv_to_xlsx, plot_histogram, plot_scatter, plot_line.

csv_query uses pandas .query() expressions — not raw SQL. Plots emit PNG under the state dir; the returned path is the evidence to cite (see EVIDENCE CITATION in core.md).

Distinct from database(...) (real SQL engines) and from office(...) (Excel document creation, not analysis).

USE THIS, NOT filesystem.read, for ANY request about the DATA in a .csv/.xlsx file — including generic verbs ("analyze / look at / summarize / what's in / how many / total / average this file"). filesystem.read returns raw bytes with NO computation; data_analysis runs real pandas: csv_query for filters/aggregates, csv_describe for stats, csv_profile for an overview.
