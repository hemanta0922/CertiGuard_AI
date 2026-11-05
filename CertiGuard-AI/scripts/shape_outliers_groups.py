"""
Experiment 7 - Shape of data: five-number summary, skewness, kurtosis, box plots,
               outliers (1.5 x IQR rule) and comparison of groups.

Needs:  pip install pandas numpy matplotlib
Input:  data/generated/certificate_dataset.csv (run the generator first)
Output: console report and files in outputs/experiment7/
"""
import textwrap
import warnings
from pathlib import Path
warnings.filterwarnings("ignore")
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# ============================== SETTINGS (edit these) ==============================
ROOT       = Path(__file__).resolve().parents[1]
CSV_PATH   = ROOT / "data" / "generated" / "certificate_dataset.csv"
OUTPUT_DIR = ROOT / "outputs" / "experiment7"
REF_DATE   = pd.Timestamp("2026-11-05")          # fixed reference date used by the synthetic generator
VARIABLES  = ["days_to_expiry", "days_since_issue"]   # numeric variables to study
MAIN_VAR   = "days_to_expiry"                    # variable used for the group comparison
GROUPS     = ["ground_truth", "institution_type", "qualification_level"]   # grouping columns
SEED       = 42
# ===================================================================================
def line(t): print("\n" + "=" * 76 + f"\n{t}\n" + "=" * 76)

if not CSV_PATH.is_file():
    raise FileNotFoundError(f"Dataset not found: {CSV_PATH}. Run scripts/generate_certificate_dataset.py first.")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
raw = pd.read_csv(CSV_PATH)
# days_since_issue: a second continuous variable derived from issue_date (invalid dates become missing)
raw["days_since_issue"] = (REF_DATE - pd.to_datetime(raw["issue_date"], errors="coerce")).dt.days
print(f"Rows: {len(raw)}   Columns: {raw.shape[1]}")
print("Missing values:", {c: int(raw[c].isna().sum()) for c in VARIABLES})

# ---------------------------------------------------------------- helper functions
def five_number(v):
    """minimum, Q1, median, Q3, maximum (linear-interpolation quartiles, the pandas/NumPy default)"""
    return v.min(), v.quantile(.25), v.median(), v.quantile(.75), v.max()

def skew_manual(v):
    """moment coefficient g1 = m3 / m2^1.5   (population form)"""
    d = v - v.mean(); return (d ** 3).mean() / (d ** 2).mean() ** 1.5

def kurt_manual(v):
    """excess kurtosis g2 = m4 / m2^2 - 3   (population form; a normal curve gives 0)"""
    d = v - v.mean(); return (d ** 4).mean() / (d ** 2).mean() ** 2 - 3

def fences(v, k=1.5):
    q1, q3 = v.quantile(.25), v.quantile(.75); iqr = q3 - q1
    return q1 - k * iqr, q3 + k * iqr

def describe_shape(sk, ku):
    s = "roughly symmetric" if abs(sk) < 0.5 else ("moderately " if abs(sk) < 1 else "strongly ") + ("left-skewed" if sk < 0 else "right-skewed")
    k = "normal-like tails" if abs(ku) < 0.5 else ("heavy tails (peaked)" if ku > 0 else "light tails (flat)")
    return s + ", " + k

# ------------------------------------------------ PART 1: five-number summary + shape
line("PART 1: FIVE-NUMBER SUMMARY, SKEWNESS AND KURTOSIS")
rows = []
for c in VARIABLES:
    v = raw[c].dropna()
    mn, q1, md, q3, mx = five_number(v)
    rows.append([c, len(v), mn, q1, md, q3, mx, q3 - q1, v.mean(), v.std(), v.skew(), skew_manual(v), v.kurt(), kurt_manual(v)])
F = pd.DataFrame(rows, columns=["Variable", "n", "Min", "Q1", "Median", "Q3", "Max", "IQR", "Mean", "SD",
                                "Skew (adjusted)", "Skew (moment)", "Excess kurt (adjusted)", "Excess kurt (moment)"])
print(F.round(3).to_string(index=False)); F.round(4).to_csv(OUTPUT_DIR / "five_number_summary.csv", index=False)
print()
for _, r in F.iterrows():
    print(f"{r['Variable']}: {describe_shape(r['Skew (adjusted)'], r['Excess kurt (adjusted)'])}")
print("\nHow to read the numbers:")
print("  Skewness  < 0 : long tail on the LEFT (mean < median).  > 0 : long tail on the RIGHT (mean > median).")
print("  Excess kurtosis > 0 : heavier tails / sharper peak than a normal curve.  < 0 : lighter tails / flatter.")
print("  'adjusted' is the sample version used by pandas; 'moment' is the plain population formula. They agree closely for large n.")

