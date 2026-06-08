#SAF Finance Codes: 
from __future__ import annotations
from math import tanh
from math import exp
import SAF_dependencies.SAF_Cost_Scaling_FINAL as cs
import SAF_dependencies.SAF_OPEX_FINAL as opex
import SAF_dependencies.biofuel_production_FINAL as bp
import SAF_dependencies.SAF_BaseEconomics_FINAL as econ
import SAF_dependencies.SAF_plots_FINAL as sp
import pandas as pd
import numpy as np
import numpy_financial as npf
import pandas as pd
import matplotlib.pyplot as plt
from scipy.optimize import brentq



def depreciation_schedule(FCI, Equipment_Costs, max_years=16):
    """
    Parameters:
    - breakdown_dict: from TCI_calculation
    - equipment_costs: 
    - max_years: 15
    
    Returns:
    - annual_depreciation: list of depreciation by year
    """
    
    # MACRS schedules
    macrs_10yr = [
        0.10,
        0.18,
        0.1440,
        0.1152,
        0.0922,
        0.0737,
        0.0655,
        0.0655,
        0.0656,
        0.0655,
        0.0328
    ]
    
    macrs_15yr_200DB = [
            0.0500,
            0.0950,
            0.0855,
            0.0770,
            0.0693,
            0.0623,
            0.0590,
            0.0590,
            0.0591,
            0.0590,
            0.0591,
            0.0590,
            0.0591,
            0.0590,
            0.0591,
            0.0295
        ] # 200% DB 15-year
    
    annual_depreciation = [0] * max_years
    
    # Depreciate specific equipment
    # --- GASIFICATION ---
    syngas_generation_cost = Equipment_Costs[0]

    # --- SYNGAS CLEANING ---
    amine_system_cost = Equipment_Costs[1]
    lo_cat_absorber_cost = Equipment_Costs[2]
    lo_cat_oxidizer_cost = Equipment_Costs[3]
    sulfur_separator_cost = Equipment_Costs[4]
    co2_compressor_cost = Equipment_Costs[5]
    direct_quench_recycle_cost = Equipment_Costs[6]
    venturi_recycle_cooling_cost = Equipment_Costs[7]
    venturi_scrubber_cost = Equipment_Costs[8]
    direct_quench_syngas_cooler_cost = Equipment_Costs[9]
    venturi_liquid_tank_cost = Equipment_Costs[10]

    # --- FUEL SYNTHESIS ---
    hc_production_cost = Equipment_Costs[11]
    syngas_preheater_cost = Equipment_Costs[12]
    reformed_syngas_whb_cost = Equipment_Costs[13]
    syngas_cooler_1_cost = Equipment_Costs[14]
    steam_methane_reformer_cost = Equipment_Costs[15]
    water_gas_shift_cost = Equipment_Costs[16]
    zno_beds_cost = Equipment_Costs[17]
    booster_compressor_cost = Equipment_Costs[18]
    recycle_booster_cost = Equipment_Costs[19]
    psa_booster_cost = Equipment_Costs[20]
    psa_knockout_cost = Equipment_Costs[21]
    syngas_cooler_2_cost = Equipment_Costs[22]
    recycle_preheater_cost = Equipment_Costs[23]
    fischer_tropsch_cost = Equipment_Costs[24]
    psa_unit_cost = Equipment_Costs[25]
    ft_knockout_cost = Equipment_Costs[26]
    water_separator_cost = Equipment_Costs[27]

    # --- HYDROPROCESSING ---
    hydrocracking_cost = Equipment_Costs[28]

    # --- AIR SEPARATION ---
    air_compressor_cost = Equipment_Costs[29]
    air_cooler_cost = Equipment_Costs[30]
    o2_compressor_cooler_1_cost = Equipment_Costs[31]
    o2_compressor_cooler_2_cost = Equipment_Costs[32]
    o2_compressor_cost = Equipment_Costs[33]
    hp_condenser_cost = Equipment_Costs[34]
    hp_condenser_accum_cost = Equipment_Costs[35]
    hp_reflux_pump_cost = Equipment_Costs[36]
    hp_tower_cost = Equipment_Costs[37]
    intercooler_1_cost = Equipment_Costs[38]
    intercooler_2_cost = Equipment_Costs[39]
    intercooler_3_cost = Equipment_Costs[40]
    lp_boiler_cost = Equipment_Costs[41]
    lp_tower_cost = Equipment_Costs[42]
    water_knockout_1_cost = Equipment_Costs[43]
    gas_expander_cost = Equipment_Costs[44]
    water_knockout_2_cost = Equipment_Costs[45]
    
    # --- APPLY 10-YEAR MACRS TO ALL EQUIPMENT ---
    for i in range(min(len(macrs_10yr), max_years)):
        annual_depreciation[i] += syngas_generation_cost * macrs_10yr[i]
        annual_depreciation[i] += amine_system_cost * macrs_10yr[i]
        annual_depreciation[i] += lo_cat_absorber_cost * macrs_10yr[i]
        annual_depreciation[i] += lo_cat_oxidizer_cost * macrs_10yr[i]
        annual_depreciation[i] += sulfur_separator_cost * macrs_10yr[i]
        annual_depreciation[i] += co2_compressor_cost * macrs_10yr[i]
        annual_depreciation[i] += direct_quench_recycle_cost * macrs_10yr[i]
        annual_depreciation[i] += venturi_recycle_cooling_cost * macrs_10yr[i]
        annual_depreciation[i] += venturi_scrubber_cost * macrs_10yr[i]
        annual_depreciation[i] += direct_quench_syngas_cooler_cost * macrs_10yr[i]
        annual_depreciation[i] += venturi_liquid_tank_cost * macrs_10yr[i]
        annual_depreciation[i] += hc_production_cost * macrs_10yr[i]
        annual_depreciation[i] += syngas_preheater_cost * macrs_10yr[i]
        annual_depreciation[i] += reformed_syngas_whb_cost * macrs_10yr[i]
        annual_depreciation[i] += syngas_cooler_1_cost * macrs_10yr[i]
        annual_depreciation[i] += steam_methane_reformer_cost * macrs_10yr[i]
        annual_depreciation[i] += water_gas_shift_cost * macrs_10yr[i]
        annual_depreciation[i] += zno_beds_cost * macrs_10yr[i]
        annual_depreciation[i] += booster_compressor_cost * macrs_10yr[i]
        annual_depreciation[i] += recycle_booster_cost * macrs_10yr[i]
        annual_depreciation[i] += psa_booster_cost * macrs_10yr[i]
        annual_depreciation[i] += psa_knockout_cost * macrs_10yr[i]
        annual_depreciation[i] += syngas_cooler_2_cost * macrs_10yr[i]
        annual_depreciation[i] += recycle_preheater_cost * macrs_10yr[i]
        annual_depreciation[i] += fischer_tropsch_cost * macrs_10yr[i]
        annual_depreciation[i] += psa_unit_cost * macrs_10yr[i]
        annual_depreciation[i] += ft_knockout_cost * macrs_10yr[i]
        annual_depreciation[i] += water_separator_cost * macrs_10yr[i]
        annual_depreciation[i] += hydrocracking_cost * macrs_10yr[i]
        annual_depreciation[i] += air_compressor_cost * macrs_10yr[i]
        annual_depreciation[i] += air_cooler_cost * macrs_10yr[i]
        annual_depreciation[i] += o2_compressor_cooler_1_cost * macrs_10yr[i]
        annual_depreciation[i] += o2_compressor_cooler_2_cost * macrs_10yr[i]
        annual_depreciation[i] += o2_compressor_cost * macrs_10yr[i]
        annual_depreciation[i] += hp_condenser_cost * macrs_10yr[i]
        annual_depreciation[i] += hp_condenser_accum_cost * macrs_10yr[i]
        annual_depreciation[i] += hp_reflux_pump_cost * macrs_10yr[i]
        annual_depreciation[i] += hp_tower_cost * macrs_10yr[i]
        annual_depreciation[i] += intercooler_1_cost * macrs_10yr[i]
        annual_depreciation[i] += intercooler_2_cost * macrs_10yr[i]
        annual_depreciation[i] += intercooler_3_cost * macrs_10yr[i]
        annual_depreciation[i] += lp_boiler_cost * macrs_10yr[i]
        annual_depreciation[i] += lp_tower_cost * macrs_10yr[i]
        annual_depreciation[i] += water_knockout_1_cost * macrs_10yr[i]
        annual_depreciation[i] += gas_expander_cost * macrs_10yr[i]
        annual_depreciation[i] += water_knockout_2_cost * macrs_10yr[i]

    # Remainder of FCI on 15-year MACRS
    rest_of_plant = FCI - sum(Equipment_Costs)
    
    for i in range(min(len(macrs_15yr_200DB), max_years)):
        annual_depreciation[i] += rest_of_plant * macrs_15yr_200DB[i]

    return annual_depreciation

