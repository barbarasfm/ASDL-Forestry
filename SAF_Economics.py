##################### INTEGRATED SAF CASH FLOW #############################

from __future__ import annotations
from math import tanh
from math import exp
import SAF_dependencies.SAF_Cost_Scaling_FINAL as cs
import SAF_dependencies.SAF_OPEX_FINAL as opex
import SAF_dependencies.biofuel_production_FINAL as bp
import SAF_dependencies.SAF_BaseEconomics_FINAL as econ
import SAF_dependencies.SAF_plots_FINAL as sp
from SAF_dependencies.SAF_Finance_FINAL import (
    depreciation_schedule,
    policy_revenue,
    build_loan_schedule,
    build_cash_flow_analysis,
    solve_mfsp
)
import pandas as pd
import numpy as np
import numpy_financial as npf
import pandas as pd
import matplotlib.pyplot as plt
from scipy.optimize import brentq
import Jobscreation

def get_model_inputs():
    """
    Returns a dictionary of all user controlled assumptions
    """
    inputs = {
        'year': 2025, # Year For Analaysis

        #Feedstock and Plant Specifications
        'forest_throughput' : 100_000, #tons/year
        'pulpwood_throughput' : 100_000, #tons/year
        'sawmill_throughput' : 100_000, #tons/year
        'forest_obtainibility' : 0.8, #fraction of forest throughput that can be obtained
        'pulpwood_obtainibility' : 0.8, #fraction of pulpwood throughput that can be obtained
        'sawmill_obtainibility' : 0.8, #fraction of sawmill throughput that can be obtained
        'distillate' : 'distillate 1', #Distillation Type 
        'plant_lifespan' : 20, #plant lifespan/time horizon for analysis

        #Discount Rates
        'real_discount_rate': 0.10, #equity required return, real money terms 
        'inflation_rate' : 0.025, #general price inflation

        # Financing Options
        'debt_fraction' : 0.70,  #percent of plant financed by bank
        'loan_rate': 0.08, #interest rate on loan payment
        'loan_term': 15, #how long you are paying back the loan


        'CPI' : 321.05, #Consumer Price Index, take directly from online
        'PDC_forest' : 60,    #PLANT DELIVERED COST - THIS COMES FROM JONATHAN'S FEEDSTOCK SUPPLY CHAIN MODEL
        'PDC_pulpwood' : 60,    #PLANT DELIVERED COST - THIS COMES FROM JONATHAN'S FEEDSTOCK SUPPLY CHAIN MODEL
        'PDC_sawmill' : 60,    #PLANT DELIVERED COST - THIS COMES FROM JONATHAN'S FEEDSTOCK SUPPLY CHAIN MODEL

        #Plant Degradation Rate
        'degredation_factor': 0.0,  # FT plant degradation captured via catalyst replacement 
                             # and maintenance costs. Set >0 for sensitivity analysis.

        #User Defined Selling Prices
        'SAF_price' : 1.61,    #assuming selling price for SAF
        'DIESEL_price': 1.03,  #assuming selling price for Diesel
        'NAPTHA_price': 0.75,  #assuming selling price for Naptha

        # Price and Cost Escalation Factors to Deal with Rising Costs
        'price_escalation': 0.025,   #annual escalation applied to all three fuel selling prices
        'fuel_escalation': 0.025,    #annual escalation applied to the feedstock cost
        'cost_escalation': 0.025,    #annual escalation applied to uttilities and indirect opex
        'catalyst_escalation': 0.025, #annual escalation applied to catalyst replacement cost

        #Tax Rates
        'federal_tax_rate' : 0.21,
        'state_tax_rate' : 0.07,
    }

    return inputs

def main():
    print("\n" + "="*65)
    print("BIOFUEL PRODUCTION PLANT PLANT CASH FLOW ANALYSIS")
    print("="*65)

    p = get_model_inputs()

    df, metrics = build_cash_flow_analysis(
        p['year'],
        p['forest_throughput'],
        p['pulpwood_throughput'],
        p['sawmill_throughput'],
        p['forest_obtainibility'],
        p['pulpwood_obtainibility'],
        p['sawmill_obtainibility'],
        p['distillate'],
        p['plant_lifespan'],
        p['real_discount_rate'],
        p['inflation_rate'],
        p['debt_fraction'],
        p['loan_rate'],
        p['loan_term'],
        p['CPI'],
        p['PDC_forest'],
        p['PDC_pulpwood'],
        p['PDC_sawmill'],
        p['degredation_factor'],
        p['SAF_price'],
        p['DIESEL_price'],
        p['NAPTHA_price'],
        p['price_escalation'],
        p['fuel_escalation'],
        p['cost_escalation'],
        p['catalyst_escalation'],
        p['federal_tax_rate'],
        p['state_tax_rate']
    )

    figs= sp.plot_all(df, metrics)
    #plt.show()

    mfsp = solve_mfsp(
    p['year'],
    p['forest_throughput'],
    p['pulpwood_throughput'],
    p['sawmill_throughput'],
    p['forest_obtainibility'],
    p['pulpwood_obtainibility'],
    p['sawmill_obtainibility'],
    p['distillate'],
    p['plant_lifespan'],
    p['real_discount_rate'],
    p['inflation_rate'],
    p['debt_fraction'],
    p['loan_rate'],
    p['loan_term'],
    p['CPI'],
    p['PDC_forest'],
    p['PDC_pulpwood'],
    p['PDC_sawmill'],
    p['degredation_factor'],
    p['price_escalation'],
    p['fuel_escalation'],
    p['cost_escalation'],
    p['catalyst_escalation'],
    p['federal_tax_rate'],
    p['state_tax_rate'])
    print("\n" + "="*65)
    print("ANALYSIS COMPLETE")
    print("="*65)

    bio_out = Jobscreation.jobs_from_biofuel("Biofuel Plant", df['Revenue'][1])
    #print("\n=== BIOFUEL PLANT RESULTS ===")
    Jobscreation.plot_job_breakdown(bio_out, title="Biofuel Plant Jobs Analysis")


    return mfsp, df, metrics

if __name__ == "__main__":
    mfsp, df, metrics = main ()
    print(f"MFSP SAF:    ${mfsp['MFSP SAF ($/L)']:.4f} /L")
    print(f"MFSP Diesel: ${mfsp['MFSP Diesel ($/L)']:.4f} /L")
    print(f"MFSP Naptha: ${mfsp['MFSP Naptha ($/L)']:.4f} /L")
    print(f"NPV at MFSP: ${mfsp['NPV at MFSP']:,.2f}")







    


