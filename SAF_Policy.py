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
import SAF_Economics as sf

_BG="#0e1621";_BG_AX="#131f2e";_GRID="#1e2d3d";_TEXT="#c9d1e0";_SPINE="#1e2d3d"

def plot_policy_comparison(df1, df2):
    years = df1['Year'].iloc[1:].values
    cf1 = df1['Free CF to Equity'].iloc[1:].values / 1e6
    cf2 = df2['Free CF to Equity'].iloc[1:].values / 1e6

    x = np.arange(len(years))
    width = 0.35

    fig, ax = plt.subplots(figsize=(16, 5.5))
    fig.patch.set_facecolor(_BG)
    ax.set_facecolor(_BG_AX)

    ax.bar(x - width/2, cf1, width, label='No policy',            color='#6b7280', alpha=0.9)
    ax.bar(x + width/2, cf2, width, label='IRA 45Z Clean Fuel Credit', color='#1D9E75', alpha=0.9)

    ax.set_xlabel('Year', fontsize=14, color=_TEXT)
    ax.set_ylabel('Cash Flow ($M)', fontsize=14, color=_TEXT)
    ax.set_title('Annual FCF to Equity — SAF Policy Scenarios',
                 fontsize=16, fontweight='bold', color=_TEXT)
    ax.set_xticks(x)
    ax.set_xticklabels(years, fontsize=9, color=_TEXT)
    ax.tick_params(colors=_TEXT, labelsize=11)
    for lbl in ax.get_xticklabels() + ax.get_yticklabels():
        lbl.set_color(_TEXT)
    import matplotlib.ticker as _mtick
    ax.yaxis.set_major_formatter(_mtick.FuncFormatter(lambda v, _: f'${v:.0f}M'))
    leg = ax.legend(fontsize=12, facecolor=_BG, edgecolor=_SPINE)
    for t in leg.get_texts(): t.set_color(_TEXT)
    ax.grid(axis='y', linestyle='--', linewidth=0.5, color=_GRID)
    ax.set_axisbelow(True)
    ax.spines[['top','right']].set_visible(False)
    ax.spines[['left','bottom']].set_color(_SPINE)

    plt.tight_layout()
    plt.savefig('Policy_plots/policy_comparison.png', dpi=150, bbox_inches='tight')

def credit_cash_flow_analysis(
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
        PDC_pulpwood,    #PLANT DELIVERED COST - THIS COMES FROM JONATHAN'S FEEDSTOCK SUPPLY CHAIN MODEL
        PDC_sawmill,    #PLANT DELIVERED COST - THIS COMES FROM JONATHAN'S FEEDSTOCK SUPPLY CHAIN MODEL
        degredation_factor,
        SAF_price,
        DIESEL_price,
        NAPTHA_price,
        price_escalation,   #annual escalation applied to all three fuel selling prices
        fuel_escalation,    #annual escalation applied to the feedstock cost
        cost_escalation,    #annual escalation applied to uttilities and indirect opex
        catalyst_escalation, #annual escalation applied to catalyst replacement cost
        credit_SAF = 0.35,
        credit_nonSAAF = 0.20,
        credit_duration = 10,
        federal_tax_rate = 0.21,
        state_tax_rate = 0.07,
        verbose = True
):
    #
    ########################## HOW MUCH FUEL ARE WE PRODUCING ###############

    forest_throughput = forest_throughput * forest_obtainibility
    pulpwood_throughput = pulpwood_throughput * pulpwood_obtainibility
    sawmill_throughput = sawmill_throughput * sawmill_obtainibility

    annual_throughput = forest_throughput + pulpwood_throughput + sawmill_throughput

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
    forest_feedstock_cost_yr1 = forest_throughput * PDC_forest # tons * dollar/ton
    pulpwood_feedstock_cost_yr1 = pulpwood_throughput * PDC_pulpwood # tons * dollar/ton
    sawmill_feedstock_cost_yr1 = sawmill_throughput * PDC_sawmill # tons * dollar/ton
    feedstock_cost_yr1 = forest_feedstock_cost_yr1 + pulpwood_feedstock_cost_yr1 + sawmill_feedstock_cost_yr1

    #Utilities
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
        'Feedstock Cost ($)':                 0,
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
        

        saf_GGE = saf_GGE_hr * 7884
        diesel_GGE = diesel_GGE_hr * 7884
        naptha_GGE = naptha_GGE_hr * 7884

        

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
        PDC_forest_yr          = PDC_forest         * fuel_mult ##doesnt the fuel multiplier change? 
        PDC_pulpwood_yr        = PDC_pulpwood       * fuel_mult
        PDC_sawmill_yr         = PDC_sawmill        * fuel_mult

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
        #feedstock_cost  = forest_feedstock_cost_yr1 * PDC_forest_yr + pulpwood_feedstock_cost_yr1 * PDC_pulpwood_yr + sawmill_feedstock_cost_yr1 * PDC_sawmill_yr ##is this correct as well

        forest_cost    = forest_throughput  * PDC_forest_yr
        pulpwood_cost  = pulpwood_throughput * PDC_pulpwood_yr
        sawmill_cost   = sawmill_throughput  * PDC_sawmill_yr
        feedstock_cost = forest_cost + pulpwood_cost + sawmill_cost

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

        # --- credits as separate cash inflow ---
        if yr <= credit_duration:
            total_credits = (saf_GGE * credit_SAF 
                        + diesel_GGE * credit_nonSAAF 
                        + naptha_GGE * credit_nonSAAF)
            SAF_tax_credit = saf_GGE * credit_SAF 
            DIESEL_tax_credit = diesel_GGE * credit_nonSAAF 
            NAPTHA_tax_credit = naptha_GGE * credit_nonSAAF
        else:
            total_credits = 0.0

        total_tax  = state_tax + federal_tax - total_credits
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
            'Forest Fuel Cost ($/ton)':           PDC_forest,
            'Pulpwood Fuel Cost ($/ton)':         PDC_pulpwood,
            'Sawmill Fuel Cost ($/ton)':          PDC_sawmill,
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
            'Feedstock Cost ($)':                -feedstock_cost,
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
        'Total Utilities ($, Yr1)':      total_utilities_yr1,
        'Catalyst Replacement Cost (3yr)':  total_3yr_cost,
        'Indirect OPEX ($, Yr1)':        indirect_cost_yr1,
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

