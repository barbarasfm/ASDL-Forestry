###############################################################
# DIRECT OPEX
###############################################################


import pandas as pd
from math import tanh
from SAF_dependencies import biofuel_production

# -----------------------------
# CEPCI Calculations
# -----------------------------

def getModelMetadata():
    return {"creator": u"Neural", "modelName": u"", "predicted": u"CEPCI", "table": u"Untitled", "version": u"18.2.2", "timestamp": u"2025-12-05T18:04:49Z"}

def getInputMetadata():
    return {u"year": "float"}

def getOutputMetadata():
    return {u"Predicted CEPCI_1": "float"}

def score(indata, outdata):

    H2_1 = tanh((95.8658540212012 + -0.0480902391335061 * indata[u"year"]))
    H2_2 = tanh((168.899151293119 + -0.0850141463046976 * indata[u"year"]))
    H2_3 = tanh((-39.7188467278445 + 0.0198729775942967 * indata[u"year"]))
    H2_4 = tanh((-173.931605025729 + 0.087493074553695 * indata[u"year"]))
    H2_5 = tanh((-16.2963582788506 + 0.00840416633022081 * indata[u"year"]))

    H1_1_1 = tanh((0.032674320257208 + -0.0707535445049631 * H2_1 + 0.0590957669900188 * H2_2 + 0.114282201528049 * H2_3 + -0.651016330100104 * H2_4 + -0.0369594788970825 * H2_5))
    H1_2_1 = tanh((0.620844186843358 + -1.3559127755334 * H2_1 + 0.752647930239482 * H2_2 + 0.687214572822089 * H2_3 + -0.361110248267074 * H2_4 + -0.379859272117235 * H2_5))
    H1_3_1 = tanh((0.469008947414524 + -0.0980754849677295 * H2_1 + -0.565726127816262 * H2_2 + -0.732754978764598 * H2_3 + -0.651397419243305 * H2_4 + -0.799956518487368 * H2_5))
    H1_4_1 = tanh((-0.451804743874949 + -0.632259916517125 * H2_1 + -0.959503408155128 * H2_2 + 0.548229916690545 * H2_3 + 0.923192171807363 * H2_4 + -0.423565513225777 * H2_5))
    H1_5_1 = tanh((-0.538980466546353 + 0.116395373382689 * H2_1 + 0.139604029638408 * H2_2 + 0.544998595622798 * H2_3 + -0.121224947232126 * H2_4 + -0.23677657994394 * H2_5))
    H1_6_1 = tanh((0.203564386448606 + -0.267812643684438 * H2_1 + -0.593630822581117 * H2_2 + 0.320562782354496 * H2_3 + 0.468982996197454 * H2_4 + 0.0669175707923384 * H2_5))
    H1_7_1 = tanh((-0.594937176050763 + -0.850532917721057 * H2_1 + 0.867224440822612 * H2_2 + -0.0547519140681932 * H2_3 + 0.204198753332548 * H2_4 + -0.578168643184816 * H2_5))
    H1_8_1 = tanh((0.082466370848229 + 0.0851536151513514 * H2_1 + -0.222728604477707 * H2_2 + 0.2786261721389 * H2_3 + -0.649019237461678 * H2_4 + 0.0926259271078834 * H2_5))
    H1_9_1 = tanh((-0.544666087937977 + 0.449988296946931 * H2_1 + -0.245618976661163 * H2_2 + -0.0442945044327383 * H2_3 + -0.0293516660266628 * H2_4 + -0.513411720864981 * H2_5))
    H1_10_1 = tanh((-0.311975967852518 + -0.595240925113974 * H2_1 + 0.0996423895063498 * H2_2 + -0.742760566265295 * H2_3 + 0.232956624524826 * H2_4 + -0.114374442855619 * H2_5))

    outdata[u"Predicted CEPCI_1"] = (
        -81819.0296360724
        + 19252.9367986606 * H1_1_1
        - 168920.829502933 * H1_10_1
        + 34398.5717836449 * H1_2_1
        + 37238.8835296783 * H1_3_1
        - 2091.39311660399 * H1_4_1
        - 113767.449583642 * H1_5_1
        - 9939.35224489736 * H1_6_1
        + 40739.4036532272 * H1_7_1
        - 185117.590557358 * H1_8_1
        + 6929.13001945077 * H1_9_1
    )

    return outdata[u"Predicted CEPCI_1"]

