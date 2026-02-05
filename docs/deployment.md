Since you just gave Marvin the SSH credentials, the **`deployment.md`** file is arguably the most important one for him to see. It proves that the "Intelligence Hub" isn't just a loose collection of scripts on your laptop, but a structured platform living on his Azure infrastructure.

Here is a professional deployment log you can drop in there. It specifically highlights the **Network Security Group (NSG)** and **TimescaleDB** work you did to get the environment stable.

---

# 🚀 Deployment & Infrastructure Guide

## Environment Overview

* **Cloud Provider:** Azure
* **Host:** `20.106.102.183` (Standard D-Series VM)
* **OS:** Ubuntu 22.04 LTS
* **Database:** PostgreSQL 15 + TimescaleDB (Optimized for time-series usage data)

## Infrastructure Configuration (Completed Step 2)

1. **Network Security Groups (NSG):** * Port 22 (SSH) restricted for management.
* Port 5432 (PostgreSQL) locked to internal VNET traffic for security.


2. **Database Hardening:**
* Configured `pg_hba.conf` to allow secure local socket connections for the Python engine.
* Initialized `mvno_usage_db` with relational constraints to prevent data corruption.



## Software Stack

* **Language:** Python 3.10
* **ML Engine:** Stan / CmdStanPy (Bayesian Inference)
* **Dependency Management:** Python Virtual Environment (`venv`)

## Running the Deployment

To execute a manual deployment sync and run the intelligence pipeline:

1. **Activate Env:** `source venv/bin/activate`
2. **Verify DB:** `sudo systemctl status postgresql`
3. **Run Pipeline:** `PYTHONPATH=. python -m main`

## Maintenance Notes

* **Logs:** System logs are directed to the standard output and can be piped to `/logs` for audit trails.
* **Storage:** TimescaleDB "hypertables" automatically handle data partitioning to ensure the VM storage doesn't hit a bottleneck as CDR volume grows.