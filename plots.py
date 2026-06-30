#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Dec 10 10:50:15 2025

@author: trava
"""

import matplotlib.pyplot as plt
import numpy as np
from collections import defaultdict

def trend_plot(df, h_el, h_smr, Prices, St):
    
    H2_cumul = np.cumsum(h_el + h_smr)
    
    # Extract constant prices
    pi_ng = Prices["pi_ng"]
    pi_ppa = Prices["pi_ppa"]
    
    fig, axes = plt.subplots(5, 1, figsize=(7, 10), sharex=True)
    plt.subplots_adjust(hspace=0.05)
    
    #%%
    # ---------------------------------------------------------
    # 1) Electricity price, PPA price, NG price (NG secondary axis)
    # ---------------------------------------------------------
    ax = axes[0]
    ax2 = ax.twinx()
    
    ax.plot(df.index, df['el_price[€/MWh]'], label='El Market Price', lw=1.5)
    ax.axhline(pi_ppa, label='PPA Price', linestyle='--', color='C1')
    ax2.plot(df.index, df['ng_price[€/kg]'], label='NG Market Price', color='red', lw=1.5)
        
    ax.set_ylabel("Electricity Price [€/MWh]")
    ax2.set_ylabel("NG Price [€/kg]")
    # ax1.set_title("Electricity, PPA and NG Prices")
    
    # Combine legends
    lines1, lbls1 = ax.get_legend_handles_labels()
    lines2, lbls2 = ax2.get_legend_handles_labels()
    ax.legend(lines1 + lines2, lbls1 + lbls2, loc="center right")
    ax.grid(alpha=0.3)
    
    #%%
    # ---------------------------------------------------------
    # 2) Power flows (Wind + Grid power)
    # ---------------------------------------------------------
    ax = axes[1]
    
    wind = df["P_w[MW]"].values
    sold = df["p_w_sold[MW]"].values
    purch = df["p_purchased[MW]"].values
    curt = df["P_w_curt[MW]"].values
    wind_to_el = df["p_w_t_h2[MW]"].values
    
    # For wind attribution, only the wind share of p_el matters  
    # If p_el includes grid electricity, you could subtract p_purchased first
    wind_to_el = np.clip(wind_to_el, 0, None)
    
    ax.plot(df.index, wind, color="black", lw=1.5, label="Wind Power")
    
    # fill areas under wind curve
    ax.fill_between(df.index, 0, wind_to_el,
                    alpha=0.4, label="Used in Electrolyzer")
    
    remaining = wind_to_el
    ax.fill_between(df.index, remaining, remaining + sold,
                    alpha=0.4, label="Sold to Grid")
    
    remaining = remaining + sold
    ax.fill_between(df.index, remaining, remaining + curt,
                    alpha=0.4, label="Curtailment")
    
    ax.plot(df.index, df['p_purchased[MW]'], label='Power Purchased (Grid)', color='r')
    
    ax.set_ylabel("Power [MW]")
    # ax.set_title("Wind Power Allocation")
    ax.grid(alpha=0.3)
    ax.set_ylim(0)
    # ax.legend(loc="upper right", ncol=2)
    ax.legend(loc='upper left', bbox_to_anchor=(1.02, 0.8),   # x offset, y offset in axes units
    borderaxespad=0,
    ncol=1                      # or 2 if you want two columns
    )
    
    #%%
    # ---------------------------------------------------------
    # 3) H₂ Production (Electrolyzer vs SMR)
    # ---------------------------------------------------------
    ax = axes[2]
    ax2 = ax.twinx()
    
    ax.plot(df.index, df['h2_el[kg]'], label='El H₂ Production')
    ax.plot(df.index, df['h_smr'], label='SMR H₂ Production')
    
    # find all available module columns
    h2_pos = [i for i, c in enumerate(df.columns) if c == 'h2_el_u[kg]']
    
    # number of modules found
    N_modules = len(h2_pos)
    
    if N_modules == 0:
        print("Warning: No H2 modules found named 'h2_el_u[kg]'")
    else:
        # extract matrix of module production: shape (N_modules, T)
        h2_mat = np.array([df.iloc[:, p].values for p in h2_pos])
    
        cum_prev = np.zeros(len(df))
        line_colors = plt.cm.Blues(np.linspace(0.3, 1, N_modules))
    
        for i in range(N_modules):
            module_h2 = h2_mat[i]
    
            ax.fill_between(
                df.index,
                cum_prev,
                cum_prev + module_h2,
                color=line_colors[i],
                alpha=0.6,
                label=f"EL Module {i+1}",
            )
    
            cum_prev += module_h2
    
    ax2.plot(df.index, H2_cumul / 1e03, linestyle="--", lw=2,
             label="Cumulative H₂", color='k')
    
    ax.set_ylabel("H₂ Production [kg]")
    ax2.set_ylabel("H₂ cumulative Production [t]")
    
    ax.grid(alpha=0.3)
    ax.set_ylim(0)
    
    # merge legends
    lines1, labels1 = ax.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    
    ax.legend(
        lines1 + lines2,
        labels1 + labels2,
        loc='upper left',
        bbox_to_anchor=(1.1, .95),
        borderaxespad=0,
        ncol=1
    )
    
    #%%
    # ---------------------------------------------------------
    # 4) Storage behavior
    # ---------------------------------------------------------
    ax = axes[3]
    ax3 = ax.twinx()
    
    ax.plot(df.index, df['Hin_str[kg]'], label='Storage Charge', color='g')
    ax.fill_between(df.index, df['Hin_str[kg]'], color='g', alpha=.3)
    ax.plot(df.index, df['Hout_str[kg]']*(-1), label='Storage Discharge', color='r')
    ax.fill_between(df.index, df['Hout_str[kg]']*(-1), color='r', alpha=.3)
    
    ax3.plot(df.index, df['soc_str[kg]'] / St['Capacity'] * 100, linestyle=":", label="CStorage SOC₂", color='k')
    
    ax.set_ylabel("H₂ flow [kg]")
    ax3.set_ylabel("Storage Soc")
    
    ax.grid(alpha=0.3)
    # ax.set_ylim(0)
    
    # merge legends
    lines1, labels1 = ax.get_legend_handles_labels()
    lines2, labels2 = ax3.get_legend_handles_labels()
    
    ax.legend(
        lines1 + lines2,
        labels1 + labels2,
        loc='upper left',
        bbox_to_anchor=(1.1, .65),
        borderaxespad=0,
        ncol=1
    )
    
    #%%
    # ---------------------------------------------------------
    # 5) Electrolyzer & SMR States
    # ---------------------------------------------------------
    ax = axes[4]        
    
    # extract module lists
    
    # ---------------------------------------------
    # 1. Detect repeated columns using POSITIONS
    # ---------------------------------------------
    z_on_pos  = [i for i, c in enumerate(df.columns) if c == 'z_on']
    z_psb_pos = [i for i, c in enumerate(df.columns) if c == 'z_psb']
    z_hsb_pos = [i for i, c in enumerate(df.columns) if c == 'z_hsb']
    z_off_pos = [i for i, c in enumerate(df.columns) if c == 'z_off']
    
    # Number of EL modules is the minimum across all state signals
    N_status_modules = min(len(z_on_pos), len(z_psb_pos), len(z_hsb_pos), len(z_off_pos))
    
    # ---------------------------------------------
    # 2. Line styles for each module
    # ---------------------------------------------
    line_styles = ['-', '--', ':', '-.', (0, (1, 1)), (0, (3,1,1,1))]
    styles = (line_styles * (N_status_modules // len(line_styles) + 1))[:N_status_modules]
    
    base_color_EL  = "tab:blue"
    base_color_SMR = "tab:orange"
    
    # ---------------------------------------------
    # 3. Plot ELECTROLYZER state per module
    # ---------------------------------------------
    for i in range(N_status_modules):
    
        z_on  = df.iloc[:, z_on_pos[i]]
        z_psb = df.iloc[:, z_psb_pos[i]]
        z_hsb = df.iloc[:, z_hsb_pos[i]]
        z_off = df.iloc[:, z_off_pos[i]]
    
        # state encoding
        state = (
              0*z_off +
              1*z_hsb +
              2*z_psb +
              3*z_on
        )
    
        ax.step(df.index, state,
                lw=1.8,
                color=base_color_EL,
                linestyle=styles[i],
                label=f"EL Module {i+1}"
               )


    
    # ---- SMR status encoding ----
    SMR_off  = df["s_smr_off"]
    SMR_sb   = df["s_smr_sb"]
    SMR_su   = df["s_smr_su"]
    SMR_on   = df["s_smr_on"]
    
    smr_state = (
        0*SMR_off +
        1*SMR_su +
        2*SMR_sb +
        3*SMR_on
    )
    
    ax.step(df.index, smr_state, label="SMR State", lw=2, color='C1')
    
    # ax.set_ylabel("State (0=Off → 3=On)")
    ax.legend()
    
    ax.set_yticks([0, 1, 2, 3])
    ax.set_yticklabels(["Off", "Hot SB/Startup", "Pressurized SB", "On"])
    ax.grid(alpha=0.3)
    ax.set_ylim(0)
    #%%
    
    axes[-1].set_xlabel("Time step [h]")
    axes[-1].set_xlim(0, len(H2_cumul))
    
    # plt.savefig('td_plot_250h.svg', dpi=600)
    plt.show()
    
    return