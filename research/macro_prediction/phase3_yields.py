"""
Phase 3 — Yield Direction Prediction
Walk-forward logistic regression + RF on FRED yield features.

Key finding: No robust edge. Pre-COVID 70.3% (p=0.096, marginal).
Post-COVID model inverts (43.1% < majority class 52.9%).
All-period: 54.5%, McNemar p=1.000.
"""
import os
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import accuracy_score
import scipy.stats as stats

YIELD_FEATURES = [
    'DGS10', 'DGS2', 'FEDFUNDS', 'T10Y2Y', 'T10YIEM',
    'YIELD_SLOPE_CHG', 'FEDFUNDS_CHG',
    'CPIAUCSL_MOM', 'CPILFESL_MOM', 'UNRATE', 'CES0500000003_MOM', 'MICH',
    'YF_TLT_RET', 'YF_SPY_RET', 'YF_HYG_RET', 'YF_DBC_RET',
]


def wilson_ci(k, n, z=1.96):
    if n == 0:
        return 0, 0
    p = k / n
    denom = 1 + z**2 / n
    center = (p + z**2 / (2 * n)) / denom
    margin = z * np.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / denom
    return max(0, center - margin), min(1, center + margin)


def era_label(d):
    if d < pd.Timestamp('2020-03-01'):
        return 'Pre-COVID'
    if d < pd.Timestamp('2022-01-01'):
        return 'COVID'
    return 'Post-COVID'


def run_phase3(m: pd.DataFrame) -> pd.DataFrame:
    """
    Run Phase 3 yield direction walk-forward.

    Args:
        m: Feature-engineered monthly master frame with TARGET_YIELD_DIR column.

    Returns:
        DataFrame with columns: actual, naive, logit, rf, era
    """
    feats = [f for f in YIELD_FEATURES if f in m.columns]
    df = m[feats + ['TARGET_YIELD_DIR']].dropna()

    X = df[feats].values
    y = df['TARGET_YIELD_DIR'].values
    dates = df.index

    results = {'date': [], 'actual': [], 'naive': [], 'logit': [], 'rf': [], 'era': []}

    for i in range(36, len(X)):
        X_tr, y_tr = X[:i], y[:i]
        X_te = X[i:i+1]
        d = dates[i]
        naive_pred = float(y_tr.mean() > 0.5)

        sc = StandardScaler()
        X_tr_s = sc.fit_transform(X_tr)
        X_te_s = sc.transform(X_te)

        logit = LogisticRegression(C=1.0, max_iter=500, random_state=42)
        logit.fit(X_tr_s, y_tr)
        logit_pred = float(logit.predict(X_te_s)[0])

        rf = RandomForestClassifier(n_estimators=200, max_depth=3, random_state=42)
        rf.fit(X_tr, y_tr)
        rf_pred = float(rf.predict(X_te)[0])

        results['date'].append(d)
        results['actual'].append(float(y[i]))
        results['naive'].append(naive_pred)
        results['logit'].append(logit_pred)
        results['rf'].append(rf_pred)
        results['era'].append(era_label(d))

    return pd.DataFrame(results).set_index('date')


def print_results(r: pd.DataFrame):
    print(f"\n{'='*65}")
    print(f"PHASE 3 — Yield Direction Walk-Forward (n={len(r)} months)")
    print(f"{'='*65}")
    for era in ['All', 'Pre-COVID', 'COVID', 'Post-COVID']:
        sub = r if era == 'All' else r[r['era'] == era]
        if len(sub) < 5:
            continue
        n = len(sub)
        maj_acc = max(float(sub['actual'].mean()), 1 - float(sub['actual'].mean()))
        logit_acc = float(accuracy_score(sub['actual'], sub['logit']))
        lo, hi = wilson_ci(int(logit_acc * n), n)

        naive_w = (sub['actual'] != sub['naive']).values
        logit_w = (sub['actual'] != sub['logit']).values
        b = int(np.sum(naive_w & ~logit_w))
        c = int(np.sum(~naive_w & logit_w))
        if b + c > 0:
            chi2 = (abs(b - c) - 1)**2 / (b + c)
            pval = float(1 - stats.chi2.cdf(chi2, df=1))
        else:
            pval = 1.0

        sig = '✓ SIG' if pval < 0.05 else ''
        print(f"  {era} (n={n}):")
        print(f"    Majority class: {maj_acc:.1%}")
        print(f"    Logit:          {logit_acc:.1%}  CI:[{lo:.1%}–{hi:.1%}]  McNemar p={pval:.3f}  {sig}")
        print()
