import numpy as np
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import statsmodels.api as sm
from matplotlib import rcParams


## Import time series dataset

# Read CSV file
data = pd.read_csv('data/EL_NG_CF_mrkt_h.csv')


# Convert date into datatime
data["Datetime"] = pd.to_datetime(data["Datetime"] , errors="coerce")

# Add comumn with year, month, day, hour
data['Year'] = data['Datetime'].dt.year
data['Month'] = data['Datetime'].dt.month
data['Day'] = data['Datetime'].dt.day
data['Hour'] = data['Datetime'].dt.hour
# data['Minute'] = data['Datetime'].dt.minute

# Set datetime column as index
data.set_index('Datetime', inplace = True)

def data_pi_e(N_t):
    arr = data[['electricity_price']].to_numpy().flatten()
    arr = arr.astype('float64')
    arr = arr[:int(N_t)]
    return arr

def data_pi_ng(N_t):
    arr = data[['Price_EUR_per_kg']].to_numpy().flatten()
    arr = arr.astype('float64')
    arr = arr[:int(N_t)]
    return arr

def data_CP_w(N_t):
    arr = data[['CF']].to_numpy().flatten()
    arr = arr.astype('float64')
    arr = arr[:int(N_t)]
    return arr