line("DATA CHECK: REPEATED VALUES (a histogram spike can distort shape measures)")
vc = raw["days_to_expiry"].value_counts()
print("Most frequent days_to_expiry values:", {int(k): int(v) for k, v in vc.head(4).items()})
n0 = int((raw["days_since_issue"] == 0).sum())
print(f"Certificates issued exactly on the reference date (days_since_issue = 0): {n0} of {int(raw['days_since_issue'].notna().sum())} ({n0 / raw['days_since_issue'].notna().sum():.1%})")
print("These all have days_to_expiry = validity period (731, 1096 or 1461 days). This spike comes from how the synthetic data was")
print("generated (dates after the reference date were set to the reference date), not from real-world behaviour.")

line("REFERENCE SHAPES (to calibrate the numbers; 20000 simulated values each)")
rng = np.random.default_rng(SEED)
ref = {"Normal": rng.normal(0, 1, 20000), "Uniform": rng.uniform(0, 1, 20000),
       "Exponential (right-skewed)": rng.exponential(1, 20000), "Student t, 4 df (heavy tails)": rng.standard_t(4, 20000)}
R = pd.DataFrame([[k, pd.Series(a).skew(), pd.Series(a).kurt()] for k, a in ref.items()], columns=["Shape", "Skewness", "Excess kurtosis"])
print(R.round(2).to_string(index=False))

# ------------------------------------------------ PART 2: outliers
line("PART 2: OUTLIERS BY THE 1.5 x IQR RULE")
out_rows, all_out = [], []
for c in VARIABLES:
    v = raw[c].dropna()
    lo, hi = fences(v); lo3, hi3 = fences(v, 3)
    low, high = v[v < lo], v[v > hi]
    extreme = v[(v < lo3) | (v > hi3)]
    out_rows.append([c, len(v), lo, hi, len(low), len(high), len(low) + len(high), len(extreme)])
    for idx in v[(v < lo) | (v > hi)].index: all_out.append([c, raw.loc[idx, "record_id"], raw.loc[idx, c], raw.loc[idx, "ground_truth"], raw.loc[idx, "scenario"]])
OT = pd.DataFrame(out_rows, columns=["Variable", "n", "Lower fence", "Upper fence", "Low outliers", "High outliers", "Total outliers", "Extreme (3 x IQR)"])
print(OT.round(1).to_string(index=False))
OL = pd.DataFrame(all_out, columns=["Variable", "record_id", "Value", "ground_truth", "scenario"]).sort_values(["Variable", "Value"])
OL.to_csv(OUTPUT_DIR / "outliers.csv", index=False)
print("\nOutlier records (days_to_expiry):")
print(OL[OL.Variable == MAIN_VAR].to_string(index=False))
v = raw[MAIN_VAR].dropna(); lo, hi = fences(v)
without = v[(v >= lo) & (v <= hi)]
print(f"\nEffect on summaries of {MAIN_VAR}: with outliers mean = {v.mean():.1f}, median = {v.median():.1f}, SD = {v.std():.1f}, skew = {v.skew():.2f}")
print(f"                              without outliers mean = {without.mean():.1f}, median = {without.median():.1f}, SD = {without.std():.1f}, skew = {without.skew():.2f}")
print("The rule only FLAGS unusual values. Whether to remove them depends on why they are unusual.")

# ------------------------------------------------ PART 3: compare groups
line(f"PART 3: COMPARING GROUPS ON {MAIN_VAR}")
gs = []
for g in GROUPS:
    for name, d in raw.groupby(g):
        x = d[MAIN_VAR].dropna()
        if len(x) < 3: continue
        mn, q1, md, q3, mx = five_number(x); l, h = fences(x)
        gs.append([g, name, len(x), mn, q1, md, q3, mx, q3 - q1, x.mean(), x.std(), x.skew(), x.kurt(), int(((x < l) | (x > h)).sum())])
GS = pd.DataFrame(gs, columns=["Grouping", "Group", "n", "Min", "Q1", "Median", "Q3", "Max", "IQR", "Mean", "SD", "Skew", "Excess kurt", "Outliers (within group)"])
for g in GROUPS:
    print(f"\n--- by {g}"); print(GS[GS.Grouping == g].drop(columns="Grouping").round(1).to_string(index=False))
