import matplotlib.pyplot as plt
import pandas as pd
import numpy as np


def biofuel_production(annual_throughput, case):
    """
    annual_throughput : tonnes/year of biomass
    returns: SAF, Diesel, Naphtha in GGE/hour
    """

    # ----- Distillate yields -----
    if case == 'distillate 1':
        saf_yield = 0.50 * 0.18
        diesel_yield = 0.30 * 0.18
        naptha_yield = 0.20 * 0.18

    elif case == 'distillate 2':
        saf_yield = 0.40 * 0.18
        diesel_yield = 0.40 * 0.18
        naptha_yield = 0.20 * 0.18

    else:
        raise ValueError("case must be 'distillate 1' or 'distillate 2'")

    # ----- Fuel densities (kg/L) -----
    jet_density = 0.75
    diesel_density = 0.885
    naptha_density = (0.715+0.792)/2

    # ----- Liters per GGE (energy equivalent) -----
    L_per_GGE_SAF = 3.46
    L_per_GGE_DIESEL = 3.11
    L_per_GGE_NAPTHA = 3.75

    HOURS_PER_YEAR = 8760

    # ----- Convert throughput to kg/year -----
    throughput_kg = annual_throughput * 1000

    # ----- Product mass (kg/year) -----
    saf_mass = saf_yield * throughput_kg
    diesel_mass = diesel_yield * throughput_kg
    naptha_mass = naptha_yield * throughput_kg

    # ----- Mass -> liters/year -----
    saf_L_yr = saf_yield/jet_density*annual_throughput*1000 #saf_mass / jet_density
    diesel_L_yr = diesel_yield/diesel_density*annual_throughput*1000#diesel_mass / diesel_density
    naptha_L_yr = naptha_yield/naptha_density*annual_throughput*1000#naptha_mass / naptha_density

    # ----- Liters/year -> GGE/year -----
    saf_GGE_yr = saf_L_yr / L_per_GGE_SAF
    diesel_GGE_yr = diesel_L_yr / L_per_GGE_DIESEL
    naptha_GGE_yr = naptha_L_yr / L_per_GGE_NAPTHA

    # ----- GGE/year -> GGE/hour -----
    saf_GGE_hr = saf_GGE_yr / HOURS_PER_YEAR
    diesel_GGE_hr = diesel_GGE_yr / HOURS_PER_YEAR
    naptha_GGE_hr = naptha_GGE_yr / HOURS_PER_YEAR

    return saf_GGE_hr, diesel_GGE_hr, naptha_GGE_hr, saf_L_yr, diesel_L_yr, naptha_L_yr



if __name__ == "__main__":

    # # Create range of biomass throughput values
    # biomass_range = np.linspace(0, 1000000, 100)

    # data = []
    # for biomass in biomass_range:
    #     saf, diesel, naptha = biofuel_production(biomass, "distillate 1")

    #     data.append({
    #         'Biomass_Throughput_tonnes_year': biomass,
    #         'SAF_GGE_hr': saf,
    #         'Diesel_GGE_hr': diesel,
    #         'Naphtha_GGE_hr': naptha
    #     })

    # df = pd.DataFrame(data)

    # plt.figure(figsize=(12, 7))

    # plt.plot(df['Biomass_Throughput_tonnes_year']/1000, df['SAF_GGE_hr'], label='SAF')
    # plt.plot(df['Biomass_Throughput_tonnes_year']/1000, df['Diesel_GGE_hr'], label='Diesel')
    # plt.plot(df['Biomass_Throughput_tonnes_year']/1000, df['Naphtha_GGE_hr'], label='Naphtha')

    # plt.xlabel('Biomass Throughput (thousand tonnes/year)')
    # plt.ylabel('Product Output (GGE/hour)')
    # plt.title('Biofuel Production vs Biomass Throughput')
    # plt.legend()
    # plt.grid(True)
    # plt.show()
    _,_,_,saf, diesel, naptha = biofuel_production(100000, "distillate 1")
    print('SAF (L/y):',saf)
    print('Diesel (L/y):',diesel)
    print('Naptha (L/y):',naptha)
