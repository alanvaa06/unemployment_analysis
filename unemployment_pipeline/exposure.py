"""Load external AI-exposure indices and join them on 6-digit SOC.

Sources (downloaded by ``fetch_reference``):
- GPTs-are-GPTs (Eloundou et al.): github.com/openai/GPTs-are-GPTs data/occ_level.csv
- AIOE (Felten, Raj & Seamans): github.com/AIOE-Data/AIOE
Parsers are column-name tolerant so they survive minor upstream schema drift.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional, Sequence

import pandas as pd

from unemployment_pipeline.crosswalks import onet_to_soc6


def _find_col(df: pd.DataFrame, *needles: str) -> Optional[str]:
    for col in df.columns:
        low = str(col).lower()
        if any(n in low for n in needles):
            return col
    return None


def load_gpts(path: Path) -> pd.DataFrame:
    """Read GPTs-are-GPTs occupation exposure -> soc6 + alpha/beta/gamma (mean)."""
    df = pd.read_csv(path)
    code_col = _find_col(df, "onet", "soc", "occ")
    if code_col is None:
        raise ValueError("GPTs file: could not find occupation-code column")
    df = df.copy()
    df["soc6"] = df[code_col].map(onet_to_soc6)
    out = pd.DataFrame({"soc6": df["soc6"]})
    for name in ("alpha", "beta", "gamma"):
        col = _find_col(df, name)
        if col is not None:
            out[f"gpts_{name}"] = pd.to_numeric(df[col], errors="coerce")
    grouped = out.groupby("soc6", as_index=False).mean(numeric_only=True)
    return grouped


def _read_sheet_with(path: Path, *required: str) -> pd.DataFrame:
    """Return the first sheet whose columns satisfy all ``required`` needles."""
    xl = pd.ExcelFile(path)
    for sheet in xl.sheet_names:
        df = xl.parse(sheet)
        if all(_find_col(df, r) is not None for r in required):
            return df
    return xl.parse(xl.sheet_names[0])


def load_aioe(path: Path, langmod_path: Optional[Path] = None) -> pd.DataFrame:
    """Read AIOE appendix -> soc6 + aioe (+ aioe_langmod if available)."""
    df = _read_sheet_with(path, "soc", "aioe")
    code_col = _find_col(df, "soc")
    aioe_col = _find_col(df, "aioe")
    if code_col is None or aioe_col is None:
        raise ValueError("AIOE file: could not find SOC or AIOE column")
    out = pd.DataFrame({
        "soc6": df[code_col].map(onet_to_soc6),
        "aioe": pd.to_numeric(df[aioe_col], errors="coerce"),
    })
    if langmod_path is not None and Path(langmod_path).exists():
        lm = pd.read_excel(langmod_path)
        lm_code = _find_col(lm, "soc")
        lm_val = _find_col(lm, "aioe", "language")
        if lm_code is not None and lm_val is not None:
            lm_out = pd.DataFrame({
                "soc6": lm[lm_code].map(onet_to_soc6),
                "aioe_langmod": pd.to_numeric(lm[lm_val], errors="coerce"),
            })
            out = out.merge(lm_out, on="soc6", how="left")
    if "aioe_langmod" not in out.columns:
        out["aioe_langmod"] = pd.NA
    return out.groupby("soc6", as_index=False).first()


def load_aiie(path: Path) -> pd.DataFrame:
    """Read AIOE industry appendix -> naics (str) + aiie."""
    df = _read_sheet_with(path, "naics", "aiie")
    code_col = _find_col(df, "naics")
    aiie_col = _find_col(df, "aiie")
    if code_col is None or aiie_col is None:
        raise ValueError("AIIE file: could not find NAICS or AIIE column")
    out = pd.DataFrame({
        "naics": df[code_col].astype(str).str.replace(r"\.0$", "", regex=True),
        "aiie": pd.to_numeric(df[aiie_col], errors="coerce"),
    })
    return out.dropna(subset=["aiie"]).groupby("naics", as_index=False).first()


def build_exposure_occupation(
    soc_codes: Sequence[str],
    gpts: pd.DataFrame,
    aioe: pd.DataFrame,
) -> tuple[pd.DataFrame, list[str]]:
    """Left-join exposure scores onto the requested SOC list.

    Returns (joined, unmatched) where unmatched have no score in either source.
    """
    base = pd.DataFrame({"soc6": list(dict.fromkeys(soc_codes))})
    joined = base.merge(gpts, on="soc6", how="left").merge(aioe, on="soc6", how="left")
    score_cols = [c for c in joined.columns if c != "soc6"]
    matched_mask = joined[score_cols].notna().any(axis=1)
    unmatched = joined.loc[~matched_mask, "soc6"].tolist()
    return joined, unmatched
