import numpy as np
import numpy_financial as npf
import pandas as pd
from scipy.optimize import brentq

# OPERATING COST PARAMETERS

FIXED_OM_FACTOR = 4.2  # % of installed cost ($/yr)
VAR_OM_FACTOR   = 4.7  # (USD/MWh)


def calculate_financial_parameters(FCI, annual_AC_year1, capacity_factor,
                                    real_discount_rate, Plant_Lifespan):
    cf_decimal        = capacity_factor / 100
    Plant_Capacity_kW = annual_AC_year1 / (cf_decimal * 8760)
    Plant_Capacity_MW = Plant_Capacity_kW / 1000
    annual_gen_MWh    = annual_AC_year1 / 1000

    OCC             = FCI / Plant_Capacity_kW
    Fixed_OM_annual = (FIXED_OM_FACTOR / 100) * FCI
    Fixed_OM_per_kW = Fixed_OM_annual / Plant_Capacity_kW
    Var_OM_per_kWh  = VAR_OM_FACTOR / 1000
    Var_OM_annual   = Var_OM_per_kWh * annual_AC_year1

    params = {
        'Plant Capacity (MW)':         Plant_Capacity_MW,
        'Plant Capacity (kW)':         Plant_Capacity_kW,
        'Capacity Factor (%)':         capacity_factor,
        'Capacity Factor (decimal)':   cf_decimal,
        'Annual Generation (kWh)':     annual_AC_year1,
        'Annual Generation (MWh)':     annual_gen_MWh,
        'OCC ($/kW)':                  OCC,
        'Fixed O&M ($)':            Fixed_OM_annual,
        'Fixed O&M ($/kW-yr)':         Fixed_OM_per_kW,
        'Variable O&M ($)':         Var_OM_annual,
        'Variable O&M/kWh ($)':        Var_OM_per_kWh,
        'Fixed O&M Factor (%)':        FIXED_OM_FACTOR,
        'Variable O&M Factor ($/MWh)': VAR_OM_FACTOR
    }

    return params


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
    federal_tax_rate=0.21,
    state_tax_rate=0.07,
    verbose=True
):
    # Fisher equation: nominal = (1 + real) × (1 + inflation) - 1
    nominal_discount_rate = (1 + real_discount_rate) * (1 + inflation_rate) - 1
    equity_fraction       = 1 - debt_fraction

    if verbose:
        print(f"\n=== DISCOUNT RATES ===")
        print(f"  Real:    {real_discount_rate*100:.2f}%  [input — equity required return]")
        print(f"  Infl:    {inflation_rate*100:.2f}%  [input]")
        print(f"  Nominal: {nominal_discount_rate*100:.4f}%  [derived via Fisher]")

    loan_amount     = TCI * debt_fraction
    equity_invested = TCI * equity_fraction

    if verbose:
        print(f"\n=== FINANCING ===")
        print(f"  TCI:             ${TCI:,.2f}")
        print(f"  Loan:            ${loan_amount:,.2f}  ({debt_fraction*100:.1f}%)")
        print(f"  Equity:          ${equity_invested:,.2f}  ({equity_fraction*100:.1f}%)")
        print(f"  Loan Rate:       {loan_rate*100:.2f}%   Loan Term: {loan_term} yrs")
        print(f"  Years {loan_term+1}-{Plant_Lifespan}: debt-free — most profitable period")

    interest_sch, principal_sch, balance_sch, annual_payment = \
        build_loan_schedule(loan_amount, loan_rate, loan_term, Plant_Lifespan)

    if loan_amount > 0:
        beg = loan_amount
        for yr in range(min(loan_term, Plant_Lifespan)):
            beg = balance_sch[yr]

    params = calculate_financial_parameters(
        FCI, annual_AC_year1, capacity_factor, real_discount_rate, Plant_Lifespan)

    annual_gen_kwh_yr1 = params['Annual Generation (kWh)']
    annual_gen_mwh_yr1 = params['Annual Generation (MWh)']
    fixed_om_yr1       = params['Fixed O&M ($)']
    var_om_per_kwh_yr1 = params['Variable O&M/kWh ($)']
    var_om__yr1 = params['Variable O&M ($)']
    plant_capacity = params['Plant Capacity (MW)']

    if verbose:
        print(f"\n=== BASELINE PLANT PARAMETERS IN YEAR 1===")
        print("ANNUAL GEN. kWH:", annual_gen_kwh_yr1)
        print("ANNUAL GEN. MWh:", annual_gen_mwh_yr1)
        print("FIXED O&M YEAR ! ($):", fixed_om_yr1)
        print("VAR O&M YEAR !:", var_om__yr1)
        print("EST. PLANT CAPACITY:", plant_capacity)

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

        deg_mult       = (1 - degradation_factor) ** (year - 1)
        annual_gen_kwh = annual_gen_kwh_yr1 * deg_mult
        annual_gen_mwh = annual_gen_kwh / 1000

        esc = year - 1
        elec_price_yr            = electricity_price      * (1 + electricity_escalation) ** esc
        c_fuel_per_ton_forest_yr = c_fuel_per_ton_forest  * (1 + fuel_escalation)        ** esc
        c_fuel_per_ton_mill_yr   = c_fuel_per_ton_mill    * (1 + fuel_escalation)        ** esc
        fixed_om_yr              = fixed_om_yr1            * (1 + fixed_om_escalation)    ** esc
        var_om_rate_yr           = var_om_per_kwh_yr1      * (1 + var_om_escalation)      ** esc

        annual_revenue = annual_gen_mwh * elec_price_yr

        forest_fuel_cost = forest_annual_tons * c_fuel_per_ton_forest_yr
        mill_fuel_cost   = mill_annual_tons   * c_fuel_per_ton_mill_yr
        total_fuel_cost  = forest_fuel_cost + mill_fuel_cost
        var_om           = var_om_rate_yr * annual_gen_kwh
        total_op_cost    = fixed_om_yr + var_om + total_fuel_cost

        year_dep = (annual_depreciation_schedule[year - 1]
                    if year <= len(annual_depreciation_schedule) else 0.0)

        interest_expense  = interest_sch[year - 1]
        principal_payment = principal_sch[year - 1]
        loan_balance      = balance_sch[year - 1]

        ebitda = annual_revenue - total_op_cost
        ebit   = ebitda - year_dep

        ebt = ebit - interest_expense

        state_taxable = ebt + state_loss_carryforward
        if state_taxable < 0:
            state_loss_carryforward = state_taxable
            state_tax = 0.0
        else:
            state_loss_carryforward = 0.0
            state_tax = state_taxable * state_tax_rate

        fed_taxable = ebt - state_tax + federal_loss_carryforward
        if fed_taxable < 0:
            federal_loss_carryforward = fed_taxable
            federal_tax = 0.0
        else:
            federal_loss_carryforward = 0.0
            federal_tax = fed_taxable * federal_tax_rate

        total_tax  = state_tax + federal_tax
        net_income = ebt - total_tax

        free_cf = net_income + year_dep - principal_payment

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

    # NPV
    npv = df['Discounted CF'].sum()

    # Equity IRR
    equity_cf = [-equity_invested] + list(df['Free CF to Equity'][1:])
    try:
        equity_irr = npf.irr(equity_cf)
    except Exception:
        equity_irr = np.nan

    # LCOE: NPV(costs) / NPV(generation)
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


