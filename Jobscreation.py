###creating my own jobs created model
import matplotlib.pyplot as plt
import numpy as np
import math
#######################################         MULTIPLIER METHODOLOGY      #####################################################################
# https://www.epi.org/publication/updated-employment-multipliers-for-the-u-s-economy/
def jobs_from_biopower(plant_name, Final_Demand):
    "Final Demand is determined as the revenue of the plant. Not what you are paying or anything like that, the final product and what it is sold for"
    "This table was made in 2019 - convert to 2019 dollars" # https://www.in2013dollars.com/us/inflation/2019
    Final_Demand = Final_Demand/1.2782
    direct = 1.06 * Final_Demand/1e6
    indirect = 4.23 * Final_Demand/1e6
    induced = 1.75 * Final_Demand/1e6
    total = direct + indirect + induced
    return {
        "plant": plant_name,
        "direct_jobs": math.ceil(direct),
        "indirect_jobs": math.ceil(indirect),
        "induced_jobs": math.ceil(induced),
        "total_jobs": math.ceil(total)
    }

def jobs_from_biofuel(plant_name, Final_Demand):
    "Convert to 2019 dollars. Sector specific multipliers are used, petroleum manufacturing is the closest sector"
    Final_Demand = Final_Demand/1.2782
    direct = 0.22 * Final_Demand/1e6
    indirect = 2.08 * Final_Demand/1e6
    induced = 1.11 * Final_Demand/1e6
    total = direct + indirect + induced
    return {
        "plant": plant_name,
        "direct_jobs": math.ceil(direct),
        "indirect_jobs": math.ceil(indirect),
        "induced_jobs": math.ceil(induced),
        "total_jobs": math.ceil(total)
    }

def plot_job_breakdown(job_dict, title=None):
    """Plots a dark-themed bar chart of job breakdown (direct, indirect, induced)."""
    _BG = "#0e1621"; _BG_AX = "#131f2e"; _GRID = "#1e2d3d"
    _TEXT = "#c9d1e0"; _SPINE = "#1e2d3d"
    _COLORS = ["#60a5fa", "#f59e0b", "#22c55e"]   # blue, amber, green

    job_types  = ["Direct", "Indirect", "Induced"]
    job_values = [float(job_dict["direct_jobs"]),
                  float(job_dict["indirect_jobs"]),
                  float(job_dict["induced_jobs"])]
    total = job_dict.get("total_jobs", sum(job_values))

    fig, ax = plt.subplots(figsize=(7, 5.5))
    fig.patch.set_facecolor(_BG)
    ax.set_facecolor(_BG_AX)

    bars = ax.bar(job_types, job_values, color=_COLORS, width=0.5, alpha=0.9)

    for bar, v in zip(bars, job_values):
        ax.text(bar.get_x() + bar.get_width()/2, v + max(job_values)*0.02,
                f"{int(v):,}", ha="center", va="bottom",
                fontsize=12, fontweight="bold", color=_TEXT)

    ax.set_xlabel("Job Type", fontsize=13, color=_TEXT)
    ax.set_ylabel("Number of Jobs", fontsize=13, color=_TEXT)
    _plot_title = title if title else f"Job Creation — {job_dict.get('plant', 'Plant')}"
    ax.set_title(f"{_plot_title}\nTotal: {int(total):,} jobs", fontsize=15, color=_TEXT)
    ax.tick_params(colors=_TEXT, labelsize=11)
    for lbl in ax.get_xticklabels() + ax.get_yticklabels():
        lbl.set_color(_TEXT)
    ax.spines[["top","right"]].set_visible(False)
    ax.spines[["left","bottom"]].set_color(_SPINE)
    ax.yaxis.grid(True, linestyle="--", linewidth=0.5, color=_GRID)
    ax.set_axisbelow(True)

    plt.tight_layout()
    plt.savefig("Jobscreation_plots/plot_jobs.png", dpi=150, bbox_inches="tight")
    plt.close()
    print("Saved: plot_jobs.png")






    
#########
# # ##############################         RIMS II METHODOLOGY      #####################################################################
# # I AM TRYING A METHODOLOGY FROM RIMS II MULTIPLIERS! (instead of using the paper xD), https://www.nrc.gov/docs/ML0630/ML063000203.pdf
# # def jobs_construction(plant_name, FCI):
#     "Calculate the number of jobs created in the construction phase from the fixed capital investment"
    
#     #must convert dollars to 2002 dollars, assuming a base year of 2026
#     FCI_2002 = FCI/1.82 #https://www.in2013dollars.com/us/inflation/2002?amount=1
#     direct = FCI_2002/1e6 * 1.6985
#     total = FCI_2002/1e6 * 15.0767
#     direct = total * 1.6985
#     induced_indirect = total - direct
#     return {
#         "plant": plant_name,
#         "direct_jobs_impact_on_other_industries" : math.ceil(direct),
#         "total_jobs_from_industry": math.ceil(total)
#     }

# def jobs_powergen(plant_name, revenue):
#     "Calculate the number of jobs created in bioenergy operations (assuming only year 1)"
#     #assuming base year is 2026
#     revenue_2002 = revenue/1.82
#     #direct = revenue_2002/1e6 * 2.4128
#     total = revenue_2002/1e6 * 5.5636
#     direct = total * 2.4128
#     induced_indirect = total - direct
#     return {
#         "plant": plant_name,
#         "direct_jobs_impact_on_other_industries" : math.ceil(direct),
#         "total_jobs_from_industry": math.ceil(total)
#     }

