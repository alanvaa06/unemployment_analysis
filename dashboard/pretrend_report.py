"""Console report for the Information event-study pre-trend / placebo test.

Fits the gap log(emp Information) - log(emp control ex-Information) on the clean
2015-2019 window (Newey-West HAC), projects it forward with a 95% prediction
band, and reports the pre-trend slope and where the observed gap leaves the band.

Run:  python -m dashboard.pretrend_report
"""
from __future__ import annotations

from dashboard.advanced import event_pretrend
from dashboard.prepare import load_observations


def main() -> None:
    obs = load_observations()
    r = event_pretrend(obs)
    lo, hi = r["slope_ci"]
    print("Prueba de tendencia previa (pre-trend / placebo) — Informacion vs control ex-Informacion")
    print(f"  Ventana de ajuste: 2015-01 a 2019-12  (n={r['n_pre']}; COVID 2020-21 excluido)")
    print(f"  Pendiente pre-trend: {r['slope_pct_yr']:+.2f} %/ano")
    print(f"    IC 95% (Newey-West, L={r['hac_lags']}): [{lo:+.2f}, {hi:+.2f}] %/ano")
    print(f"    Deriva pre-2020 significativa: {'si' if r['slope_sig'] else 'no'}")
    print(f"  Ancla: {r['anchor'].date()}")
    em = r["exit_month"]
    if em is None:
        print("  La brecha observada NO sale de la banda proyectada "
              "(consistente con tendencia previa + ciclo, no con una ruptura).")
    else:
        print(f"  La brecha observada sale por debajo de la banda en: {em.strftime('%Y-%m')}")
    print("  (Descriptivo: el test no afirma causalidad.)")


if __name__ == "__main__":
    main()
