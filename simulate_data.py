"""
Simulated dataset generator for the ERP Invoice Approval Processing Queue
EEI6373 - Performance Modelling Mini Project

Models a two-stage queuing network:
  Stage 1: Initial Review (by branch-level reviewers)
  Stage 2: Manager Approval (final sign-off)

Arrivals follow a non-homogeneous Poisson process (higher rate near month-end,
mimicking real invoice submission patterns in distributor ERP systems).
Service times follow exponential-ish distributions with stage-specific means.
"""

import csv
import random
import math
from datetime import datetime, timedelta

random.seed(42)

DAYS = 30
START_DATE = datetime(2026, 6, 1, 8, 0, 0)  # ERP business hours start 08:00
WORKDAY_HOURS = 9  # 08:00 - 17:00

DISTRIBUTORS = [f"DIST-{i:03d}" for i in range(1, 13)]
STAGE1_APPROVERS = ["Reviewer-A", "Reviewer-B", "Reviewer-C"]
STAGE2_APPROVERS = ["Manager-X", "Manager-Y"]

# Mean service times (minutes)
STAGE1_MEAN_SERVICE = 6.0
STAGE2_MEAN_SERVICE = 9.5

rows = []
invoice_counter = 1

# Track when each server becomes free (simple multi-server FIFO simulation)
stage1_free_time = {a: None for a in STAGE1_APPROVERS}
stage2_free_time = {a: None for a in STAGE2_APPROVERS}


def exp_sample(mean):
    return random.expovariate(1.0 / mean)


for day in range(DAYS):
    current_date = START_DATE + timedelta(days=day)
    # Skip Sundays (weekday() == 6) to mimic a 6-day work week
    if current_date.weekday() == 6:
        continue

    day_of_month = current_date.day
    # Month-end surge: arrival rate roughly triples in the last 5 days of month
    is_month_end = day_of_month >= 26
    base_rate_per_hour = 14 if is_month_end else 5  # invoices/hour

    # Reset server free times at the start of each business day
    for a in stage1_free_time:
        stage1_free_time[a] = current_date
    for a in stage2_free_time:
        stage2_free_time[a] = current_date

    t = current_date
    end_of_day = current_date + timedelta(hours=WORKDAY_HOURS)

    while t < end_of_day:
        # Time to next arrival (Poisson process)
        interarrival_min = exp_sample(60.0 / base_rate_per_hour)
        t = t + timedelta(minutes=interarrival_min)
        if t >= end_of_day:
            break

        arrival_time = t
        distributor = random.choice(DISTRIBUTORS)
        invoice_amount = round(random.uniform(5000, 850000), 2)  # LKR
        priority = random.choices(["Normal", "High"], weights=[0.85, 0.15])[0]

        # ---- Stage 1: Initial Review ----
        # Assign to the approver who becomes free earliest
        approver1 = min(stage1_free_time, key=lambda a: stage1_free_time[a])
        stage1_start = max(arrival_time, stage1_free_time[approver1])
        wait1_min = (stage1_start - arrival_time).total_seconds() / 60.0
        service1_min = exp_sample(STAGE1_MEAN_SERVICE)
        if priority == "High":
            service1_min *= 0.8  # high priority processed slightly faster
        stage1_end = stage1_start + timedelta(minutes=service1_min)
        stage1_free_time[approver1] = stage1_end

        # ---- Outcome after Stage 1 ----
        outcome1 = random.choices(
            ["Proceed", "Returned"], weights=[0.88, 0.12]
        )[0]

        if outcome1 == "Returned":
            status = "Returned to Distributor"
            stage2_start = None
            stage2_end = None
            approver2 = None
            wait2_min = None
            service2_min = None
            total_turnaround = (stage1_end - arrival_time).total_seconds() / 60.0
        else:
            # ---- Stage 2: Manager Approval ----
            approver2 = min(stage2_free_time, key=lambda a: stage2_free_time[a])
            stage2_start = max(stage1_end, stage2_free_time[approver2])
            wait2_min = (stage2_start - stage1_end).total_seconds() / 60.0
            service2_min = exp_sample(STAGE2_MEAN_SERVICE)
            if priority == "High":
                service2_min *= 0.85
            stage2_end = stage2_start + timedelta(minutes=service2_min)
            stage2_free_time[approver2] = stage2_end

            status = random.choices(
                ["Approved", "Rejected"], weights=[0.93, 0.07]
            )[0]
            total_turnaround = (stage2_end - arrival_time).total_seconds() / 60.0

        rows.append({
            "Invoice_ID": f"INV-{invoice_counter:05d}",
            "Distributor_ID": distributor,
            "Priority": priority,
            "Invoice_Amount_LKR": invoice_amount,
            "Submission_Timestamp": arrival_time.strftime("%Y-%m-%d %H:%M:%S"),
            "Stage1_Approver": approver1,
            "Stage1_Wait_min": round(wait1_min, 2),
            "Stage1_Service_min": round(service1_min, 2),
            "Stage1_Outcome": outcome1,
            "Stage2_Approver": approver2 if approver2 else "",
            "Stage2_Wait_min": round(wait2_min, 2) if wait2_min is not None else "",
            "Stage2_Service_min": round(service2_min, 2) if service2_min is not None else "",
            "Final_Status": status,
            "Total_Turnaround_min": round(total_turnaround, 2),
            "Is_Month_End_Period": is_month_end,
        })
        invoice_counter += 1

print(f"Generated {len(rows)} invoice records")

with open("/home/claude/project/invoice_queue_dataset.csv", "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)

# ---- Quick summary stats for the report ----
def mean(vals):
    vals = [v for v in vals if v != "" and v is not None]
    return sum(vals) / len(vals) if vals else 0

total_wait1 = mean([r["Stage1_Wait_min"] for r in rows])
total_wait2 = mean([r["Stage2_Wait_min"] for r in rows if r["Stage2_Wait_min"] != ""])
total_turnaround = mean([r["Total_Turnaround_min"] for r in rows])

month_end_rows = [r for r in rows if r["Is_Month_End_Period"]]
normal_rows = [r for r in rows if not r["Is_Month_End_Period"]]

print(f"Avg Stage 1 wait: {total_wait1:.2f} min")
print(f"Avg Stage 2 wait: {total_wait2:.2f} min")
print(f"Avg total turnaround: {total_turnaround:.2f} min")
print(f"Records - normal days: {len(normal_rows)}, month-end days: {len(month_end_rows)}")
print(f"Avg turnaround (normal): {mean([r['Total_Turnaround_min'] for r in normal_rows]):.2f} min")
print(f"Avg turnaround (month-end): {mean([r['Total_Turnaround_min'] for r in month_end_rows]):.2f} min")
