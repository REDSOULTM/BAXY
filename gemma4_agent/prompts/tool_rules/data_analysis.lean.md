Data-analysis rule: data_analysis(...) = local CSV/XLSX analysis with pandas + matplotlib. Actions: status, csv_profile, csv_describe, csv_query, csv_head, csv_to_xlsx, plot_histogram, plot_scatter, plot_line.

- csv_query uses pandas .query() expressions — NOT raw SQL.
- Plots emit PNG under the state dir; returned path = evidence to cite (see EVIDENCE CITATION in core.md).
- Distinct from database(...) (real SQL engines) and office(...) (Excel doc creation, not analysis).

USE THIS, NOT filesystem.read, for ANY request about the DATA in a .csv/.xlsx — including generic verbs ("analyze / look at / summarize / what's in / how many / total / average this file"). filesystem.read returns raw bytes with NO computation; data_analysis runs real pandas:
- filters/aggregates -> csv_query
- stats -> csv_describe
- overview -> csv_profile