def policy_revenue(case, product_stream):
    """
    Calculates the Revenue from Policy
    Inputs: case - string indicating policy type ('bioenergycredit' or 'safcredit')
            product_stream - numeric value (kWh for bioenergycredit, gallons for safcredit)

    Outputs: revenue - calculated revenue based on policy
    """
    if case == 'bioenergycredit':
        revenue = product_stream * 0.003  # renewable energy production credit (base credit of 0.3 cents per kWh)
    elif case == 'safcredit':
        revenue = product_stream * 0.35  # clean fuel production credit, product stream must be in gallons
    else:
        revenue = 0  # or raise an error if you prefer
    
    return revenue

def build_loan_schedule(loan_amount, loan_rate, loan_term, plant_lifespan):
    """
    Returns interest_schedule, principal_schedule, balance_schedule, annual_payment.
    All schedule lists have length = plant_lifespan.
    """
    if loan_amount == 0 or loan_rate == 0:
        z = [0.0] * plant_lifespan
        return z, z, z, 0.0

    annual_payment = loan_amount * (
        loan_rate * (1 + loan_rate) ** loan_term /
        ((1 + loan_rate) ** loan_term - 1)
    )

    interest_sch, principal_sch, balance_sch = [], [], []
    balance = loan_amount

    for yr in range(1, plant_lifespan + 1):
        if yr <= loan_term and balance > 1e-6:
            interest  = balance * loan_rate
            principal = annual_payment - interest
            balance   = max(balance - principal, 0.0)
        else:
            interest = principal = 0.0
        interest_sch.append(interest)
        principal_sch.append(principal)
        balance_sch.append(balance)

    return interest_sch, principal_sch, balance_sch, annual_payment

