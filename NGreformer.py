#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Dec  5 14:17:45 2025

@author: trava
"""

import pyomo.environ as pyo

def SMR_u(b, SMR, delta_t):
    
    """
    This function constructs the SMR Block.
     
    Parameters:
    - b: Pyomo Block instance
    
    - SMR: Dictionary containing SMR parameters:
        'SMR_cap': [kg/15min] Nominal Hydrogen Production Capacity 
        'eta_full': [-] Efficiency ( kg H2 out / kg NG in)
        'eta_min': [-] Efficiency ( kg H2 out / kg NG in)
        'eta_smr': [-] Efficiency ( kg H2 out / kg NG in)
        'LHV_NG': [MWh/kg_NG] Lower Heating Value of Natural Gas (approx)
        'LHV_H2': [MWh/kg_H2]
        'CO2_em': [kgCO2/kgNG] ref chrome-extension://efaidnbmnnnibpcajpcglclefindmkaj/https://ocw.tudelft.nl/wp-content/uploads/Summary_table_with_heating_values_and_CO2_emissions.pdf
        'min_load': [p.u.] Minimum stable operation
        'ramp_rate_hr': [p.u./h] Ramp rate (10% per hour)
        'T_su': [h] Startup duration
        'su_cons': [p.u.] Gas consumption during startup (approx 30% of nominal)
        'sb_cons': [p.u.] Gas consumption in Standby (e.g., 10% of nominal input)
        'C_su': [EUR/event] Wear and tear cost per startup
        
    - delta_t: Time step duration (hours)
    """
    
    m = b.model()#Access the parent model to get Sets (T, U) and external variables
    
    # --- SMR Variables ---
    # State Binaries
    b.s_smr_on = pyo.Var(m.T, domain=pyo.Binary) # On: Producing H2
    b.s_smr_su = pyo.Var(m.T, domain=pyo.Binary) # Startup: 8 hours fixed
    b.s_smr_off = pyo.Var(m.T, domain=pyo.Binary) # Off
    b.s_smr_sb  = pyo.Var(m.T, domain=pyo.Binary) # Standby (Hot, Ready, No H2)
    # Transitions
    b.smr_off_su = pyo.Var(m.T, domain=pyo.Binary) # Start sequence
    b.smr_su_on  = pyo.Var(m.T, domain=pyo.Binary) # Finish startup
    b.smr_on_sb  = pyo.Var(m.T, domain=pyo.Binary) # On -> Standby
    b.smr_sb_on  = pyo.Var(m.T, domain=pyo.Binary) # Standby -> On (Instant)
    b.smr_sb_off = pyo.Var(m.T, domain=pyo.Binary) # Standby -> Off     b.smr_on_off = pyo.Var(m.T, domain=pyo.Binary) # Shut down     
    b.smr_on_off = pyo.Var(m.T, domain=pyo.Binary) # On -> Off
    # Operations
    b.h_smr    = pyo.Var(m.T, domain=pyo.NonNegativeReals) # H2 production [kg]
    b.q_ng_smr = pyo.Var(m.T, domain=pyo.NonNegativeReals) # NG Consumption [kg]
    
    
    # --- Pre-calculation for Variable Efficiency ---
    # We calculate the linear coefficients (Input = m*Output + c)
    # Point 1: Full Load
    p_full = SMR['SMR_cap']
    q_full = p_full / SMR['eta_full']
    
    # Point 2: Min Load
    p_min = SMR['SMR_cap'] * SMR['eta_min']
    q_min = p_min / SMR['eta_min']
    
    # Linear Regression (Slope and Intercept)
    # Slope (Marginal fuel consumption)
    slope = (q_full - q_min) / (p_full - p_min)
    # Intercept (Fixed fuel consumption when ON)
    intercept = q_full - (slope * p_full)
    
    
    # 1. State Logic (Mutually Exclusive)
    def cst_smr_state_sum(b, t):
        return b.s_smr_on[t] + b.s_smr_su[t] + b.s_smr_sb[t] + b.s_smr_off[t] == 1
    b.cst_smr_state_sum = pyo.Constraint(m.T, rule=cst_smr_state_sum)
    
    # 2. State Transitions
    def cst_smr_trans_su(b, t):
        if t == 0: return pyo.Constraint.Skip
        # Evolution of Startup State
        return b.s_smr_su[t] - b.s_smr_su[t-1] == b.smr_off_su[t] - b.smr_su_on[t]
    b.cst_smr_trans_su = pyo.Constraint(m.T, rule=cst_smr_trans_su)

    def cst_smr_trans_on(b, t):
        if t == 0: return pyo.Constraint.Skip
        # Evolution of On State
        return b.s_smr_on[t] - b.s_smr_on[t-1] == b.smr_su_on[t] + b.smr_sb_on[t] - b.smr_on_sb[t] - b.smr_on_off[t]
    b.cst_smr_trans_on = pyo.Constraint(m.T, rule=cst_smr_trans_on)
    
    def cst_smr_trans_sb(b, t):
        if t == 0: return pyo.Constraint.Skip
        # Balance: Previous + (In from ON) - (Out to ON) - (Out to OFF)
        return b.s_smr_sb[t] - b.s_smr_sb[t-1] == b.smr_on_sb[t] - b.smr_sb_on[t] - b.smr_sb_off[t]# Standby State (Enters from ON; Exits to ON or OFF)
    b.cst_smr_trans_sb = pyo.Constraint(m.T, rule=cst_smr_trans_sb)
    
    def cst_smr_startup_duration(b, t):
        # If we finish startup at t (smr_su_on=1), we must have started it SMR['T_su']  ago
        if t < SMR['T_su'] : 
            return b.smr_su_on[t] == 0
        return b.smr_off_su[t - SMR['T_su'] ] >= b.smr_su_on[t]
    b.cst_smr_startup_duration = pyo.Constraint(m.T, rule=cst_smr_startup_duration)
    
    def cst_smr_startup_lock(b, t):
        # Once started, must finish (cannot abort startup in this simplified logic)
        if t < SMR['T_su'] : return pyo.Constraint.Skip
        # Sum of SU states in the window must equal SMR['T_su']  if we just turned ON
        return sum(b.s_smr_su[t-k] for k in range(1, SMR['T_su'] +1)) >= SMR['T_su']  * b.smr_su_on[t]
    b.cst_smr_startup_lock = pyo.Constraint(m.T, rule=cst_smr_startup_lock)

    # Operational Limits (40% - 100%)
    def cst_smr_min_load(b, t):
        return b.h_smr[t] >= SMR['SMR_cap'] * SMR['min_load'] * b.s_smr_on[t]
    b.cst_smr_min_load = pyo.Constraint(m.T, rule=cst_smr_min_load)

    def cst_smr_max_load(b, t):
        return b.h_smr[t] <= SMR['SMR_cap'] * b.s_smr_on[t]
    b.cst_smr_max_load = pyo.Constraint(m.T, rule=cst_smr_max_load)

    # Ramp Rates (10%/hour)
    smr_ramp = SMR['SMR_cap'] * SMR['ramp_rate_hr'] * delta_t # Capacity * 10%/h * 0.25h
    
    def cst_smr_ramp_up(b, t):
        if t == 0: return pyo.Constraint.Skip
        
        return b.h_smr[t] - b.h_smr[t-1] <= smr_ramp + SMR['SMR_cap'] * SMR['min_load'] * (1 - b.s_smr_on[t-1])# Only constrain ramp if staying ON. If starting up (su_on=1), jump is allowed (handled by min load)
    b.cst_smr_ramp_up = pyo.Constraint(m.T, rule=cst_smr_ramp_up)
    
    def cst_smr_ramp_down(b, t):
        if t == 0: return pyo.Constraint.Skip
        return b.h_smr[t-1] - b.h_smr[t] <= smr_ramp + SMR['SMR_cap'] * (1 - b.s_smr_on[t])
    b.cst_smr_ramp_down = pyo.Constraint(m.T, rule=cst_smr_ramp_down)

    # 6. Gas Consumption Calculation
    def cst_smr_gas_cons(b, t):
        
        # q_op = (b.h_smr[t]) / SMR['eta_smr']# Consumption during Operation [kg] = (H2_kg ) / Efficiency
        q_op = (slope * b.h_smr[t]) + (intercept * b.s_smr_on[t])
        
        q_su = SMR['nominal_input'] * SMR['su_cons'] * b.s_smr_su[t]# Consumption during Startup [kg] (Assumed constant % of nominal input)
        # q_su = q_su_n * b.s_smr_su[t]
        
        q_sb = SMR['nominal_input'] * SMR['sb_cons'] * b.s_smr_sb[t]# Consumption during sb [kg] (Assumed constant % of nominal input)
        # q_sb = q_sb_n * b.s_smr_sb[t]
       
        return b.q_ng_smr[t] == q_op + q_su +q_sb
    b.cst_smr_gas_cons = pyo.Constraint(m.T, rule=cst_smr_gas_cons)
    