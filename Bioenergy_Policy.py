######### BIOENERGY WITH POLICY INCORPORATED IINTO THE SCRIPT ##########
from math import tanh
from math import exp
import numpy as np
import numpy_financial as npf
import pandas as pd
from scipy.optimize import brentq
from BioEnergy_Economics import predict_output
import matplotlib.pyplot as plt
import Bioenergy_dependencies.bioenergy_costs_FINAL as bc
import Bioenergy_dependencies.bioenergy_finance_FINAL as bf
import Bioenergy_dependencies.bioenergyproduction_FINAL as bp
from Bioenergy_dependencies.bioenergy_plots_FINAL import plot_all
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np


FIXED_OM_FACTOR = 4.2  # % of installed cost ($/yr)
VAR_OM_FACTOR = 4.7    # (USD/MWh)


# ── Dark theme constants ──────────────────────────────────────────────────────
_BG = "#0e1621"; _BG_AX = "#131f2e"; _GRID = "#1e2d3d"
_TEXT = "#c9d1e0"; _SPINE = "#1e2d3d"
_GREY = "#6b7280"; _TEAL = "#1D9E75"; _BLUE = "#378ADD"

def plot_policy_comparison(df1, df2, df3):
    years = df1['Year'].iloc[1:].values
    cf1 = df1['Free CF to Equity'].iloc[1:].values / 1e6
    cf2 = df2['Free CF to Equity'].iloc[1:].values / 1e6
    cf3 = df3['Free CF to Equity'].iloc[1:].values / 1e6

    x = np.arange(len(years))
    width = 0.28

    fig, ax = plt.subplots(figsize=(16, 5.5))
    fig.patch.set_facecolor(_BG)
    ax.set_facecolor(_BG_AX)

    ax.bar(x - width, cf1, width, label='No policy',             color=_GREY, alpha=0.9)
    ax.bar(x,         cf2, width, label='Production credit (PTC)', color=_TEAL, alpha=0.9)
    ax.bar(x + width, cf3, width, label='Investment credit (ITC)',  color=_BLUE, alpha=0.9)

    ax.set_xlabel('Year', fontsize=14, color=_TEXT)
    ax.set_ylabel('Cash Flow ($M)', fontsize=14, color=_TEXT)
    ax.set_title('Annual FCF to Equity — Policy Scenarios', fontsize=16,
                 fontweight='bold', color=_TEXT)
    ax.set_xticks(x)
    ax.set_xticklabels(years, fontsize=9, color=_TEXT)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f'${v:.0f}M'))
    ax.tick_params(colors=_TEXT, labelsize=11)
    for lbl in ax.get_xticklabels() + ax.get_yticklabels():
        lbl.set_color(_TEXT)
    leg = ax.legend(fontsize=12, facecolor=_BG, edgecolor=_SPINE)
    for t in leg.get_texts(): t.set_color(_TEXT)
    ax.grid(axis='y', linestyle='--', linewidth=0.5, color=_GRID)
    ax.set_axisbelow(True)
    ax.spines[['top','right']].set_visible(False)
    ax.spines[['left','bottom']].set_color(_SPINE)

    plt.tight_layout()
    plt.savefig('Policy_plots/policy_comparison.png', dpi=150, bbox_inches='tight')


def policy_revenue(case, product_stream=0, FCI=0):
    """
    Calculates the Revenue from Policy
    Inputs: case - string indicating base or optimized credit
            product_stream - numeric value (kWh for bioenergycredit, gallons for safcredit)

    Outputs: revenue - calculated revenue based on policy
    """
    if case == 'basecredit':
        revenue = product_stream * 0.003  # renewable energy production credit (base credit of 0.3 cents per kWh)
    elif case == 'investmentcredit':
        #hshs
        revenue = FCI * 0.06
    else:
        revenue = 0  # or raise an error if you prefer
    
    return revenue


