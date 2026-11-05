"""
Experiment 5 - Data inspection, data quality and sampling methods
Aim: load the synthetic certificate dataset, check its quality, and compare five sampling methods by
     how close each sample mean (statistic) is to the population mean (parameter).

Needs:  pip install pandas numpy matplotlib
Input:  data/generated/certificate_dataset.csv (run the generator first)
Output: console report and files in outputs/experiment5/
"""
import re
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# ============================== SETTINGS (edit these) ==============================
ROOT        = Path(__file__).resolve().parents[1]
CSV_PATH    = ROOT / "data" / "generated" / "certificate_dataset.csv"
OUTPUT_DIR  = ROOT / "outputs" / "experiment5"
TARGET      = "days_to_expiry"  # numeric certificate field; negative values indicate expired certificates
STRATA_COL  = "institution_type"
CLUSTER_COL = "scenario"
SAMPLE_SIZE = None      # None = 10% of the population (at least 20)
SEED        = 42
N_REPEATS   = 10        # number of different seeds for Steps 7 and 8
N_COMPARE   = 200       # repeats used to compare the five methods fairly (Step 6b)
# If the automatic scale-of-measurement guess is wrong, correct it here, e.g. {"year": "ordinal"}
MEASUREMENT_OVERRIDE = {}
# ===================================================================================

def line(t): print("\n" + "=" * 72 + f"\n{t}\n" + "=" * 72)

# ------------------------------------------------------------------ 1. LOAD
line("STEP 1: LOAD AND INSPECT THE DATA")
if not CSV_PATH.is_file():
    raise FileNotFoundError(f"Dataset not found: {CSV_PATH}. Run scripts/generate_certificate_dataset.py first.")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
raw = pd.read_csv(CSV_PATH)
print(f"Rows: {raw.shape[0]}   Columns: {raw.shape[1]}\n")
print("First 5 rows:"); print(raw.head().to_string(index=False))
print("\nColumn names and data types:"); print(raw.dtypes.to_string())

# ------------------------------------------------- 2. SCALES OF MEASUREMENT
line("STEP 2: SCALE OF MEASUREMENT OF EACH COLUMN")
ORDINAL_VALUES = [{"low", "medium", "high"}, {"a", "b", "c", "d", "e", "f"}, {"poor", "average", "good", "excellent"},
                  {"first", "second", "third"}, {"fresher", "sophomore", "junior", "senior"}]
RATIO_HINTS = ["age", "mark", "score", "hour", "attendance", "percent", "pct", "fee", "income", "height", "weight",
               "count", "number", "distance", "salary", "cgpa", "gpa", "time", "amount", "spend"]
INTERVAL_HINTS = ["temp", "year_of", "calendar", "rating_scale"]

def classify(col, s):
    name = col.lower()
    nun = s.nunique(dropna=True)
    if re.search(r"(^id$|_id$|^id_|roll|reg_?no|enrol)", name) or nun == len(s.dropna()) and s.dtype == object:
        return "nominal", "identifier / label with no order"
    if s.dtype == object or str(s.dtype) in ("str", "string", "category"):
        vals = {str(v).strip().lower() for v in s.dropna().unique()}
        if any(vals <= o for o in ORDINAL_VALUES):
            return "ordinal", "categories with a natural order"
        return "nominal", "categories with no natural order"
    if nun <= 2:
        return "nominal", "two categories coded as numbers"
    if any(h in name for h in INTERVAL_HINTS):
        return "interval", "numeric, equal steps, no true zero"
    if re.search(r"(year|sem|semester|class|level|rank|rating)$", name) and nun <= 12:
        return "ordinal", "small set of ordered levels"
    if any(h in name for h in RATIO_HINTS) or s.min() >= 0:
        return "ratio", "numeric with a true zero"
    return "interval", "numeric, equal steps, no true zero"

scale = {}
rows = []
for c in raw.columns:
    sc, why = classify(c, raw[c])
    sc = MEASUREMENT_OVERRIDE.get(c, sc)
    scale[c] = sc
    rows.append([c, str(raw[c].dtype), raw[c].nunique(), sc.upper(), why])
