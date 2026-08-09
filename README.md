# EEI6373 – Performance Modelling: Mini Project

**System:** Invoice Approval Processing Queue in a Web-Based ERP System
**Student:** Afri Ahmath
**Course:** EEI6373 – Performance Modelling, The Open University of Sri Lanka

This repository covers BOTH OULMS submissions (both due 10 Aug 2026):
- **Mini Project Deliverable** (system + objectives + dataset) — share this repo's URL in the OULMS text box.
- **Mini Project Report** (full formal report) — likely a direct file upload; see the assignment page for whether it wants the .docx uploaded directly there too.

## Contents

| File | Description |
|---|---|
| `EEI6373_MiniProject_Preliminary_Submission.docx` | Deliverable: system description, performance objectives, dataset methodology |
| `EEI6373_MiniProject_Report.docx` | Full Mini Project Report: modelling, equations, charts, findings, limitations, references |
| `invoice_queue_dataset.csv` | Simulated dataset — 1,429 invoice records across a 30-day period |
| `simulate_data.py` | Python script used to generate the dataset (two-stage queuing simulation) |
| `analyze.py` | Python script: Erlang-C analytical model, validation, and all 5 charts |
| `analysis_summary.csv` | Summary table of analytical vs. simulated results (utilisation, wait times) |
| `chart1`–`chart5` `.png` | The five figures used in the report |

## Dataset summary

- 2-stage tandem queue: **Stage 1 – Initial Review** (3 reviewers) → **Stage 2 – Manager Approval** (2 managers)
- 30-day simulation period, business hours 08:00–17:00
- Arrival rate ~5 invoices/hour on normal days, ~14/hour during month-end (days 26–30)
- Fields include per-stage wait/service times, approver assignment, final status, and turnaround time

Regenerate the dataset at any time with:

```bash
python3 simulate_data.py
```

## How to push this to GitHub

1. Create a new **public** repository on GitHub (e.g. `eei6373-mini-project`).
2. From this folder, run:

```bash
git init
git add .
git commit -m "Mini project: deliverable, full report, dataset, analysis"
git branch -M main
git remote add origin https://github.com/<your-username>/eei6373-mini-project.git
git push -u origin main
```

3. Copy the repository URL and paste it into:
   - Section 5 of `EEI6373_MiniProject_Preliminary_Submission.docx`
   - Section 7 of `EEI6373_MiniProject_Report.docx`
   (both currently have a placeholder), then re-save/export and re-push before submitting.
