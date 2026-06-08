import pandas as pd
from math import exp

import Bioenergy_dependencies.bioenergyproduction_FINAL as bioenergyproduction_FINAL
import Jobscreation

from Bioenergy_dependencies.bioenergy_costs_FINAL import equipment_costs, TCI_calculation, depreciation_schedule
from Bioenergy_dependencies.bioenergy_finance_FINAL import build_cash_flow_analysis, get_lcoe
from Bioenergy_dependencies.bioenergy_plots_FINAL import plot_all



def predict_output(forest_biomass, mill_biomass, forest_obtainability, mill_obtainability):
    input_data = {
        "Forest Residue Obtainable":                    forest_obtainability,
        "Forest Residues (bone dry tons/yr)":           forest_biomass,
        "Mill Residue Obtainability":                   mill_obtainability,
        "Primary Mill Resides (bone dry tons/yr)":      mill_biomass,
    }
    output_data = {}
    bioenergyproduction_FINAL.energyprediction(input_data, output_data)

    annual_AC_year1 = exp(output_data["Predicted Log[Annual AC Energy in Year 1 (kWh)+1]"]) - 1

    print(f"\n=== Energy PREDICTIONS ===")
    print(f"  Annual AC Output (Year 1): {annual_AC_year1:,.0f} kWh  "
          f"({annual_AC_year1/1e6:.2f} GWh)")

    return annual_AC_year1


def get_model_inputs():
    """
    Returns a dictionary of all user-controlled assumptions.
    """
    inputs = {

        # --- Plant / Feedstock ---
        'forest_annual_tons':      10648,  # bone dry tons/year
        'mill_annual_tons':         335233,  # bone dry tons/year
        'forest_obtainability':     100,      # % forest residue obtainability (75–100%)
        'mill_obtainability':       75,      # % mill residue obtainability
        'cepci_year':               2030,     # year for CEPCI equipment cost escalation
        'Plant_Lifespan':           30,       # years
        'degradation_factor':       0.005,    # 0.5%/yr — plant loses conversion efficiency

        # --- Revenue ---s
        'electricity_price':        165.0,    # $/MWh Year 1

        # --- Fuel Costs ---
        'c_fuel_per_ton_forest':    26.61,     # $/dry ton Year 1 — forest residue
        'c_fuel_per_ton_mill':      31.44,     # $/dry ton Year 1 — mill residue

        # --- Escalation Rates ---
        # 0.0 = flat prices (real analysis), >0 = growing prices (nominal analysis)
        'electricity_escalation':   0.01,
        'fuel_escalation':          0.025,    # applied equally to both feedstocks
        'fixed_om_escalation':      0.025,
        'var_om_escalation':        0.02,

        # --- Discount Rates ---
        # Nominal rate derived automatically: (1+real)×(1+inflation)-1
        'real_discount_rate':       0.085,     # equity required return, real terms
        'inflation_rate':           0.025,    # general price inflation

        # --- Financing ---
        # debt_fraction = 0.0 → all-equity
        'debt_fraction':            0.60,     # 60% of TCI financed by bank loan
        'loan_rate':                0.09,    # annual bank interest rate
        'loan_term':                15,       # years to repay

        # --- Tax ---
        'federal_tax_rate':         0.21,     # 21% federal corporate income tax
        'state_tax_rate':           0.07,     # 7% state income tax (deductible federally)
    }

    return inputs