# def jobs_biofuel(plant_name, revenue):
#     "Calculate the number of jobs "
#     revenue_2002 = revenue/1.82
#    # direct = revenue_2002/1e6 * 2.8919
#     total = revenue_2002/1e6 * 4.7120
#     direct = total * 2.8919
#     induced_indirect = total - direct
#     return {
#         "plant": plant_name,
#         "direct_jobs_impact_on_other_industries" : math.ceil(direct),
#         "total_jobs_from_industry": math.ceil(total)
#     }
# ##################################################################################################################################################


# ######################################         BIOPOWER PAPER METHOD     #######################################################
# #This is another paper that I found for a jobs created for a biopower plant
# def jobs_biopower(plant_name, AnnualOutput): #https://www.sciencedirect.com/science/article/pii/S0960148107003734?casa_token=V7pNrtNnfKAAAAAA:I50WA7tWqCyBnmNYCkWWKqfc2uG3x98VBMubvOvfJvU0xR8JUM6Qg6km0AlMgrOMLtZ0zmXQB7k
#     AnnualOutput = AnnualOutput / 1e6  # convert from kWh to GWh
#     total = 1.27 * AnnualOutput

#     a = 228.5 / 100 # multiplier for indirect jobs,  #https://www.epi.org/publication/updated-employment-multipliers-for-the-u-s-economy/
#     b = 134.8 / 100 # multiplier for induced jobs,   #https://www.epi.org/publication/updated-employment-multipliers-for-the-u-s-economy/

#     direct = total / (1 + a + b)
#     indirect = a * direct
#     induced = b * direct

#     return {
#         "plant": plant_name,
#         "direct_jobs": math.ceil(direct),
#         "indirect_jobs": math.ceil(indirect),
#         "induced_jobs": math.ceil(induced),
#         "total_jobs": math.ceil(total)
#     }



# ######################################         BIOMASS SUPPLY CHAIN METHODOLOGY      #######################################################
# # Jobs Creation Tool
# # Equations used:
# # Direct jobs: VA–EBE method (EBE provided directly from cash flows)
# # ExternalCosts: treat as purchased inputs (your assumption: bioenergy total_op_cost is utilities-only, no wages)
# # Indirect + Induced jobs: EPI multipliers for "Agriculture, forest, fishing, and hunting" ONLY (per 100 direct jobs)
# # EPI multipliers (per 100 direct jobs) - ONLY ONE INDUSTRY INCLUDED

# EPI_AG_FOREST_MULTIPLIERS = {
#     "indirect_per_100": 228.5,  #https://www.epi.org/publication/updated-employment-multipliers-for-the-u-s-economy/
#     "induced_per_100": 134.8    #https://www.epi.org/publication/updated-employment-multipliers-for-the-u-s-economy/
# }


# def calc_direct_jobs_va_ebe(revenue=None, external_costs=None, ebe=None,
#                            wage_bill=None,
#                            alpha=1.431e-5, beta=2.539):
#     """
#     Calculates direct jobs using either:
#     1. Provided wage_bill (preferred if available)
#     2. Estimated wage_bill = (Revenue - ExternalCosts) - EBE

#     Parameters:
#         revenue (float): Annual revenue ($)
#         external_costs (float): External consumption ($)
#         ebe (float): EBITDA ($)
#         wage_bill (float, optional): If provided, overrides calculation
#         alpha, beta: regression coefficients

#     Returns:
#         direct_jobs (float)
#     """

#     # Use provided wage bill if available
#     if wage_bill is not None:
#         wb = wage_bill
#     else:
#         if revenue is None or external_costs is None or ebe is None:
#             raise ValueError("Must provide either wage_bill OR (revenue, external_costs, ebe)")
        
#         va = revenue - external_costs
#         wb = va - ebe

#     print("Wage Bill used:", wb)

#     direct_jobs = alpha * wb + beta

#     return max(direct_jobs, 0.0)


# def calc_epi_supplier_and_induced(direct_jobs):
#     """
#     EPI multipliers are per 100 direct jobs:
#     supplier_jobs = direct_jobs * (indirect_per_100 / 100)
#     induced_jobs  = direct_jobs * (induced_per_100 / 100)
#     """
#     indirect_jobs = direct_jobs * (EPI_AG_FOREST_MULTIPLIERS["indirect_per_100"] / 100.0)
#     induced_jobs = direct_jobs * (EPI_AG_FOREST_MULTIPLIERS["induced_per_100"] / 100.0)
#     return indirect_jobs, induced_jobs


# def jobs_altfuel(plant_name, plant_inputs, alpha=1.431e-5, beta=2.539):
#     """
#     plant_inputs must be:
#     {
#       "revenue": float,
#       "external_costs": float,
#       "ebe": float,
#       OPTIONAL:
#       "wage_bill": float
#     }
#     """

#     revenue = plant_inputs.get("revenue")
#     external_costs = plant_inputs.get("external_costs")
#     ebe = plant_inputs.get("ebe")
#     wage_bill = plant_inputs.get("wage_bill", None)

#     # Correct call using keyword arguments
#     direct = calc_direct_jobs_va_ebe(
#         revenue=revenue,
#         external_costs=external_costs,
#         ebe=ebe,
#         wage_bill=wage_bill,
#         alpha=alpha,
#         beta=beta
#     )

#     indirect, induced = calc_epi_supplier_and_induced(direct)
#     total = direct + indirect + induced

#     return {
#         "plant": plant_name,
#         "direct_jobs": math.ceil(direct),
#         "indirect_jobs": math.ceil(indirect),
#         "induced_jobs": math.ceil(induced),
#         "total_jobs": math.ceil(total)
#     }