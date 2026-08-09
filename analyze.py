import pandas as pd
import numpy as np
import math
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick

plt.rcParams.update({
    "font.size": 11,
    "axes.edgecolor": "#444444",
    "axes.labelcolor": "#222222",
    "text.color": "#222222",
    "xtick.color": "#222222",
    "ytick.color": "#222222",
})

NAVY = "#1F3864"
TEAL = "#0E7C7B"
ORANGE = "#D97D3D"
GREY = "#8C8C8C"
LIGHTBLUE = "#6FA8DC"

df = pd.read_csv("/home/claude/project/invoice_queue_dataset.csv")
df["Submission_Timestamp"] = pd.to_datetime(df["Submission_Timestamp"])
df["Is_Month_End_Period"] = df["Is_Month_End_Period"].astype(bool)

# ----------------------------------------------------------------
# 1. Empirical arrival / service rates per period
# ----------------------------------------------------------------
WORK_HOURS_PER_DAY = 9

normal_days = df.loc[~df.Is_Month_End_Period, "Submission_Timestamp"].dt.date.nunique()
me_days = df.loc[df.Is_Month_End_Period, "Submission_Timestamp"].dt.date.nunique()

results = {}
for period_name, mask, ndays in [
    ("Normal", ~df.Is_Month_End_Period, normal_days),
    ("Month-End", df.Is_Month_End_Period, me_days),
]:
    sub = df[mask]
    total_hours = ndays * WORK_HOURS_PER_DAY

    # Stage 1: every invoice enters stage 1
    lam1 = len(sub) / total_hours  # invoices/hour
    mu1_min = sub["Stage1_Service_min"].mean()  # mean service time, minutes
    mu1 = 60.0 / mu1_min  # services/hour per server
    c1 = 3

    # Stage 2: only invoices that proceeded past stage 1
    sub2 = sub[sub["Stage1_Outcome"] == "Proceed"]
    lam2 = len(sub2) / total_hours
    mu2_min = sub2["Stage2_Service_min"].mean()
    mu2 = 60.0 / mu2_min
    c2 = 2

    results[period_name] = dict(
        lam1=lam1, mu1=mu1, c1=c1, mu1_min=mu1_min,
        lam2=lam2, mu2=mu2, c2=c2, mu2_min=mu2_min,
        sim_wait1=sub["Stage1_Wait_min"].mean(),
        sim_wait2=sub2["Stage2_Wait_min"].mean(),
        sim_turnaround=sub["Total_Turnaround_min"].mean(),
        n=len(sub),
    )


def erlang_c_wait_minutes(lam_per_hr, mu_per_hr, c):
    """Return theoretical Wq (minutes) for an M/M/c queue via the Erlang-C formula."""
    a = lam_per_hr / mu_per_hr  # offered load, erlangs
    rho = a / c
    if rho >= 1:
        return float("inf"), rho, 1.0
    sum_terms = sum((a ** k) / math.factorial(k) for k in range(c))
    last_term = (a ** c) / (math.factorial(c) * (1 - rho))
    p0 = 1.0 / (sum_terms + last_term)
    p_wait = last_term * p0  # Erlang-C probability of queueing
    wq_hours = p_wait / (c * mu_per_hr - lam_per_hr)
    return wq_hours * 60.0, rho, p_wait


summary_rows = []
for period_name, r in results.items():
    wq1_theory, rho1, pwait1 = erlang_c_wait_minutes(r["lam1"], r["mu1"], r["c1"])
    wq2_theory, rho2, pwait2 = erlang_c_wait_minutes(r["lam2"], r["mu2"], r["c2"])
    row = dict(period=period_name,
               lam1=r["lam1"], mu1=r["mu1"], rho1=rho1, wq1_theory=wq1_theory, wq1_sim=r["sim_wait1"],
               lam2=r["lam2"], mu2=r["mu2"], rho2=rho2, wq2_theory=wq2_theory, wq2_sim=r["sim_wait2"],
               turnaround_sim=r["sim_turnaround"], n=r["n"])
    summary_rows.append(row)
    print(period_name)
    print(f"  Stage1: lambda={r['lam1']:.2f}/hr mu={r['mu1']:.2f}/hr c={r['c1']} rho={rho1:.3f}  Wq_theory={wq1_theory:.2f}min  Wq_sim={r['sim_wait1']:.2f}min")
    print(f"  Stage2: lambda={r['lam2']:.2f}/hr mu={r['mu2']:.2f}/hr c={r['c2']} rho={rho2:.3f}  Wq_theory={wq2_theory:.2f}min  Wq_sim={r['sim_wait2']:.2f}min")
    print(f"  Mean total turnaround (sim): {r['sim_turnaround']:.2f} min   n={r['n']}")