def build_cash_flow_analysis(
        
        year,
        forest_throughput,
        pulpwood_throughput,
        sawmill_throughput,
        forest_obtainibility,
        pulpwood_obtainibility,
        sawmill_obtainibility,
        distillate,
        plant_lifespan,
        real_discount_rate,
        inflation_rate,
        debt_fraction,
        loan_rate,
        loan_term,
        CPI,
        PDC_forest,    #PLANT DELIVERED COST - THIS COMES FROM JONATHAN'S FEEDSTOCK SUPPLY CHAIN MODEL
        PDC_pulpwood,
        PDC_sawmill,
        degredation_factor,
        SAF_price,
        DIESEL_price,
        NAPTHA_price,
        price_escalation,   #annual escalation applied to all three fuel selling prices
        fuel_escalation,    #annual escalation applied to the feedstock cost
        cost_escalation,    #annual escalation applied to uttilities and indirect opex
        catalyst_escalation, #annual escalation applied to catalyst replacement cost
        federal_tax_rate = 0.21,
        state_tax_rate = 0.07,
        verbose = True
):
    # Find the total Annual Throughput
    forest_throughput = forest_throughput * forest_obtainibility
    pulpwood_throughput = pulpwood_throughput * pulpwood_obtainibility
    sawmill_throughput = sawmill_throughput * sawmill_obtainibility

    annual_throughput = forest_throughput + pulpwood_throughput + sawmill_throughput
 
    ########################## HOW MUCH FUEL ARE WE PRODUCING ###############
    
    saf_GGE_hr, diesel_GGE_hr, naptha_GGE_hr, saf_ML_yr, diesel_ML_yr, naptha_ML_yr = bp.biofuel_production(annual_throughput, distillate)
    fuel_GGE_hr = saf_GGE_hr + diesel_GGE_hr + naptha_GGE_hr

    SAF_L_yr = saf_ML_yr#*1e6
    DIESEL_L_yr = diesel_ML_yr #* 1e6
    NAPTHA_L_yr = naptha_ML_yr #*1e6

    ######################## Equipment Cost Scaling ##########################
    # Equipment costs scaled from reference plant using feedstock rate
    # (kg/hr) and total fuel output (GGE/hr).
    # Operating assumption: 90% uptime = 7,884 hr/yr.
    # ===============================================================

        # convert to kg/hr
    feedstock_kg_hr = annual_throughput * 1000 / 7884   #converting tons/year to Kg/hr, assuming plant is operating 90% of the year
    Equipment_Costs = cs.EC_scaling(feedstock_kg_hr, fuel_GGE_hr, year) #MAKE EDITS HERE IT IS A DICTIONARY - transform to list

    #need to write out the the total equipment costs

    DEFAULT_FCI_RATIO_FACTORS = {
    "equipment_installation": 0.47,
    "instrumentation_control": 0.36,
    "piping_installed": 0.68,
    "electrical_installed": 0.11,
    "buildings_services": 0.18,
    "yard_improvements": 0.10,
    "service_facilities": 0.55,
    "engineering_supervision": 0.33,
    "construction_expenses": 0.41,
    "legal_expenses": 0.04,
    "contractors_fee": 0.05,
    "contingency": 0.10,
}
    #################### Calculate the Fixed Capital Investment##################

    FCI = econ.fixed_capital_investment_usd(Equipment_Costs, DEFAULT_FCI_RATIO_FACTORS)

    #working capital: 15%
    working_capital = 0.15
    TCI = FCI * (1 + working_capital)

    ########################## DETERMINE THE ANNUAL DEPRECIATION COSTS ######################

    #Transform the Equipment Costs from a Dictionary to a List
    Equipment_Costs = list(Equipment_Costs.values())

    # Equipment items use 10-year MACRS; remainder of FCI uses
    # 15-year MACRS 200DB. No changes made to that function.
    # ================================================================
    annual_depreciation_schedule = depreciation_schedule(FCI, Equipment_Costs)

    total_PEC = sum(Equipment_Costs)


  # ----------------------------------------------------------------
    #  RATE CONVERSIONS
    # Fisher equation: nominal = (1 + real) × (1 + inflation) - 1   https://docs.nlr.gov/docs/legosti/old/5173.pdf
    # ----------------------------------------------------------------
    nominal_discount_rate = (1 + real_discount_rate) * (1 + inflation_rate) - 1
    equity_fraction       = 1 - debt_fraction

    if verbose:
        print(f"\n=== DISCOUNT RATES ===")
        print(f"  Real:    {real_discount_rate*100:.2f}%  [input — equity required return]")
        print(f"  Infl:    {inflation_rate*100:.2f}%  [input]")
        print(f"  Nominal: {nominal_discount_rate*100:.4f}%  [derived via Fisher]") #this is calculated and should be shown in the dash board!

    # ----------------------------------------------------------------
    #  DEBT / EQUITY SPLIT
    # ----------------------------------------------------------------
    loan_amount     = TCI * debt_fraction
    equity_invested = TCI * equity_fraction

    if verbose:
        print(f"\n=== FINANCING ===")
        print(f"  TCI:             ${TCI:,.2f}")
        print(f"  Loan:            ${loan_amount:,.2f}  ({debt_fraction*100:.1f}%)")
        print(f"  Equity:          ${equity_invested:,.2f}  ({equity_fraction*100:.1f}%)")
        print(f"  Loan Rate:       {loan_rate*100:.2f}%   Loan Term: {loan_term} yrs")
        print(f"  Years {loan_term+1}-{plant_lifespan}: debt-free — most profitable period")

    # ----------------------------------------------------------------
    #  LOAN AMORTIZATION
    # ----------------------------------------------------------------
    interest_sch, principal_sch, balance_sch, annual_payment = \
        build_loan_schedule(loan_amount, loan_rate, loan_term, plant_lifespan)

    if loan_amount > 0:
        #print(f"\n  Annual P&I (fixed): ${annual_payment:,.2f}")
        #print(f"  Yr | Beg Balance     | Interest       | Principal      | End Balance")
        # print(f"  ---+----------------+----------------+----------------+---------------")
        beg = loan_amount
        for yr in range(min(loan_term, plant_lifespan)):
            #print(f"  {yr+1:2d} | ${beg:>13,.2f} | ${interest_sch[yr]:>13,.2f} "
            #      f"| ${principal_sch[yr]:>13,.2f} | ${balance_sch[yr]:>13,.2f}")
            beg = balance_sch[yr]

    
    ##########################################################
    # CALCULATE THE YEAR ONE OPERATING COST BASELINE
    ##########################################################

    ################
    # DIRECT OPEX
    
    REF_CAPACITY_GGEHR = 32300000 / (310 * 24)
    operating_hours = 7884  #ASSUMING THAT THE PLANT IS OPERATING 90 PERCENT OF THE YEAR ( 0.9 X 8760)
    cap_ratio = fuel_GGE_hr / REF_CAPACITY_GGEHR

    #Calculate Electricity Needed to Run the Plant
    total_MW = opex.plant_electricity_MW(fuel_GGE_hr)

    #Calculate Flow of Natural Gas to the Plant
    NG_flow = opex.natural_gas_backup(total_MW, operating_hours)

    #Calculate the Utility Costs
    #PDC IS IN $/ODMT (oven dried metric ton)

    #Feedstock
    forest_cost_yr1 = forest_throughput*PDC_forest
    pulpwood_cost_yr1 = pulpwood_throughput*PDC_pulpwood
    sawmill_cost_yr1 = sawmill_throughput*PDC_sawmill
    feedstock_cost_yr1 = forest_cost_yr1 + pulpwood_cost_yr1 + sawmill_cost_yr1
    steam_cost_yr1 = opex.steam_cost(cap_ratio, CPI,operating_hours, price = 0.00904)
    cooling_water_cost_yr1 = opex.cooling_water_cost(cap_ratio, CPI, operating_hours, price=0.00002)
    wastewater_cost_yr1 = opex.wastewater_cost(cap_ratio, CPI, operating_hours, price= 3.3 / 100)
    ash_cost_yr1 = opex.ash_cost(cap_ratio, CPI, operating_hours, price = 23.52/907)
    hydro_costs_yr1 = opex.hydroprocessing_cost(cap_ratio, CPI, operating_hours, price=4)
    elec_cost_yr1= opex.electricity_cost(total_MW, operating_hours, price=0.072)
    ng_cost_yr1 = opex.natural_gas_cost(NG_flow, 5.09)

    total_utilities_yr1 = steam_cost_yr1 + cooling_water_cost_yr1 + wastewater_cost_yr1 + ash_cost_yr1 + hydro_costs_yr1 + elec_cost_yr1 + ng_cost_yr1


    #Calculate the Costs of Catalysts - CATALYST COSTS ARE DIVIDED BY THREE BECAUSE THEY ARE ONLY CHARGED EVERY THREE YEARS

    CEPCI_current = opex.cepci_from_year(year)

    total_3yr_cost, total_annual_cost =opex.catalyst_costs(
        fuel_GGE_hr = fuel_GGE_hr,
        CEPCI_current = CEPCI_current
    )

    ################################################
    # INDIRECT OPEX
    ###############################################

    indirect_cost_yr1 = opex.indirect_opex_from_FCI(FCI, annual_throughput, CEPCI_current)["Total Indirect Operating Cost"]
    wage_bill_year1 = opex.indirect_opex_from_FCI(FCI, annual_throughput, CEPCI_current)["Operating salaries"]
    #print("I AM INDIRECT COST IN YEAR ONE:", indirect_cost_yr1)
    #total_operating_costs = indirect_costs_yr1 + total_utilities_yr1 + total_annual_cost + total_feedstock_cost #total operating cost in year one


    #############################################################
    # CALCULATE ANNUAL REVENUE in Year 1
    #############################################################

    SAF_rev_yr1 = SAF_L_yr * SAF_price
    DIESEL_rev_yr1 = DIESEL_L_yr * DIESEL_price
    NAPTHA_rev_yr1 = NAPTHA_L_yr * NAPTHA_price
    total_rev_yr1 = SAF_rev_yr1 + DIESEL_rev_yr1 + NAPTHA_rev_yr1

    # ----------------------------------------------------------------
    # YEAR-BY-YEAR CASH FLOW LOOP
    # ----------------------------------------------------------------
    cash_flow_data = []

    # YEAR 0: equity outlay only
    cash_flow_data = []
    cash_flow_data.append({
        'Year':                               0,
        'Loan Balance':                       loan_amount,
        'Annual SAF Generation (L/yr)':       0,
        'Annual Biodiesel Generation (L/yr)': 0,
        'Annual Naptha Generation (L/yr)':    0,
        'SAF Price ($/L)':                    SAF_price,
        'Biodiesel Price ($/L)':              DIESEL_price,
        'Bionaptha Price ($/L)':              NAPTHA_price,
        'Forest Fuel Cost ($/ton)':           PDC_forest,
        'Pulpwood Fuel Cost ($/ton)':         PDC_pulpwood,
        'Sawmill Fuel Cost ($/ton)':          PDC_sawmill,
        'SAF Revenue ($)':                    0,
        'Biodiesel Revenue ($)':              0,
        'Naptha Revenue ($)':                 0,
        'Revenue':                            0,
        'Steam Cost ($)':                     0,
        'Cooling Water Cost ($)':             0,
        'Waste Water Cost ($)':               0,
        'Ash Cost ($)':                       0,
        'Hydroprocessing Cost ($)':           0,
        'Operating Electricity Cost ($)':     0,
        'Operating Natural Gas Cost ($)':     0,
        'Total Feedstock Cost ($)':           0,
        'Forest Residue Cost ($)':            0,
        'Pulpwood Cost ($)':                  0,
        'Sawmill Residue Cost ($)':           0,
        'Catalyst Cost ($)':                  0,
        'Indirect OPEX ($)':                  0,
        'Total Operating Cost':               0,
        'EBITDA':                             0,
        'Depreciation':                       0,
        'EBIT':                               0,
        'Interest Expense':                   0,
        'EBT':                                0,
        'State Tax':                          0,
        'Federal Tax':                        0,
        'Total Tax':                          0,
        'Net Income':                         0,
        'Principal Repayment':                0,
        'Free CF to Equity':                 -equity_invested,
        'Cumulative CF':                     -equity_invested,
        'Discounted CF':                     -equity_invested,
    })

    cumulative_cf             = -equity_invested
    state_loss_carryforward   = 0.0
    federal_loss_carryforward = 0.0

    for yr in range(1, plant_lifespan + 1):

        # 
        # Year 1 = full capacity; Year 2 = (1−d)^1, etc.
        # ------------------------------------------------------------
        deg_mult    = (1 - degredation_factor) ** (yr - 1)

        saf_L_yr    = SAF_L_yr    * deg_mult
        diesel_L_yr = DIESEL_L_yr * deg_mult
        naptha_L_yr = NAPTHA_L_yr * deg_mult

        # ------------------------------------------------------------
        # esc = years elapsed since Year 1 baseline (0 in Year 1).
        # Each cost/price category escalates independently.
        # ------------------------------------------------------------
        esc = yr - 1

        price_mult    = (1 + price_escalation)    ** esc
        fuel_mult     = (1 + fuel_escalation)     ** esc
        cost_mult     = (1 + cost_escalation)     ** esc
        catalyst_mult = (1 + catalyst_escalation) ** esc

        saf_price_yr    = SAF_price    * price_mult
        diesel_price_yr = DIESEL_price * price_mult
        naptha_price_yr = NAPTHA_price * price_mult
        PDC_forest_yr   = PDC_forest   * fuel_mult
        PDC_pulpwood_yr   = PDC_pulpwood          * fuel_mult
        PDC_sawmill_yr   = PDC_sawmill          * fuel_mult

        # ------------------------------------------------------------
        # Annual REVENUE
        # ------------------------------------------------------------
        saf_rev    = saf_L_yr    * saf_price_yr
        diesel_rev = diesel_L_yr * diesel_price_yr
        naptha_rev = naptha_L_yr * naptha_price_yr
        total_rev  = saf_rev + diesel_rev + naptha_rev

        # ------------------------------------------------------------
        #  OPERATING COSTS WITH ESCALATION
        # ------------------------------------------------------------
        forest_cost = forest_throughput*PDC_forest_yr
        pulpwood_cost = pulpwood_throughput*PDC_pulpwood_yr
        sawmill_cost = sawmill_throughput*PDC_sawmill_yr

        feedstock_cost  = forest_cost + pulpwood_cost + sawmill_cost

        steam_cost      = steam_cost_yr1      * cost_mult
        cooling_water   = cooling_water_cost_yr1   * cost_mult
        wastewater      = wastewater_cost_yr1      * cost_mult
        ash_cost        = ash_cost_yr1        * cost_mult
        hydro_cost      = hydro_costs_yr1      * cost_mult
        elec_cost       = elec_cost_yr1       * cost_mult
        ng_cost         = ng_cost_yr1         * cost_mult
        total_utilities = (steam_cost + cooling_water + wastewater +
                           ash_cost + hydro_cost + elec_cost + ng_cost)

        indirect_cost   = indirect_cost_yr1   * cost_mult

        # ------------------------------------------------------------
        # CATALYST COST — EVERY 3 YEARS STARTING YEAR 1
        # Full replacement cost charged in Years 1, 4, 7, 10 ...
        # Base cost also escalated by catalyst_escalation.
        # ------------------------------------------------------------
        if yr % 3 == 1:
            catalyst_cost = total_3yr_cost * catalyst_mult
        else:
            catalyst_cost = 0.0

        # ------------------------------------------------------------
        # TOTAL OPERATING COST
        # ------------------------------------------------------------
        total_op_cost = feedstock_cost + total_utilities + catalyst_cost + indirect_cost

        # ------------------------------------------------------------
        #  DEPRECIATION
        # Pulled from the schedule computed by depreciation_schedule()
        # in Step 3. Zero after the schedule is exhausted.
        # Source: IRS Pub. 946; 26 U.S.C. § 167
        # ------------------------------------------------------------
        year_dep = (annual_depreciation_schedule[yr - 1]
                    if yr <= len(annual_depreciation_schedule) else 0.0)

        # ------------------------------------------------------------
        #  DEBT SERVICE
        # ------------------------------------------------------------
        interest_expense  = interest_sch[yr - 1]
        principal_payment = principal_sch[yr - 1]
        loan_balance      = balance_sch[yr - 1]

        # ------------------------------------------------------------
        # 10i. INCOME STATEMENT
        #
        # EBITDA = Revenue − Operating Costs
        # EBIT   = EBITDA  − Depreciation          (26 U.S.C. § 167)
        # EBT    = EBIT    − Interest               (26 U.S.C. § 163)
        #
        # State tax with loss carry-forward          (26 U.S.C. § 172)
        # Federal tax: state tax is deductible       (26 U.S.C. § 164)
        # Federal rate: TCJA Pub. L. 115-97 § 13001 (2017)
        # ------------------------------------------------------------
        ebitda = total_rev - total_op_cost
        ebit   = ebitda    - year_dep
        ebt    = ebit      - interest_expense

        # State tax with loss carry-forward
        state_taxable = ebt + state_loss_carryforward
        if state_taxable < 0:
            state_loss_carryforward = state_taxable
            state_tax = 0.0
        else:
            state_loss_carryforward = 0.0
            state_tax = state_taxable * state_tax_rate

        # Federal tax with loss carry-forward (state tax deductible)
        fed_taxable = ebt - state_tax + federal_loss_carryforward
        if fed_taxable < 0:
            federal_loss_carryforward = fed_taxable
            federal_tax = 0.0
        else:
            federal_loss_carryforward = 0.0
            federal_tax = fed_taxable * federal_tax_rate

        total_tax  = state_tax + federal_tax
        net_income = ebt - total_tax

        # ------------------------------------------------------------
        # FREE CASH FLOW TO EQUITY
        # ------------------------------------------------------------
        free_cf = net_income + year_dep - principal_payment

        cumulative_cf += free_cf
        discounted_cf  = free_cf / (1 + nominal_discount_rate) ** yr

        # ------------------------------------------------------------
        # 10k. APPEND ROW
        #
        # Costs stored as NEGATIVE numbers — explicit sign convention.
        # ------------------------------------------------------------
        cash_flow_data.append({
            'Year':                               yr,
            'Loan Balance':                       loan_balance,
            'Annual SAF Generation (L/yr)':       saf_L_yr,
            'Annual Biodiesel Generation (L/yr)': diesel_L_yr,
            'Annual Naptha Generation (L/yr)':    naptha_L_yr,
            'SAF Price ($/L)':                    saf_price_yr,
            'Biodiesel Price ($/L)':              diesel_price_yr,
            'Bionaptha Price ($/L)':              naptha_price_yr,
            'Forest Fuel Cost ($/ton)':           PDC_forest_yr,
            'Pulpwood Fuel Cost ($/ton)':         PDC_pulpwood_yr,
            'Sawmill Fuel Cost ($/ton)':          PDC_sawmill_yr,
            'SAF Revenue ($)':                    saf_rev,
            'Biodiesel Revenue ($)':              diesel_rev,
            'Naptha Revenue ($)':                 naptha_rev,
            'Revenue':                            total_rev,
            'Steam Cost ($)':                    -steam_cost,
            'Cooling Water Cost ($)':            -cooling_water,
            'Waste Water Cost ($)':              -wastewater,
            'Ash Cost ($)':                      -ash_cost,
            'Hydroprocessing Cost ($)':          -hydro_cost,
            'Operating Electricity Cost ($)':    -elec_cost,
            'Operating Natural Gas Cost ($)':    -ng_cost,
            'Total Feedstock Cost ($)':          -feedstock_cost,
            'Forest Residue Cost ($)':           -forest_cost,
            'Pulpwood Cost ($)':                 -pulpwood_cost,
            'Sawmill Residue Cost ($)':          -sawmill_cost,
            'Catalyst Cost ($)':                 -catalyst_cost,
            'Indirect OPEX ($)':                 -indirect_cost,
            'Total Operating Cost':              -total_op_cost,
            'EBITDA':                             ebitda,
            'Depreciation':                      -year_dep,
            'EBIT':                               ebit,
            'Interest Expense':                  -interest_expense,
            'EBT':                                ebt,
            'State Tax':                         -state_tax,
            'Federal Tax':                       -federal_tax,
            'Total Tax':                         -total_tax,
            'Net Income':                         net_income,
            'Principal Repayment':               -principal_payment,
            'Free CF to Equity':                  free_cf,
            'Cumulative CF':                      cumulative_cf,
            'Discounted CF':                      discounted_cf,
        })

    df = pd.DataFrame(cash_flow_data)

    # ================================================================
    # FINANCIAL METRICS
    # ================================================================

    # NPV
    npv = df['Discounted CF'].sum()

    # Equity IRR
    equity_cf = [-equity_invested] + list(df['Free CF to Equity'][1:])
    try:
        equity_irr = npf.irr(equity_cf)
    except Exception:
        equity_irr = np.nan

    # Payback period (simple, un-discounted)
    payback_year = None
    for i, row in df.iterrows():
        if row['Cumulative CF'] >= 0 and i > 0:
            prev_cf      = df.loc[i - 1, 'Cumulative CF']
            payback_year = (i - 1) + abs(prev_cf) / row['Free CF to Equity']
            break

    irr_str = f"{equity_irr*100:.2f}%" if not np.isnan(equity_irr) else "N/A"
    pb_str  = f"{payback_year:.2f} yrs" if payback_year else "Never"

    if verbose:
        print(f"\n{'='*60}")
        print(f"{'FINANCIAL RESULTS':^60}")
        print(f"{'='*60}")
        print(f"  NPV (Equity, Nominal):     ${npv:>14,.2f}")
        print(f"  Equity IRR:                {irr_str:>14}")
        print(f"  Payback Period:            {pb_str:>14}")
        print(f"\n  Year 1 SAF:      {df.loc[1,'Annual SAF Generation (L/yr)']:>14,.0f} L")
        print(f"  Year {plant_lifespan} SAF:     {df.loc[plant_lifespan,'Annual SAF Generation (L/yr)']:>14,.0f} L")
        loss = (1 - df.loc[plant_lifespan, 'Annual SAF Generation (L/yr)'] /
                    df.loc[1,             'Annual SAF Generation (L/yr)']) * 100
        print(f"  Output loss (degradation): {loss:>13.2f}%")
        print(f"{'='*60}\n")

    metrics = {
        # Discount / inflation
        'Real Discount Rate':               real_discount_rate,
        'Nominal Discount Rate':            nominal_discount_rate,
        'Inflation Rate':                   inflation_rate,
        # Escalation rates
        'Price Escalation':                 price_escalation,
        'Fuel Escalation':                  fuel_escalation,
        'Cost Escalation':                  cost_escalation,
        'Catalyst Escalation':              catalyst_escalation,
        # Capital
        'Total Capital Investment (TCI)':   TCI,
        'Fixed Capital Investment (FCI)':   FCI,
        'Total PEC':                        total_PEC,
        'Equity Invested':                  equity_invested,
        # Financing
        'Debt Fraction':                    debt_fraction,
        'Loan Amount':                      loan_amount,
        'Loan Rate':                        loan_rate,
        'Loan Term':                        loan_term,
        'Annual Loan Payment':              annual_payment,
        # Production (Year 1, full capacity)
        'SAF (L/yr, Yr1)':                  SAF_L_yr,
        'Diesel (L/yr, Yr1)':               DIESEL_L_yr,
        'Naptha (L/yr, Yr1)':               NAPTHA_L_yr,
        # OPEX (Year 1)
        'Feedstock Cost ($, Yr1)':       feedstock_cost_yr1,
        'Forest Residue Cost ($, Yr1)':  forest_cost_yr1,
        'Pulpwood Cost ($, Yr1)':        pulpwood_cost_yr1,
        'Sawmill Cost ($, Yr1)':         sawmill_cost_yr1,
        'Total Utilities ($, Yr1)':      total_utilities_yr1,
        'Catalyst Replacement Cost (3yr)':  total_3yr_cost,
        'Indirect OPEX ($, Yr1)':        indirect_cost_yr1,
        'Wage Bill ($, Yr1)':            wage_bill_year1,
        # Revenue (Year 1)
        'SAF Revenue ($/yr, Yr1)':          SAF_rev_yr1,
        'Diesel Revenue ($/yr, Yr1)':       DIESEL_rev_yr1,
        'Naptha Revenue ($/yr, Yr1)':       NAPTHA_rev_yr1,
        'Total Revenue ($/yr, Yr1)':        total_rev_yr1,
        # Fuel prices (user-defined)
        'SAF Price ($/L)':                  SAF_price,
        'Diesel Price ($/L)':               DIESEL_price,
        'Naptha Price ($/L)':               NAPTHA_price,
        # Financial results
        'NPV (Equity, Nominal)':            npv,
        'Equity IRR':                       equity_irr,
        'Payback Period (years)':           payback_year,
        'Degradation Factor':               degredation_factor,
    }

    return df, metrics