def required_credit_for_market(
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
        PDC_pulpwood,    #PLANT DELIVERED COST - THIS COMES FROM JONATHAN'S FEEDSTOCK SUPPLY CHAIN MODEL
        PDC_sawmill,    #PLANT DELIVERED COST - THIS COMES FROM JONATHAN'S FEEDSTOCK SUPPLY CHAIN MODEL
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
        verbose = False
):
    def npv_given_credit(credit_SAF):
        credit_nonSAAF = credit_SAF / 1.75
        _, metrics = credit_cash_flow_analysis(year,
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
        PDC_pulpwood,    #PLANT DELIVERED COST - THIS COMES FROM JONATHAN'S FEEDSTOCK SUPPLY CHAIN MODEL
        PDC_sawmill,    #PLANT DELIVERED COST - THIS COMES FROM JONATHAN'S FEEDSTOCK SUPPLY CHAIN MODEL
        degredation_factor,
        SAF_price,
        DIESEL_price,
        NAPTHA_price,
        price_escalation,   #annual escalation applied to all three fuel selling prices
        fuel_escalation,    #annual escalation applied to the feedstock cost
        cost_escalation,    #annual escalation applied to uttilities and indirect opex
        catalyst_escalation, #annual escalation applied to catalyst replacement cost
        credit_SAF = credit_SAF,
        credit_nonSAAF = credit_nonSAAF,
        credit_duration = 10,
        federal_tax_rate = 0.21,
        state_tax_rate = 0.07,
        verbose = False)
        return metrics['NPV (Equity, Nominal)']


    m_low = 0.001
    m_high = 0.50
    found_bracket = False

    for _ in range(500):
       # print('TEST')
        m_high = m_high*2
        if npv_given_credit(m_high) > 0:
            found_bracket = True
            break
    if not found_bracket:
        raise RuntimeError("Could not find Tax Credit to make NPV > 0")
    
    SAF_Credit_Solved = brentq(npv_given_credit, m_low, m_high, xtol = 1e-6)
    NonSAF_Credit_Solved = SAF_Credit_Solved / 1.75

    print(f"\n=== REQUIRED CREDIT FOR BREAKEVEN ===")
    print(f"  SAF Market Price:     ${SAF_price:.2f}/L")
    print(f"  Diesel Market Price:     ${DIESEL_price:.2f}/L")
    print(f"  Naptha Market Price:     ${NAPTHA_price:.2f}/L")
    print(f"  Required SAF Credit:  $ (${SAF_Credit_Solved:.6f}/g)")
    print(f"  Required NonSAF Credit:  $ (${NonSAF_Credit_Solved:.6f}/g)")
    #print(f"Net Present Value: ${metrics_solved['NPV (Equity, Nominal)']})")
    #print(f"  Credit Years:     {credit_years} yrs")

    return SAF_Credit_Solved, NonSAF_Credit_Solved