print(pd.DataFrame(rows, columns=["Column", "dtype", "Unique", "Scale", "Reason"]).to_string(index=False))
print("\n(The scale is guessed from names and values. Check it and correct it with MEASUREMENT_OVERRIDE.)")

# ------------------------------------------------------ 3. DATA QUALITY
line("STEP 3: MISSING VALUES AND DUPLICATE ROWS")
miss = raw.isna().sum()
print("Missing values per column:")
print(pd.DataFrame({"missing": miss, "percent": (miss / len(raw) * 100).round(1)}).query("missing > 0").to_string()
      if miss.sum() else "None")
dups = int(raw.duplicated().sum())
print(f"\nDuplicate rows (exact copies): {dups}")
if dups:
    print(raw[raw.duplicated(keep=False)].sort_values(list(raw.columns[:2])).head(8).to_string(index=False))

# ---- choose columns
numeric = [c for c in raw.columns if scale[c] in ("ratio", "interval") and pd.api.types.is_numeric_dtype(raw[c])]
def pick(cands, hints):
    for h in hints:
        for c in cands:
            if h in c.lower(): return c
    return cands[0] if cands else None
if TARGET is None:      TARGET = pick(numeric, ["mark", "score", "cgpa", "gpa", "percent", "attendance"])
cat = [c for c in raw.columns if scale[c] in ("nominal", "ordinal") and c != TARGET and 2 <= raw[c].nunique() <= 20]
if STRATA_COL is None:  STRATA_COL = pick([c for c in cat if raw[c].nunique() <= 6], ["depart", "branch", "course", "gender", "year"])
if CLUSTER_COL is None: CLUSTER_COL = pick([c for c in cat if 6 <= raw[c].nunique() <= 20 and c != STRATA_COL], ["section", "class", "batch", "group", "city"])
print(f"\nColumns chosen -> target: {TARGET} | strata: {STRATA_COL} | clusters: {CLUSTER_COL}")

# ---- clean (cleaning decisions are stated, not hidden)
if TARGET is None or TARGET not in raw.columns:
    raise ValueError("No usable numeric TARGET column was found. Set TARGET to a numeric CSV column.")
pop = raw.drop_duplicates().dropna(subset=[TARGET]).reset_index(drop=True)
if len(pop) < 4:
    raise ValueError("At least four usable rows are required for the sampling experiment.")
print(f"Cleaning: removed {len(raw) - len(pop)} rows (duplicates and rows with missing '{TARGET}'). Population size N = {len(pop)}")

# ----------------------------------------------------- 4. POPULATION MEAN
line("STEP 4: POPULATION MEAN (PARAMETER)")
N = len(pop)
mu = pop[TARGET].mean()
sigma = pop[TARGET].std(ddof=0)
n = min(N, SAMPLE_SIZE if SAMPLE_SIZE is not None else max(20, round(0.10 * N)))
if n < 2:
    raise ValueError("SAMPLE_SIZE must be at least 2.")
print(f"The whole cleaned dataset is treated as the population.")
print(f"Mean of {TARGET} (mu) = {mu:.4f}    Std deviation (sigma) = {sigma:.4f}    Sample size n = {n}")

# ---------------------------------------------------- 5. SAMPLING METHODS
def simple_random(df, n, seed):
    return df.sample(n=n, random_state=seed)

def systematic(df, n, seed):
    k = len(df) // n
    start = np.random.default_rng(seed).integers(0, k)
    return df.iloc[start::k].head(n)

def stratified(df, n, seed):
    if STRATA_COL not in df.columns:
        raise ValueError(f"Stratification column not found: {STRATA_COL}")
    groups = [(key, group) for key, group in df.groupby(STRATA_COL, dropna=False)]
    exact = [n * len(group) / len(df) for _, group in groups]
    allocation = [int(value) for value in exact]
    # Largest-remainder allocation keeps the total sample size exactly n.
    remaining = n - sum(allocation)
    order = sorted(range(len(groups)), key=lambda i: exact[i] - allocation[i], reverse=True)
    for i in order[:remaining]:
        allocation[i] += 1
    parts = [
        group.sample(n=min(size, len(group)), random_state=seed)
        for (_, group), size in zip(groups, allocation) if size > 0
    ]
    return pd.concat(parts).sample(frac=1, random_state=seed)