def cepci_from_year(year: float) -> float:
    out = {}
    score({"year": float(year)}, out)
    return float(out["Predicted CEPCI_1"])


REF_CAPACITY_GGEHR = 32300000 / (310 * 24)
BASE_CPI = 226.4
operating_hours = 7884

# ============================
# UTILITY COST FUNCTIONS
# ============================

def feedstock_calc(feedstock_kg_hr, feed_cost    
):
    total_feed_cost = feedstock_kg_hr/1000 * 7884 * feed_cost
    return total_feed_cost

def steam_cost(cap_ratio, CPI, hrs, price=0.00904):
    ref_kg_hr = 1352 * 1000 / 24
    return ref_kg_hr * cap_ratio * hrs * price * (CPI / BASE_CPI)


def cooling_water_cost(cap_ratio, CPI, hrs, price=0.00002):
    ref_kg_hr = 3500000 / 0.31 / 7446 * 1000
    return ref_kg_hr * cap_ratio * hrs * price * (CPI / BASE_CPI)


def wastewater_cost(cap_ratio, CPI, hrs, price= 3.3 / 100):
    ref_cf_hr = 1500000 / 0.033 / hrs
    return ref_cf_hr * cap_ratio * hrs * price * (CPI / BASE_CPI)


def ash_cost(cap_ratio, CPI, hrs, price= 23.52 / 907):
    ref_kg_hr = 119 * 1000 / hrs
    return ref_kg_hr * cap_ratio * hrs * price * (CPI / BASE_CPI)


def hydroprocessing_cost(cap_ratio, CPI, hrs, price=4):
    ref_bbl_hr = 3000000 / 4 / hrs
    return ref_bbl_hr * cap_ratio * hrs * price * (CPI / BASE_CPI)



##Need to fix these 2

def electricity_cost(total_MW, hrs, price):
    return total_MW * 1000 * hrs * price



ELECTRICITY_REFERENCE_MW = {
    "Lockhopper": 0.2,
    "Lean amine solution pump": 0.7,
    "Syngas Booster compressor": 1.0,
    "PSA Compressor": 0.1,
    "Recycle Compressor": 0.3,
    "Hydroprocessing Area": 1.7,
    "Oxygen Compressor (ASU)": 2.8,
    "Air Compressor (ASU)": 6.3,
    "CO2 compressor": 0.4
}


def plant_electricity_MW(fuel_GGE_hr):

    cap_ratio = fuel_GGE_hr / REF_CAPACITY_GGEHR

    electricity_scaled = {}

    total_MW = 0

    for unit, ref_MW in ELECTRICITY_REFERENCE_MW.items():

        scaled_MW = ref_MW * cap_ratio

        electricity_scaled[unit] = scaled_MW

        total_MW += scaled_MW

    return total_MW


## Natural Gas Calculating

def natural_gas_backup(total_MW, operating_hours):

    BTU_PER_MW = 3_412_141
    NG_EFFICIENCY = 0.35
    NG_HHV = 1050
    BACKUP_FRACTION = 0.05

    flow = (
        total_MW
        * BTU_PER_MW
        / NG_EFFICIENCY
        / NG_HHV
        * (BACKUP_FRACTION * operating_hours)
        / 1000
    )
    return flow

def natural_gas_cost(flow,price):
    flow = flow
    return flow * price

###############################################################
# CATALYST COST MODEL
###############################################################