summary_df = pd.DataFrame(summary_rows)
summary_df.to_csv("/home/claude/project/analysis_summary.csv", index=False)

# Scalability what-if: add a 3rd manager at Stage 2 during month-end
r = results["Month-End"]
wq2_extra, rho2_extra, _ = erlang_c_wait_minutes(r["lam2"], r["mu2"], 3)
wq2_current, rho2_current, _ = erlang_c_wait_minutes(r["lam2"], r["mu2"], 2)
print(f"\nScalability check (Month-End Stage 2): c=2 -> Wq={wq2_current:.2f}min (rho={rho2_current:.2f});"
      f" c=3 -> Wq={wq2_extra:.2f}min (rho={rho2_extra:.2f})")

# Scalability what-if: double the arrival rate at Stage 2 (normal day), c=2
r_n = results["Normal"]
wq2_double, rho2_double, _ = erlang_c_wait_minutes(r_n["lam2"] * 2, r_n["mu2"], 2)
print(f"Scalability check (double normal-day volume, Stage 2, c=2): Wq={wq2_double:.2f}min (rho={rho2_double:.2f})")

with open("/home/claude/project/scalability.txt", "w") as f:
    f.write(f"{wq2_current:.2f},{rho2_current:.3f},{wq2_extra:.2f},{rho2_extra:.3f},{wq2_double:.2f},{rho2_double:.3f}\n")

# ----------------------------------------------------------------
# CHART 1: Mean wait time by stage, normal vs month-end (theory vs sim)
# ----------------------------------------------------------------
fig, ax = plt.subplots(figsize=(7.2, 4.2), dpi=200)
labels = ["Stage 1\n(Normal)", "Stage 1\n(Month-End)", "Stage 2\n(Normal)", "Stage 2\n(Month-End)"]
theory_vals = [
    summary_df.loc[summary_df.period == "Normal", "wq1_theory"].values[0],
    summary_df.loc[summary_df.period == "Month-End", "wq1_theory"].values[0],
    summary_df.loc[summary_df.period == "Normal", "wq2_theory"].values[0],
    summary_df.loc[summary_df.period == "Month-End", "wq2_theory"].values[0],
]
sim_vals = [
    summary_df.loc[summary_df.period == "Normal", "wq1_sim"].values[0],
    summary_df.loc[summary_df.period == "Month-End", "wq1_sim"].values[0],
    summary_df.loc[summary_df.period == "Normal", "wq2_sim"].values[0],
    summary_df.loc[summary_df.period == "Month-End", "wq2_sim"].values[0],
]
x = np.arange(len(labels))
w = 0.35
ax.bar(x - w/2, theory_vals, w, label="Analytical M/M/c (Erlang-C)", color=NAVY)
ax.bar(x + w/2, sim_vals, w, label="Discrete-event simulation", color=TEAL)
ax.set_xticks(x)
ax.set_xticklabels(labels)
ax.set_ylabel("Mean queueing wait, Wq (minutes)")
ax.set_title("Theoretical vs. Simulated Queueing Delay by Stage and Period", fontsize=12, color=NAVY, weight="bold")
ax.legend(frameon=False, loc="upper left")
ax.spines[["top", "right"]].set_visible(False)
plt.tight_layout()
plt.savefig("/home/claude/project/chart1_wait_theory_vs_sim.png", facecolor="white")
plt.close()

# ----------------------------------------------------------------
# CHART 2: Turnaround time distribution, normal vs month-end (histogram)
# ----------------------------------------------------------------
fig, ax = plt.subplots(figsize=(7.2, 4.2), dpi=200)
normal_t = df.loc[~df.Is_Month_End_Period, "Total_Turnaround_min"].dropna()
me_t = df.loc[df.Is_Month_End_Period, "Total_Turnaround_min"].dropna()
bins = np.linspace(0, 120, 30)
ax.hist(normal_t, bins=bins, alpha=0.75, label=f"Normal days (mean={normal_t.mean():.1f} min)", color=TEAL)
ax.hist(me_t, bins=bins, alpha=0.75, label=f"Month-end days (mean={me_t.mean():.1f} min)", color=ORANGE)
ax.set_xlabel("Total turnaround time (minutes)")
ax.set_ylabel("Number of invoices")
ax.set_title("Distribution of End-to-End Invoice Turnaround Time", fontsize=12, color=NAVY, weight="bold")
ax.legend(frameon=False)
ax.spines[["top", "right"]].set_visible(False)
plt.tight_layout()
plt.savefig("/home/claude/project/chart2_turnaround_hist.png", facecolor="white")
plt.close()

