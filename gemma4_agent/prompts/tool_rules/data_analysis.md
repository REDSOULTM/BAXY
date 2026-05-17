Data-analysis rule: data_analysis(...) is local CSV/XLSX analysis with pandas + matplotlib. Actions: status, csv_profile, csv_describe, csv_query, csv_head, csv_to_xlsx, plot_histogram, plot_scatter, plot_line.

csv_query uses pandas .query() expressions — not raw SQL. Plots emit PNG under the state dir; the returned path is the evidence to cite (see EVIDENCE CITATION in core.md).

Distinct from database(...) (real SQL engines) and from office(...) (Excel document creation, not analysis).
