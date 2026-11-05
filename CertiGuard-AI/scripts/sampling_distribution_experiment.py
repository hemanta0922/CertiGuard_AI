"""
Experiment 6 (certificate dataset) - Sample means, standard error, central tendency and dispersion
Aim: see how sample means behave as sample size grows (SE = s / sqrt(n)), and summarise the
     dataset with mean/median/mode and range/variance/SD/IQR (using n-1 for samples).

Needs:  pip install pandas numpy matplotlib
Input:  certificate_dataset.csv (same folder, produced in Experiment 4)
Output: console report, se_vs_n.csv, descriptive_stats.csv, outlier_comparison.csv, experiment6_dashboard.png
"""
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# ============================== SETTINGS (edit these) ==============================
ROOT = Path(__file__).resolve().parents[1]
CSV_PATH  = ROOT / "data" / "generated" / "certificate_dataset.csv"
OUTPUT_DIR = ROOT / "outputs" / "experiment6"
TARGET    = "days_to_expiry"      # numeric column studied (days from 5-Nov-2026 to expiry; negative = expired)
NUM_COLS  = ["validity_years", "days_to_expiry", "db_record_count", "missing_fields"]
NOMINAL   = ["institution_type", "qualification_level", "expected_action"]
SIZES     = [5, 10, 20, 30, 50, 100]
REPEATS   = 2000                  # random samples drawn for each n
SEED      = 42
# ===================================================================================
rng = np.random.default_rng(SEED)
def line(t): print("\n" + "=" * 74 + f"\n{t}\n" + "=" * 74)

if not CSV_PATH.is_file():
    raise FileNotFoundError(f"Dataset not found: {CSV_PATH}. Run scripts/generate_certificate_dataset.py first.")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
raw = pd.read_csv(CSV_PATH)
print(f"Rows: {len(raw)}, duplicate rows: {int(raw.duplicated().sum())}")
df = raw.drop_duplicates().dropna(subset=[TARGET]).reset_index(drop=True)
x = df[TARGET].to_numpy(float)
N, mu, sigma = len(x), x.mean(), x.std(ddof=0)
if N < 2:
    raise ValueError(f"At least two non-missing {TARGET} values are required; found {N}.")
SIZES = sorted({min(int(size), N) for size in SIZES if min(int(size), N) >= 2})
print(f"Population = {N} certificates with a valid expiry date ({len(raw) - N} rows excluded: date invalid, so '{TARGET}' is missing)")
print(f"Population mean = {mu:.4f} days, std (sigma) = {sigma:.4f} days")

# ---------------------------------------------------- PART 1: sample means vary
line("PART 1: SAMPLE MEANS VARY AROUND THE POPULATION MEAN (n = 30, ten random samples)")
rows = []
for k in range(1, 11):
    s = rng.choice(x, 30, replace=False)
    rows.append([k, round(s.mean(), 3), round(s.mean() - mu, 3)])
print(pd.DataFrame(rows, columns=["Sample", "Sample mean", "Error (mean - mu)"]).to_string(index=False))
P1 = rows
m = np.array([r[1] for r in rows])
print(f"\nPopulation mean = {mu:.3f}; the ten sample means range from {m.min():.1f} to {m.max():.1f}.")
print("No sample hits mu exactly, but they scatter on both sides of it: this is sampling variation.")

# -------------------------------------------- PART 2: standard error and n
line(f"PART 2: STANDARD ERROR FALLS AS n GROWS (each n repeated {REPEATS} times)")
res, all_means = [], {}
for n in SIZES:
    means = np.empty(REPEATS); sds = np.empty(REPEATS)
    for i in range(REPEATS):
        s = rng.choice(x, n, replace=False)
        means[i], sds[i] = s.mean(), s.std(ddof=1)            # ddof=1 -> sample standard deviation s
    all_means[n] = means
    se_emp = means.std(ddof=1)                                # observed spread of the sample means
    se_form = sds.mean() / np.sqrt(n)                         # SE = s / sqrt(n), averaged over samples
    fpc = np.sqrt((N - n) / (N - 1))
    one = rng.choice(x, n, replace=False)
    res.append([n, round(means.mean(), 3), round(se_emp, 3), round(se_form, 3), round(se_form * fpc, 3),
                round(se_emp * np.sqrt(n), 3), round(one.std(ddof=1) / np.sqrt(n), 3)])
