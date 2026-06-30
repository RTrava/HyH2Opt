# -*- coding: utf-8 -*-
"""
Created on Wed Jan  7 09:45:57 2026

@author: riccardotravag
"""

import pyomo.environ as pyo

def H2_Storage(b, St, delta_t):
    """
    This function constructs the Hydrogen Storage Block.
    
    Parameters:
    - b: Pyomo Block instance
    
    - St: Dictionary containing storage parameters:
        'Capacity': Max storage (kg)
        'Min_SOC': Min storage level (fraction, e.g., 0.05)
        'Initial_SOC': Starting level (fraction)
        'eta_in': Charging efficiency (fraction)
        'eta_out': Discharging efficiency (fraction)
        'max_flow_in': Max charge rate (kg/h)
        'max_flow_out': Max discharge rate (kg/h)
        
    - delta_t: Time step duration (hours)
    """
    
    m = b.model()
    
    # --- Variables ---
    # State of Charge [kg]
    b.soc = pyo.Var(m.T, domain=pyo.NonNegativeReals, bounds=(0, St['Capacity']))
    
    # H2 flow INTO storage (Charging) [kg]
    b.h_in = pyo.Var(m.T, domain=pyo.NonNegativeReals)
    
    # H2 flow OUT of storage (Discharging) [kg]
    b.h_out = pyo.Var(m.T, domain=pyo.NonNegativeReals)
    
    # Binary to prevent simultaneous charge/discharge (Optional, prevents mathematical loop flows)
    b.u_store_in = pyo.Var(m.T, domain=pyo.Binary)

    # --- Constraints ---
    
    # 1. SOC Balance: SOC(t) = SOC(t-1) + Input - Output
    def cst_soc_balance(b, t):
        # Calculate flow terms (converting mass to mass stored via efficiency)
        # Note: Assuming h_in/out are Mass quantities [kg] per step, not Rates [kg/h]
        inflow = b.h_in[t] * St['eta_in']
        outflow = b.h_out[t] / St['eta_out']
        
        if t == 0:
            soc_prev = St['Capacity'] * St['Initial_SOC']
        else:
            soc_prev = b.soc[t-1]
            
        return b.soc[t] == soc_prev + inflow - outflow
    b.cst_soc_balance = pyo.Constraint(m.T, rule=cst_soc_balance)

    # 2. Minimum SOC limit, constraint set to represent the gas grid which always contains 1t of H2
    def cst_min_soc(b, t):
        return b.soc[t] >= St['Capacity'] * St['Min_SOC']
    b.cst_min_soc = pyo.Constraint(m.T, rule=cst_min_soc)

    # 3. Flow Rate Limits (Convert kg/h parameter to kg/step limit)
    def cst_max_in(b, t):
        return b.h_in[t] <= St['max_flow_in'] * delta_t * b.u_store_in[t]
    b.cst_max_in = pyo.Constraint(m.T, rule=cst_max_in)
    
    def cst_max_out(b, t):
        return b.h_out[t] <= St['max_flow_out'] * delta_t * (1 - b.u_store_in[t])
    b.cst_max_out = pyo.Constraint(m.T, rule=cst_max_out)
    
    # 4. Cyclic Constraint (End SOC >= Start SOC)
    def cst_cyclic(b):
        return b.soc[m.T.last()] >= St['Capacity'] * St['Initial_SOC']
    b.cst_cyclic = pyo.Constraint(rule=cst_cyclic)