def base_credit_cash_flow_analysis(case,
    TCI, FCI,
    annual_depreciation_schedule,
    annual_AC_year1,
    forest_annual_tons,
    mill_annual_tons,
    degradation_factor,
    capacity_factor,
    Plant_Lifespan,
    c_fuel_per_ton_forest,
    c_fuel_per_ton_mill,
    electricity_price,
    real_discount_rate,
    inflation_rate,
    debt_fraction,
    loan_rate,
    loan_term,
    electricity_escalation,
    fuel_escalation,
    fixed_om_escalation,
    var_om_escalation,
    federal_tax_rate = 0.21,
    state_tax_rate   = 0.07,
    verbose = True
):
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
        print(f"  Years {loan_term+1}-{Plant_Lifespan}: debt-free — most profitable period")

    itc_amount = 0.0
    if case == 'investmentcredit':
        itc_amount = policy_revenue('investmentcredit',FCI=FCI)
        print("I AM TOTAL INVESTMENT TAX CREDIT:", itc_amount)
        basis_reduction = 0.50 * itc_amount
        total_dep = sum(annual_depreciation_schedule) #https://irc.bloombergtax.com/public/uscode/doc/irc/section_50
        if total_dep > 0:
            scale_factor = (total_dep - basis_reduction) / total_dep
            annual_depreciation_schedule = [d * scale_factor
                                            for d in annual_depreciation_schedule]
        else:
            scale_factor = 1.0
            
        if verbose:
            print(f"\n=== ITC BASIS REDUCTION ===")
            print(f"  ITC Amount:         ${itc_amount:,.2f}")
            print(f"  Basis Reduction:    ${basis_reduction:,.2f}")
            print(f"  Scale Factor:       {scale_factor:.6f}")
            print(f"  Original Total Dep: ${total_dep:,.2f}")
            print(f"  Adjusted Total Dep: ${sum(annual_depreciation_schedule):,.2f}")

    # ----------------------------------------------------------------
    #  LOAN AMORTIZATION
    # ----------------------------------------------------------------
    interest_sch, principal_sch, balance_sch, annual_payment = \
        bf.build_loan_schedule(loan_amount, loan_rate, loan_term, Plant_Lifespan)

    if loan_amount > 0:
        #print(f"\n  Annual P&I (fixed): ${annual_payment:,.2f}")
        #print(f"  Yr | Beg Balance     | Interest       | Principal      | End Balance")
        # print(f"  ---+----------------+----------------+----------------+---------------")
        beg = loan_amount
        for yr in range(min(loan_term, Plant_Lifespan)):
            #print(f"  {yr+1:2d} | ${beg:>13,.2f} | ${interest_sch[yr]:>13,.2f} "
            #      f"| ${principal_sch[yr]:>13,.2f} | ${balance_sch[yr]:>13,.2f}")
            beg = balance_sch[yr]

    # ----------------------------------------------------------------
    #  PLANT PARAMETERS
    # ----------------------------------------------------------------
    params = bf.calculate_financial_parameters(
        FCI, annual_AC_year1, capacity_factor, real_discount_rate, Plant_Lifespan)

    annual_gen_kwh_yr1 = params['Annual Generation (kWh)']
    annual_gen_mwh_yr1 = params['Annual Generation (MWh)']
    fixed_om_yr1       = params['Fixed O&M ($)']
    var_om_per_kwh_yr1 = params['Variable O&M/kWh ($)']
    var_om__yr1 = params['Variable O&M ($)']
    plant_capacity = params['Plant Capacity (MW)']

    # Year 1 fuel costs — calculated separately per feedstock
    forest_fuel_cost_yr1 = forest_annual_tons * c_fuel_per_ton_forest
    mill_fuel_cost_yr1   = mill_annual_tons   * c_fuel_per_ton_mill
    total_fuel_cost_yr1  = forest_fuel_cost_yr1 + mill_fuel_cost_yr1
    annual_revenue_yr1   = annual_gen_mwh_yr1 * electricity_price

    if verbose:
        print(f"\n=== YEAR 1 BASELINE — KEY NUMBERS ===")
        print(f"  Revenue:            ${annual_revenue_yr1:,.2f}")
        print(f"  Forest Fuel Cost:   ${forest_fuel_cost_yr1:,.2f}  "
            f"[{forest_annual_tons:,} tons × ${c_fuel_per_ton_forest:.2f}/ton]")
        print(f"  Mill Fuel Cost:     ${mill_fuel_cost_yr1:,.2f}  "
            f"[{mill_annual_tons:,} tons × ${c_fuel_per_ton_mill:.2f}/ton]")
        print(f"  Total Fuel Cost:    ${total_fuel_cost_yr1:,.2f}")
        #print(f"  NOTE: Fuel volumes are FLAT every year (fixed throughput).")
        #print(f"\n  Escalation rates — 0.0=flat/real, >0=nominal:")
        #print(f"    Electricity {electricity_escalation*100:.2f}%/yr | "
            #  f"Fuel {fuel_escalation*100:.2f}%/yr (both feedstocks) | "
            #  f"Fixed O&M {fixed_om_escalation*100:.2f}%/yr | "
            #  f"Var O&M {var_om_escalation*100:.2f}%/yr")

    # ----------------------------------------------------------------
    # YEAR-BY-YEAR CASH FLOW LOOP
    # ----------------------------------------------------------------
    itc_carryforward = itc_amount if case == 'investmentcredit' else 0.0
    cash_flow_data = []

    # YEAR 0: equity outlay only
    cash_flow_data.append({
        'Year': 0, 'Loan Balance': loan_amount,
        'Annual Generation (kWh)':   0,
        'Annual Generation (MWh)':   0,
        'Electricity Price ($/MWh)': electricity_price,
        'Forest Fuel Cost ($/ton)':  c_fuel_per_ton_forest,
        'Mill Fuel Cost ($/ton)':    c_fuel_per_ton_mill,
        'Revenue':             0,
        'Policy Credits':      0,
        'Fixed O&M':           0,
        'Variable O&M':        0,
        'Forest Fuel Cost ($)': 0,
        'Mill Fuel Cost ($)':   0,
        'Total Fuel Cost ($)':  0,
        'Total Operating Cost': 0,
        'EBITDA':              0,
        'Depreciation':        0,
        'EBIT':                0,
        'Interest Expense':    0,
        'EBT':                 0,
        'State Tax':           0,
        'Federal Tax':         0,
        'Total Tax':           0,
        'Net Income':          0,
        'Principal Repayment': 0,
        'Free CF to Equity':  -equity_invested,
        'Cumulative CF':      -equity_invested,
        'Discounted CF':      -equity_invested,
    })

    cumulative_cf             = -equity_invested
    state_loss_carryforward   = 0.0
    federal_loss_carryforward = 0.0

    for year in range(1, Plant_Lifespan + 1):

        # Generation degrades
        deg_mult       = (1 - degradation_factor) ** (year - 1)
        annual_gen_kwh = annual_gen_kwh_yr1 * deg_mult
        annual_gen_mwh = annual_gen_kwh / 1000

        # Escalation multipliers
        esc = year - 1
        elec_price_yr            = electricity_price      * (1 + electricity_escalation) ** esc
        c_fuel_per_ton_forest_yr = c_fuel_per_ton_forest  * (1 + fuel_escalation)        ** esc
        c_fuel_per_ton_mill_yr   = c_fuel_per_ton_mill    * (1 + fuel_escalation)        ** esc
        fixed_om_yr              = fixed_om_yr1            * (1 + fixed_om_escalation)    ** esc
        var_om_rate_yr           = var_om_per_kwh_yr1      * (1 + var_om_escalation)      ** esc

        # Revenue
        annual_revenue = annual_gen_mwh * elec_price_yr
        #print("I AM REVENUE:", annual_revenue)

        # Operating costs — fuel tracked separately per feedstock
        forest_fuel_cost = forest_annual_tons * c_fuel_per_ton_forest_yr
        mill_fuel_cost   = mill_annual_tons   * c_fuel_per_ton_mill_yr
        total_fuel_cost  = forest_fuel_cost + mill_fuel_cost
        var_om           = var_om_rate_yr * annual_gen_kwh
        total_op_cost    = fixed_om_yr + var_om + total_fuel_cost
        #print("I AM TOTAL ANNUAL COST:", total_op_cost)
        # Policy credits
        # if year <= 10:
        #     policy_credits = policy_revenue('basecredit', product_stream=annual_gen_kwh)
        # else:
        #     policy_credits = 0.0

        if case == 'basecredit' and year <=10:
            policy_credits = policy_revenue('basecredit', product_stream=annual_gen_kwh)
        elif case == 'investmentcredit' and year ==1:
            policy_credits = policy_revenue('investmentcredit',FCI = FCI) # https://www.law.cornell.edu/uscode/text/26/48E
            #print("I AM THE TOTAL INVESTMENT CREDIT!!!!!!!!!!:", policy_credits)
        else:
            policy_credits = 0

        # Depreciation
        year_dep = (annual_depreciation_schedule[year - 1]
                    if year <= len(annual_depreciation_schedule) else 0.0)
        #print("I AM DEPRECIATION:", year_dep)
        
        # Debt service
        interest_expense  = interest_sch[year - 1]
        principal_payment = principal_sch[year - 1]
        loan_balance      = balance_sch[year - 1]

        # Income statement
        ebitda = annual_revenue - total_op_cost
        #print("I AM EBITDA:", ebitda)
        ebit   = ebitda - year_dep  # https://www.irs.gov/publications/p946, https://www.law.cornell.edu/uscode/text/26/167
        #print("I AM EBIT:", ebit)
        # Interest deducted before tax (tax shield)
        ebt = ebit - interest_expense  # https://www.law.cornell.edu/uscode/text/26/163
        #print("I AM EBT:", ebt)
        # State tax with loss carryforward
        state_taxable = ebt + state_loss_carryforward  # https://www.law.cornell.edu/uscode/text/26/172
        #print("I AM STATE TAXABLE:", state_taxable)
        if state_taxable < 0:
            state_loss_carryforward = state_taxable
            state_tax = 0.0
        else:
            state_loss_carryforward = 0.0
            state_tax = state_taxable * state_tax_rate  # Brealey, Myers & Allen (2023), Ch. 19
        #print("I AM STATE TAX", state_tax)

        # Federal tax — state tax deductible
        fed_taxable = ebt - state_tax + federal_loss_carryforward  # https://www.law.cornell.edu/uscode/text/26/164
        #print("I AM FED TAXABLE:", fed_taxable)
        if fed_taxable < 0:
            federal_loss_carryforward = fed_taxable
            federal_tax = 0.0
        else:
            federal_loss_carryforward = 0.0
            federal_tax = fed_taxable * federal_tax_rate  # TCJA Pub. L. 115-97, § 13001 (2017)
        #print("I AM FED TAX", federal_tax)
        if case == 'investmentcredit': # https://uslawexplained.com/form_3468
            raw_tax = state_tax + federal_tax
            credit_used        = min(itc_carryforward, raw_tax)   # can't reduce below zero
            itc_carryforward  -= credit_used                      # reduce the remaining balance of what was used each year
            #print("I AM ITC CARRY FORWARD:", itc_carryforward)
            total_tax          = raw_tax - credit_used
            policy_credits     = credit_used                      # for record keeping in your df
        elif case == 'basecredit' and year <=10:
        #Production Tax Credits are Direct Reductions of the Tax Bill Owed, and are Not Tax Deduction, which reduce the amount of taxable income
            total_tax  = state_tax + federal_tax - policy_credits # https://legalclarity.org/understanding-the-production-tax-credit-under-irc-section-45/
        else:
            policy_credits = 0.0
            total_tax = state_tax + federal_tax

        net_income = ebt - total_tax

        # Free CF to Equity
        free_cf = net_income + year_dep - principal_payment  # SFAS No. 95; Damodaran (2012), Ch. 3

        cumulative_cf += free_cf
        discounted_cf  = free_cf / (1 + nominal_discount_rate) ** year

        cash_flow_data.append({
            'Year':                        year,
            'Loan Balance':                loan_balance,
            'Annual Generation (kWh)':     annual_gen_kwh,
            'Annual Generation (MWh)':     annual_gen_mwh,
            'Electricity Price ($/MWh)':   elec_price_yr,
            'Forest Fuel Cost ($/ton)':    c_fuel_per_ton_forest_yr,
            'Mill Fuel Cost ($/ton)':      c_fuel_per_ton_mill_yr,
            'Revenue':                     annual_revenue,
            'Policy Credits':              policy_credits,
            'Fixed O&M':                  -fixed_om_yr,
            'Variable O&M':               -var_om,
            'Forest Fuel Cost ($)':       -forest_fuel_cost,
            'Mill Fuel Cost ($)':         -mill_fuel_cost,
            'Total Fuel Cost ($)':        -total_fuel_cost,
            'Total Operating Cost':       -total_op_cost,
            'EBITDA':                      ebitda,
            'Depreciation':               -year_dep,
            'EBIT':                        ebit,
            'Interest Expense':           -interest_expense,
            'EBT':                         ebt,
            'State Tax':                  -state_tax,
            'Federal Tax':                -federal_tax,
            'Total Tax':                  -total_tax,
            'Net Income':                  net_income,
            'Principal Repayment':        -principal_payment,
            'Free CF to Equity':           free_cf,
            'Cumulative CF':               cumulative_cf,
            'Discounted CF':               discounted_cf,
        })

    df = pd.DataFrame(cash_flow_data)

    # ----------------------------------------------------------------
    # FINANCIAL METRICS
    # ----------------------------------------------------------------

    # NPV
    npv = df['Discounted CF'].sum()

    # Equity IRR
    equity_cf = [-equity_invested] + list(df['Free CF to Equity'][1:])
    try:
        equity_irr = npf.irr(equity_cf)
    except Exception:
        equity_irr = np.nan

    # # LCOE: NPV(costs) / NPV(generation)
    # pv_costs = equity_invested
    # pv_gen   = 0.0
    # for _, row in df[df['Year'] > 0].iterrows():
    #     yr = int(row['Year'])
    #     d  = (1 + nominal_discount_rate) ** yr
    #     pv_costs += abs(row['Total Operating Cost']) / d
    #     pv_gen   += row['Annual Generation (kWh)']   / d
    # lcoe_kwh = pv_costs / pv_gen if pv_gen > 0 else np.nan
    # lcoe_mwh = lcoe_kwh * 1000

    # Payback
    payback_year = None
    for i, row in df.iterrows():
        if row['Cumulative CF'] >= 0 and i > 0:
            prev_cf      = df.loc[i - 1, 'Cumulative CF']
            payback_year = (i - 1) + abs(prev_cf) / row['Free CF to Equity']
            break

    metrics = {
        **params,
        'Real Discount Rate':            real_discount_rate,
        'Nominal Discount Rate':         nominal_discount_rate,
        'Inflation Rate':                inflation_rate,
        'Electricity Escalation':        electricity_escalation,
        'Fuel Escalation':               fuel_escalation,
        'Fixed O&M Escalation':          fixed_om_escalation,
        'Var O&M Escalation':            var_om_escalation,
        'Debt Fraction':                 debt_fraction,
        'Loan Amount':                   loan_amount,
        'Equity Invested':               equity_invested,
        'Loan Rate':                     loan_rate,
        'Loan Term':                     loan_term,
        'Annual Loan Payment':           annual_payment,
        'NPV (Equity, Nominal)':         npv,
        'Equity IRR':                    equity_irr,
        # 'LCOE ($/kWh)':                  lcoe_kwh,
        # 'LCOE ($/MWh)':                  lcoe_mwh,
        'Payback Period (years)':        payback_year,
        'Total Capital Investment':      TCI,
        'FCI':                           FCI,
        'Forest Annual Tons':            forest_annual_tons,
        'Mill Annual Tons':              mill_annual_tons,
        'Forest Fuel Cost ($/ton, Yr1)': c_fuel_per_ton_forest,
        'Mill Fuel Cost ($/ton, Yr1)':   c_fuel_per_ton_mill,
        'Forest Fuel Cost ($/yr, Yr1)':  forest_fuel_cost_yr1,
        'Mill Fuel Cost ($/yr, Yr1)':    mill_fuel_cost_yr1,
        'Total Fuel Cost ($/yr, Yr1)':   total_fuel_cost_yr1,
        'Annual Revenue (Yr1)':          annual_revenue_yr1,
        'Degradation Factor':            degradation_factor,
    }

    irr_str = f"{equity_irr*100:.2f}%" if not np.isnan(equity_irr) else "N/A"
    pb_str  = f"{payback_year:.2f} yrs" if payback_year else "Never"

    if verbose:
        print(f"\n{'='*60}")
        print(f"{'FINANCIAL RESULTS':^60}")
        print(f"{'='*60}")
        print(f"  NPV (Equity, Nominal):  ${npv:>14,.2f}")
        print(f"Credit Applied: ${0.003}")
        print(f"  Equity IRR:             {irr_str:>14}")
        #print(f"  LCOE:                   ${lcoe_mwh:>13.2f}/MWh")
        print(f"  Payback Period:         {pb_str:>14}")
        print(f"\n  Year 1 Output:  {df.loc[1,'Annual Generation (MWh)']:,.0f} MWh")
        print(f"  Year {Plant_Lifespan} Output: {df.loc[Plant_Lifespan,'Annual Generation (MWh)']:,.0f} MWh")
        loss = (1 - df.loc[Plant_Lifespan,'Annual Generation (MWh)'] /
                    df.loc[1,'Annual Generation (MWh)']) * 100
        print(f"  Output loss:    {loss:.2f}%  (degradation only — fuel cost unchanged)")
        print(f"{'='*60}\n")

        
    return df, metrics


