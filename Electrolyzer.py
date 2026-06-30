#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Dec  5 14:34:21 2025

@author: trava
"""

import pyomo.environ as pyo

def ALK_u(b, El, delta_t):
    
    """
    This function constructs the Alkaline Block.
    Parameters:
    - b: Pyomo Block instance
    
    - EL: Dictionary containing storage parameters:
        'El_cap_tot': Total electrolyzer capacity [MW]
        'El_cap': Electrolyzer module capacity [MW]
        'N_u': number of modules
        'N_stacks_per_module': 
        'Stack_cap':          
        'P_min': % minimum module load
        'P_sb': % Power consumption in stand-by state
        'H_standby_hours': h of sb before turning off      
        'hsb-on_lag': [h] time lag before starting H2 production during transition hsb-on 
        'off-on_lag': [h] time lag before starting H2 production during transition hsb-on
        'ramp_up': fraction of capacity per time step 
        'ramp_down': fraction of capacity per time step
        # --- degr PARAMETERS ---
        'C_op': Operational degradation cost [EUR/MW/hr]
        'C_cold': Shutdown degradation cost [EUR/MW/event]
        'degr': efficiency loss per hour of operation
        'degr_cold': efficiency loss per per cold start
        'LHV_H2': [MWh/kg] Lower Heating Value to calculate waste heat
         
    - delta_t: Time step duration (hours)
    """
    
    m = b.model()#Access the parent model to get Sets (T, U) and external variables
    
    # --- Electrolyzer Variables ---
    b.p_el_u = pyo.Var(m.TU, bounds = (0, El['El_cap'])) # power input in the electrolyzer unit u in hour t [MW]
    b.h_el_u = pyo.Var(m.TU, bounds = (0, None)) # hydorgen produced in the electrolyzer unit u in hour t  [kg/h]
    b.p_s    = pyo.Var(m.TU, bounds = (0, None)) # power for unit u , time t
    #status
    b.z_on  = pyo.Var(m.TU, domain=pyo.Binary) # binary variable for on state
    b.z_off = pyo.Var(m.TU, domain=pyo.Binary) # binary variable for off state
    b.z_psb = pyo.Var(m.TU, domain=pyo.Binary) # binary variable for pressurized standby state (new)
    b.z_hsb = pyo.Var(m.TU, domain=pyo.Binary) # binary variable for hot standby state (new)     
    #Transition
    b.y_off_on     = pyo.Var(m.TU, domain=pyo.Binary) # Off --> On (Cold start)
    b.y_psb_on     = pyo.Var(m.TU, domain=pyo.Binary) # Pressurized SB --> On (Warm start 1)
    b.y_hsb_on     = pyo.Var(m.TU, domain=pyo.Binary) # Hot SB --> On (Warm start 2)
    b.y_on_psb     = pyo.Var(m.TU, domain=pyo.Binary) # On --> Pressurized SB
    b.y_psb_hsb    = pyo.Var(m.TU, domain=pyo.Binary) # Pressurized SB --> Hot SB
    b.y_hsb_off    = pyo.Var(m.TU, domain=pyo.Binary) # Hot SB --> Off
    b.y_hsb_boost  = pyo.Var(m.TU, domain=pyo.Binary) # Action of applying power to stay in HSB
    # Power lag/delay variables
    b.z_lag_on = pyo.Var(m.TU, domain=pyo.Binary) 
    b.h_sink   = pyo.Var(m.TU, domain=pyo.NonNegativeReals) 
    #Degradation
    b.degr_u = pyo.Var(m.TU, bounds=(0,1))  # cumulative degradation fraction (0=no loss, 1=fully degraded)

    b.xi = pyo.Var(m.TU,bounds = (0, None)) # Auxiliary variable for each conic region
    
    
    # Status
    def cst_bin(b,t,u):
        return b.z_on[t,u] + b.z_psb[t,u] + b.z_hsb[t,u] + b.z_off[t,u] == 1
    b.cst_bin = pyo.Constraint(m.TU, rule=cst_bin)
    
    # Power consumption, Only On, Pressurized and hot SB consume power
    def cst_p_sold_tot(b,t,u):
        return b.p_el_u[t,u]==b.p_s[t,u] + El['P_sb']*El['El_cap'] * (b.z_psb[t,u] + b.y_hsb_boost[t,u])
    b.cst_p_sold_tot = pyo.Constraint(m.TU, rule = cst_p_sold_tot)
    
    def cst_boost_in_hsb(b,t,u): #Boosting can only happen in HSB
        return b.y_hsb_boost[t,u] <= b.z_hsb[t,u]
    b.cst_boost_in_hsb = pyo.Constraint(m.TU, rule = cst_boost_in_hsb)
    
    def cst_ps_lb(b,t,u):
        return b.p_s[t,u]>=b.z_on[t,u]*El['P_min']*El['El_cap']
    b.cst_ps_lb = pyo.Constraint(m.TU, rule = cst_ps_lb)
   
    def cst_ps_ub(b,t,u):
        return b.p_s[t,u]<=b.z_on[t,u]*El['El_cap']
    b.cst_ps_ub= pyo.Constraint(m.TU, rule = cst_ps_ub)
    
    
    #------------------ MIN and MAX SB ------------------ 
    
    
    def cst_min_hsb_for_shutdown(b, t, u):#allows to shut down after T_sb_max.
        T_hsb_min = int(El['H_standby_hours'] / delta_t) # 
        
        if t < T_hsb_min:
            # Not possible to have been in SB for T_sb_max steps yet
            return b.y_hsb_off[t,u] == 0
        else:
            # Sum of standby steps in the *past* T_sb_max time steps
            past_hsb_steps = sum(b.z_hsb[k,u] for k in range(t-T_hsb_min, t))
            
            # y_sb_off can only be 1 if past_sb_steps is >= T_sb_max
            return T_hsb_min * b.y_hsb_off[t,u] <= past_hsb_steps
    b.cst_min_hsb_for_shutdown = pyo.Constraint(m.TU, rule=cst_min_hsb_for_shutdown)
    
    def cst_max_hsb_boost(b, t, u):
        """
        This constraint models the 8-hour thermal decay.
        In any 8-hour + 1-timestep window (N+1 steps):
        1. If no boost (y_hsb_boost) occurs, the unit can be in HSB
           for a maximum of N steps (it is forced to exit).
        2. If one or more boosts (y_hsb_boost) occur in the window,
           this limit is relaxed, allowing the unit to stay in HSB.
        """
        max_hsb_steps = int(El['H_standby_hours'] / delta_t)
        N_window = max_hsb_steps + 1 # We check a window of N+1 steps
        t_list = sorted(list(m.T))
        idx = t_list.index(t)
        if idx < max_hsb_steps: 
            return pyo.Constraint.Skip
        else:
            
            window_steps = [t_list[idx - k] for k in range(0, N_window)]# Get the timesteps for the full window ending at t
            hsb_in_window = sum(b.z_hsb[step, u] for step in window_steps)# Sum of HSB states in the window
            boosts_in_window = sum(b.y_hsb_boost[step, u] for step in window_steps)# Sum of "boosts" in the window
            
            return hsb_in_window <= max_hsb_steps + boosts_in_window # Allow staying in HSB (sum=33) ONLY if a boost happens (sum >= 1)
    b.cst_max_hsb_boost = pyo.Constraint(m.TU, rule=cst_max_hsb_boost)
    
    
    #------------------ H2 lag DEFINITION ------------------ 
   
    
    def cst_z_lag_on(b, t, u):# If z_on=1 and coming from Off or HSB, it enters a lag state
        # z_lag_on must be 1 if z_on=1 AND the unit just transitioned from Off or HSB (at time t)
        # Or if it was in lag at t-1 AND the lag time limit isn't reached
        return b.z_lag_on[t,u] <= b.z_on[t,u]
    b.cst_z_lag_on = pyo.Constraint(m.TU, rule=cst_z_lag_on)

    T_lag_hsb = int(El['hsb-on_lag'] / delta_t) 
    T_lag_off = int(El['off-on_lag'] / delta_t)

    def cst_hsb_lag(b, t, u):# If z_on is entered from HSB (y_hsb_on), the first T_lag_hsb steps must have z_lag_on=1
        t_list = sorted(list(m.T))
        idx = t_list.index(t)
        if idx < T_lag_hsb: 
            return pyo.Constraint.Skip
        else:
            # sum of z_lag_on must be at least T_lag_hsb after y_hsb_on
            return sum(b.z_lag_on[k, u] for k in range(t-T_lag_hsb, t)) >= T_lag_hsb * b.y_hsb_on[t-T_lag_hsb,u]
    b.cst_hsb_lag = pyo.Constraint(m.TU, rule=cst_hsb_lag)

    def cst_off_lag(b, t, u):# If z_on is entered from Off (y_off_on), the first T_lag_off steps must have z_lag_on=1
        t_list = sorted(list(m.T))
        idx = t_list.index(t)
        if idx < T_lag_off: 
            return pyo.Constraint.Skip
        else:
            return sum(b.z_lag_on[k, u] for k in range(t-T_lag_off, t)) >= T_lag_off * b.y_off_on[t-T_lag_off,u]
    b.cst_off_lag = pyo.Constraint(m.TU, rule=cst_off_lag)
        

    #------------------ STATES DEFINITION ------------------ 
    
    
    def cst_state_on(b, t, u):
         t_list = sorted(list(m.T))
         t0 = t_list[0]
         if t == t0:
             return pyo.Constraint.Skip#b.z_on[t,u] == b.y_psb_on[t,u] 
         else:
             # State at t is state at t-1 + transitions IN - transitions OUT
             return b.z_on[t,u] == b.z_on[t-1,u] + b.y_off_on[t,u] + b.y_psb_on[t,u] + b.y_hsb_on[t,u] - b.y_on_psb[t,u]
    b.cst_state_on = pyo.Constraint(m.TU, rule=cst_state_on)

    def cst_state_psb(b, t, u):
        t_list = sorted(list(m.T))
        t0 = t_list[0]
        if t == t0:
            return pyo.Constraint.Skip#b.z_psb[t,u] == 1 - b.y_psb_on[t,u]
        else:
            # State at t is state at t-1 + transitions IN - transitions OUT
            return b.z_psb[t,u] == b.z_psb[t-1,u] + b.y_on_psb[t,u] - b.y_psb_on[t,u] - b.y_psb_hsb[t,u]
    b.cst_state_psb = pyo.Constraint(m.TU, rule=cst_state_psb)

    def cst_state_hsb(b, t, u):
        t_list = sorted(list(m.T))
        t0 = t_list[0]
        if t == t0:
            return pyo.Constraint.Skip#b.z_hsb[t,u] == 0
        else:
            # State at t is state at t-1 + transitions IN - transitions OUT
            return b.z_hsb[t,u] == b.z_hsb[t-1,u] + b.y_psb_hsb[t,u] - b.y_hsb_on[t,u] - b.y_hsb_off[t,u]
    b.cst_state_hsb = pyo.Constraint(m.TU, rule=cst_state_hsb)

    def cst_state_off(b, t, u):
        t_list = sorted(list(m.T))
        t0 = t_list[0]
        if t == t0:
            return pyo.Constraint.Skip#b.z_off[t,u] == 0# 
        else:
            return b.z_off[t,u] == b.z_off[t-1,u] + b.y_hsb_off[t,u] - b.y_off_on[t,u]
    b.cst_state_off = pyo.Constraint(m.TU, rule=cst_state_off)
    
    
    #------------------ STATE TRANSITION ------------------
    
    
    def cst_off_on(b, t, u):# Allowed transition: Off(t-1) -> On(t) - no lag power at t-1 
        t_list = sorted(list(m.T))
        t0 = t_list[0]
        if t == t0:
            return pyo.Constraint.Skip
        else:
            return b.y_off_on[t,u] <= b.z_off[t-1,u]
    b.cst_off_on = pyo.Constraint(m.TU, rule=cst_off_on)

    
    def cst_psb_on(b, t, u):# Allowed transition: PSB(t-1) -> On(t) - no lag
        t_list = sorted(list(m.T))
        t0 = t_list[0]
        if t == t0:
            return b.y_psb_on[t,u] == 0
        else:
            return b.y_psb_on[t,u] <= b.z_psb[t-1,u]
    b.cst_psb_on = pyo.Constraint(m.TU, rule=cst_psb_on)
    
    
    def cst_hsb_on(b, t, u):# Allowed transition: HSB(t-1) -> On(t) - requires a 30 min delay
        t_list = sorted(list(m.T))
        t0 = t_list[0]
        if t == t0:
            return b.y_hsb_on[t,u] == 0
        else:
            return b.y_hsb_on[t,u] <= b.z_hsb[t-1,u]
    b.cst_hsb_on = pyo.Constraint(m.TU, rule=cst_hsb_on)
    
    
    def cst_on_psb(b, t, u):# Only allowed transition: On(t-1) -> PSB(t)
        t_list = sorted(list(m.T))
        t0 = t_list[0]
        if t == t0:
            return b.y_on_psb[t,u] == 0
        else:
            return b.y_on_psb[t,u] <= b.z_on[t-1,u]
    b.cst_on_psb = pyo.Constraint(m.TU, rule=cst_on_psb)


    def cst_psb_hsb(b, t, u):# Transition: PSB(t-1) -> HSB(t)
        t_list = sorted(list(m.T))
        t0 = t_list[0]
        if t == t0:
            return b.y_psb_hsb[t,u] == 0
        else:
            return b.y_psb_hsb[t,u] <= b.z_psb[t-1,u]
    b.cst_psb_hsb = pyo.Constraint(m.TU, rule=cst_psb_hsb)

    
    def cst_hsb_off(b, t, u):# Transition: HSB(t-1) -> Off(t)
        t_list = sorted(list(m.T))
        t0 = t_list[0]
        if t == t0:
            return b.y_hsb_off[t,u] == 0
        else:
            return b.y_hsb_off[t,u] <= b.z_hsb[t-1,u]
    b.cst_hsb_off = pyo.Constraint(m.TU, rule=cst_hsb_off)
    
    
    def cst_one_transition_per_step(b, t, u):
        """A unit can only make one transition per time step."""
        return b.y_off_on[t,u] + b.y_psb_on[t,u] + b.y_hsb_on[t,u] + b.y_on_psb[t,u] + b.y_psb_hsb[t,u] + b.y_hsb_off[t,u] <= 1
    b.cst_one_transition_per_step = pyo.Constraint(m.TU, rule=cst_one_transition_per_step)

   
    #------------------ DEGRADATION ------------------ 
    
    
    def cst_degradation(b, t, u):
        degr_full = El['degr']
        degr_cold = El['degr_cold']
        t_list = sorted(list(m.T))
        t0 = t_list[0]
            
        if t == t0:
            prev_degr_val = 0.0
            prev_on_val = 0.0
            
            if 'prev_degr' in El:
                prev_degr_val = El['prev_degr'][u]
            if 'prev_on' in El:
                prev_on_val = El['prev_on'][u]
                
            return b.degr_u[t,u] == prev_degr_val + delta_t * (degr_full * prev_on_val) + degr_cold * b.y_off_on[t,u]
        else:
            # degradation accumulates with operation
            return b.degr_u[t,u] == b.degr_u[t-1,u] + delta_t * (degr_full * b.z_on[t-1,u]) + degr_cold * b.y_off_on[t,u]
    b.cst_degradation = pyo.Constraint(m.TU, rule=cst_degradation)
         
    # #------------------ Ramp rates ------------------ 
    # def cst_ramp_up(b, t, u):
    #     ramp_up = El['ramp_up'] * El['El_cap']
    #     t_list = sorted(list(m.T))
    #     t0 = t_list[0]
    #     if t == t0:
    #         return pyo.Constraint.Skip
    #     else:
    #         return b.p_el_u[t,u] - b.p_el_u[t-1,u] <= ramp_up
    # b.cst_ramp_up = pyo.Constraint(m.TU, rule=cst_ramp_up)

    # def cst_ramp_down(b, t, u):
    #     ramp_down = El['ramp_down'] * El['El_cap']
    #     t_list = sorted(list(m.T))
    #     t0 = t_list[0]
    #     if t == t0:
    #         return pyo.Constraint.Skip
    #     else:
    #         return b.p_el_u[t-1,u] - b.p_el_u[t,u] <= ramp_down
    # b.cst_ramp_down = pyo.Constraint(m.TU, rule=cst_ramp_down)
    
    #------------------ Hydrogen production ------------------
    def cst_h_prod(b, t, u):
        h_theor = El['D_0']*b.z_on[t,u] + El['D_1'] * b.p_s[t,u]  + El['D_2']*b.xi[t,u]#*(1 - b.z_lag_on[t,u])
        return b.h_el_u[t,u] == (h_theor * (1 - b.degr_u[t,u])) * delta_t - b.h_sink[t,u]
    b.cst_h_prod = pyo.Constraint(m.TU, rule = cst_h_prod)
    
    def cst_force_h_zero_lag(b, t, u):
        # If z_lag_on is 1, h_el_u must be <= 0 (i.e., 0)
        # BigM just needs to be larger than max production
        return b.h_el_u[t,u] <= 50000 * (1 - b.z_lag_on[t,u])
    b.cst_force_h_zero_lag = pyo.Constraint(m.TU, rule=cst_force_h_zero_lag)

    def cst_sink_limit(b, t, u):
        # If z_lag_on is 0, sink must be 0 (normal operation)
        # If z_lag_on is 1, sink can be positive (absorbing the fake production)
        return b.h_sink[t,u] <= 50000 * b.z_lag_on[t,u]
    b.cst_sink_limit = pyo.Constraint(m.TU, rule=cst_sink_limit)
    
    def cst_h_prod_q(b,t,u):
        return b.xi[t,u]>=b.p_s[t,u]**2
    b.cst_h_prod_q = pyo.Constraint(m.TU, rule = cst_h_prod_q)
    