GS.round(3).to_csv(OUTPUT_DIR / "group_summary.csv", index=False)
print("\nHow to compare: look at the MEDIANS first, then the IQRs (spread) and the box overlap. If the medians differ by")
print("less than the IQR and the boxes overlap heavily, the groups are similar; if the boxes barely overlap, they differ.")
sub = GS[GS.Grouping == "institution_type"]
gap = sub.Median.max() - sub.Median.min(); ratio = gap / sub.IQR.mean()
verdict = "a noticeable difference" if ratio > 0.4 else "a small difference"
print(f"\nInstitution types: medians range {sub.Median.min():.0f} to {sub.Median.max():.0f} days (gap {gap:.0f}), the average IQR is {sub.IQR.mean():.0f} days,")
print(f"so the gap is {ratio:.2f} x IQR -> {verdict}. Highest median: {sub.loc[sub.Median.idxmax(), 'Group']}.")
print("Note: institution_type and qualification_level are nested here (University = Degree, Training Centre = Skill Certificate),")
print("so their box plots describe largely the same certificates.")
print("Outliers measured against the WHOLE data can be perfectly normal inside their own group:")
ge = raw[raw.ground_truth == "Genuine (expired)"][MAIN_VAR].dropna()
print(f"  'Genuine (expired)' group: all {len(ge)} values are <= {ge.max():.0f}; "
      f"{int((raw.loc[raw[MAIN_VAR].notna(), MAIN_VAR].lt(lo)).sum())} of them are flagged as outliers against all data, "
      f"but only {int(((ge < fences(ge)[0]) | (ge > fences(ge)[1])).sum())} are outliers inside the group.")

# ------------------------------------------------ figures
plt.rcParams.update({"font.size": 9})
fig, ax = plt.subplots(2, 2, figsize=(12, 7), gridspec_kw={"height_ratios": [3, 1.3]})
for j, c in enumerate(VARIABLES):
    v = raw[c].dropna(); l, h = fences(v)
    a = ax[0, j]; a.hist(v, bins=30, color="#BFD0E8", edgecolor="white")
    a.axvline(v.mean(), color="#C0392B", lw=2, label=f"Mean {v.mean():.0f}"); a.axvline(v.median(), color="#2E5C9A", lw=2, label=f"Median {v.median():.0f}")
    a.set_title(f"{c}\nskew = {v.skew():.2f}, excess kurtosis = {v.kurt():.2f}"); a.set_ylabel("Count"); a.legend(fontsize=8)
    b = ax[1, j]; b.boxplot(v, vert=False, whis=1.5, patch_artist=True, boxprops=dict(facecolor="#D9E2F3"), flierprops=dict(marker="o", markerfacecolor="#C0392B", markeredgecolor="#C0392B"))
    b.set_yticks([]); b.set_xlabel(c); b.set_xlim(a.get_xlim())
    b.text(0.99, 0.9, f"outliers: {int(((v < l) | (v > h)).sum())}", transform=b.transAxes, ha="right", va="top", color="#C0392B")
plt.tight_layout(); plt.savefig(OUTPUT_DIR / "fig1_shape.png", dpi=150); plt.close()

fig, ax = plt.subplots(1, 3, figsize=(13, 4.8))
for a, g in zip(ax, GROUPS):
    cats = list(raw[g].dropna().unique()); cats.sort(key=lambda k: raw[raw[g] == k][MAIN_VAR].median())
    data = [raw[raw[g] == k][MAIN_VAR].dropna() for k in cats]
    a.boxplot(data, whis=1.5, patch_artist=True, boxprops=dict(facecolor="#D9E2F3"), flierprops=dict(marker="o", markerfacecolor="#C0392B", markeredgecolor="#C0392B", markersize=4), medianprops=dict(color="#2E5C9A", lw=2))
    a.set_xticks(range(1, len(cats) + 1)); a.set_xticklabels([f"{textwrap.fill(k, 12)}\n(n={len(d)})" for k, d in zip(cats, data)], fontsize=7, rotation=0)
    a.axhline(0, color="grey", ls=":"); a.set_title(f"by {g}"); a.set_ylabel(MAIN_VAR)
plt.tight_layout(); plt.savefig(OUTPUT_DIR / "fig2_groups.png", dpi=150); plt.close()

fig, ax = plt.subplots(1, 4, figsize=(13, 3.2))
for a, (k, arr) in zip(ax, ref.items()):
    a.hist(arr, bins=60, color="#BFD0E8", edgecolor="white", range=(np.percentile(arr, 0.2), np.percentile(arr, 99.8)))
    s = pd.Series(arr); a.set_title(f"{k}\nskew {s.skew():.2f}, kurt {s.kurt():.2f}", fontsize=8); a.set_yticks([])
plt.tight_layout(); plt.savefig(OUTPUT_DIR / "fig3_reference_shapes.png", dpi=150); plt.close()
print(f"\nSaved experiment 7 outputs in: {OUTPUT_DIR}")