T = pd.DataFrame(res, columns=["n", "Avg sample mean", "SE observed", "SE = s/sqrt(n)", "SE with finite-pop. correction",
                               "SE observed x sqrt(n)", "SE from ONE sample"])
print(T.to_string(index=False)); T.to_csv(OUTPUT_DIR / "se_vs_n.csv", index=False)
print(f"\nPopulation sigma = {sigma:.3f}. 'SE observed x sqrt(n)' stays near sigma at small n, so SE is proportional to 1/sqrt(n).")
print("Quadrupling n (for example 5 -> 20) roughly halves the standard error.")
print("s/sqrt(n) matches the observed SE for small n. For large n the sample is a big share of a")
print("finite population, so the observed SE is smaller; the correction column accounts for this.")

# ---------------------------------------- PART 3: central tendency + outliers
line("PART 3: MEAN, MEDIAN AND MODE")
rows = []
for c in NUM_COLS:
    v = raw[c].dropna()
    mo = v.mode()
    rows.append([c, len(v), round(v.mean(), 3), round(v.median(), 3), round(mo.iloc[0], 3), int((v == mo.iloc[0]).sum()), len(mo)])
C = pd.DataFrame(rows, columns=["Column", "n", "Mean", "Median", "Mode (first)", "Mode count", "No. of modes"])
print(C.to_string(index=False))
print("\nNominal columns (mean and median do not exist; the mode is the only measure):")
NOM = []
for c in NOMINAL:
    vc = raw[c].value_counts(); NOM.append([c, vc.index[0], int(vc.iloc[0]), round(vc.iloc[0] / len(raw) * 100, 1)])
    print(f"  {c}: mode = {vc.index[0]} ({vc.iloc[0]} of {len(raw)}, {vc.iloc[0] / len(raw):.1%})")

line(f"OUTLIERS IN '{TARGET}' (real data, no values were inserted)")
q1, q3 = np.percentile(x, [25, 75]); iqr = q3 - q1; lo, hi = q1 - 1.5 * iqr, q3 + 1.5 * iqr
mask = (x < lo) | (x > hi)
print(f"Q1 = {q1:.1f}, Q3 = {q3:.1f}, IQR = {iqr:.1f}; fences = [{lo:.1f}, {hi:.1f}]")
print(f"Outliers by the 1.5 x IQR rule: {int(mask.sum())}  ->  low: {int((x < lo).sum())}, high: {int((x > hi).sum())}")
print("Outlier values:", sorted(x[mask].astype(int).tolist()))
y = x[~mask]
def mode1(a): return pd.Series(a).mode().iloc[0]
O = pd.DataFrame({"Measure": ["Mean", "Median", "Mode (first)", "Std deviation (n-1)", "IQR", "Range"],
    "All values": [x.mean(), np.median(x), mode1(x), x.std(ddof=1), iqr, x.max() - x.min()],
    "Outliers removed": [y.mean(), np.median(y), mode1(y), y.std(ddof=1), np.subtract(*np.percentile(y, [75, 25])), y.max() - y.min()]})
O["Change"] = O["Outliers removed"] - O["All values"]
print(O.round(2).to_string(index=False)); O.round(3).to_csv(OUTPUT_DIR / "outlier_comparison.csv", index=False)
print(f"\nSkewness of '{TARGET}': {pd.Series(x).skew():.2f} (negative = long tail towards expired / low values)")
print("Mean and standard deviation are pulled by the extreme values; median and IQR change much less.")
print("With outliers or skew, trust the MEDIAN (and IQR). Use the mean only when the data are roughly symmetric.")

# ------------------------------------------------------ PART 4: dispersion
line("PART 4: RANGE, VARIANCE, STANDARD DEVIATION AND IQR")
rows = []
for c in NUM_COLS:
    v2 = raw[c].dropna()
    a, b_ = v2.quantile(.25), v2.quantile(.75)
    rows.append([c, round(v2.max() - v2.min(), 3), round(v2.var(ddof=0), 3), round(v2.var(ddof=1), 3),
                 round(v2.std(ddof=0), 3), round(v2.std(ddof=1), 3), round(b_ - a, 3)])
