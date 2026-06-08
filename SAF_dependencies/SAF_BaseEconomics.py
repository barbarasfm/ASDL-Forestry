"""
SAF Techno-Economic Tool
==========================================================
"""

from __future__ import annotations
from math import tanh
import pandas as pd
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

# ==========================================================
# Equipment cost
# ==========================================================

def EC_scaling(feedstock_kg_hr, fuel_GGE_hr, year):

    from equipment_library import EQUIPMENT

    CEPCI_current = cepci_from_year(year)

    scaled_costs = {}

    for name, equipment in EQUIPMENT.items():

        # Decide scaling basis
        if equipment.base_feedstock > 10000:
            # These are feedstock-scaled items (kg/hr)
            capacity = feedstock_kg_hr
        else:
            # These are fuel-scaled items (GGE/hr)
            capacity = fuel_GGE_hr

        scaled_cost = (
            equipment.base_cost *
            (capacity / equipment.base_feedstock) ** equipment.scalingexponent *
            (CEPCI_current / equipment.baseCEPCI)
        )

        scaled_costs[name] = scaled_cost
        print(f"{equipment.name}: ${scaled_cost:,.2f}")

    return scaled_costs


# ==========================================================
# CAPEX
# ==========================================================

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


###################### ALBRECHT FCI ###########################
def fixed_capital_investment_usd(
    equipment_costs: dict,
    factors: dict = DEFAULT_FCI_RATIO_FACTORS
) -> float:

    direct_indirect_factor = (
        factors["equipment_installation"]
        + factors["instrumentation_control"]
        + factors["piping_installed"]
        + factors["electrical_installed"]
        + factors["buildings_services"]
        + factors["yard_improvements"]
        + factors["service_facilities"]
        + factors["engineering_supervision"]
        + factors["construction_expenses"]
        + factors["legal_expenses"]
    )

    total_D_plus_I = 0.0

    for name, PEC in equipment_costs.items():
        if PEC <= 0:
            raise ValueError(f"Equipment cost for {name} must be > 0")

        D_plus_I_i = PEC * (1.0 + direct_indirect_factor)
        total_D_plus_I += D_plus_I_i

    fee_and_contingency = (
        factors["contractors_fee"] + factors["contingency"]
    ) * total_D_plus_I

    FCI = total_D_plus_I + fee_and_contingency

    return float(FCI)

###########################################################################################################################


#############ACC DO WE NEED? ###################

def annualized_capital_cost_usd(
    FCI_usd: float,
    plant_life_years: int,
    interest_rate: float,
) -> float:

    IR = interest_rate
    y = plant_life_years
    annuity = (IR * (1 + IR) ** y) / ((1 + IR) ** y - 1)
    TCI = FCI_usd / 0.9
    WC = 0.10 * TCI
    return float(FCI_usd * annuity + IR * WC)

# ==========================================================
# OPEX
# ==========================================================



# Biomass: 97.4 euro in 2014 which is about 130 $ in 2014

#BIOMASS_PRICE_USD_PER_T = 130.0

#def direct_opex_usd(biomass_tonnes_per_year: float) -> pd.DataFrame:

 #   cost = biomass_tonnes_per_year * BIOMASS_PRICE_USD_PER_T

 #   return pd.DataFrame([
 #       ("Biomass", biomass_tonnes_per_year, BIOMASS_PRICE_USD_PER_T, cost),
 #   ], columns=["Item", "Annual amount (t/yr)", "Unit price ($/t)", "Annual cost ($/yr)"])


# ==========================================================
# Operating Labor Cost
# ==========================================================

#def operators_per_shift(P: int, N_np: int) -> float:

  #  if P < 0 or N_np < 0:
  #      raise ValueError("Process step counts must be non-negative")

   # return (6.29 + 31.7 * P**2 + 0.23 * N_np) ** 0.5


#def total_operators_required(
   # P: int,
   # N_np: int,
   # shifts_per_year: int = 1095,       
   # shifts_per_operator: int = 245,     
#) #> float:
 #   N_OL = operators_per_shift(P, N_np)
  #  return N_OL * (shifts_per_year / shifts_per_operator)


#def operating_labor_cost_usd(
#    P: int,
#    N_np: int,
#    salary_per_operator_usd: float,
#) -> float:
    
#    if salary_per_operator_usd <= 0:
#        raise ValueError("Operator salary must be > 0")

#   n_operators = total_operators_required(P, N_np)
#    return float(n_operators * salary_per_operator_usd)


