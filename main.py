import numpy as np
import pandas as pd 
import components, input_data
import plots
import model_op_HYP_SOC
from data.comp_size import Prices, El, St, SMR

# %% Define config
config_dict = {
      'eff_type': 3, # Choose model for hydorgen production curve1 (1:HYP-MIL, 2: HYP-L, 3: HYP-SOC, 4: HYP_MISOC)
      'solver':'gurobi', # choose solver (gurobi)
      'print_model': 0, # control model printing
      'threads': 16
      }

# %% Time horizon

delta_t     = 60/60         # Define the length of the time step in hours (15 minutes = 0.25 hours)
N_t         = 8760#24*30# / delta_t    # Number of timesteps (it has to be <= the length of the input dataset)

horizon_len = 24*10 # 1 week optimization
step_len    = 24*7 # 1 week optimization
total_steps = N_t

# %% Input data

################# Electrolyzer data #################
El_cap_tot  = 100.0 # Total electrolyzer capacity  [MW]
S_per_M     = 2 #number of stacks per module [-]
S_cap       = 10 #single stack capacity [MW]
M_cap       = S_cap * S_per_M #sinfle module capacity
N_M         = El_cap_tot / M_cap

N_u         = int(N_M) # Number of units (integer value)
El_cap      = M_cap # Capacity of each unit [MW]

El['El_cap_tot']            = El_cap_tot    # Total electrolyzer capacity [MW] 
El['El_cap']                = El_cap        # Electrolyzer module capacity [MW] 
El['N_u']                   = N_u           # number of modules 
El['N_stacks_per_module']   = S_per_M 
El['Stack_cap']             = S_cap 
El['C_stack']               = El['C_stack_kW'] * 1e03  *El['El_cap']

################ Wind data #################
W_E_ratio = 2 # Wind/Electrolyzer capacity ratio  
W         = W_E_ratio*El_cap_tot # Wind installed capacity [MW]

Wind = {'W': W, # Wind installed capacity [MW]
        'CP': input_data.data_CP_w(N_t)} # wind capacity factors
P_w = Wind['CP'] * Wind['W'] # wind production [MW]    
Wind.update({'P_w': P_w})

################# Prices ################# 
pi_e    = input_data.data_pi_e(N_t)
pi_ng   = input_data.data_pi_ng(N_t)

Prices['pi_e']  = pi_e     # Electricity market prices [EUR/MWh]
Prices['pi_ng'] = pi_ng    # NG prices [EUR/kg] ->30 €/MWH * SMR['LHV_NG'] =0.392
Prices['N_t']   = len(pi_e)# Number of timesteps

################# Steam Methane Reformer #################

SMR['SMR_cap']          = 4000*delta_t      # [kg/15min] Nominal Hydrogen Production Capacity 
SMR['T_su']             = int(8/delta_t)    # [h] Startup duration
SMR['nominal_input']    = (SMR['SMR_cap'] / SMR['eta_full'])

################# Hydrogen demand #################

if Prices['N_t']<int(24 / delta_t):
   D_period = Prices['N_t']   

H_p_max = SMR['SMR_cap'] * Prices['N_t']

Demand = {'H_target':       SMR['SMR_cap'],
        'load_factor':      1,
        }

# Find power corresponding to max. efficiency
P_eta_max = components.p_eta_max_fun(El) # around 28% of maximum power

# Define number of segments for HYP-MIL and HYP-L
num = 2

P_segments = [
    [El['P_min'],1],
    [El['P_min'],P_eta_max,1], #2
    ]

p_val = np.array(P_segments[num-1])*El["El_cap"]
     
El.update({'p_val': p_val})

# Initialize electrolyzer based on the chosen model for the hydrogen production curve
components.initialize_electrolyzer(El,config_dict) # Initialize electrolyzer (approximation coeff., etc.)
components.plot_el_curves(El, config_dict) # Plot the nonlinear and approximated curve

# %% 2. ROLLING HORIZON LOOP

results_list = [] # To store result DataFrames
obj_val = []
comp_time = []
p_el = []
p_el_u = []
p_u = []
h_el = []
h_el_u = []
z_on = []
z_psb = []
z_off = []
y_off_on = []
z_hsb = []
z_s = []
p_s = []
xi = []
degr_u = []
h_smr = []
h_green_res = []
h_lowcarbon_res = []

prev_state = None # No previous state for the first week

print(f"Starting simulation for {total_steps} hours in chunks of {horizon_len}...")

