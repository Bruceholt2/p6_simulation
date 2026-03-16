# P6 Schedule Discrete Event Simulation

A Python-based discrete event simulation that reads Primavera P6 XER files, builds an activity dependency network, and simulates project execution using SimPy with resource constraints and calendar awareness. Supports deterministic and Monte Carlo analysis across single files or multi-file portfolios.

## Features

- **XER Parsing** -- Reads P6 XER export files into pandas DataFrames with automatic type conversion for dates, numerics, and IDs
- **Portfolio Loading** -- Merges multiple XER files from a directory into a unified portfolio, enabling multi-project simulation
- **Activity Network** -- Builds a directed dependency graph with topological ordering, cycle detection, and critical path identification
- **Calendar Engine** -- Parses P6 calendar data including weekly schedules, lunch breaks, holidays, and exception dates; uses bulk week-skipping with bisect for fast finish-date calculation
- **SimPy Simulation** -- Discrete event simulation respecting all four relationship types (FS, FF, SS, SF) with lag, resource constraints, and calendar-aware scheduling; fast-path direct traversal for non-resource-constrained runs
- **Monte Carlo Analysis** -- Stochastic duration modeling with triangular and PERT distributions, seeded RNG for reproducibility, and percentile statistics (P10/P50/P80/P90)
- **Visualization** -- Gantt charts, duration histograms, S-curves, resource utilization, and criticality index charts via matplotlib

## Project Structure

```
p6_simulation/
├── run_simulation.py        # Main entry point -- loads portfolio and runs full pipeline
├── requirements.txt         # Python dependencies
├── src/
│   ├── xer_parser.py        # XER file parser
│   ├── portfolio_loader.py  # Multi-file portfolio loader and merger
│   ├── activity_network.py  # Dependency graph builder
│   ├── calendar_engine.py   # Calendar-aware time calculations
│   ├── simulation_engine.py # SimPy DES engine with Monte Carlo
│   └── visualization.py     # Chart generation (Gantt, histogram, S-curve)
├── tests/                   # pytest tests
├── data/                    # XER files (all files loaded as portfolio)
├── docs/                    # Module documentation
└── results/                 # Simulation output (charts + CSV, generated at runtime)
```

## Quick Start

### Installation

```bash
git clone https://github.com/Bruceholt2/p6_simulation.git
cd p6_simulation
pip install -r requirements.txt
```

### Run the Simulation

```bash
python run_simulation.py
```

This loads all XER files from `data/`, merges them into a portfolio, and runs the full pipeline:
1. Loads and merges all XER files via `PortfolioLoader`
2. Builds the activity network and identifies the critical path
3. Runs a deterministic simulation
4. Runs 50 Monte Carlo iterations with triangular duration uncertainty
5. Runs a resource-constrained simulation
6. Saves all charts and CSV results to `results/`

To use a different data directory:

```bash
python run_simulation.py path/to/xer_directory
```

### Run Tests

```bash
pytest tests/ -v
```

## Usage Example

```python
from src.portfolio_loader import PortfolioLoader
from src.simulation_engine import SimulationEngine, triangular_sampler
from src.visualization import gantt_chart, duration_histogram

# Load all XER files from a directory
portfolio = PortfolioLoader("data")
portfolio.summary()

# Single deterministic run
engine = SimulationEngine(portfolio, resource_constrained=False)
result = engine.run()  # convert_calendar=True by default
engine.summary(result)
gantt_chart(result, top_n=30, save_path="results/gantt.png")

# Monte Carlo with triangular durations
mc_engine = SimulationEngine(
    portfolio,
    duration_sampler=triangular_sampler(0.8, 1.0, 1.5),
    seed=42,
    resource_constrained=False,
)
results = mc_engine.run_monte_carlo(num_runs=50)  # convert_calendar=False for speed
mc_engine.monte_carlo_summary(results)
duration_histogram(results, save_path="results/histogram.png")
```

## Sample Output

### Deterministic Simulation
```
Project start:    2014-02-01 08:00:00
Project finish:   2016-11-19 12:00:00
Duration (hours): 6776.0
Activities:       3353
Critical:         153
```

### Monte Carlo (50 runs)
```
Mean duration:   7653.3 hours
Std deviation:   292.4 hours
P10 duration:    7440.0 hours
P50 duration:    7574.2 hours
P80 duration:    7707.2 hours
P90 duration:    7998.6 hours
```

## Tech Stack

- **Python 3.11+**
- **SimPy** -- Discrete event simulation framework
- **pandas** -- Data manipulation and XER table parsing
- **NumPy** -- Numerical operations and stochastic sampling
- **Matplotlib** -- Visualization (Gantt charts, histograms, S-curves)
- **pytest** -- Test framework

## Documentation

Detailed module documentation is in the `docs/` folder:

- [xer_parser.md](docs/xer_parser.md) -- XER file parser
- [portfolio_loader.md](docs/portfolio_loader.md) -- Multi-file portfolio loader
- [activity_network.md](docs/activity_network.md) -- Dependency graph and critical path
- [calendar_engine.md](docs/calendar_engine.md) -- Calendar-aware time calculations
- [simulation_engine.md](docs/simulation_engine.md) -- Simulation engine with fast-path and SimPy modes
- [visualization.md](docs/visualization.md) -- Chart generation
- [run_simulation.md](docs/run_simulation.md) -- Pipeline entry point
- [xer_format_reference.md](docs/xer_format_reference.md) -- P6 XER file format reference

## License

MIT
