import pyomo.environ as pyo
import numpy as np
import pandas as pd
from functools import partial # Needed to pass arguments to the block
from NGreformer import SMR_u
from Electrolyzer import ALK_u
from H2_storage import H2_Storage

################# Model for conic hydrogen production over the whole operating range (15-100%) #################

def model_HYP_SOC(delta_t, config_dict,El,St,Wind,Demand,Prices, smr, prev_state=None):
    
     solver = config_dict['solver'] # Choose solver
     
     m = pyo.ConcreteModel() # Initialize optimization model
     # delta_t = 15/60         # Define the length of the time step in hours (15 minutes = 0.25 hours)
     
     #%%  Define sets
     T   = np.array([t for t in range(0, Prices['N_t'])]) # Sets with timesteps
     m.T = pyo.Set(initialize=T) 
     
     # Define sets for untis
     U      = np.array([m for m in range(0, El['N_u'])]) # Sets with electrolyzer units
     m.U    = pyo.Set(initialize=U)
     m.TU   = pyo.Set(initialize= m.T * m.U)
     
    
     #%% Define the optimization variables
     
     # --- market related Variables ---
     m.p_wind_to_h  = pyo.Var(m.T, bounds = (0, Wind['W'])) # wind energy exploiter by the EL in ts t [MWh]
     m.p_sold       = pyo.Var(m.T, bounds = (0, Wind['W'])) # energy sold to the grid in ts t [MWh] 
     m.p_purch      = pyo.Var(m.T, bounds = (0, El['El_cap_tot'])) # energy sold to the grid in ts t [MWh] 
         
     m.h2_wind = pyo.Var(m.T, domain=pyo.NonNegativeReals) # H2 mass from Wind [kg]
     m.h2_grid = pyo.Var(m.T, domain=pyo.NonNegativeReals) # H2 mass from Grid [kg]
              
     
     #%%import blocks
     
     # =================================================================
     #                      === ELECTROLYZER ===
     # =================================================================      
     
     m.ALK = pyo.Block(rule=partial(ALK_u, El=El, delta_t=delta_t))     
     
     # =================================================================
     #                          == SMR ===
     # =================================================================
     m.SMR = pyo.Block(rule=partial(SMR_u, SMR=smr, delta_t=delta_t))
     
     # =================================================================
     #                          == H2 storage ===
     # =================================================================
     m.H2_st = pyo.Block(rule=partial(H2_Storage, St=St, delta_t=delta_t))
     
     #%%  Define optimization constraints

     # =================================================================
     # Rolling Horizon Linking Constraints
     # =================================================================
     # If previous state exists, link t=0 to the previous week's end state
     if prev_state is not None:
         
         # 1. Electrolyzer Startup Link
         # If it was OFF previously (0) and ON now (1), y_off_on must be 1.
         def cst_alk_link_su(m, u):
             return m.ALK.y_off_on[0, u] >= m.ALK.z_on[0, u] - prev_state['alk_on'][u]
         m.cst_alk_link_su = pyo.Constraint(m.U, rule=cst_alk_link_su)
         
         # Prevent Off -> PSB transition at t=0         
         def cst_alk_link_psb(m, u):
             return m.ALK.z_psb[0, u] <= prev_state['z_psb'][u]
         m.cst_alk_link_psb = pyo.Constraint(m.U, rule=cst_alk_link_psb)

         # Prevent Off -> HSB transition at t=0
         def cst_alk_link_hsb(m, u):
             return m.ALK.z_hsb[0, u] <= prev_state['z_hsb'][u]
         m.cst_alk_link_hsb = pyo.Constraint(m.U, rule=cst_alk_link_hsb)
         
         # 2. SMR Startup Link
         def cst_smr_link_su(m):
             return m.SMR.s_smr_su[0] >= m.SMR.s_smr_on[0] - prev_state['smr_on']
         m.cst_smr_link_su = pyo.Constraint(rule=cst_smr_link_su)

     # Energy balance
     
     # Input Balance
     # The EL is fed by (Used Wind) + (Grid Imports)
     def cst_el_bal(m, t):
         total_el_power = sum(m.ALK.p_el_u[t,u] for u in m.U)
         return total_el_power == m.p_wind_to_h[t] + m.p_purch[t]
     m.cst_el_bal = pyo.Constraint(m.T, rule=cst_el_bal)
     
     
     # Wind Farm Output Balance
     # Total Wind = Used + Sold + curtailed
     # Curtailments/Waste allowed
     def cst_wind_bal(m, t):
         return m.p_wind_to_h[t] + m.p_sold[t] <= Wind['P_w'][t]
     m.cst_wind_bal = pyo.Constraint(m.T, rule=cst_wind_bal)
         
     def cst_global_demand(m,t):
         #Sum total H2 from Electrolyzer (h_el_u is in kg)
         total_h2_alk = sum(m.ALK.h_el_u[t,u] for u in m.U)
         
         #Sum total H2 from SMR (h_smr is rate [kg], so multiply by delta_t)
         total_h2_smr = m.SMR.h_smr[t]
                  
         # Storage Flows
         h2_storage_out = m.H2_st.h_out[t]
         h2_storage_in = m.H2_st.h_in[t]
            
         return total_h2_alk + total_h2_smr + h2_storage_out == Demand['H_target'] + h2_storage_in
     
     m.cst_global_demand = pyo.Constraint(m.T, rule=cst_global_demand)
     
     def cst_h2_attribution_bal(m, t):
         total_h2_alk = sum(m.ALK.h_el_u[t,u] for u in m.U)
         return m.h2_wind[t] + m.h2_grid[t] == total_h2_alk
     m.cst_h2_attribution_bal = pyo.Constraint(m.T, rule=cst_h2_attribution_bal)
    
     def cst_h2_wind_limit(m, t):
         return m.h2_wind[t] <= m.p_wind_to_h[t] * El['eta_max']
     m.cst_h2_wind_limit = pyo.Constraint(m.T, rule=cst_h2_wind_limit)
    
     def cst_h2_grid_limit(m, t):
         return m.h2_grid[t] <= m.p_purch[t] * El['eta_max']
     m.cst_h2_grid_limit = pyo.Constraint(m.T, rule=cst_h2_grid_limit)
     
     #%%  Define the objective function
     m.obj_val = pyo.Objective(expr = 
                               #electricity costs
                               sum((Prices['pi_e'][t] + Prices['nr_tariff'] + Prices['C_var']) * m.p_purch[t] * delta_t for t in m.T)
                               + sum((Prices['pi_ppa'] + Prices['nr_tariff']) * Wind['P_w'][t] * delta_t for t in m.T)
                               #EL degradation
                               + sum((El['degr_cold']*El['C_stack']/El['lifetime'])*m.ALK.y_off_on[t,u] for t in m.T for u in m.U)#El['C_cold']*m.ALK.y_off_on[t,u] * El['El_cap']
                               + sum((El['degr']*El['C_stack']/El['lifetime'])*m.ALK.z_on[t,u]*delta_t for t in m.T for u in m.U)#El['C_op']*m.ALK.z_on[t,u]*delta_t * El['El_cap']
                               #SMR
                               + sum(Prices['pi_ng'][t] * m.SMR.q_ng_smr[t] for t in m.T) # NG Fuel Cost
                               + sum(smr['C_su'] * m.SMR.smr_off_su[t] for t in m.T)                # Startup Cost
                               #Earnings
                               - sum(Prices['pi_e'][t] * m.p_sold[t] * delta_t for t in m.T)
                               # --- Earnings from Premiums ---
                               - sum(Prices['prem_green'] * m.h2_wind[t] for t in m.T)
                               - sum(Prices['prem_grid'] * m.h2_grid[t] for t in m.T)
                               , sense=pyo.minimize)
     
     #%% ############# Solve the problem ##################
     # Define solver
     Solver = pyo.SolverFactory(solver)
     if solver == 'gurobi':
         Solver.options['NonConvex'] = 2
         Solver.options['threads'] = config_dict['threads']
         Solver.options['NodefileStart'] = 0.5   # start writing nodes to disk after 0.5 GB per thread
         Solver.options['MIPGap'] = 0.01
         
     SolverResults = Solver.solve(m, tee=True)
     SolverResults.write()

     if config_dict['print_model']==1:
        m.pprint()

     comp_time =  SolverResults.Solver.system_time

     
     #%% ############# Save results ##################
     obj_val=m.obj_val()
     
     c_el    = np.atleast_2d(np.array([Prices['pi_e']])).T
     c_ng    = np.atleast_2d(np.array([Prices['pi_ng']])).T
     P_w     =np.atleast_2d(np.array([Wind['P_w']])).T
     p_w_t_h = np.atleast_2d(np.array([m.p_wind_to_h[t].value for t in m.T])).T
     
     p_grid_s   = np.atleast_2d(np.array([m.p_sold[t].value for t in m.T])).T
     p_grid_p   = np.atleast_2d(np.array([m.p_purch[t].value for t in m.T])).T
     
     'electrolyzer'
     p_el       =  np.atleast_2d(np.array([sum(m.ALK.p_el_u[t,u].value for u in m.U) for t in m.T])).T
     h_el       =  np.atleast_2d(np.array([sum(m.ALK.h_el_u[t,u].value for u in m.U) for t in m.T])).T
     P_curt     = P_w - (p_grid_s+p_w_t_h)
     
     p_el_u = np.reshape(np.array([m.ALK.p_el_u[t,u].value for t in m.T for u in m.U]), (Prices['N_t'],El['N_u']))
     h_el_u = np.reshape(np.array([m.ALK.h_el_u[t,u].value for t in m.T for u in m.U]), (Prices['N_t'],El['N_u']))
    
     z_on       = np.reshape(np.array([m.ALK.z_on[t,u].value for t in m.T for u in m.U]), (Prices['N_t'],El['N_u']))
     z_psb      = np.reshape(np.array([m.ALK.z_psb[t,u].value for t in m.T for u in m.U]), (Prices['N_t'],El['N_u']))
     z_hsb      = np.reshape(np.array([m.ALK.z_hsb[t,u].value for t in m.T for u in m.U]), (Prices['N_t'],El['N_u']))
     z_off      = np.reshape(np.array([m.ALK.z_off[t,u].value for t in m.T for u in m.U]), (Prices['N_t'],El['N_u']))
     z_lag_on   = np.reshape(np.array([m.ALK.z_lag_on[t,u].value for t in m.T for u in m.U]), (Prices['N_t'],El['N_u']))
     
     y_off_on       = np.reshape(np.array([m.ALK.y_off_on[t,u].value for t in m.T for u in m.U]), (Prices['N_t'],El['N_u']))
     y_psb_on       = np.reshape(np.array([m.ALK.y_psb_on[t,u].value for t in m.T for u in m.U]), (Prices['N_t'],El['N_u']))
     y_hsb_on       = np.reshape(np.array([m.ALK.y_hsb_on[t,u].value for t in m.T for u in m.U]), (Prices['N_t'],El['N_u']))
     y_hsb_boost    = np.reshape(np.array([m.ALK.y_hsb_boost[t,u].value for t in m.T for u in m.U]), (Prices['N_t'],El['N_u']))
     
     degr_u = np.reshape(np.array([m.ALK.degr_u[t,u].value for t in m.T for u in m.U]), (Prices['N_t'],El['N_u']))
     p_s = np.reshape(np.array([m.ALK.p_s[t,u].value for t in m.T for u in m.U]), (Prices['N_t'],El['N_u']))   
     xi = np.reshape(np.array([m.ALK.xi[t,u].value for t in m.T for u in m.U]), (Prices['N_t'],El['N_u']))

     'SMR'
     s_smr_on   = np.atleast_2d(np.array([m.SMR.s_smr_on[t].value for t in m.T])).T
     s_smr_su   = np.atleast_2d(np.array([m.SMR.s_smr_su[t].value for t in m.T])).T
     s_smr_off  = np.atleast_2d(np.array([m.SMR.s_smr_off[t].value for t in m.T])).T
     s_smr_sb   = np.atleast_2d(np.array([m.SMR.s_smr_sb[t].value for t in m.T])).T
     h_smr      = np.atleast_2d(np.array([m.SMR.h_smr[t].value for t in m.T])).T
     q_ng_smr   = np.atleast_2d(np.array([m.SMR.q_ng_smr[t].value for t in m.T])).T
     
     H2_cumul = np.cumsum(h_el + h_smr)

     'H2 storage'
     soc_str    = np.atleast_2d(np.array([m.H2_st.soc[t].value for t in m.T])).T    
     Hin_str    = np.atleast_2d(np.array([m.H2_st.h_in[t].value for t in m.T])).T    
     Hout_str   = np.atleast_2d(np.array([m.H2_st.h_out[t].value for t in m.T])).T    
     
     #split by input source
     h_total_val = np.array([sum(m.ALK.h_el_u[t,u].value for u in m.U) for t in m.T])
     p_wind_val = np.array([m.p_wind_to_h[t].value for t in m.T])
     p_grid_val = np.array([m.p_purch[t].value for t in m.T])
     p_total_val = p_wind_val + p_grid_val
     h_green_res = np.where(p_total_val > 0, h_total_val * (p_wind_val / p_total_val), 0)
     h_lowcarbon_res = np.where(p_total_val > 0, h_total_val * (p_grid_val / p_total_val), 0)


     df = pd.DataFrame(np.concatenate((c_el, c_ng, P_w, p_w_t_h, P_curt, p_grid_s, p_grid_p, p_el, h_el, h_smr, q_ng_smr, soc_str, Hin_str, Hout_str, p_el_u, h_el_u, z_on, z_psb, z_hsb, z_off, z_lag_on, y_off_on, y_psb_on, y_hsb_on, y_hsb_boost, degr_u, s_smr_on, s_smr_sb, s_smr_su, s_smr_off), axis=1),
                       columns =['el_price[€/MWh]','ng_price[€/kg]', 'P_w[MW]', 'p_w_t_h2[MW]', 'P_w_curt[MW]', 'p_w_sold[MW]', 'p_purchased[MW]','p_el[MW]', 'h2_el[kg]', 'h_smr', 'q_ng_smr', 'soc_str[kg]', 'Hin_str[kg]', 'Hout_str[kg]',]+['p_el_u[MW]']*El['N_u']+['h2_el_u[kg]']*El['N_u'] + ['z_on']*El['N_u'] + ['z_psb']*El['N_u'] + ['z_hsb']*El['N_u'] + ['z_off']*El['N_u'] + ['z_lag_on']*El['N_u'] + ['y_off_on']*El['N_u'] + ['y_psb_on']*El['N_u'] + ['y_hsb_on']*El['N_u'] + ['y_hsb_boost']*El['N_u'] + ['degr_u']*El['N_u'] +['s_smr_on', 's_smr_sb', 's_smr_su', 's_smr_off'])
    
     z_s = None # variable not defined for HYP-L and for HYP-SOC, but only for HYP-MIL and HYP-MISOC
     return  obj_val, comp_time, df, p_el, p_el_u, p_grid_s, h_el, h_el_u, z_on, z_psb, z_off, y_off_on, z_hsb, z_s, p_s, xi, degr_u, h_smr, h_green_res, h_lowcarbon_res
                                                                                                                                         