# %% Solve the optimization problem
for t_start in range(0, total_steps, step_len):
    
    
    # A. Determine window size (handle last week if year isn't perfect multiple)
    t_end = min(t_start + horizon_len, total_steps)
    current_N_t = t_end - t_start
    print(f"Solving Week: Hours {t_start} to {t_end}...")

    # B. Slice Data for current week
    # Prices
    Prices_Slice = Prices.copy()
    Prices_Slice['pi_e'] = Prices['pi_e'][t_start:t_end]
    Prices_Slice['pi_ng'] = Prices['pi_ng'][t_start:t_end]
    Prices_Slice['N_t'] = current_N_t
    
    # Wind
    Wind_Slice = Wind.copy()
    Wind_Slice['P_w'] = Wind['P_w'][t_start:t_end]
    
    # Demand (Assuming constant target, if variable slice it here too)
    Demand_Slice = Demand.copy()
    
    # C. Update Storage SOC
    St_Slice = St.copy() 
    El_Slice = El.copy() 
    
    # D. Solve Optimization
    res = model_op_HYP_SOC.model_HYP_SOC(delta_t, config_dict, El, St_Slice, Wind_Slice, Demand_Slice, Prices_Slice, SMR, prev_state)
    
    
    # E. Extract Results
    actual_step = min(step_len, current_N_t)
    df_res_full = res[2] # 10-day DataFrame
    df_res = df_res_full.iloc[:actual_step].copy() # Keep only first 7 days
    z_on_res = res[8][:actual_step] # z_on status
    s_smr_on_res = res[-4][:actual_step] # SMR on status (check your return index for s_smr_on, typically in df or variables)
    
    obj_val.append(res[0])
    comp_time.append(res[1])
    p_el.append(res[3][:actual_step])
    p_el_u.append(res[4][:actual_step])
    p_u.append(res[5][:actual_step])
    h_el.append(res[6][:actual_step])
    h_el_u.append(res[7][:actual_step])
    z_on.append(res[8][:actual_step])
    z_psb.append(res[9][:actual_step])
    z_off.append(res[10][:actual_step])
    y_off_on.append(res[11][:actual_step])
    z_hsb.append(res[12][:actual_step])
    z_s.append(res[13])
    p_s.append(res[14][:actual_step])
    xi.append(res[15][:actual_step])
    degr_u.append(res[16][:actual_step])
    h_smr.append(res[17][:actual_step])
    h_green_res.append(res[18][:actual_step])
    h_lowcarbon_res.append(res[19][:actual_step])
        
    # Add a time column to the result to keep track of global time
    df_res['Global_Hour'] = range(t_start, t_start + actual_step)
    results_list.append(df_res)
    
    # F. Prepare State for NEXT Week
    # 1. Get final SOC of this week -> Initial SOC of next week
    final_soc_kg = df_res['soc_str[kg]'].iloc[-1]
    final_soc_perc = final_soc_kg / St['Capacity']
    St['Initial_SOC'] = final_soc_perc # Update global St for next iteration
    
    # 2. Get final On/Off status -> prev_state for next week
    # Extract last row of z_on columns. 
    # Note: z_on columns in df might be named 'z_on' multiple times (one per unit).
    # It is safer to use the numpy array 'z_on_res' returned by the function.
    last_z_on = res[8][actual_step-1, :] # Last timestep, all units
    last_z_psb = res[9][actual_step-1, :] # Last timestep, all units
    last_z_hsb = res[12][actual_step-1, :] # Last timestep, all units
    last_degr = res[16][actual_step-1, :]
    
    # For SMR, we need the on status. 
    last_smr_on = df_res['s_smr_on'].iloc[-1]
    
    prev_state = {
        'alk_on': last_z_on,
        'smr_on': last_smr_on,
        'z_psb':  last_z_psb,
        'z_hsb':  last_z_hsb, 
    }
    
    El['prev_degr'] = last_degr # List/Array of degr per unit
    El['prev_on']   = prev_state['alk_on']   # List/Array of binary on status

df_full_optspan = pd.concat(results_list, ignore_index=True)

df_H2 = pd.DataFrame()
df_H2['H2_tot']= df_full_optspan['h2_el[kg]'] + df_full_optspan['h_smr']
df_H2['H2_EL']= df_full_optspan['h2_el[kg]']
df_H2['H2_green']= np.concat(h_green_res)
df_H2['H2_lowC']= np.concat(h_lowcarbon_res)
df_H2['H2_SMR']= df_full_optspan['h_smr']

'_________________obj_val________________________'
obj_val_def = components.obj_func(El, Wind, SMR, Prices, df_full_optspan, df_H2, y_off_on, z_on, delta_t) 

print("Objective value = ", obj_val_def, " EUR")
pd.set_option('display.max_columns', None)

print("Computational time = ", comp_time, " s")

# %% Results

# Plot optimal dispatch
# results.plot_results(config_dict,El,St,Wind,Demand,Prices, obj_val, p_u, p_el, h_el, z_on, z_psb, z_off, y_off_on, z_hsb, df, z_s, p_s, comp_time)
plots.trend_plot(df_full_optspan, np.concat(h_el), np.concat(h_smr), Prices, St)

