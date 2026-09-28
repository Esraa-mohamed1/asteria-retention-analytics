"""Statistical association analysis between retention outcomes and external indicators."""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy import stats

from asteria_retention.config import MIN_PAIRS_FOR_CORRELATION
from asteria_retention.schemas.panel_schema import ASSOCIATION_COLUMNS


@dataclass
class AssociationResult:
    objective_id: str
    indicator_id: str
    scope: str            # "ALL" | country ISO-2
    method: str           # "pearson" | "spearman" | "pearson_within_country"
    n: int
    r: float | None
    ci_lower: float | None
    ci_upper: float | None
    p_value: float | None
    p_bonferroni: float | None
    insufficient_n: bool
    note: str = ""
    caveat: str = field(
        default=(
            "Observational data only. Correlation does not imply causation. "
            "Confounders (sector mix, company growth phase, local labour law) "
            "are not controlled for. Repeated country-quarter measures inflate "
            "effective sample size."
        )
    )


def _fisher_ci(r: float, n: int, alpha: float = 0.05) -> tuple[float, float]:
    """95% CI for Pearson r via Fisher z-transformation."""
    if n < 4:
        return (float("nan"), float("nan"))
    z = math.atanh(r)
    se = 1.0 / math.sqrt(n - 3)
    z_crit = stats.norm.ppf(1 - alpha / 2)
    return (math.tanh(z - z_crit * se), math.tanh(z + z_crit * se))


def _correlate_pair(
    x: np.ndarray, y: np.ndarray, method: str
) -> tuple[float | None, float | None]:
    """Return (r, p) or (None, None) on degenerate input."""
    if len(x) < 2 or np.std(x) == 0 or np.std(y) == 0:
        return None, None
    if method == "spearman":
        r, p = stats.spearmanr(x, y)
    else:
        r, p = stats.pearsonr(x, y)
    return float(r), float(p)


def correlate(
    panel: pd.DataFrame,
    n_comparisons: int | None = None,
) -> pd.DataFrame:
    """Compute association statistics for every (objective, indicator, scope, method)."""
    results: list[AssociationResult] = []

    # SENIOR_HIRE_12M is always a non-finding (too few per-country cohorts)
    results.append(
        AssociationResult(
            objective_id="SENIOR_HIRE_12M",
            indicator_id="ALL",
            scope="ALL",
            method="ALL",
            n=0,
            r=None,
            ci_lower=None,
            ci_upper=None,
            p_value=None,
            p_bonferroni=None,
            insufficient_n=True,
            note=(
                "SENIOR_HIRE_12M association analysis skipped: cohorts are "
                "2-3 employees per country-quarter, well below the minimum of "
                f"{MIN_PAIRS_FOR_CORRELATION} pairs required for any correlation. "
                "This is an explicit non-finding, not a data gap."
            ),
        )
    )

    objectives = panel["objective_id"].unique() if not panel.empty else []
    indicators = panel["indicator_id"].unique() if not panel.empty else []

    all_results_for_bonferroni: list[AssociationResult] = []

    for obj_id in objectives:
        obj_panel = panel[panel["objective_id"] == obj_id].copy()

        for ind_id in indicators:
            sub = obj_panel[obj_panel["indicator_id"] == ind_id].dropna(subset=["ind_value", "value"])
            if sub.empty:
                continue

            x_all = sub["ind_value"].to_numpy(dtype=float)
            y_all = sub["value"].to_numpy(dtype=float)
            n_all = len(x_all)

            # --- pooled Pearson and Spearman ---
            for method in ("pearson", "spearman"):
                r, p = _correlate_pair(x_all, y_all, method)
                ci_low, ci_high = _fisher_ci(r, n_all) if r is not None and method == "pearson" else (None, None)
                res = AssociationResult(
                    objective_id=obj_id,
                    indicator_id=ind_id,
                    scope="ALL",
                    method=method,
                    n=n_all,
                    r=r,
                    ci_lower=ci_low,
                    ci_upper=ci_high,
                    p_value=p,
                    p_bonferroni=None,
                    insufficient_n=n_all < MIN_PAIRS_FOR_CORRELATION,
                    note="insufficient_n: non-finding" if n_all < MIN_PAIRS_FOR_CORRELATION else "",
                )
                all_results_for_bonferroni.append(res)

            # --- within-country demeaned Pearson ---
            sub2 = sub.copy()
            sub2["x_dm"] = sub2["ind_value"] - sub2.groupby("geo")["ind_value"].transform("mean")
            sub2["y_dm"] = sub2["value"] - sub2.groupby("geo")["value"].transform("mean")
            dm = sub2.dropna(subset=["x_dm", "y_dm"])
            n_groups = dm["geo"].nunique()
            n_dm = len(dm)
            df_dm = n_dm - n_groups
            if df_dm >= 2:
                x_dm = dm["x_dm"].to_numpy(dtype=float)
                y_dm = dm["y_dm"].to_numpy(dtype=float)
                r_dm, _ = _correlate_pair(x_dm, y_dm, "pearson")
                if r_dm is not None and abs(r_dm) < 1.0:
                    t_stat = r_dm * math.sqrt(df_dm / (1 - r_dm**2))
                    p_dm = float(2 * stats.t.sf(abs(t_stat), df=df_dm))
                else:
                    p_dm = None
                ci_dm = _fisher_ci(r_dm, n_dm) if r_dm is not None else (None, None)
            else:
                r_dm, p_dm = None, None
                ci_dm = (None, None)

            res_wc = AssociationResult(
                objective_id=obj_id,
                indicator_id=ind_id,
                scope="ALL",
                method="pearson_within_country",
                n=n_dm,
                r=r_dm,
                ci_lower=ci_dm[0] if ci_dm else None,
                ci_upper=ci_dm[1] if ci_dm else None,
                p_value=p_dm,
                p_bonferroni=None,
                insufficient_n=(df_dm < MIN_PAIRS_FOR_CORRELATION if df_dm >= 0 else True),
                note=f"demeaned by country; df={df_dm}; insufficient_n: non-finding"
                if df_dm < MIN_PAIRS_FOR_CORRELATION
                else f"demeaned by country; df={df_dm}",
            )
            all_results_for_bonferroni.append(res_wc)

    # Bonferroni correction
    real_tests = [r for r in all_results_for_bonferroni if not r.insufficient_n and r.p_value is not None]
    n_comp = n_comparisons if n_comparisons is not None else max(len(real_tests), 1)
    for res in all_results_for_bonferroni:
        if res.p_value is not None:
            res.p_bonferroni = min(1.0, res.p_value * n_comp)
        else:
            res.p_bonferroni = None

    all_results = results + all_results_for_bonferroni
    rows = []
    for r in all_results:
        rows.append(
            {
                "objective_id": r.objective_id,
                "indicator_id": r.indicator_id,
                "scope": r.scope,
                "method": r.method,
                "n": r.n,
                "r": r.r,
                "ci_lower": r.ci_lower,
                "ci_upper": r.ci_upper,
                "p_value": r.p_value,
                "p_bonferroni": r.p_bonferroni,
                "insufficient_n": r.insufficient_n,
                "note": r.note,
                "caveat": r.caveat,
            }
        )
    return pd.DataFrame(rows)