def catalyst_costs(
        fuel_GGE_hr,
        CEPCI_current,
):

    BASE_CEPCI_CATALYST = 525.4  # adjust if base year differs

    CATALYST_REFERENCE_COSTS = {

        "FT catalyst": 6_128_000,
        "WGS catalyst": 105_000,
        "SMR catalyst": 103_000,
        "PSA packing": 497_000,
        "ZnO bed": 424_410

    }
    cap_ratio = fuel_GGE_hr / REF_CAPACITY_GGEHR

    results = {}

    total_3yr = 0
    total_annual = 0

    for name, ref_cost in CATALYST_REFERENCE_COSTS.items():

        model_cost = (
            ref_cost
            * cap_ratio
            * (CEPCI_current / BASE_CEPCI_CATALYST)
        )

        annual_cost = model_cost / 3

        results[name] = {
            "Reference Cost": ref_cost,
            "Model Cost (3yr)": model_cost,
            "Annual Cost": annual_cost
        }

        total_3yr += model_cost
        total_annual += annual_cost

    results["Total (3 year replacement cost)"] = total_3yr
    results["Total Annual Catalyst Cost"] = total_annual

    return total_3yr, total_annual

###############################################################
# INDIRECT OPEX
###############################################################

LANG_FACTOR = 4.46

def fixed_capital_investment_usd(total_PEC) -> float:

    #total_PEC = 83_000_000

    if total_PEC <= 0:
        raise ValueError("Total purchased equipment cost must be > 0")

    FCI = total_PEC * LANG_FACTOR

    return FCI



#FCI_usd = fixed_capital_investment_usd()


# print("\n==============================")
# print("FCI (Lang Factor Method)")
# print("==============================")
#print(f"Fixed Capital Investment (×4.46): ${FCI_usd:,.0f}")


###############################################################
# INDIRECT OPEX
###############################################################

BASE_CPI_LABOR = 112.2 


def operating_labor_cost(feedstock_tonnes_per_year, CEPCI):

    import math

    feed_per_day = feedstock_tonnes_per_year / (0.9 * 365)

    shift_supervisors = max(math.ceil(5 * feed_per_day / 2000), 3)
    shift_operators   = max(math.ceil(38 * feed_per_day / 2000), 18)
    yard              = max(math.ceil(4 * feed_per_day / 2000), 2)
    clerks            = max(math.ceil(3 * feed_per_day / 2000), 1)

    salaries_2011 = {
        "Plant manager": 161400,
        "Plant engineer": 76800,
        "Maintenance supervision": 62600,
        "Lab manager": 61500,
        "Lab technician": 43900 * 3,
        "Shift supervisor": 52700 * shift_supervisors,
        "Shift operators": 52700 * shift_operators,
        "Yard employees": 30700 * yard,
        "Clerk & secretaries": 39500 * clerks,
    }

    escalation = 144.2 / BASE_CPI_LABOR
    total_labor = sum(salaries_2011.values()) * escalation

    return total_labor


def indirect_opex_from_FCI(
        FCI_usd,
        feedstock_tonnes_per_year,
        CEPCI
    ):

    # --------------------------
    # Operating Labor
    # --------------------------
    salaries = operating_labor_cost(
        feedstock_tonnes_per_year,
        CEPCI
    )

    # --------------------------
    # Fixed Operating Costs
    # --------------------------
    property_insurance = 0.01 * FCI_usd
    local_taxes        = 0.015 * FCI_usd
    maintenance_repairs = 0.06 * FCI_usd
    overhead            = 0.60 * salaries

    total_indirect = (
        property_insurance +
        local_taxes +
        maintenance_repairs +
        overhead
    )

    return {
        "Property insurance (1% FCI)": property_insurance,
        "Local taxes (1.5% FCI)": local_taxes,
        "Maintenance & repairs (6% FCI)": maintenance_repairs,
        "Overhead (60% salaries)": overhead,
        "Operating salaries": salaries,
        "Total Indirect Operating Cost": total_indirect + salaries
    }


# # -----------------------------
# # DIRECT OPEX TEST
# # -----------------------------
# # Using SAME inputs as SAF model
# biomass_tonnes_per_year = 200_000
# case = "distillate 1"
# target_year = 2025
# # convert to kg/hr
# feedstock_kg_hr = biomass_tonnes_per_year * 1000 / 7884


# # Run production model
# saf, diesel, naptha, saf_MML, diesel_MML, naptha_MML = biofuel_production(
#     biomass_tonnes_per_year,
#     case
# )

# total_fuel_GGE_hr = saf + diesel + naptha

# print(f"Feedstock input: {biomass_tonnes_per_year:,.0f} t/yr")
# print(f"Fuel output: {total_fuel_GGE_hr:,.2f} GGE/hr")