def needed_credit_cash_flow_analysis(
    TCI, 
    FCI,
    annual_depreciation_schedule,
    annual_AC_year1,
    forest_annual_tons,
    mill_annual_tons,
    degradation_factor,
    capacity_factor,
    Plant_Lifespan,
    c_fuel_per_ton_forest,
    c_fuel_per_ton_mill,
    electricity_price,
    real_discount_rate,
    inflation_rate,
    debt_fraction,
    loan_rate,
    loan_term,
    electricity_escalation,
    fuel_escalation,
    fixed_om_escalation,
    var_om_escalation,
    credit_per_kWh = 0.001,
    credit_duration = 10,
    federal_tax_rate = 0.21,
    state_tax_rate   = 0.07,
    verbose = True
):
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
        print(f"  Years {loan_term+1}-{Plant_Lifespan}: debt-free — most profitable period")

    # ----------------------------------------------------------------
    #  LOAN AMORTIZATION
    # ----------------------------------------------------------------
    interest_sch, principal_sch, balance_sch, annual_payment = \
        bf.build_loan_schedule(loan_amount, loan_rate, loan_term, Plant_Lifespan)

    if loan_amount > 0:
        #print(f"\n  Annual P&I (fixed): ${annual_payment:,.2f}")
        #print(f"  Yr | Beg Balance     | Interest       | Principal      | End Balance")
        # print(f"  ---+----------------+----------------+----------------+---------------")
        beg = loan_amount
        for yr in range(min(loan_term, Plant_Lifespan)):
            #print(f"  {yr+1:2d} | ${beg:>13,.2f} | ${interest_sch[yr]:>13,.2f} "
            #      f"| ${principal_sch[yr]:>13,.2f} | ${balance_sch[yr]:>13,.2f}")
            beg = balance_sch[yr]

    # ----------------------------------------------------------------
    #  PLANT PARAMETERS
    # ----------------------------------------------------------------
    params = bf.calculate_financial_parameters(
        FCI, annual_AC_year1, capacity_factor, real_discount_rate, Plant_Lifespan)

    annual_gen_kwh_yr1 = params['Annual Generation (kWh)']
    annual_gen_mwh_yr1 = params['Annual Generation (MWh)']
    fixed_om_yr1       = params['Fixed O&M ($)']
    var_om_per_kwh_yr1 = params['Variable O&M/kWh ($)']

    # Year 1 fuel costs — calculated separately per feedstock
    forest_fuel_cost_yr1 = forest_annual_tons * c_fuel_per_ton_forest
    mill_fuel_cost_yr1   = mill_annual_tons   * c_fuel_per_ton_mill
    total_fuel_cost_yr1  = forest_fuel_cost_yr1 + mill_fuel_cost_yr1
    annual_revenue_yr1   = annual_gen_mwh_yr1 * electricity_price

    if verbose:
        print(f"\n=== YEAR 1 BASELINE — KEY NUMBERS ===")
        print(f"  Revenue:            ${annual_revenue_yr1:,.2f}")
        print(f"  Forest Fuel Cost:   ${forest_fuel_cost_yr1:,.2f}  "
            f"[{forest_annual_tons:,} tons × ${c_fuel_per_ton_forest:.2f}/ton]")
        print(f"  Mill Fuel Cost:     ${mill_fuel_cost_yr1:,.2f}  "
            f"[{mill_annual_tons:,} tons × ${c_fuel_per_ton_mill:.2f}/ton]")
        print(f"  Total Fuel Cost:    ${total_fuel_cost_yr1:,.2f}")
        #print(f"  NOTE: Fuel volumes are FLAT every year (fixed throughput).")
        #print(f"\n  Escalation rates — 0.0=flat/real, >0=nominal:")
        #print(f"    Electricity {electricity_escalation*100:.2f}%/yr | "
            #  f"Fuel {fuel_escalation*100:.2f}%/yr (both feedstocks) | "
            #  f"Fixed O&M {fixed_om_escalation*100:.2f}%/yr | "
            #  f"Var O&M {var_om_escalation*100:.2f}%/yr")

    # ----------------------------------------------------------------
    # YEAR-BY-YEAR CASH FLOW LOOP
    # ----------------------------------------------------------------
    cash_flow_data = []

    # YEAR 0: equity outlay only
    cash_flow_data.append({
        'Year': 0, 'Loan Balance': loan_amount,
        'Annual Generation (kWh)':   0,
        'Annual Generation (MWh)':   0,
        'Electricity Price ($/MWh)': electricity_price,
        'Forest Fuel Cost ($/ton)':  c_fuel_per_ton_forest,
        'Mill Fuel Cost ($/ton)':    c_fuel_per_ton_mill,
        'Revenue':             0,
        'Policy Credits':      0,
        'Fixed O&M':           0,
        'Variable O&M':        0,
        'Forest Fuel Cost ($)': 0,
        'Mill Fuel Cost ($)':   0,
        'Total Fuel Cost ($)':  0,
        'Total Operating Cost': 0,
        'EBITDA':              0,
        'Depreciation':        0,
        'EBIT':                0,
        'Interest Expense':    0,
        'EBT':                 0,
        'State Tax':           0,
        'Federal Tax':         0,
        'Total Tax':           0,
        'Net Income':          0,
        'Principal Repayment': 0,
        'Free CF to Equity':  -equity_invested,
        'Cumulative CF':      -equity_invested,
        'Discounted CF':      -equity_invested,
    })

    cumulative_cf             = -equity_invested
    state_loss_carryforward   = 0.0
    federal_loss_carryforward = 0.0

    for year in range(1, Plant_Lifespan + 1):

        # Generation degrades
        deg_mult       = (1 - degradation_factor) ** (year - 1)
        annual_gen_kwh = annual_gen_kwh_yr1 * deg_mult
        annual_gen_mwh = annual_gen_kwh / 1000

        # Escalation multipliers
        esc = year - 1
        elec_price_yr            = electricity_price      * (1 + electricity_escalation) ** esc
        c_fuel_per_ton_forest_yr = c_fuel_per_ton_forest  * (1 + fuel_escalation)        ** esc
        c_fuel_per_ton_mill_yr   = c_fuel_per_ton_mill    * (1 + fuel_escalation)        ** esc
        fixed_om_yr              = fixed_om_yr1            * (1 + fixed_om_escalation)    ** esc
        var_om_rate_yr           = var_om_per_kwh_yr1      * (1 + var_om_escalation)      ** esc

        # Revenue
        annual_revenue = annual_gen_mwh * elec_price_yr
        #print("I AM REVENUE:", annual_revenue)

        # Operating costs — fuel tracked separately per feedstock
        forest_fuel_cost = forest_annual_tons * c_fuel_per_ton_forest_yr
        mill_fuel_cost   = mill_annual_tons   * c_fuel_per_ton_mill_yr
        total_fuel_cost  = forest_fuel_cost + mill_fuel_cost
        var_om           = var_om_rate_yr * annual_gen_kwh
        total_op_cost    = fixed_om_yr + var_om + total_fuel_cost
        #print("I AM TOTAL ANNUAL COST:", total_op_cost)

        # Policy credits
        if year <= credit_duration:
            policy_credits = credit_per_kWh * annual_gen_kwh
        else:
            policy_credits = 0.0

        # Depreciation
        year_dep = (annual_depreciation_schedule[year - 1]
                    if year <= len(annual_depreciation_schedule) else 0.0)
        
        #print("I AM DEPRECIATION:", year_dep)

        # Debt service
        interest_expense  = interest_sch[year - 1]
        principal_payment = principal_sch[year - 1]
        loan_balance      = balance_sch[year - 1]

        # Income statement
        ebitda = annual_revenue - total_op_cost
        #print("I AM EBITDA:", ebitda)
        ebit   = ebitda - year_dep  # https://www.irs.gov/publications/p946, https://www.law.cornell.edu/uscode/text/26/167
        #print("I AM EBIT:", ebit)
        # Interest deducted before tax (tax shield)
        ebt = ebit - interest_expense  # https://www.law.cornell.edu/uscode/text/26/163
        #print("I AM EBT:", ebt)
        # State tax with loss carryforward
        state_taxable = ebt + state_loss_carryforward  # https://www.law.cornell.edu/uscode/text/26/172
        #print("I AM STATE TAXABLE:", state_tax)
        if state_taxable < 0:
            state_loss_carryforward = state_taxable
            state_tax = 0.0
        else:
            state_loss_carryforward = 0.0
            state_tax = state_taxable * state_tax_rate  # Brealey, Myers & Allen (2023), Ch. 19

        # Federal tax — state tax deductible
        fed_taxable = ebt - state_tax + federal_loss_carryforward  # https://www.law.cornell.edu/uscode/text/26/164
        #print("I AM FED TAXABLE:", fed_taxable)
        if fed_taxable < 0:
            federal_loss_carryforward = fed_taxable
            federal_tax = 0.0
        else:
            federal_loss_carryforward = 0.0
            federal_tax = fed_taxable * federal_tax_rate  # TCJA Pub. L. 115-97, § 13001 (2017)

        #Production Tax Credits are Direct Reductions of the Tax Bill Owed, and are Not Tax Deduction, which reduce the amount of taxable income
        total_tax  = state_tax + federal_tax - policy_credits # https://legalclarity.org/understanding-the-production-tax-credit-under-irc-section-45/
        net_income = ebt - total_tax

        # Free CF to Equity
        free_cf = net_income + year_dep - principal_payment  # SFAS No. 95; Damodaran (2012), Ch. 3

        cumulative_cf += free_cf
        discounted_cf  = free_cf / (1 + nominal_discount_rate) ** year

        cash_flow_data.append({
            'Year':                        year,
            'Loan Balance':                loan_balance,
            'Annual Generation (kWh)':     annual_gen_kwh,
            'Annual Generation (MWh)':     annual_gen_mwh,
            'Electricity Price ($/MWh)':   elec_price_yr,
            'Forest Fuel Cost ($/ton)':    c_fuel_per_ton_forest_yr,
            'Mill Fuel Cost ($/ton)':      c_fuel_per_ton_mill_yr,
            'Revenue':                     annual_revenue,
            'Policy Credits':              policy_credits,
            'Fixed O&M':                  -fixed_om_yr,
            'Variable O&M':               -var_om,
            'Forest Fuel Cost ($)':       -forest_fuel_cost,
            'Mill Fuel Cost ($)':         -mill_fuel_cost,
            'Total Fuel Cost ($)':        -total_fuel_cost,
            'Total Operating Cost':       -total_op_cost,
            'EBITDA':                      ebitda,
            'Depreciation':               -year_dep,
            'EBIT':                        ebit,
            'Interest Expense':           -interest_expense,
            'EBT':                         ebt,
            'State Tax':                  -state_tax,
            'Federal Tax':                -federal_tax,
            'Total Tax':                  -total_tax,
            'Net Income':                  net_income,
            'Principal Repayment':        -principal_payment,
            'Free CF to Equity':           free_cf,
            'Cumulative CF':               cumulative_cf,
            'Discounted CF':               discounted_cf,
        })

    df = pd.DataFrame(cash_flow_data)

    # ----------------------------------------------------------------
    # FINANCIAL METRICS
    # ----------------------------------------------------------------

    # NPV
    npv = df['Discounted CF'].sum()

    # Equity IRR
    equity_cf = [-equity_invested] + list(df['Free CF to Equity'][1:])
    try:
        equity_irr = npf.irr(equity_cf)
    except Exception:
        equity_irr = np.nan

    # # LCOE: NPV(costs) / NPV(generation)
    # pv_costs = equity_invested
    # pv_gen   = 0.0
    # for _, row in df[df['Year'] > 0].iterrows():
    #     yr = int(row['Year'])
    #     d  = (1 + nominal_discount_rate) ** yr
    #     pv_costs += abs(row['Total Operating Cost']) / d
    #     pv_gen   += row['Annual Generation (kWh)']   / d
    # lcoe_kwh = pv_costs / pv_gen if pv_gen > 0 else np.nan
    # lcoe_mwh = lcoe_kwh * 1000

    # Payback
    payback_year = None
    for i, row in df.iterrows():
        if row['Cumulative CF'] >= 0 and i > 0:
            prev_cf      = df.loc[i - 1, 'Cumulative CF']
            payback_year = (i - 1) + abs(prev_cf) / row['Free CF to Equity']
            break

    metrics = {
        **params,
        'Real Discount Rate':            real_discount_rate,
        'Nominal Discount Rate':         nominal_discount_rate,
        'Inflation Rate':                inflation_rate,
        'Electricity Escalation':        electricity_escalation,
        'Fuel Escalation':               fuel_escalation,
        'Fixed O&M Escalation':          fixed_om_escalation,
        'Var O&M Escalation':            var_om_escalation,
        'Debt Fraction':                 debt_fraction,
        'Loan Amount':                   loan_amount,
        'Equity Invested':               equity_invested,
        'Loan Rate':                     loan_rate,
        'Loan Term':                     loan_term,
        'Annual Loan Payment':           annual_payment,
        'NPV (Equity, Nominal)':         npv,
        'Equity IRR':                    equity_irr,
        # 'LCOE ($/kWh)':                  lcoe_kwh,
        # 'LCOE ($/MWh)':                  lcoe_mwh,
        'Payback Period (years)':        payback_year,
        'Total Capital Investment':      TCI,
        'FCI':                           FCI,
        'Forest Annual Tons':            forest_annual_tons,
        'Mill Annual Tons':              mill_annual_tons,
        'Forest Fuel Cost ($/ton, Yr1)': c_fuel_per_ton_forest,
        'Mill Fuel Cost ($/ton, Yr1)':   c_fuel_per_ton_mill,
        'Forest Fuel Cost ($/yr, Yr1)':  forest_fuel_cost_yr1,
        'Mill Fuel Cost ($/yr, Yr1)':    mill_fuel_cost_yr1,
        'Total Fuel Cost ($/yr, Yr1)':   total_fuel_cost_yr1,
        'Annual Revenue (Yr1)':          annual_revenue_yr1,
        'Degradation Factor':            degradation_factor,
    }

    irr_str = f"{equity_irr*100:.2f}%" if not np.isnan(equity_irr) else "N/A"
    pb_str  = f"{payback_year:.2f} yrs" if payback_year else "Never"

    if verbose:
        print(f"\n{'='*60}")
        print(f"{'FINANCIAL RESULTS':^60}")
        print(f"{'='*60}")
        print(f"  NPV (Equity, Nominal):  ${npv:>14,.2f}")
        print(f"  Equity IRR:             {irr_str:>14}")
        #print(f"  LCOE:                   ${lcoe_mwh:>13.2f}/MWh")
        print(f"  Payback Period:         {pb_str:>14}")
        print(f"\n  Year 1 Output:  {df.loc[1,'Annual Generation (MWh)']:,.0f} MWh")
        print(f"  Year {Plant_Lifespan} Output: {df.loc[Plant_Lifespan,'Annual Generation (MWh)']:,.0f} MWh")
        loss = (1 - df.loc[Plant_Lifespan,'Annual Generation (MWh)'] /
                    df.loc[1,'Annual Generation (MWh)']) * 100
        print(f"  Output loss:    {loss:.2f}%  (degradation only — fuel cost unchanged)")
        print(f"{'='*60}\n")

        
    return df, metrics

