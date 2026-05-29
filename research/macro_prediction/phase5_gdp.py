"""
Phase 5 — GDP Nowcast
Quarterly real GDP QoQ growth % predicted from monthly leading indicators
(last month of each quarter, available before GDP release).

Key finding: No robust edge.
- All-period RF RMSE 2.21% vs naive 2.09% (RF worse). DM p=0.244.
- Pre-COVID RF beats naive (0.625% vs 0.691%, corr=0.628) but n=10 too small.
- COVID quarters dominate variance (Q2 2020: -7.9%, Q3 2020: +7.8%).
- Top predictors: CLAIMS_TREND, SAHM_PROXY, PAYEMS_MOM, UNRATE, HOUST_MOM.
- Would need ISM PMI + ADP for real nowcasting edge.
"""
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_squared_error
import scipy.stats as stats

NOWCAST_FEATURES = [
    'INDPRO_MOM', 'RSAFS_MOM', 'HOUST_MOM', 'PAYEMS_MOM',
    'UNRATE', 'CPIAUCSL_MOM', 'FEDFUNDS', 'T10Y2Y',
    'YF_SPY_RET', 'YF_HYG_RET', 'CLAIMS_TREND', 'SAHM_PROXY', 'MICH',
]


def era_label(d):
    if d < pd.Timestamp('2020-03-01'):
        return 'Pre-COVID'
    if d < pd.Timestamp('2022-01-01'):
        return 'COVID'
    return 'Post-COVID'


def run_phase5(m: pd.DataFrame, fred_data: dict) -> pd.DataFrame:
    """
    Run Phase 5 GDP nowcast walk-forward.

    Args:
        m: Feature-engineered monthly master frame.
        fred_data: Dict of FRED series (needs 'GDPC1').

    Returns:
        DataFrame with columns: actual, naive, ridge, rf, era
    """
    # Build quarterly GDP growth
    gdp = fred_data['GDPC1'].copy()
    gdp.index = pd.to_datetime(gdp.index)
    gdp_q = gdp.resample('QS').last()
    gdp_q_growth = gdp_q.pct_change() * 100
    gdp_q_growth.name = 'GDP_QOQ'

    # Resample monthly features to quarterly (last month of quarter)
    feats = [f for f in NOWCAST_FEATURES if f in m.columns]
    m_q = m[feats].resample('QS').last()
    m_q.index = pd.to_datetime(m_q.index)

    df = pd.concat([m_q, gdp_q_growth], axis=1).dropna()

    X = df[feats].values
    y = df['GDP_QOQ'].values
    dates = df.index

    results = {'date': [], 'actual': [], 'naive': [], 'ridge': [], 'rf': [], 'era': []}

    for i in range(12, len(X)):
        X_tr, y_tr = X[:i], y[:i]
        X_te = X[i:i+1]
        d = dates[i]
        naive_pred = float(y_tr.mean())  # Historical mean (appropriate for mean-reverting GDP)

        sc = StandardScaler()
        X_tr_s = sc.fit_transform(X_tr)
        X_te_s = sc.transform(X_te)

        ridge = Ridge(alpha=1.0)
        ridge.fit(X_tr_s, y_tr)
        ridge_pred = float(ridge.predict(X_te_s)[0])

        rf = RandomForestRegressor(n_estimators=200, max_depth=3, random_state=42)
        rf.fit(X_tr, y_tr)
        rf_pred = float(rf.predict(X_te)[0])

        results['date'].append(d)
        results['actual'].append(float(y[i]))
        results['naive'].append(naive_pred)
        results['ridge'].append(ridge_pred)
        results['rf'].append(rf_pred)
        results['era'].append(era_label(d))

    return pd.DataFrame(results).set_index('date')


def print_results(r: pd.DataFrame):
    print(f"\n{'='*65}")
    print(f"PHASE 5 — GDP Nowcast Walk-Forward (n={len(r)} quarters)")
    print(f"{'='*65}")
    for era in ['All', 'Pre-COVID', 'COVID', 'Post-COVID']:
        sub = r if era == 'All' else r[r['era'] == era]
        if len(sub) < 4:
            continue
        n_rmse = float(np.sqrt(mean_squared_error(sub['actual'], sub['naive'])))
        r_rmse = float(np.sqrt(mean_squared_error(sub['actual'], sub['ridge'])))
        f_rmse = float(np.sqrt(mean_squared_error(sub['actual'], sub['rf'])))
        f_corr = float(np.corrcoef(sub['actual'].values, sub['rf'].values)[0, 1])

        d_arr = ((sub['actual'].values - sub['naive'].values)**2
                 - (sub['actual'].values - sub['rf'].values)**2)
        if d_arr.std(ddof=1) > 0:
            dm_stat = d_arr.mean() / (d_arr.std(ddof=1) / np.sqrt(len(d_arr)))
            dm_p = float(2 * (1 - stats.t.cdf(abs(dm_stat), df=len(d_arr) - 1)))
        else:
            dm_p = 1.0

        beat = '✓ BEATS NAIVE' if f_rmse < n_rmse else '✗'
        print(f"  {era} (n={len(sub)}):")
        print(f"    Naive  RMSE={n_rmse:.4f}%")
        print(f"    Ridge  RMSE={r_rmse:.4f}%  {'✓' if r_rmse < n_rmse else '✗'}")
        print(f"    RF     RMSE={f_rmse:.4f}%  corr={f_corr:.3f}  DM p={dm_p:.3f}  {beat}")
        print()