def get_model_inputs():
    """
    Returns a dictionary of all user controlled assumptions
    """
    inputs = {
        'year': 2025, # Year For Analaysis

        #Feedstock and Plant Specifications
        'forest_throughput' : 100_000, #tons/year
        'pulpwood_throughput' : 50_000, #tons/year
        'sawmill_throughput' : 50_000, #tons/year
        'forest_obtainibility' : 1, #percent of forest feedstock that can be obtained
        'pulpwood_obtainibility' : 1, #percent of pulpwood feedstock that can be obtained
        'sawmill_obtainibility' : 1, #percent of sawmill feedstock that can be obtained
        'distillate' : 'distillate 1', #Distillation Type 
        'plant_lifespan' : 40, #plant lifespan/time horizon for analysis

        #Discount Rates
        'real_discount_rate': 0.10, #equity required return, real money terms 
        'inflation_rate' : 0.025, #general price inflation

        # Financing Options
        'debt_fraction' : 0.60,  #percent of plant financed by bank
        'loan_rate': 0.10, #interest rate on loan payment
        'loan_term': 15, #how long you are paying back the loan


        'CPI' : 321.05, #Consumer Price Index, take directly from online
        'PDC_forest' : 30,    #PLANT DELIVERED COST - THIS COMES FROM JONATHAN'S FEEDSTOCK SUPPLY CHAIN MODEL
        'PDC_pulpwood' : 30,    #PLANT DELIVERED COST - THIS COMES FROM JONATHAN'S FEEDSTOCK SUPPLY CHAIN MODEL
        'PDC_sawmill' : 25,    #PLANT DELIVERED COST - THIS COMES FROM JONATHAN'S FEEDSTOCK SUPPLY CHAIN MODEL

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
    print("BIOFUEL PRODUCTION PLANT PLANT POLICY ANALYSIS")
    print("="*65)

    p = get_model_inputs()

    
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

    SAF_mfsp = mfsp[ 'MFSP SAF ($/L)']
    DIESEL_mfsp = mfsp['MFSP Diesel ($/L)']
    NAPTHA_mfsp = mfsp['MFSP Naptha ($/L)']

    print("\n" + "="*5)
    print('SAF MFSP:',SAF_mfsp)
    print('Diesel MFSP:',DIESEL_mfsp)
    print('Naptha MFSP:',NAPTHA_mfsp)
    print("="*5)

    #do the problem selling with no policy

    df1, metrics1 = sf.build_cash_flow_analysis(
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
        SAF_mfsp,
        DIESEL_mfsp,
        NAPTHA_mfsp,
        p['price_escalation'],
        p['fuel_escalation'],
        p['cost_escalation'],
        p['catalyst_escalation'],
        p['federal_tax_rate'],
        p['state_tax_rate']
    )

    ## Now sell with Policy

    df2, metrics3 = credit_cash_flow_analysis(
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
        SAF_mfsp,
        DIESEL_mfsp,
        NAPTHA_mfsp,
        p['price_escalation'],
        p['fuel_escalation'],
        p['cost_escalation'],
        p['catalyst_escalation']
    )
    #figs = sp.plot_annual_cashflow(df, metrics)
    plot_policy_comparison(df1, df2)

    # Show the Current Market Prices for Jet-A, Diesel, and Naptha in $/L
    JET_market = 0.82 # $/L
    DIESEL_market = 1.34 # $/L
    NAPTHA_market = 0.98 # $/L, price of gasoline is assumed for naptha

    SAF_Credit_Solved, NonSAF_Credit_Solved = required_credit_for_market(
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
        JET_market,
        DIESEL_market,
        NAPTHA_market,
        p['price_escalation'],
        p['fuel_escalation'],
        p['cost_escalation'],
        p['catalyst_escalation'],
        p['federal_tax_rate'],
        p['state_tax_rate']
    )

    

    print("\n" + "="*65)
    print("ANALYSIS COMPLETE")
    print("="*65)

if __name__ == "__main__":
    main()