# ----------------------------------------------------------------
# CHART 3: Hourly arrival rate profile (average invoices per hour-of-day)
# ----------------------------------------------------------------
df["hour"] = df["Submission_Timestamp"].dt.hour
hourly_normal = df.loc[~df.Is_Month_End_Period].groupby("hour").size() / normal_days
hourly_me = df.loc[df.Is_Month_End_Period].groupby("hour").size() / me_days

fig, ax = plt.subplots(figsize=(7.2, 4.2), dpi=200)
hours = sorted(set(hourly_normal.index) | set(hourly_me.index))
ax.plot(hourly_normal.index, hourly_normal.values, marker="o", color=TEAL, label="Normal days")
ax.plot(hourly_me.index, hourly_me.values, marker="o", color=ORANGE, label="Month-end days")
ax.set_xlabel("Hour of day")
ax.set_ylabel("Mean invoices arriving per hour")
ax.set_title("Hourly Invoice Arrival Profile", fontsize=12, color=NAVY, weight="bold")
ax.legend(frameon=False)
ax.spines[["top", "right"]].set_visible(False)
ax.set_xticks(range(8, 17))
plt.tight_layout()
plt.savefig("/home/claude/project/chart3_hourly_arrivals.png", facecolor="white")
plt.close()

# ----------------------------------------------------------------
# CHART 4: Server utilisation (rho) by stage/period + scalability scenario
# ----------------------------------------------------------------
fig, ax = plt.subplots(figsize=(7.2, 4.2), dpi=200)
scen_labels = ["Stage1\nNormal", "Stage1\nMonth-End", "Stage2\nNormal", "Stage2\nMonth-End\n(c=2, current)", "Stage2\nMonth-End\n(c=3, +1 mgr)"]
rho_vals = [
    summary_df.loc[summary_df.period == "Normal", "rho1"].values[0],
    summary_df.loc[summary_df.period == "Month-End", "rho1"].values[0],
    summary_df.loc[summary_df.period == "Normal", "rho2"].values[0],
    rho2_current,
    rho2_extra,
]
colors = [TEAL, TEAL, NAVY, NAVY, ORANGE]
bars = ax.bar(scen_labels, rho_vals, color=colors)
ax.axhline(0.85, color="red", linestyle="--", linewidth=1, label="High-congestion threshold (\u03c1=0.85)")
ax.set_ylabel("Server utilisation, \u03c1")
ax.set_ylim(0, 1.05)
ax.yaxis.set_major_formatter(mtick.PercentFormatter(xmax=1.0))
ax.set_title("Server Utilisation by Stage, Period, and Staffing Scenario", fontsize=12, color=NAVY, weight="bold")
ax.legend(frameon=False)
ax.spines[["top", "right"]].set_visible(False)
for b, v in zip(bars, rho_vals):
    ax.text(b.get_x() + b.get_width()/2, v + 0.02, f"{v*100:.0f}%", ha="center", fontsize=9)
plt.tight_layout()
plt.savefig("/home/claude/project/chart4_utilisation.png", facecolor="white")
plt.close()

# ----------------------------------------------------------------
# CHART 5: Outcome breakdown (funnel-style bar)
# ----------------------------------------------------------------
outcome_counts = df["Final_Status"].value_counts()
fig, ax = plt.subplots(figsize=(6.4, 4.0), dpi=200)
colors_map = {"Approved": TEAL, "Returned to Distributor": ORANGE, "Rejected": "#C0504D"}
bars = ax.bar(outcome_counts.index, outcome_counts.values,
               color=[colors_map.get(k, GREY) for k in outcome_counts.index])
ax.set_ylabel("Number of invoices")
ax.set_title("Final Invoice Outcomes (n=%d)" % len(df), fontsize=12, color=NAVY, weight="bold")
ax.spines[["top", "right"]].set_visible(False)
for b in bars:
    ax.text(b.get_x() + b.get_width()/2, b.get_height() + 5, str(int(b.get_height())), ha="center", fontsize=9)
plt.xticks(rotation=10)
plt.tight_layout()
plt.savefig("/home/claude/project/chart5_outcomes.png", facecolor="white")
plt.close()

print("\nAll charts saved.")
print(summary_df.to_string(index=False))
