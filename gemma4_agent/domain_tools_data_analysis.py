"""Data Analysis (CSV/Excel) domain tool — extracted from domain_tools.py
(R2 sprint 2026-05-28).

Análisis local de CSV/XLSX via pandas + matplotlib (Agg headless). Acciones:
profile, describe, query, head, to_xlsx + 3 plot kinds. NO sale a internet.
Pandas/matplotlib son deps opcionales — el tool reporta needs_dependency si
faltan.

Funciones extraídas (8):
  data_analysis_tool             (entry, 9 acciones)
  _data_load_df                  (CSV o XLSX -> DataFrame)
  _data_csv_profile / _describe / _query / _head / _to_xlsx
  _data_plot                     (histogram / scatter / line, Agg backend)

Seguridad query (T2-data_analysis-pandas-query-eval-035):
  - Rechaza '@' (acceso a variable local) y backticks en la expresión.
  - Prefiere engine='numexpr' (restrictivo) si está instalado, fallback python.

Auto-contenido (pandas/matplotlib lazy)."""
from __future__ import annotations

import importlib.util
import time
from pathlib import Path
from typing import Any

from ._shared import _err, _ok
from .tool_result import ToolResult
from .state import AgentState


__all__ = [
    "data_analysis_tool",
    "_data_load_df",
    "_data_csv_profile",
    "_data_csv_describe",
    "_data_csv_query",
    "_data_csv_head",
    "_data_csv_to_xlsx",
    "_data_plot",
]


# R4 sprint 2026-05-28: handler migrado a ToolResult con .to_dict().
def _ok_tr(**kw):
    return ToolResult.ok_result(**kw).to_dict()


def _err_tr(msg, **kw):
    return ToolResult.err(msg, **kw).to_dict()