def main():
    print("\n" + "="*65)
    print("BIOENERGY POWER PLANT CASH FLOW ANALYSIS")
    print("="*65)

    p = get_model_inputs()

    print(f"\nINPUT PARAMETERS:")
    print(f"  Forest Residues (Annual):  {p['forest_annual_tons']:,} tons/yr  [fixed throughput]")
    print(f"  Mill Residues (Annual):    {p['mill_annual_tons']:,} tons/yr  [fixed throughput]")
    print(f"  Forest Obtainability:      {p['forest_obtainability']}%")
    print(f"  Mill Obtainability:        {p['mill_obtainability']}%")
    print(f"  Plant Lifespan:            {p['Plant_Lifespan']} years")
    print(f"  Electricity Price (Yr 1):  ${p['electricity_price']}/MWh")
    print(f"  Forest Fuel Cost (Yr 1):   ${p['c_fuel_per_ton_forest']}/dry ton")
    print(f"  Mill Fuel Cost (Yr 1):     ${p['c_fuel_per_ton_mill']}/dry ton")
    print(f"  Degradation:               {p['degradation_factor']*100:.2f}%/yr  [output only — not fuel]")
    print(f"  Real Discount Rate:        {p['real_discount_rate']*100:.1f}%")
    print(f"  Inflation Rate:            {p['inflation_rate']*100:.1f}%")
    print(f"  Debt Fraction:             {p['debt_fraction']*100:.0f}%")
    print(f"  Loan Rate:                 {p['loan_rate']*100:.1f}%")
    print(f"  Loan Term:                 {p['loan_term']} yrs")
    print(f"  Escalation — Electricity:  {p['electricity_escalation']*100:.1f}%/yr")
    print(f"  Escalation — Fuel:         {p['fuel_escalation']*100:.1f}%/yr (both feedstocks)")
    print(f"  Escalation — Fixed O&M:    {p['fixed_om_escalation']*100:.1f}%/yr")
    print(f"  Escalation — Var O&M:      {p['var_om_escalation']*100:.1f}%/yr")
    print(f"  Federal Tax:               {p['federal_tax_rate']*100:.0f}%")
    print(f"  State Tax:                 {p['state_tax_rate']*100:.0f}%")

    total_annual_tons = p['forest_annual_tons'] + p['mill_annual_tons']
    biomass_daily     = total_annual_tons / 365

    annual_AC_year1 = predict_output(
        p['forest_annual_tons'],
        p['mill_annual_tons'],
        p['forest_obtainability'],
        p['mill_obtainability'],
    )

    capacity_factor = 81

    EC, stoker_cost, fuel_eq_cost, turbine_cost, EC_list = equipment_costs(
        biomass_daily, p['cepci_year'])

    TCI, FCI, breakdown = TCI_calculation(EC, EC_list)

    annual_dep = depreciation_schedule(
        breakdown, EC_list, max_years=p['Plant_Lifespan'])
    
    forest_annual_tons_after_obtain = p['forest_annual_tons']*p['forest_obtainability']/100
    mill_annual_tons_after_obtain = p['mill_annual_tons']*p['mill_obtainability']/100

    df, metrics = build_cash_flow_analysis(
        TCI                          = TCI,
        FCI                          = FCI,
        annual_depreciation_schedule = annual_dep,
        annual_AC_year1              = annual_AC_year1,
        forest_annual_tons           = forest_annual_tons_after_obtain,
        mill_annual_tons             = mill_annual_tons_after_obtain,
        degradation_factor           = p['degradation_factor'],
        capacity_factor              = capacity_factor,
        Plant_Lifespan               = p['Plant_Lifespan'],
        c_fuel_per_ton_forest        = p['c_fuel_per_ton_forest'],
        c_fuel_per_ton_mill          = p['c_fuel_per_ton_mill'],
        electricity_price            = p['electricity_price'],
        real_discount_rate           = p['real_discount_rate'],
        inflation_rate               = p['inflation_rate'],
        debt_fraction                = p['debt_fraction'],
        loan_rate                    = p['loan_rate'],
        loan_term                    = p['loan_term'],
        electricity_escalation       = p['electricity_escalation'],
        fuel_escalation              = p['fuel_escalation'],
        fixed_om_escalation          = p['fixed_om_escalation'],
        var_om_escalation            = p['var_om_escalation'],
        federal_tax_rate             = p['federal_tax_rate'],
        state_tax_rate               = p['state_tax_rate'],
    )

    print("\n" + "="*160)
    print("DETAILED CASH FLOW TABLE")
    print("="*160)
    pd.options.display.float_format = '{:,.2f}'.format
    print(df.to_string(index=False))

    lcoe = get_lcoe(
        TCI                          = TCI,
        FCI                          = FCI,
        annual_depreciation_schedule = annual_dep,
        annual_AC_year1              = annual_AC_year1,
        forest_annual_tons           = forest_annual_tons_after_obtain,
        mill_annual_tons             = mill_annual_tons_after_obtain,
        degradation_factor           = p['degradation_factor'],
        capacity_factor              = capacity_factor,
        Plant_Lifespan               = p['Plant_Lifespan'],
        c_fuel_per_ton_forest        = p['c_fuel_per_ton_forest'],
        c_fuel_per_ton_mill          = p['c_fuel_per_ton_mill'],
        electricity_price            = p['electricity_price'],
        real_discount_rate           = p['real_discount_rate'],
        inflation_rate               = p['inflation_rate'],
        debt_fraction                = p['debt_fraction'],
        loan_rate                    = p['loan_rate'],
        loan_term                    = p['loan_term'],
        electricity_escalation       = p['electricity_escalation'],
        fuel_escalation              = p['fuel_escalation'],
        fixed_om_escalation          = p['fixed_om_escalation'],
        var_om_escalation            = p['var_om_escalation'],
        federal_tax_rate             = p['federal_tax_rate'],
        state_tax_rate               = p['state_tax_rate'],
        verbose                      = False
    )

    print(lcoe)

    print("\n" + "="*65)
    print("ANALYSIS COMPLETE")
    print("="*65)

    #figs = plot_all(df,metrics)


    # IF WE WANT TO CALCULATE THE JOBS CREATED!
    # RECALL THE PAPERS WAY OF ACCOUNTING IS SLIGHTLY DIFFERENT THAN OURS!
    # Sales + capitalized production     = Production        (eq. 4) https://www.sciencedirect.com/science/article/pii/S2352550917300234
    # Production - external consumption  = VA                (eq. 5) https://www.sciencedirect.com/science/article/pii/S2352550917300234
    # VA + grant - wage bill - payroll   = EBE               (eq. 6) https://www.sciencedirect.com/science/article/pii/S2352550917300234

    #for our jobs model, we assume that production is equal to revenue
    #the external consumption/the external costs are assumed as the variable O&M and the fuel costs
    # we assume that we have no grants - tax credits are not equal to grants
    # we assume that payroll tax is bundled into Fixed O&M
    prod = df['Revenue'][1]
    external_cost = abs(df['Total Fuel Cost ($)'][1]) + abs(df['Variable O&M'][1])
    #print("I AM EXTERNAL COST", external_cost)

    ebitda =df['EBITDA'][1]
    #print("I AM EBITDA:", df['EBITDA'][1])
    wage_bill = (prod - external_cost) - ebitda
    #print("I AM CALC WAGE BILL:", wage_bill)

    sup_wage_bill = metrics['Variable O&M ($)']
    #print("I AM FIX O&M (SUPPOSED WAGE BILL):", sup_wage_bill)

    #check for difference between supposed wage bill and calculated wage bill
    if abs(wage_bill - sup_wage_bill)/sup_wage_bill > 0.05:
        bioenergy_inputs = {
            "revenue": df['Revenue'][1],        # $/yr (annual_revenue)
            "external_costs": abs(df['Total Fuel Cost ($)'][1]) + abs(df['Fixed O&M'][1]),  # $/yr (total_op_cost treated as external)
            "ebe": df['EBITDA'][1]             # $/yr (EBITDA/EBE from cash flow)
        }
    else:
        bioenergy_inputs = {
            "wage_bill": sup_wage_bill 
        }

    
    print("\n=== BIOENERGY PLANT RESULTS ===")
    bio_out=Jobscreation.jobs_from_biopower("Bioenergy Plant", df['Revenue'][1])
    Jobscreation.plot_job_breakdown(bio_out, title="Bioenergy Plant Jobs Analysis")

    return df, metrics, lcoe


if __name__ == "__main__":
    df, metrics, lcoe = main()