#def indirect_opex_usd(TCI_usd: float, labor_cost: float) -> pd.DataFrame:
#
#    FCI = 0.9 * TCI_usd
#
#    maint_labor = 0.02 * FCI
#    maint_material = 0.02 * FCI
#   oppsupplies = (maint_labor + maint_material) * 0.15
#    insurance = 0.02 * FCI


#    supervision = 0.15 * labor_cost
#    lab = 0.20 * labor_cost

#    TLC = labor_cost + supervision + maint_labor
#    overhead = 0.60 * TLC
#    admin = 0.25 * overhead

#    return pd.DataFrame([
#        ("Maintenance labor", maint_labor),
#        ("Maintenance material", maint_material),
#        ("Operating supplies",oppsupplies),
#        ("Insurance & taxes", insurance),
#        ("Operating supervision", supervision),
#        ("Laboratory charges", lab),
#        ("Plant overhead", overhead),
#        ("Administrative costs", admin),
#    ], columns=["Item", "Annual cost ($/yr)"])

# ==========================================================
# Net Production Cost
# ==========================================================

def npc_usd_per_L(
    ACC_usd: float,
    direct_opex_df: pd.DataFrame,
    indirect_opex_df: pd.DataFrame,
    labor_cost: float,
    annual_fuel_mass_kg: float,
    fuel_density_kg_per_L: float,
) -> float:

    annual_volume_L = annual_fuel_mass_kg / fuel_density_kg_per_L

    total_opex = (
        direct_opex_df["Annual cost ($/yr)"].sum()
        + indirect_opex_df["Annual cost ($/yr)"].sum()
        + labor_cost
    )
    
    return float((ACC_usd + total_opex) / annual_volume_L)











#Autogenerated Use case for now, will be replaced with more detailed/validated assumptions

if __name__ == "__main__":

    print("\n==============================")
    print("SAF TEA MODEL – INTEGRATED TEST RUN")
    print("==============================\n")

    target_year = 2025

    # -----------------------------
    # FEEDSTOCK INPUT
    # -----------------------------
    biomass_tonnes_per_year = 200_000
    case = "distillate 1"

    # convert to kg/hr
    feedstock_kg_hr = biomass_tonnes_per_year * 1000 / 8760

    # -----------------------------
    # PRODUCTION MODEL
    # -----------------------------
    saf, diesel, naptha = biofuel_production(biomass_tonnes_per_year, case)

    total_fuel_GGE_hr = saf + diesel + naptha

    print(f"Feedstock: {feedstock_kg_hr:,.0f} kg/hr")
    print(f"Total fuel capacity: {total_fuel_GGE_hr:,.2f} GGE/hr\n")

    # -----------------------------
    # CAPEX using real scaling
    # -----------------------------
    equipment_costs = EC_scaling(
        feedstock_kg_hr=feedstock_kg_hr,
        fuel_GGE_hr=total_fuel_GGE_hr,
        year=target_year
    )

    FCI_usd = fixed_capital_investment_usd(equipment_costs)
    TCI_usd = FCI_usd / 0.9

    ACC_usd = annualized_capital_cost_usd(
        FCI_usd=FCI_usd,
        plant_life_years=20,
        interest_rate=0.09,
    )

    print(f"\nFCI: ${FCI_usd:,.0f}")
    print(f"ACC: ${ACC_usd:,.0f}\n")

    # -----------------------------
    # OPEX
    # -----------------------------
    direct_opex_df = direct_opex_usd(biomass_tonnes_per_year)

    labor_cost = operating_labor_cost_usd(
        P=3,
        N_np=14,
        salary_per_operator_usd=90_000,
    )

    indirect_opex_df = indirect_opex_usd(
        TCI_usd=TCI_usd,
        labor_cost=labor_cost,
    )

    # -----------------------------
    # Estimate SAF NPC ONLY
    # -----------------------------
    # convert SAF GGE/hr -> kg/year for NPC function
    MJ_per_GGE = 120
    MJ_per_L_SAF = 34.7
    L_per_GGE = MJ_per_GGE / MJ_per_L_SAF

    saf_L_hr = saf * L_per_GGE
    saf_kg_hr = saf_L_hr * 0.75
    saf_kg_year = saf_kg_hr * 8760

    npc = npc_usd_per_L(
        ACC_usd=ACC_usd,
        direct_opex_df=direct_opex_df,
        indirect_opex_df=indirect_opex_df,
        labor_cost=labor_cost,
        annual_fuel_mass_kg=saf_kg_year,
        fuel_density_kg_per_L=0.75,
    )

    print("==============================")
    print(f"SAF Net Production Cost: ${npc:.2f} per liter")
    print("==============================\n")
