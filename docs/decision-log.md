# Decision Log

This document records important technical and analytical decisions made during implementation after approval of Project Specification v1.0.

The purpose is to prevent silent design changes and preserve the reasoning behind important choices.

---

## DL-001 — Dataset Timeframe

**Date:** 2026-08-11  
**Status:** Approved / Frozen

**Decision**

Simulate activity from:

**1 January 2024 – 30 June 2026**

Dataset snapshot:

**1 July 2026 00:00 UTC**

**Reason**

Thirty months provides sufficient history for seasonality, mature cohorts, annual renewals, churn/LTV analysis, forecasting, and year-over-year comparisons without introducing unnecessary long-term regime changes.

---

## DL-002 — Local Project Location

**Date:** 2026-08-11  
**Status:** Approved

**Decision**

Local repository root:

`G:\Personal Projects\pulse-product-analytics`

---

## DL-003 — GitHub Repository

**Date:** 2026-08-11  
**Status:** Approved

**Decision**

Repository:

`ashasif/pulse-product-analytics`

Visibility:

Public

---

## DL-004 — Python Version

**Date:** 2026-08-11  
**Status:** Approved

**Decision**

Use Python 3.12 for the project virtual environment.

Validated installation:

Python 3.12.5

---

## DL-005 — Python Environment

**Date:** 2026-08-11  
**Status:** Approved

**Decision**

Use Python's built-in `venv` with a project-local environment:

`.venv`

Dependency management will initially use:

- `requirements.txt`
- `requirements-dev.txt`

Packages will be introduced only when genuinely required.

---

## DL-006 — Generated Data and Git

**Date:** 2026-08-11  
**Status:** Approved

**Decision**

Generated files under:

- `data/raw/`
- `data/quarantine/`

will not normally be committed to Git.

The code, configuration, seeds and documentation required to reproduce synthetic datasets will instead be version controlled.

Small sample datasets may be considered later if they provide genuine value.