# Check tightness of the relaxation for conic model
# err, gap, h_physics = results.check_tightness(config_dict,El, Prices, p_el,p_el_u,p_s,  xi, z_on, h_el_u, z_s)
    

# Creare df with results for analysis
res_data  = [{'eff_type':   config_dict['eff_type'],
              'solver':     config_dict['solver'],
              'p_val':      p_val/El_cap,
              'N_s':        El['N_s'],
              'N_u':        El['N_u'],
              'comp_time_s':comp_time,
              'threads':    config_dict['threads'],
              'obj_val':    obj_val_def,
              'h_prod':     sum(df_H2['H2_tot']),
              'h_smr':      sum(df_H2['H2_SMR']),
              'h_green':    sum(df_H2['H2_green']),
              'h_grid':     sum(df_H2['H2_lowC']), 
              'p_w_to_h':   sum(df_full_optspan['p_w_t_h2[MW]']),
              'p_w_curt':   sum(df_full_optspan['P_w_curt[MW]']),
              'p_w_sold':   sum(df_full_optspan['p_w_sold[MW]']),
              'p_purch':    sum(df_full_optspan['p_purchased[MW]']),
              'Cost_wind':  sum((Prices['pi_ppa'] + Prices['nr_tariff']) * Wind['P_w'] * delta_t),
              'Cost_grid':  sum((Prices['pi_e'] + Prices['nr_tariff'] + Prices['C_var']) * df_full_optspan['p_purchased[MW]'] * delta_t),
              'Cost_cold_d':sum(sum((El['degr_cold']*El['C_stack']/El['lifetime'])*np.concatenate(y_off_on))),
              'Cost_op_d':  sum(sum((El['degr']*El['C_stack']/El['lifetime'])*np.concatenate(z_on)*delta_t)),
              'Cost_ng':    sum(Prices['pi_ng'] * df_full_optspan['q_ng_smr']),
              
              'Rev_p_sell': sum(Prices['pi_e'] * df_full_optspan['p_w_sold[MW]'] * delta_t),
              'Rev_h_green':sum(Prices['prem_green'] * df_H2['H2_green']),
              'Rev_h_grid': sum(Prices['prem_grid'] * df_H2['H2_lowC']),
              
              'p_u':        np.sum(np.concat(p_u)),
              'z_on':       np.sum(np.concat(z_on)),
              'z_psb':      np.sum(np.concat(z_psb)),
              'z_off':      np.sum(np.concat(z_off)),
              'y_off_on':   np.sum(np.concat(y_off_on)),
              'z_hsb':      np.sum(np.concat(z_hsb)),
              'degr':       np.sum(np.concat(degr_u)),             
              # 'gap':gap
              }]

df_res = pd.DataFrame(res_data)

# Write to excel
df_config=pd.DataFrame(list(config_dict.items()))
df_El=pd.DataFrame(list(El.items())) 
df_Prices=pd.DataFrame(list(Prices.items()))
df_Demand=pd.DataFrame(list(Demand.items()))
df_Wind=pd.DataFrame(list(Wind.items()))

# Write to Multiple Sheets
res_name_file = 'Results_efftype%d_El_cap_tot%d_Nu%d_St_cap%d_%s_T%d_resol%dmin.xlsx' %(config_dict['eff_type'],El['El_cap_tot'],El['N_u'], St['Capacity'], config_dict['solver'], Prices['N_t'], 60*delta_t)

with pd.ExcelWriter(res_name_file) as writer:
    df_config.to_excel(writer, sheet_name='config', header = False, index=False)
    df_El.to_excel(writer, sheet_name='electrolyzer', header = False, index=False)
    df_Wind.to_excel(writer, sheet_name='wind', header = False, index=False)
    df_Prices.to_excel(writer, sheet_name='prices', header = False, index=False)
    df_Demand.to_excel(writer, sheet_name='demand', header = False, index=False)
    df_full_optspan.to_excel(writer, sheet_name='dispatch')
    df_res.to_excel(writer, sheet_name='results')

# df_full_optspan.to_csv('year_operation_5x20.csv')

print("EL On time = ", sum(np.concat(z_on)) /Prices['N_t']*100, " %")
print("EL Pressurized standby time = ", sum(np.concat(z_psb)) /Prices['N_t']*100, " %")
print("EL Hot standby time = ", sum(np.concat(z_hsb)) /Prices['N_t']*100, " %")
print("EL Off time = ", sum(np.concat(z_off)) /Prices['N_t']*100, " %")
print("EL Cold startups = ", sum(np.concat(y_off_on)))

print("SMR On time = ", sum(df_full_optspan.s_smr_on) /Prices['N_t']*100, " %")
print("SMR Standby time = ", sum(df_full_optspan.s_smr_sb) /Prices['N_t']*100, " %")
print("SMR Off time = ", sum(df_full_optspan.s_smr_off) /Prices['N_t']*100, " %")
print("SMR Cold startups = ", sum(df_full_optspan.s_smr_su))