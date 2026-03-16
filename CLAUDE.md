# P6 Schedule Discrete Event Simulation

## Project Overview

We are building a discrete event simulation that:

1. **Reads Primavera P6 XER files** — parses the proprietary XER format to extract schedule data (activities, relationships, resources, calendars, WBS).
2. **Builds an activity network** — constructs a dependency graph from the parsed schedule with predecessor/successor relationships.
3. **Simulates scheduling using SimPy** — runs a discrete event simulation with resource constraints and calendar awareness to model realistic project execution.

## Tech Stack

- **Python 3.11+**
- **SimPy** — discrete event simulation framework
- **pandas** — data manipulation and XER table parsing
- **NumPy** — numerical operations and stochastic duration sampling
- **Matplotlib** — visualization of simulation results (Gantt charts, histograms, S-curves)
- **SciPy** — statistical distributions for Monte Carlo duration modeling

## Project Structure

```
p6_simulation/
├── CLAUDE.md           # This file — project context for Claude
├── requirements.txt    # Python dependencies
├── src/                # Source code
│   └── __init__.py
├── tests/              # Test suite
│   └── __init__.py
├── data/               # Sample XER files
└── results/            # Simulation output (charts, CSV, logs)
```

## Coding Standards

- Follow **PEP 8** style conventions.
- Use **type hints** on all function signatures.
- Write **docstrings** for all public functions and classes.
- Keep modules focused — one responsibility per module.

## Commands

- Install dependencies: `pip install -r requirements.txt`
- Run tests: `pytest tests/`