def cluster(df, n, seed):
    if CLUSTER_COL not in df.columns:
        raise ValueError(f"Cluster column not found: {CLUSTER_COL}")
    labels = list(df[CLUSTER_COL].dropna().unique())
    np.random.default_rng(seed).shuffle(labels)
    chosen, total = [], 0
    for lab in labels:                                       # take WHOLE clusters until we have >= n rows
        chosen.append(lab); total += (df[CLUSTER_COL] == lab).sum()
        if total >= n: break
    return df[df[CLUSTER_COL].isin(chosen)]

def convenience(df, n, seed=None):
    return df.head(n)                                        # the first n rows = "whoever is easiest to reach"

line("STEP 5 and 6: FIVE SAMPLING METHODS vs POPULATION MEAN")
methods = {"Simple random": simple_random, "Systematic": systematic, "Stratified": stratified,
           "Cluster": cluster, "Convenience": convenience}
res = []
samples = {}
for name, f in methods.items():
    s = f(pop, n, SEED); samples[name] = s
    m = s[TARGET].mean()
    error_pct = np.nan if np.isclose(mu, 0) else abs(m - mu) / abs(mu) * 100
    res.append([name, len(s), round(m, 4), round(mu, 4), round(m - mu, 4), round(error_pct, 2)])
R = pd.DataFrame(res, columns=["Method", "Sample size", "Sample mean", "Population mean", "Error (x_bar - mu)", "Abs error %"])
print(R.to_string(index=False))
best = R.loc[R["Abs error %"].idxmin(), "Method"]
print(f"\nClosest to the population mean with seed {SEED}: {best}")
print("Caution: one sample is one draw. A method can win by luck. Step 7 shows how much one draw can vary.")
print(f"Note: cluster sampling keeps whole groups, so its size ({len(samples['Cluster'])}) can exceed n.")
R.to_csv(OUTPUT_DIR / "sampling_results.csv", index=False)

# ---- Step 6b: one draw can be lucky, so repeat every method many times
print(f"\nStep 6b: the same comparison repeated with {N_COMPARE} different seeds (fairer than one draw)")
rep = {m: np.array([f(pop, n, sd)[TARGET].mean() for sd in range(1, N_COMPARE + 1)]) for m, f in methods.items()}
R2 = pd.DataFrame([[m, round(v.mean(), 3), round(np.abs(v - mu).mean(), 3), round(v.std(ddof=1), 3)] for m, v in rep.items()],
                  columns=["Method", "Average sample mean", "Average abs error", "Spread (std) of sample means"])
print(R2.to_string(index=False))
print("Reading: a method with average sample mean near mu is unbiased; a small spread means it is precise.")
print("Convenience (first n rows) never changes with the seed, so its error is the same every time.")

# ---------------------------------------------------------- 7. SAMPLING ERROR
line(f"STEP 7: SAMPLING ERROR (simple random sample repeated with {N_REPEATS} seeds)")
seeds = list(range(1, N_REPEATS + 1))
srs_means = [simple_random(pop, n, s)[TARGET].mean() for s in seeds]
runs = pd.DataFrame({"seed": seeds, "sample_mean": np.round(srs_means, 4)})
runs["error"] = (runs["sample_mean"] - mu).round(4)
print(runs.to_string(index=False))
se_theory = sigma / np.sqrt(n) * np.sqrt((N - n) / (N - 1))
print(f"\nPopulation mean                        : {mu:.4f}")
print(f"Average of the {N_REPEATS} sample means          : {np.mean(srs_means):.4f}   (only {N_REPEATS} draws, so some luck remains)")
print(f"Average of {N_COMPARE} sample means         : {rep['Simple random'].mean():.4f}   (very close to mu: random sampling is unbiased)")
print(f"Spread of the sample means (std)       : {np.std(srs_means, ddof=1):.4f}")
print(f"Theoretical standard error             : {se_theory:.4f}   [sigma/sqrt(n) x finite-population correction]")
print("Every sample mean differs a little from mu. This random difference is SAMPLING ERROR.")
print("It is not a mistake: it averages out and shrinks as n grows.")