def solve_mfsp(
        year,
        forest_throughput,
        pulpwood_throughput,
        sawmill_throughput,
        forest_obtainibility,
        pulpwood_obtainibility,
        sawmill_obtainibility,
        distillate,
        plant_lifespan,
        real_discount_rate,
        inflation_rate,
        debt_fraction,
        loan_rate,
        loan_term,
        CPI,
        PDC_forest,    #PLANT DELIVERED COST - THIS COMES FROM JONATHAN'S FEEDSTOCK SUPPLY CHAIN MODEL
        PDC_pulpwood,
        PDC_sawmill,   #PLANT DELIVERED COST - THIS COMES FROM JONATHAN'S FEEDSTOCK SUPPLY CHAIN MODEL
        degredation_factor,
        price_escalation,   #annual escalation applied to all three fuel selling prices
        fuel_escalation,    #annual escalation applied to the feedstock cost
        cost_escalation,    #annual escalation applied to uttilities and indirect opex
        catalyst_escalation, #annual escalation applied to catalyst replacement cost
        federal_tax_rate,
        state_tax_rate):
    diesel_x = 1.02
    diesel_intercept = -0.005
    naptha_x = 0.90
    naptha_intercept = 0.040

    def npv_with_SAF(saf_mfsp):
        diesel_price = diesel_x * saf_mfsp + diesel_intercept
        naptha_price = naptha_x * saf_mfsp + naptha_intercept


        _, met = build_cash_flow_analysis(year, forest_throughput, pulpwood_throughput, sawmill_throughput,forest_obtainibility, pulpwood_obtainibility, sawmill_obtainibility, distillate, plant_lifespan, real_discount_rate, inflation_rate, debt_fraction, loan_rate, loan_term, CPI, PDC_forest, PDC_pulpwood, PDC_sawmill, degredation_factor,
                                      saf_mfsp,
                                      diesel_price,
                                      naptha_price,
                                      price_escalation, fuel_escalation, cost_escalation, catalyst_escalation, federal_tax_rate, state_tax_rate, verbose=False)
    
        return met['NPV (Equity, Nominal)']
    
    #need to create a bracket search to find where the NPV is equal to zero. start with two saf prices that show where the NPV is negative and the NPV is positive
    m_low = 0.01
    m_high = 0.01
    found_bracket = False

    #create a for loop that goes through iterations of the cash flow analysis to find what price would have the NPV at 0
    for _ in range(50): #defined for 50 iterations
        m_high = m_high * 2
        if npv_with_SAF(m_high) > 0:
            found_bracket = True
            break
    if not found_bracket:
        raise RuntimeError("Could not find a SAF Price that makes NPV Positive")
        
    #use brentq to to find the minimum fuel selling price
    saf_mfsp_solved = brentq(npv_with_SAF, m_low, m_high, xtol = 1e-6)

    diesel_mfsp = diesel_x * saf_mfsp_solved + diesel_intercept
    naptha_mfsp = naptha_x * saf_mfsp_solved + naptha_intercept

    df_mfsp, metrics_mfsp = build_cash_flow_analysis(
    year, forest_throughput, pulpwood_throughput, sawmill_throughput, forest_obtainibility, pulpwood_obtainibility, sawmill_obtainibility, distillate, plant_lifespan,
    real_discount_rate, inflation_rate, debt_fraction,
    loan_rate, loan_term, CPI, PDC_forest, PDC_pulpwood, PDC_sawmill, degredation_factor,
    saf_mfsp_solved,
    diesel_mfsp,
    naptha_mfsp,
    price_escalation, fuel_escalation,
    cost_escalation, catalyst_escalation,
    federal_tax_rate, state_tax_rate,verbose = False)

    return {
    'MFSP SAF ($/L)':    saf_mfsp_solved,
    'MFSP Diesel ($/L)': diesel_mfsp,
    'MFSP Naptha ($/L)': naptha_mfsp,
    'NPV at MFSP':       metrics_mfsp['NPV (Equity, Nominal)'],
    'df at MFSP':        df_mfsp,
    'metrics at MFSP':   metrics_mfsp,}
