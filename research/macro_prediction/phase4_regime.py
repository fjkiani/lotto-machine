"""
Phase 4 — Equity Regime Prediction
Walk-forward RF (balanced) on VIX + Sahm proxy + yield slope + macro features.

Key finding: RF 45.7% vs majority-class 60.6%.
McNemar p=0.006 — RF is significantly WORSE than naive (b=4 gains, c=18 losses).
Balanced class_weight backfires on UPTREND-dominated data (57.7% UPTREND).
DOWNTREND recall=4%. Verdict: NO EDGE, model actively harmful.

NOTE: This is monthly macro → next-month SPY regime.
Do NOT conflate with _compute_regime() in main.py (intraday, same-day).
"""
import numpy as np
import pandas as pd
from collections import Counter
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import accuracy_score, classification_report
import scipy.stats as stats

REGIME_FEATURES = [
    'UNRATE', 'SAHM_PROXY', 'CLAIMS_TREND',
    'CPIAUCSL_MOM', 'CPILFESL_MOM', 'CPI_MOM3',
    'FEDFUNDS', 'T10Y2Y', 'YIELD_SLOPE_CHG', 'T10YIEM',
    'YF_VIX', 'YF_VIX_RET',
    'YF_SPY_RET', 'YF_IWM_RET', 'YF_QQQ_RET',
    'YF_TLT_RET', 'YF_HYG_RET', 'YF_DBC_RET',
]


def era_label(d):
    if d < pd.Timestamp('2020-03-01'):
        return 'Pre-COVID'
    if d < pd.Timestamp('2022-01-01'):
        return 'COVID'
    return 'Post-COVID'


def run_phase4(m: pd.DataFrame) -> pd.DataFrame:
    """
    Run Phase 4 equity regime walk-forward.

    Args:
        m: Feature-engineered monthly master frame with TARGET_REGIME column.

    Returns:
        DataFrame with columns: actual, naive, rf, era
    """
    feats = [f for f in REGIME_FEATURES if f in m.columns]
    df = m[feats + ['TARGET_REGIME']].dropna()
    df = df[df['TARGET_REGIME'].notna()]

    le = LabelEncoder()
    y = le.fit_transform(df['TARGET_REGIME'].astype(str))
    X = df[feats].values
    dates = df.index

    results = {'date': [], 'actual': [], 'naive': [], 'rf': [], 'era': []}

    for i in range(36, len(X)):
        X_tr, y_tr = X[:i], y[:i]
        X_te = X[i:i+1]
        d = dates[i]
        naive_pred = Counter(y_tr).most_common(1)[0][0]

        rf = RandomForestClassifier(
            n_estimators=200, max_depth=4, random_state=42, class_weight='balanced'
        )
        rf.fit(X_tr, y_tr)
        rf_pred = int(rf.predict(X_te)[0])

        results['date'].append(d)
        results['actual'].append(int(y[i]))
        results['naive'].append(naive_pred)
        results['rf'].append(rf_pred)
        results['era'].append(era_label(d))

    r = pd.DataFrame(results).set_index('date')
    r.attrs['classes'] = le.classes_
    return r


def print_results(r: pd.DataFrame):
    classes = r.attrs.get('classes', ['CHOPPY', 'DOWNTREND', 'UPTREND'])
    print(f"\n{'='*65}")
    print(f"PHASE 4 — Equity Regime Walk-Forward (n={len(r)} months)")
    print(f"{'='*65}")
    for era in ['All', 'Pre-COVID', 'COVID', 'Post-COVID']:
        sub = r if era == 'All' else r[r['era'] == era]
        if len(sub) < 5:
            continue
        n = len(sub)
        maj_acc = max(Counter(sub['actual'].tolist()).values()) / n
        naive_acc = float(accuracy_score(sub['actual'], sub['naive']))
        rf_acc = float(accuracy_score(sub['actual'], sub['rf']))

        naive_w = (sub['actual'] != sub['naive']).values
        rf_w = (sub['actual'] != sub['rf']).values
        b = int(np.sum(naive_w & ~rf_w))
        c = int(np.sum(~naive_w & rf_w))
        if b + c > 0:
            chi2 = (abs(b - c) - 1)**2 / (b + c)
            pval = float(1 - stats.chi2.cdf(chi2, df=1))
        else:
            pval = 1.0

        direction = '✓ BETTER' if rf_acc > naive_acc else '✗ WORSE'
        sig = f'p={pval:.3f}' + (' ✓ SIG' if pval < 0.05 else '')
        print(f"  {era} (n={n}):")
        print(f"    Majority class: {maj_acc:.1%}")
        print(f"    Naive:          {naive_acc:.1%}")
        print(f"    RF (balanced):  {rf_acc:.1%}  {direction}  McNemar {sig}")
        print()

    print("Classification report (All periods):")
    print(classification_report(r['actual'], r['rf'],
                                 target_names=classes, zero_division=0))