def data_analysis_tool(args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    """Compound tool for CSV/Excel local data analysis.

    Actions: status, csv_profile, csv_describe, csv_query, csv_head, csv_to_xlsx,
    plot_histogram, plot_scatter, plot_line. Uses pandas + matplotlib only;
    returns needs_dependency if missing.
    """
    action = str(args.get("action") or "status").casefold()
    if action == "status":
        return _ok_tr(
            pandas=importlib.util.find_spec("pandas") is not None,
            matplotlib=importlib.util.find_spec("matplotlib") is not None,
            openpyxl=importlib.util.find_spec("openpyxl") is not None,
            install_hint="python -m pip install pandas matplotlib openpyxl",
        )
    if importlib.util.find_spec("pandas") is None:
        return _err_tr(
            "pandas is not installed",
            status="needs_dependency", verified=False,
            install_hint="python -m pip install pandas matplotlib openpyxl",
        )
    if action == "csv_profile":
        return _data_csv_profile(args)
    if action == "csv_describe":
        return _data_csv_describe(args)
    if action == "csv_query":
        return _data_csv_query(args)
    if action == "csv_head":
        return _data_csv_head(args)
    if action == "csv_to_xlsx":
        return _data_csv_to_xlsx(args, state)
    if action in {"plot_histogram", "plot_scatter", "plot_line"}:
        return _data_plot(action, args, state)
    return _err_tr(
        "unknown data_analysis action", action=action,
        valid_actions=[
            "status", "csv_describe", "csv_filter", "csv_group_agg",
            "csv_plot", "csv_export", "csv_join", "json_describe",
        ],
        status="needs_user",
    )


def _data_load_df(args: dict[str, Any]):
    import pandas as pd
    path_raw = str(args.get("path") or "").strip()
    if not path_raw:
        return None, _err_tr("missing path")
    path = Path(path_raw).expanduser()
    if not path.is_file():
        return None, _err_tr("file not found", path=str(path))
    sep = str(args.get("sep") or ",")
    try:
        if path.suffix.casefold() in {".xlsx", ".xls"}:
            df = pd.read_excel(path)
        else:
            df = pd.read_csv(path, sep=sep)
    except Exception as exc:
        return None, _err_tr(f"failed to load: {exc}", path=str(path))
    return df, None


def _data_csv_profile(args: dict[str, Any]) -> dict[str, Any]:
    df, err = _data_load_df(args)
    if err or df is None:
        return err or _err_tr("dataframe missing")
    cols = []
    for col in df.columns:
        s = df[col]
        cols.append({
            "name": str(col),
            "dtype": str(s.dtype),
            "non_null": int(s.notna().sum()),
            "null": int(s.isna().sum()),
            "unique": int(s.nunique(dropna=True)),
        })
    return _ok_tr(
        path=str(args.get("path")),
        rows=int(len(df)),
        columns=int(len(df.columns)),
        column_profile=cols,
        memory_bytes=int(df.memory_usage(index=True, deep=True).sum()),
    )


def _data_csv_describe(args: dict[str, Any]) -> dict[str, Any]:
    df, err = _data_load_df(args)
    if err or df is None:
        return err or _err_tr("dataframe missing")
    desc = df.describe(include="all").fillna("").to_dict()
    return _ok_tr(path=str(args.get("path")), rows=int(len(df)), describe=desc)


def _data_csv_query(args: dict[str, Any]) -> dict[str, Any]:
    df, err = _data_load_df(args)
    if err or df is None:
        return err or _err_tr("dataframe missing")
    query = str(args.get("query") or "").strip()
    if not query:
        return _err_tr("missing query (pandas .query() expression)")
    # T2-data_analysis-pandas-query-eval-035: rechazar `@` (local var access) y
    # backticked column names (parsea con eval). Forzar engine='numexpr' si
    # disponible (más restrictivo); fallback al python engine sólo si numexpr
    # no está y la query no contiene caracteres peligrosos.
    if "@" in query or "`" in query:
        return _err_tr(
            "query contains '@' or backticks; refused for safety. Use plain column names and operators.",
            query=query,
            status="needs_user",
        )
    engine = "numexpr" if importlib.util.find_spec("numexpr") is not None else "python"
    try:
        result = df.query(query, engine=engine)
    except (ValueError, SyntaxError, KeyError, TypeError) as exc:
        return _err_tr(f"query failed: {exc}", query=query, engine=engine)
    limit = int(args.get("limit", 50))
    return _ok_tr(
        path=str(args.get("path")), query=query, engine=engine,
        matched_rows=int(len(result)),
        preview=result.head(limit).to_dict(orient="records"),
    )


def _data_csv_head(args: dict[str, Any]) -> dict[str, Any]:
    df, err = _data_load_df(args)
    if err or df is None:
        return err or _err_tr("dataframe missing")
    n = int(args.get("n", 10))
    return _ok_tr(path=str(args.get("path")), n=n, rows=df.head(n).to_dict(orient="records"))


def _data_csv_to_xlsx(args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    df, err = _data_load_df(args)
    if err or df is None:
        return err or _err_tr("dataframe missing")
    if importlib.util.find_spec("openpyxl") is None:
        return _err_tr("openpyxl is required to write .xlsx", status="needs_dependency", install_hint="python -m pip install openpyxl")
    dst_raw = str(args.get("dst") or "").strip()
    if dst_raw:
        dst = Path(dst_raw).expanduser()
    else:
        dst = state.path.parent / "data_analysis" / f"export_{int(time.time())}.xlsx"
    dst.parent.mkdir(parents=True, exist_ok=True)
    try:
        df.to_excel(dst, index=False)
    except Exception as exc:
        return _err_tr(f"to_excel failed: {exc}", dst=str(dst))
    return _ok_tr(path=str(args.get("path")), dst=str(dst), rows=int(len(df)), verified=dst.is_file())


def _data_plot(kind: str, args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    if importlib.util.find_spec("matplotlib") is None:
        return _err_tr("matplotlib is not installed", status="needs_dependency", install_hint="python -m pip install matplotlib")
    df, err = _data_load_df(args)
    if err or df is None:
        return err or _err_tr("dataframe missing")
    import matplotlib
    matplotlib.use("Agg")  # headless backend; safe even when DISPLAY exists
    import matplotlib.pyplot as plt
    dst_raw = str(args.get("dst") or "").strip()
    if dst_raw:
        dst = Path(dst_raw).expanduser()
    else:
        dst = state.path.parent / "data_analysis" / f"{kind}_{int(time.time())}.png"
    dst.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(8, 5))
    try:
        if kind == "plot_histogram":
            col = str(args.get("column") or "")
            if col not in df.columns:
                return _err_tr("column not found", column=col, available=[str(c) for c in df.columns])
            df[col].dropna().hist(ax=ax, bins=int(args.get("bins", 20)))
            ax.set_title(f"Histogram of {col}")
            ax.set_xlabel(col)
            ax.set_ylabel("count")
        elif kind == "plot_scatter":
            x = str(args.get("x") or args.get("x_col") or "")
            y = str(args.get("y") or args.get("y_col") or "")
            if x not in df.columns or y not in df.columns:
                return _err_tr("x/y column not found", x=x, y=y, available=[str(c) for c in df.columns])
            ax.scatter(df[x], df[y])
            ax.set_xlabel(x); ax.set_ylabel(y); ax.set_title(f"{y} vs {x}")
        elif kind == "plot_line":
            x = str(args.get("x") or args.get("x_col") or "")
            y = str(args.get("y") or args.get("y_col") or "")
            if x not in df.columns or y not in df.columns:
                return _err_tr("x/y column not found", x=x, y=y, available=[str(c) for c in df.columns])
            ax.plot(df[x], df[y])
            ax.set_xlabel(x); ax.set_ylabel(y); ax.set_title(f"{y} over {x}")
        fig.tight_layout()
        fig.savefig(dst, dpi=120)
    except Exception as exc:
        return _err_tr(f"plot failed: {exc}")
    finally:
        plt.close(fig)
    return _ok_tr(path=str(args.get("path")), dst=str(dst), kind=kind, verified=dst.is_file(), size=dst.stat().st_size if dst.is_file() else 0)