def get_lcoe(
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
    federal_tax_rate=0.21,
    state_tax_rate=0.07,
    verbose=True
):
    def npv_with_lcoe(LCOE):
        _, met = build_cash_flow_analysis(
            TCI, FCI, annual_depreciation_schedule, annual_AC_year1,
            forest_annual_tons, mill_annual_tons, degradation_factor,
            capacity_factor, Plant_Lifespan, c_fuel_per_ton_forest,
            c_fuel_per_ton_mill, LCOE, real_discount_rate, inflation_rate,
            debt_fraction, loan_rate, loan_term, electricity_escalation,
            fuel_escalation, fixed_om_escalation, var_om_escalation,
            federal_tax_rate, state_tax_rate, verbose=False
        )
        return met['NPV (Equity, Nominal)']

    m_low  = 0.01
    m_high = 0.01
    found_bracket = False

    for _ in range(50):
        m_high = m_high * 2
        if npv_with_lcoe(m_high) > 0:
            found_bracket = True
            break

    if not found_bracket:
        raise RuntimeError("Could not find Price to make NPV > 0")

    LCOE_solved = brentq(npv_with_lcoe, m_low, m_high, xtol=1e-6)

    return {
        'LCOE ($/MWh)': LCOE_solved,
        'LCOE ($/kWh)': LCOE_solved / 1e3
    }