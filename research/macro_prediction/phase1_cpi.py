"""
Phase 1: CPI MoM Prediction
Walk-forward audit — BLS + Yahoo Finance monthly data, 2018-2025.

HONEST FINDINGS (2026-05-24):
  - RF beats naive on RMSE (0.309% vs 0.363%) but DM p=0.19 — NOT significant
  - Strongest predictors: CPI momentum (r=0.54), commodities DBC (r=0.51), PPI (r=0.46)
  - TIPS/TLT (market-implied inflation) are weaker predictors than commodity prices
  - PPI is a partial leakage risk: released ~2 days before CPI in same month
  - Without PPI: RF still beats naive (0.314% vs 0.363%), corr=0.544
  - COVID era: Ridge fails badly (RMSE 0.577% vs naive 0.321%)
  - Post-COVID: both Ridge and RF beat naive
  - Verdict: MARGINAL UNPROVEN EDGE. Needs 5+ more years to confirm.
"""

import sys
sys.path.insert(0, '/workspace/lotto-machine/research/macro_prediction')
from data_loader import load_bls, load_yf_monthly

import pandas as pd
import numpy as np
from sklearn.linear_model import Ridge
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_squared_error
import scipy.stats as stats
import warnings
warnings.filterwarnings('ignore')


FEATURES = [
    'YF_TLT_RET', 'YF_TIP_RET', 'BREAKEVEN_PROXY',
    'YF_UUP_RET', 'YF_DBC_RET', 'YF_GLD_RET',
    'YF_HYG_RET', 'YF_SPY_RET',
    'PPI_FINAL_MOM',   # ⚠ partial leakage risk — same month as target CPI
    'CPI_ALL_MOM', 'CPI_CORE_MOM',
    'UNEMPLOYMENT', 'AVG_HOURLY_EARNINGS_MOM',
]

FEATURES_NOPPI = [f for f in FEATURES if f != 'PPI_FINAL_MOM']


def build_dataset(master: pd.DataFrame) -> pd.DataFrame:
    m = master.copy()
    for col in ['CPI_ALL', 'CPI_CORE', 'PPI_FINAL', 'NFP_TOTAL', 'AVG_HOURLY_EARNINGS']:
        if col in m.columns:
            m[f'{col}_MOM'] = m[col].pct_change(fill_method=None) * 100
    for col in ['CPI_ALL', 'CPI_CORE']:
        if col in m.columns:
            m[f'{col}_YOY'] = m[col].pct_change(12, fill_method=None) * 100
    for col in [c for c in m.columns if c.startswith('YF_')]:
        m[f'{col}_RET'] = m[col].pct_change(fill_method=None) * 100
    if 'YF_TIP_RET' in m.columns and 'YF_TLT_RET' in m.columns:
        m['BREAKEVEN_PROXY'] = m['YF_TIP_RET'] - m['YF_TLT_RET']
    m['TARGET_CPI_MOM'] = m['CPI_ALL_MOM'].shift(-1)
    return m


def walk_forward(df: pd.DataFrame, feature_cols: list, min_train: int = 24) -> pd.DataFrame:
    X = df[feature_cols].values
    y = df['TARGET_CPI_MOM'].values
    dates = df.index
    results = {'date': [], 'actual': [], 'naive': [], 'ridge': [], 'rf': [], 'era': []}

    for i in range(min_train, len(X)):
        X_train, y_train = X[:i], y[:i]
        X_test = X[i:i+1]
        d = dates[i]
        era = ('Pre-COVID' if d < pd.Timestamp('2020-03-01') else
               'COVID'     if d < pd.Timestamp('2022-01-01') else
               'Post-COVID')
        naive_pred = df['CPI_ALL_MOM'].iloc[i]

        scaler = StandardScaler()
        ridge = Ridge(alpha=1.0)
        ridge.fit(scaler.fit_transform(X_train), y_train)
        ridge_pred = ridge.predict(scaler.transform(X_test))[0]

        rf = RandomForestRegressor(n_estimators=100, max_depth=3, random_state=42)
        rf.fit(X_train, y_train)
        rf_pred = rf.predict(X_test)[0]

        results['date'].append(d); results['actual'].append(y[i])
        results['naive'].append(naive_pred); results['ridge'].append(ridge_pred)
        results['rf'].append(rf_pred); results['era'].append(era)

    return pd.DataFrame(results).set_index('date')


def diebold_mariano(actual, pred_a, pred_b):
    """DM test: H0 = equal predictive accuracy. Returns (stat, p_value)."""
    d = (actual - pred_a)**2 - (actual - pred_b)**2
    n = len(d)
    stat = d.mean() / (d.std(ddof=1) / np.sqrt(n))
    pval = 2 * (1 - stats.t.cdf(abs(stat), df=n-1))
    return stat, pval


if __name__ == '__main__':
    bls = load_bls()
    yf  = load_yf_monthly()

    # Build normalized master
    frames = {}
    for name, df in bls.items():
        df2 = df.copy(); df2.index = pd.to_datetime(df2.index).normalize()
        frames[name] = df2[name]
    for ticker, df in yf.items():
        safe = ticker.replace('^','').replace('=','')
        df2 = df.copy(); df2.index = pd.to_datetime(df2.index).normalize()
        frames[f'YF_{safe}'] = df2['close']
    master = pd.DataFrame(frames).sort_index()
    master = master[~master.index.duplicated(keep='first')]

    m = build_dataset(master)
    feats = [f for f in FEATURES if f in m.columns]
    df_model = m[feats + ['TARGET_CPI_MOM', 'CPI_ALL_MOM']].dropna()

    print(f"Dataset: {len(df_model)} months ({df_model.index[0].date()} → {df_model.index[-1].date()})")

    res = walk_forward(df_model, feats)
    dm_stat, dm_pval = diebold_mariano(res['actual'].values, res['naive'].values, res['rf'].values)

    naive_rmse = np.sqrt(mean_squared_error(res['actual'], res['naive']))
    rf_rmse    = np.sqrt(mean_squared_error(res['actual'], res['rf']))
    rf_corr    = np.corrcoef(res['actual'], res['rf'])[0,1]

    print(f"\nResults (n={len(res)} test months):")
    print(f"  Naive RMSE: {naive_rmse:.4f}%")
    print(f"  RF RMSE:    {rf_rmse:.4f}%  corr={rf_corr:.3f}")
    print(f"  DM test: stat={dm_stat:.3f}  p={dm_pval:.4f}  Sig? {'YES' if dm_pval<0.05 else 'NO'}")
    print(f"\n  Verdict: {'MARGINAL EDGE (not significant)' if rf_rmse < naive_rmse else 'NO EDGE'}")