Dd = pd.DataFrame(rows, columns=["Column", "Range", "Variance (n)", "Variance (n-1)", "SD (n)", "SD (n-1)", "IQR"])
print(Dd.to_string(index=False))
pd.concat([C.set_index("Column"), Dd.set_index("Column")], axis=1).to_csv(OUTPUT_DIR / "descriptive_stats.csv")
print("\n(n) divides by n: correct only when the data ARE the whole population.")
print("(n-1) divides by n-1: correct when the data are a sample used to estimate the population.")

line("WHY n - 1?  (5000 samples of size 10, drawn with replacement)")
true_var = x.var(ddof=0)
v0, v1 = [], []
for _ in range(5000):
    s = rng.choice(x, 10, replace=True)
    v0.append(s.var(ddof=0)); v1.append(s.var(ddof=1))
print(f"True population variance          : {true_var:.1f}")
print(f"Average of sample variance (n)    : {np.mean(v0):.1f}   <- too small (about {(10-1)/10:.0%} of the truth)")
print(f"Average of sample variance (n-1)  : {np.mean(v1):.1f}   <- matches the truth")
print("Dividing by n-1 corrects the bias, because a sample's values sit closer to their own mean than to mu.")

# ----------------------------------------------------------------- charts
fig, ax = plt.subplots(2, 2, figsize=(13, 9))
fig.suptitle(f"Experiment 6 - {TARGET} (certificate dataset)", fontsize=14, fontweight="bold")
a = ax[0, 0]
nn = np.array(SIZES)
a.plot(nn, T["SE observed"], "o-", color="#2E5C9A", label="Observed spread of sample means")
a.plot(nn, T["SE = s/sqrt(n)"], "s--", color="#C0392B", label="s / sqrt(n)")
a.plot(nn, sigma / np.sqrt(nn), ":", color="black", label="sigma / sqrt(n)")
a.set_xlabel("Sample size n"); a.set_ylabel("Standard error (days)"); a.set_title("Standard error falls as n grows"); a.legend(fontsize=8)
b = ax[0, 1]
selected_sizes = sorted({SIZES[0], SIZES[len(SIZES) // 2], SIZES[-1]})
for n in selected_sizes:
    b.hist(all_means[n], bins=40, alpha=.6, label=f"n = {n}", density=True)
b.axvline(mu, color="black", ls="--", label="Population mean")
b.set_xlabel("Sample mean (days)"); b.set_ylabel("Density"); b.set_title(f"Distribution of sample means ({REPEATS} samples each)"); b.legend(fontsize=8)
c = ax[1, 0]
c.hist(x, bins=30, color="#BFD0E8", edgecolor="white")
c.axvline(x.mean(), color="#C0392B", lw=2, label=f"Mean {x.mean():.0f}")
c.axvline(np.median(x), color="#2E5C9A", lw=2, label=f"Median {np.median(x):.0f}")
c.axvline(mode1(x), color="#27AE60", lw=2, label=f"Mode {mode1(x):.0f}")
c.axvline(lo, color="grey", ls=":", label="IQR fences"); c.axvline(hi, color="grey", ls=":")
c.set_xlabel("days_to_expiry"); c.set_ylabel("Certificates"); c.set_title("Mean, median, mode and outlier fences"); c.legend(fontsize=8)
d = ax[1, 1]
vals = [true_var, np.mean(v0), np.mean(v1)]
d.bar(["True variance", "Divide by n", "Divide by n-1"], vals, color=["black", "#C0392B", "#2E5C9A"])
for i, vv in enumerate(vals): d.text(i, vv * 1.01, f"{vv:,.0f}", ha="center")
d.set_ylabel("Variance"); d.set_title("Average sample variance (n = 10, 5000 samples)")
plt.tight_layout(rect=[0, 0, 1, 0.96]); plt.savefig(OUTPUT_DIR / "experiment6_dashboard.png", dpi=150)
print(f"\nSaved experiment 6 outputs in: {OUTPUT_DIR}")