# ----------------------------------------------------------- 8. SAMPLING BIAS
line("STEP 8: SAMPLING BIAS (deliberately biased sample)")
cutoff = pop[TARGET].median()
top_half = pop[pop[TARGET] >= cutoff]
biased_n = min(n, len(top_half))
biased_means = [top_half.sample(n=biased_n, random_state=s)[TARGET].mean() for s in seeds]
runs["biased_mean"] = np.round(biased_means, 4)
runs["biased_error"] = (runs["biased_mean"] - mu).round(4)
runs.to_csv(OUTPUT_DIR / "sampling_error_runs.csv", index=False)
print(f"Biased design: pick only from the upper half of '{TARGET}' (>= {cutoff:.2f}); sample size = {biased_n}.")
print("like a voluntary survey that only high performers answer.\n")
print(runs[["seed", "sample_mean", "biased_mean", "error", "biased_error"]].to_string(index=False))
print(f"\nAverage error, random sampling : {np.mean(srs_means) - mu:+.4f}   (near zero, errors go both ways)")
print(f"Average error, biased sampling : {np.mean(biased_means) - mu:+.4f}   (same direction every time)")
print("Sampling error is random and averages out. Sampling BIAS is systematic: it comes from HOW the")
print("sample is chosen, so taking more repeats or a bigger sample does not remove it.")

# ------------------------------------------------------------------ CHARTS
fig, ax = plt.subplots(2, 2, figsize=(13, 9))
fig.suptitle(f"Sampling experiment - estimating mean of {TARGET}", fontsize=14, fontweight="bold")
a = ax[0, 0]
colors = ["#2E5C9A"] * 4 + ["#C0392B"]
a.bar(R["Method"], R["Sample mean"], color=colors)
a.axhline(mu, color="black", ls="--", label=f"Population mean = {mu:.2f}")
lo = min(R["Sample mean"].min(), mu); hi = max(R["Sample mean"].max(), mu); pad = (hi - lo) * 0.6 + 0.5
a.set_ylim(lo - pad, hi + pad); a.set_ylabel("Sample mean"); a.set_title("Step 6: sample mean of each method"); a.legend()
a.tick_params(axis="x", rotation=20)
b = ax[0, 1]
b.boxplot([rep[m] - mu for m in methods], tick_labels=list(methods), patch_artist=True, boxprops=dict(facecolor="#D9E2F3"))
b.axhline(0, color="black", ls="--"); b.set_ylabel("Error (sample mean - mu)"); b.set_title(f"Step 6b: error over {N_COMPARE} repeated samples")
b.tick_params(axis="x", rotation=20)
c = ax[1, 0]
c.scatter(seeds, srs_means, s=60, color="#2E5C9A", label="Simple random samples", zorder=3)
c.axhline(mu, color="black", ls="--", label="Population mean")
c.fill_between([0.5, N_REPEATS + 0.5], mu - se_theory, mu + se_theory, color="#2E5C9A", alpha=0.15, label="+/- 1 standard error")
c.set_xlabel("Seed"); c.set_ylabel("Sample mean"); c.set_title("Step 7: sampling error (random scatter around mu)"); c.legend(fontsize=8)
c.set_xlim(0.5, N_REPEATS + 0.5)
d = ax[1, 1]
d.scatter(seeds, srs_means, s=60, color="#2E5C9A", label="Random sampling")
d.scatter(seeds, biased_means, s=60, color="#C0392B", marker="s", label="Biased sampling")
d.axhline(mu, color="black", ls="--", label="Population mean")
d.set_xlabel("Seed"); d.set_ylabel("Sample mean"); d.set_title("Step 8: bias pushes every estimate the same way"); d.legend(fontsize=8)
plt.tight_layout(rect=[0, 0, 1, 0.96]); plt.savefig(OUTPUT_DIR / "sampling_dashboard.png", dpi=150)
print(f"\nSaved sampling outputs in: {OUTPUT_DIR}")