# # CEPCI from your neural model
# CEPCI_current = cepci_from_year(target_year)
# print(f"CEPCI ({target_year}): {CEPCI_current:.1f}")

# print("\n==============================")
# print("DIRECT OPEX BREAKDOWN")
# print("==============================\n")

# operating_hours = 7884
# cap_ratio = total_fuel_GGE_hr / REF_CAPACITY_GGEHR

# total_MW = plant_electricity_MW(total_fuel_GGE_hr)

# flow = natural_gas_backup(total_MW, operating_hours)


# steam = steam_cost(cap_ratio, 309.3, 0.9*365*24)
# cooling = cooling_water_cost(cap_ratio, 309.3, 0.9*365*24)
# wastewater = wastewater_cost(cap_ratio, 309.3, 0.9*365*24)
# ash = ash_cost(cap_ratio, 309.3, 0.9*365*24)
# hydro = hydroprocessing_cost(cap_ratio, 309.3, 0.9*365*24)
# elec = electricity_cost(total_MW, 0.9*365*24, 0.072)
# ng = natural_gas_cost(flow,5.09)

# print(f"{'Item':<25} {'Cost ($/yr)':>20}")

# print(f"{'Steam':<25} ${steam:>19,.0f}")
# print(f"{'Cooling water':<25} ${cooling:>19,.0f}")
# print(f"{'Wastewater disposal':<25} ${wastewater:>19,.0f}")
# print(f"{'Ash disposal':<25} ${ash:>19,.0f}")
# print(f"{'Natural gas':<25} ${ng:19.0f}")
# print(f"{'Hydroprocessing':<25} ${hydro:>19,.0f}")
# print(f"{'Electricity':<25} ${elec:>19,.0f}")

# utilities_total = (
#     steam + cooling + wastewater + ash + hydro + elec + ng
# )

# print("-"*50)

# print(f"{'Utilities Total':<25} ${utilities_total:>19,.0f}")



# CEPCI_current = cepci_from_year(target_year)

# cat_results = catalyst_costs(
#     fuel_GGE_hr = total_fuel_GGE_hr,
#     CEPCI_current = CEPCI_current
# )

# print("\n==============================")
# print("CATALYST COST BREAKDOWN")
# print("==============================")

# for name, data in cat_results.items():

#     if isinstance(data, dict):

#         print(
#             f"{name}: "
#             f"Reference=${data['Reference Cost']:,.0f}  "
#             f"3yr=${data['Model Cost (3yr)']:,.0f}  "
#             f"Annual=${data['Annual Cost']:,.0f}"
#         )
#     else:
#         print(f"{name}: ${data:,.0f}")


# # ---------------------------------
# # INDIRECT OPEX CALCULATION
# # ---------------------------------

# # indirect_results = indirect_opex_from_FCI(
# #     FCI_usd,
# #     biomass_tonnes_per_year,
# #     CEPCI_current
# # )

# # total_indirect = indirect_results["Total Indirect Operating Cost"]

# # print("\n==============================")
# # print("INDIRECT OPEX BREAKDOWN")
# # print("==============================")

# # for name, value in indirect_results.items():
# #     print(f"{name:<35} ${value:>15,.0f}")


# # print("\n==============================")
# # print("Other Variable Opex")
# # print("==============================")

# # # pull annual catalyst cost
# # annual_catalyst = cat_results["Total Annual Catalyst Cost"]

# # print(f"{'Utilities Total':<25} ${utilities_total:>19,.0f}")
# # print(f"{'Annual Catalyst Cost':<25} ${annual_catalyst:>19,.0f}")

# # print("-"*50)

# # variable_opex = utilities_total + annual_catalyst

# # print(f"{'Other Variable OPEX':<25} ${variable_opex:>19,.0f}")



# # print("\n==============================")
# # print("TOTAL OPEX")
# # print("==============================")

# # feedcost_total = feedstock_calc(feedstock_kg_hr,180)
# # print(f"{'Feedstock Cost':<25} ${feedcost_total:>19,.0f}")

# # total_Opex = variable_opex + total_indirect + feedcost_total

# # print(f"{'Final Total OPEX':<25} ${total_Opex:>19,.0f}")