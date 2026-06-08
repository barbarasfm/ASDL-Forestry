# Forestry Bioenergy and SAF Dashboard

This repository contains a Streamlit dashboard and supporting techno-economic, transport, lifecycle emissions, policy, and jobs models for comparing forest biomass pathways:

- Bioenergy: forest and mill residues to electricity
- SAF: forest residue, pulpwood, and sawmill residue to sustainable aviation fuel products

The main user-facing application is `dashboard.py`.

## Repository Structure

```text
.
├── dashboard.py                         # Streamlit dashboard entry point
├── Biomass_Transport.py                 # Biomass transport cost and routing logic
├── BioEnergy_Economics.py               # Bioenergy economics workflow
├── Bioenergy_Policy.py                  # Bioenergy policy workflow
├── SAF_Economics.py                     # SAF economics workflow
├── SAF_Policy.py                        # SAF policy workflow
├── Generate_Report.py                   # PDF/report generation helpers
├── Jobscreation.py                      # Jobs impact calculations
├── Bioenergy_dependencies/              # Bioenergy model modules
├── SAF_dependencies/                    # SAF model modules
├── LCA_dependencies/                    # Lifecycle emissions modules
├── Locations/                           # Location and supply data
├── *_plots/                             # Generated plot outputs
├── assets/                              # Static dashboard/report assets
└── environment.yml                      # Conda environment definition
```

## Setup

Create the Conda environment from `environment.yml`:

```bash
conda env create -f environment.yml
conda activate Forestry
```

## Run The Dashboard

From the repository root:

```bash
streamlit run dashboard.py
```

The dashboard is organized around the main workflow:

1. Supply chain selection
2. Biomass transport
3. Bioenergy or SAF economics
4. Lifecycle impact analysis
5. Policy analysis
6. Scenario comparison

## Main Workflows

### Supply Chain And Transport

The dashboard uses county-level biomass supply and transport assumptions to estimate available feedstock, travel distance, route options, delivered cost, and transport-related emissions.

Relevant files:

- `dashboard.py`
- `Biomass_Transport.py`
- `Locations/`

### Bioenergy Economics

The Bioenergy pathway estimates electricity production, capital costs, operating costs, financing, cash flow, LCOE, and jobs impacts.

Relevant files:

- `BioEnergy_Economics.py`
- `Bioenergy_dependencies/`
- `Bioenergy_Policy.py`

### SAF Economics

The SAF pathway estimates fuel production, SAF/diesel/naphtha revenues, capital and operating costs, MFSP, cash flow, policy impacts, and jobs impacts.

Relevant files:

- `SAF_Economics.py`
- `SAF_dependencies/`
- `SAF_Policy.py`

### Lifecycle Analysis

Lifecycle analysis modules estimate processing, transport, and production emissions for Bioenergy and SAF pathways.

Relevant files:

- `LCA_dependencies/`
- `Emissions.py`
- `dashboard.py`

## Generated Outputs

The app can regenerate plots, maps, jobs figures, and reports while running. These include:

```text
Bioenergy_plots/
SAF_plots/
LCA_plots/
Transport_plots/
Jobscreation_plots/
Policy_plots/
sc_map.html
report_Current Scenario.pdf
```

These files are useful for reports and visual inspection, but they may change simply from running the dashboard with a different active scenario or session state.