def required_credit_for_breakeven(
    TCI, FCI,
    annual_depreciation_schedule,
    annual_AC_year1,
    forest_annual_tons,
    mill_annual_tons,
    degradation_factor,
    capacity_factor,
    Plant_Lifespan,
    c_fuel_per_ton_forest,
    c_fuel_per_ton_mill,
    electricity_price,
    real_discount_rate,
    inflation_rate,
    debt_fraction,
    loan_rate,
    loan_term,
    electricity_escalation,
    fuel_escalation,
    fixed_om_escalation,
    var_om_escalation,
    federal_tax_rate = 0.21,
    state_tax_rate   = 0.07,
    verbose = True
):
    
    credit_years = 10 
    
    def npv_given_credit(credit_per_kwh):
        _, metrics = needed_credit_cash_flow_analysis(
            TCI                          = TCI,
            FCI                          = FCI,
            annual_depreciation_schedule = annual_depreciation_schedule,
            annual_AC_year1              = annual_AC_year1,
            forest_annual_tons           = forest_annual_tons,
            mill_annual_tons             = mill_annual_tons,
            degradation_factor           = degradation_factor,
            capacity_factor              = capacity_factor,
            Plant_Lifespan               = Plant_Lifespan,
            c_fuel_per_ton_forest        = c_fuel_per_ton_forest,
            c_fuel_per_ton_mill          = c_fuel_per_ton_mill,
            electricity_price            = electricity_price,  # market price, not LCOE
            real_discount_rate           = real_discount_rate,
            inflation_rate               = inflation_rate,
            debt_fraction                = debt_fraction,
            loan_rate                    = loan_rate,
            loan_term                    = loan_term,
            electricity_escalation       = electricity_escalation,
            fuel_escalation              = fuel_escalation,
            fixed_om_escalation          = fixed_om_escalation,
            var_om_escalation            = var_om_escalation,
            credit_per_kWh               = credit_per_kwh,
            credit_duration                = credit_years,
            federal_tax_rate             = federal_tax_rate,
            state_tax_rate               = state_tax_rate,
            verbose                      = False,
        )
        return metrics['NPV (Equity, Nominal)']

    m_low = 0.001
    m_high = 0.035
    found_bracket = False

    for _ in range(500):
        print('TEST')
        m_high = m_high*2
        if npv_given_credit(m_high) > 0:
            found_bracket = True
            break
    if not found_bracket:
        raise RuntimeError("Could not find Tax Credit to make NPV > 0")
    
    Credit_Solved = brentq(npv_given_credit, m_low, m_high, xtol = 1e-6)

    
    

    print(f"\n=== REQUIRED CREDIT FOR BREAKEVEN ===")
    print(f"  Market Price:     ${electricity_price:.2f}/MWh")
    print(f"  Required Credit:  $ (${Credit_Solved:.6f}/kWh)")
    #print(f"Net Present Value: ${metrics_solved['NPV (Equity, Nominal)']})")
    print(f"  Credit Years:     {credit_years} yrs")

    return Credit_Solved

