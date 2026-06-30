# -*- coding: utf-8 -*-
"""
Created on Tue Feb 17 09:14:55 2026

@author: riccardotravag
"""

################# Prices #################
Prices = {
    'pi_ppa':     50,                       # PPA price [EUR/MWh]
    'nr_tariff':  10.0,                     # [€/MWh] Non-regulated market tariff, Applies equally to market-priced energy and PPA energy
    'fee_omie':   0.04,                     # [€/MWh] Spot market operation
    'fee_ree':    0.17,                     # [€/MWh] Transmission system operation
    'atr_energy': 1.551,                    # [€/MWh] high-voltage access tariff on energy for large industrial consumers
    'tax_gen':    0.07,                     # [-] Generation tax, applied to generation cost
    'tax_exc':    0.0077,                   # [-] excise tax, applied to energy cost,
    'atr_power':  13.95,                    # [€/kW/y] high-voltage access tariff on power for large industrial consumers
    'net_loss':   0.0165,                   # [-] Network losses, it increases by this percentage the consumed energy
    
    'CO2_em':     0.46,                     # [kgCO2/kWhe] from grid mix ref chrome-extension://efaidnbmnnnibpcajpcglclefindmkaj/https://ocw.tudelft.nl/wp-content/uploads/Summary_table_with_heating_values_and_CO2_emissions.pdf
    # --- NEW PREMIUMS ---
    'prem_green': 4.0,  # Premium for Wind-H2 [€/kg]
    'prem_grid':  2.0,  # Premium for Grid-H2 [€/kg]    
      }

Prices['C_var']     = Prices['fee_omie'] + Prices['fee_ree']+ Prices['atr_energy'] # [€/MWh]
Prices['loss']      = 1 + Prices['net_loss']                    # [-] Energy multiplier
Prices['tax_mult']  = 1 + Prices['tax_gen'] + Prices['tax_exc'] # [-] Energy tax multiplier

################# Electrolyzer data #################
El = {'P_min':              0.15,       # % minimum module load
      'P_sb':               0.01,       # % Power consumption in stand-by state
      'H_standby_hours':    8,          # h of sb before turning off      
      'hsb-on_lag':         0.25,        # [h] time lag before starting H2 production during transition hsb-on 
      'off-on_lag':         1,          # [h] time lag before starting H2 production during transition hsb-on
      
      'ramp_up':            1,          # fraction of capacity per time step 
      'ramp_down':          1,          # fraction of capacity per time step
      
      # --- degr PARAMETERS ---
      'C_stack_kW':         1000*0.4,   # stack cost [EUR/kW]
      'lifetime':           0.1,        # efficiency loss allowed
      'degr':               1.3e-6,     # efficiency loss per hour of operation "The impact of degradation on the economics of green hydrogen"
      'degr_cold':          1.09e-5,    # efficiency loss per per cold start
      'LHV_H2':             33.33e-3    # [MWh/kg] Lower Heating Value to calculate waste heat
 
      } 

################# Hydrogen Storage Parameters #################
St = {
    'Capacity': 3000,    # [kg] Total tank size
    'Min_SOC': 0.10,       # [%] Minimum level 30% -> gas network storage always full
    'Initial_SOC': 0.50,   # [%] Start at 50%
    'eta_in': 0.99,        # Efficiency of compression/filling
    'eta_out': 1.00,       # Efficiency of discharging (usually high)
    'max_flow_in': 1000.0, # [kg/h] Max fill rate
    'max_flow_out': 2000.0 # [kg/h] Max discharge rate
}

################# Steam Methane Reformer #################
SMR = {
    'eta_full':     0.26,     # [-] Efficiency ( kg H2 out / kg NG in)
    'eta_min':      0.25,     # [-] Efficiency ( kg H2 out / kg NG in)
    # 'eta_smr':      0.32,     # [-] Efficiency ( kg H2 out / kg NG in)
    'LHV_NG':       13.08e-3, # [MWh/kg_NG] Lower Heating Value of Natural Gas (approx)
    'LHV_H2':       33.33e-3, # [MWh/kg_H2]
    'CO2_em':       2.75,     # [kgCO2/kgNG] ref chrome-extension://efaidnbmnnnibpcajpcglclefindmkaj/https://ocw.tudelft.nl/wp-content/uploads/Summary_table_with_heating_values_and_CO2_emissions.pdf
    'min_load':     0.40,     # [p.u.] Minimum stable operation
    'ramp_rate_hr': 0.10,     # [p.u./h] Ramp rate (10% per hour)
    'su_cons':      0.30,     # [p.u.] Gas consumption during startup (approx 30% of nominal)
    'sb_cons':      0.05,     # [p.u.] Gas consumption in Standby (e.g., 10% of nominal input)
    'C_su':         500,      # [EUR/event] Wear and tear cost per startup
}

