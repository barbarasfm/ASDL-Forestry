"""
SAF Techno-Economic Tool
==========================================================
"""

from __future__ import annotations
from math import tanh
import pandas as pd
from SAF_dependencies.biofuel_production_FINAL import biofuel_production


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

    from SAF_dependencies.equipment_library import EQUIPMENT

    CEPCI_current = cepci_from_year(year)

    scaled_costs = {}

    for key, equipment in EQUIPMENT.items():

        # choose correct capacity basis
        if equipment.scale_type == "feedstock":
            capacity = feedstock_kg_hr
        elif equipment.scale_type == "fuel":
            capacity = fuel_GGE_hr
        else:
            raise ValueError(f"Unknown scaling type for {equipment.name}")

        # ---- Excel Step 1:
        scaled_base = (
            equipment.count *
            equipment.base_cost *
            (capacity / equipment.base_capacity) ** equipment.scalingexponent
        )

        # ---- Excel Step 2: CEPCI escalation
        scaled_cost = scaled_base * (CEPCI_current / equipment.baseCEPCI)

        scaled_costs[key] = scaled_cost
        #print(f"{equipment.name}: ${scaled_cost:,.2f}")

    return scaled_costs

# ==========================================================
#Area report
# ==========================================================

def print_process_area_summary(equipment_costs: dict):
    process_groups = {

        "Gasification, syngas cleaning, fuel synthesis": [

            # --- Gasification ---
            "Syngas generation",

            # --- Syngas cleaning ---
            "Anime system",
            "LO_CAT Absorber",
            "LO_CAT Oxidizer Vessel",
            "Sulfur separator",
            "Carbon Dioxide Compressor",
            "Direct Quench Recycle Cooling",
            "Venturi Recycle Cooling",
            "Venture Scrubber",
            "Direct Quench Syngas Cooler",
            "Venturi Liquid Collection Tank",

            # --- Fuel synthesis / conditioning ---
            "Syngas preheater furnace",
            "Reformed syngas waste heat boiler",
            "Syngas cooler 1",
            "Steam methane reformer",
            "Water gas shift reactor",
            "ZnO sulfur removal beds",
            "Booster syngas compressor",
            "Recycle syngas booster compressor",
            "PSA Booster compressor",
            "PSA knock-out",
            "Syngas cooler 2",
            "Recycle syngas preheater",
            "Fischer-Tropsch reactor",
            "PSA unit",
            "FT knock-out column",
            "Water separator",
            "HC production",
        ],

        "Hydroprocessing": [
            "Hydrocracking/Hydrotreating Unit",
        ],

        "Air separation": [
            "Air compressor",
            "Air cooler",
            "Oxygen compressor cooler 1",
            "Oxygen compressor cooler 2",
            "Oxygen compressor",
            "High pressure column condenser",
            "HP column condenser accumulator",
            "HP column reflux pump",
            "HP column tower",
            "Air compressor intercooler 1",
            "Air compressor intercooler 2",
            "Air compressor intercooler 3",
            "Low pressure column boiler",
            "Low pressure column tower",
            "Water knock-out drum",
            "Gas expander",
            "Water knock-out drum 2",
        ],
    }

    print("\nProcess area")
    print("-"*70)
    print(f"{'Process area':45s} {'ISBL':6s} {'Delivered equipment cost (MM$)':>20s}")

    total = 0.0

    for area, equipment_list in process_groups.items():

        area_cost = sum(
            equipment_costs.get(eq, 0.0)
            for eq in equipment_list
        )

        if area_cost > 0:
            mm = area_cost / 1e6
            print(f"{area:45s} {'ISBL':6s} {mm:>20.1f}")
            total += area_cost

    print("-"*70)
    print(f"{'Total':45s} {'':6s} {(total/1e6):>20.1f}\n")



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
    print("COST SCALING TEST RUN")
    print("==============================\n")

    target_year = 2025

    # -----------------------------
    # FEEDSTOCK INPUT
    # -----------------------------
    biomass_tonnes_per_year = 200_000
    case = "distillate 1"

    # convert to kg/hr
    feedstock_kg_hr = biomass_tonnes_per_year * 1000 / 7884
    print("Python CEPCI:", cepci_from_year(target_year))

    # -----------------------------
    # PRODUCTION MODEL
    # -----------------------------
    saf, diesel, naptha, saf_MML, diesel_MML, naptha_MML = biofuel_production(biomass_tonnes_per_year, case)
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

    print_process_area_summary(equipment_costs)

    