def get_model_inputs():
    """
    Returns a dictionary of all user-controlled assumptions.
    """
    inputs = {

        # --- Plant / Feedstock ---
        'forest_annual_tons':       100_000,  # bone dry tons/year — can go from 1-1,000,000
                                              # plant processes this every year regardless of
                                              # degradation. Only electricity output declines.
        'mill_annual_tons':         100_000,  # bone dry tons/year
        'forest_obtainability':     100,      # % forest residue obtainability #obtainability is only from 75-100 %
        'mill_obtainability':       100,      # % mill residue obtainability
        'cepci_year':               2030,     # year for CEPCI equipment cost escalation, year that your analysis is starting
        'Plant_Lifespan':           20,       # years
        'degradation_factor':       0.005,    # 0.5%/yr — plant loses conversion efficiency

        # --- Revenue ---
        'electricity_price':        130.0,    # $/MWh Year 1

        # --- Fuel Costs ---
        'c_fuel_per_ton_forest':    25.0,     # $/dry ton Year 1 — forest residue #the plant delivered cost from jonathans model
        'c_fuel_per_ton_mill':      20.0,     # $/dry ton Year 1 — mill residue
                                              # mill residues are typically cheaper (less transport)

        # 
        # 0.0 = flat prices (real analysis, conservative base case)
        # >0  = growing prices (nominal analysis, fully consistent with nominal rate)

        'electricity_escalation':   0.01,
        'fuel_escalation':          0.025,    # applied equally to both forest and mill fuel prices
        'fixed_om_escalation':      0.025,
        'var_om_escalation':        0.02,

        # --- Discount Rates ---
        # Nominal rate derived automatically: (1+real)×(1+inflation)-1
        'real_discount_rate':       0.10,    # equity required return, real terms
        'inflation_rate':           0.025,    # general price inflation

        #
        # debt_fraction = 0.0 → all-equity
        'debt_fraction':            0.60,     # 60% of TCI financed by bank loan
        'loan_rate':                0.10,    # annual bank interest rate
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

    # Total daily throughput drives equipment sizing
    total_annual_tons = p['forest_annual_tons'] + p['mill_annual_tons']
    biomass_daily     = total_annual_tons / 365

    annual_AC_year1 = predict_output(
        p['forest_annual_tons'],
        p['mill_annual_tons'],
        p['forest_obtainability'],
        p['mill_obtainability'],
    )

    capacity_factor = 81

    EC, stoker_cost, fuel_eq_cost, turbine_cost, EC_list = bc.equipment_costs(
        biomass_daily, p['cepci_year'])

    TCI, FCI, breakdown = bc.TCI_calculation(EC, EC_list)

    annual_dep = bc.depreciation_schedule(
        breakdown, EC_list, max_years=p['Plant_Lifespan'])

    #solve for LCOE
    lcoe = bf.get_lcoe(TCI                          = TCI,
        FCI                          = FCI,
        annual_depreciation_schedule = annual_dep,
        annual_AC_year1              = annual_AC_year1,
        forest_annual_tons           = p['forest_annual_tons'],
        mill_annual_tons             = p['mill_annual_tons'],
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
        verbose = False
        )
    
    print(lcoe)
    lcoe_MWh = lcoe['LCOE ($/MWh)']
    
    df1, metrics1 = base_credit_cash_flow_analysis(
        'none',
        TCI                          = TCI,
        FCI                          = FCI,
        annual_depreciation_schedule = annual_dep,
        annual_AC_year1              = annual_AC_year1,
        forest_annual_tons           = p['forest_annual_tons'],
        mill_annual_tons             = p['mill_annual_tons'],
        degradation_factor           = p['degradation_factor'],
        capacity_factor              = capacity_factor,
        Plant_Lifespan               = p['Plant_Lifespan'],
        c_fuel_per_ton_forest        = p['c_fuel_per_ton_forest'],
        c_fuel_per_ton_mill          = p['c_fuel_per_ton_mill'],
        electricity_price            = lcoe_MWh,
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
    # Now we want to recreate the project selling at the LCOE with the Renewable Electricity Production Tax Credit In Place!

    df2, metrics2 = base_credit_cash_flow_analysis(
        'basecredit',
        TCI                          = TCI,
        FCI                          = FCI,
        annual_depreciation_schedule = annual_dep,
        annual_AC_year1              = annual_AC_year1,
        forest_annual_tons           = p['forest_annual_tons'],
        mill_annual_tons             = p['mill_annual_tons'],
        degradation_factor           = p['degradation_factor'],
        capacity_factor              = capacity_factor,
        Plant_Lifespan               = p['Plant_Lifespan'],
        c_fuel_per_ton_forest        = p['c_fuel_per_ton_forest'],
        c_fuel_per_ton_mill          = p['c_fuel_per_ton_mill'],
        electricity_price            = lcoe_MWh,
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
    #figs = plot_all(df,metrics)

    # Now use the investment credit
    df3, metrics3 = base_credit_cash_flow_analysis(
        'investmentcredit',
        TCI                          = TCI,
        FCI                          = FCI,
        annual_depreciation_schedule = annual_dep,
        annual_AC_year1              = annual_AC_year1,
        forest_annual_tons           = p['forest_annual_tons'],
        mill_annual_tons             = p['mill_annual_tons'],
        degradation_factor           = p['degradation_factor'],
        capacity_factor              = capacity_factor,
        Plant_Lifespan               = p['Plant_Lifespan'],
        c_fuel_per_ton_forest        = p['c_fuel_per_ton_forest'],
        c_fuel_per_ton_mill          = p['c_fuel_per_ton_mill'],
        electricity_price            = lcoe_MWh,
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

    plot_policy_comparison(df1, df2, df3)

    # Find the Policy for Market Price
    market_price = 120 #$/MWh

    Credit_Solved = required_credit_for_breakeven(
        TCI                          = TCI,
        FCI                          = FCI,
        annual_depreciation_schedule = annual_dep,
        annual_AC_year1              = annual_AC_year1,
        forest_annual_tons           = p['forest_annual_tons'],
        mill_annual_tons             = p['mill_annual_tons'],
        degradation_factor           = p['degradation_factor'],
        capacity_factor              = capacity_factor,
        Plant_Lifespan               = p['Plant_Lifespan'],
        c_fuel_per_ton_forest        = p['c_fuel_per_ton_forest'],
        c_fuel_per_ton_mill          = p['c_fuel_per_ton_mill'],
        electricity_price            = market_price,
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

    print("\n" + "="*65)
    print("ANALYSIS COMPLETE")
    print("="*65)

    return df1, metrics1, df2, metrics2,df3, metrics3, lcoe, Credit_Solved


if __name__ == "__main__":
    df1, metrics1, df2, metrics2,df3, metrics3, lcoe, solved_credit = main()