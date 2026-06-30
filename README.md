# HyH2Opt
This repository accompanies the paper ‘Green hydrogen integration in refineries: Optimizing multi-stack electrolyzer and steam-methane reformer operation under renewable intermittency and market exposure’, submitted to Applied Energy in July 2026. It has been developed as part of the WinHy project, funded by the Dutch Research Council (NWO) and Repsol S.A.

## 📝 Description
This repository provides the implementation of an optimization framework for hydrogen-intensive companies that operate with multiple hydrogen sources and are subjected to electricity and natural gas market exposure, as well as renewable energy availability. The model is designed to optimize operational scheduling of the plant according to both market participation and offshore wind energy availability. The framework is formulated as a Mixed-Integer Linear Programming (MILP) model and implemented in Python using Pyomo.

---

## ✨ Key Features
- Brownfield electrolysis integration: integrates renewable hydrogen production into existing refinery infrastructure, enabling progressive decarbonization while maintaining hydrogen supply reliability.
- Detailed electrolysis modeling: Component-level representation of multi-stack electrolyzer operation, including variable efficiency, degradation dynamics, modular scheduling, and operational state transitions.
- SMR–Electrolyzer synergy: Optimizes the interaction between conventional SMR production and renewable electrolysis to minimize hydrogen supply costs while reducing dependence on carbon-intensive generation.
- How to deal with market and VRE exposure: Co-optimization of electrolyzer operation under renewable electricity procurement agreements and electricity spot market conditions to capture intermittency and price variability effects.
- Scalability: A transferable optimization framework applicable to different industrial hydrogen systems, refinery configurations, electrolyzer sizes, and renewable energy scenarios.

---

## ⚙️ Model Highlights
- Developed as a techno-economic optimization framework for operational planning of hybrid refinery hydrogen systems.
- Minimizes total hydrogen supply cost under strict demand constraints, integrating SMR production with grid-connected renewable electrolysis.
- Captures detailed asset-level dynamics, including multi-stack electrolyzer operation, modular dispatch, efficiency variation, degradation effects, and operational state transitions.
- Enables coordinated optimization under renewable electricity and market exposure, explicitly accounting for wind PPA supply, gas and electricity spot market interactions, and intermittency-driven operational variability.

---

## 🧪 Case Study
The framework is demonstrated on a representative real-world refinery case study in Spain operating under electricity and gas spot market conditions, providing realistic insights into short-term operational flexibility. In this context the following sensitivity analyses have been performed:  
- **1**: Electrolyzer size
- **2**: Stack size
- **1**: Hydrogen remuneration scheme

---

## 📊 Key Results
- Up to **50% cost reduction** achieved by integrating electrolysis with SMR under favorable hydrogen pricing conditions.  
- Optimal multi-stack scheduling requires uniform load distribution to minimize degradation and maintain operational flexibility..  
- Hydrogen policy incentives dominate system economics, driving up to 57% LCOH variation and enabling 10–34% CO₂ reduction.  



---

## 📂 Repo Structure

```
├─ components.py                # Electrolyzer polarization curve discretization 
├─ Electrolyzer.py              # Alk model constraints
├─ H2_storage.py                # Hydrogen storage model constraints
├─ input_data.py                # csv reader 
├─ main.py                      # main file to run the model
├─ model_op_HYP_SOC.py          # components interactions and optimizer setup
├─ NGreformer.xlsx              # SMR model constraints
└─ plots.py                     # plotting script
├─ data/                    
│  ├─ EL_NG_CF_mrkt_h.csv       # electricity, natural gas market data and offshore wind capacity factor
│  ├─ comp_size.py              # Component capacities
```

---

## 🚀 Requirements

Install the necessary Python libraries using:

```bash
pip install -r requirements.txt
```

---

## 📈 How to Run

1. Open `main.py` in Jupyter Notebook or JupyterLab.
2. Ensure `EL_NG_CF_mrkt_h.csv` is in the "data" directory.
3. Ensure `components.py`, `Electrolyzer.py`, `H2_storage.py`, `input_data.py`, `model_op_HYP_SOC.py`, `NGreformer.py`, and `plots.py` are in the same directory as the main file.
4. Run all cells to execute the model and generate results.

---

## 📦 Dependencies

The code uses the following libraries:
- `pyomo`
- `pandas`
- `numpy`
- `matplotlib`
- `collections`
- `scipy`

You also need a solver like GLPK or Gurobi for Pyomo.

## 📚 Citations
If you use this repository in your work, please cite: 

*...*

---

## 📝 License

MIT License.
