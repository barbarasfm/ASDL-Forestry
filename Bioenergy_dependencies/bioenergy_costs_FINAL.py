from Bioenergy_dependencies.CEPCI import score

# CAPITAL COSTS SCRIPT

def equipment_costs(biomass_in, year):
    """
    Calculate equipment costs for stoker boiler and steam turbine

    Parameters:
    - biomass_in: Biomass input in tons per day
    - year: Current year for CEPCI calculation

    Returns:
    - EC: Total equipment cost
    - Individual component costs
    """
    # Reference equipment costs (USD)
    Stoker_Boiler_refcost = 18_000_000  # dollars
    Steam_Turbine_refcost = 5_425_000   # dollars
    Fuel_Handling_refcost = 2_054_433

    # Reference CEPCI (2015)
    CEPCI_ref = 556.8
    # CEPCI 2003
    CEPCI_03 = 395.6

    indata = {"year": year}
    outdata = {}

    CEPCI_current = score(indata, outdata)
    CEPCI_ratio = CEPCI_current / CEPCI_ref
    CEPCI_ratio03 = CEPCI_current / CEPCI_03
    biomass_ref = 600  # tons per day

    scale_factor = (biomass_in / biomass_ref) ** 0.72

    Stoker_cost = Stoker_Boiler_refcost * scale_factor * CEPCI_ratio
    Turbine_cost = Steam_Turbine_refcost * scale_factor * CEPCI_ratio
    Fuel_handling_cost = Fuel_Handling_refcost * scale_factor * CEPCI_ratio03
    EC = Stoker_cost + Turbine_cost + Fuel_handling_cost

    EC_list = [Stoker_cost, Turbine_cost, Fuel_handling_cost]

    print(f"\n=== EQUIPMENT COSTS ===")
    print(f"Stoker System Cost: ${Stoker_cost:,.2f}")
    print(f"Steam Turbine Cost: ${Turbine_cost:,.2f}")
    print(f"Fuel Handling Cost: ${Fuel_handling_cost:,.2f}")
    print(f"Total Equipment Cost: ${EC:,.2f}")

    return EC, Stoker_cost, Fuel_handling_cost, Turbine_cost, EC_list


def TCI_calculation(EC, EC_list):
    """
    Calculate Total Capital Investment (TCI) using Peters & Timmerhaus method
    for solid-processing plants

    Parameters:
    - EC: Total equipment cost

    Returns:
    - TCI: Total Capital Investment
    - FCI: Fixed Capital Investment
    - Breakdown dictionary
    """
    total_installation = 0
    total_instrumentation = 0
    total_piping = 0
    total_electrical = 0
    total_building = 0
    total_yard = 0
    total_service_facilities = 0

    for i, equip_cost in enumerate(EC_list):
        installation = equip_cost * 0.45
        instrumentation = equip_cost * 0.18
        piping = equip_cost * 0.16
        electrical = equip_cost * 0.10
        building = equip_cost * 0.25
        yard = equip_cost * 0.15
        service_facilities = equip_cost * 0.40

        total_installation += installation
        total_instrumentation += instrumentation
        total_piping += piping
        total_electrical += electrical
        total_building += building
        total_yard += yard
        total_service_facilities += service_facilities

    direct_cost = (EC + total_installation + total_instrumentation + total_piping +
                   total_electrical + total_building + total_yard +
                   total_service_facilities)

    total_engineering_cost = 0
    total_construction_cost = 0
    total_legal_expenses = 0
    total_contractors_fee = 0
    total_contingenecy = 0

    for i, equip_cost in enumerate(EC_list):
        engineering_cost = equip_cost * 0.33
        construction_cost = equip_cost * 0.39
        legal_expenses = equip_cost * 0.04
        contractors_fee = equip_cost * 0.17
        contingency = 0.35

        total_engineering_cost += engineering_cost
        total_construction_cost += construction_cost
        total_legal_expenses += legal_expenses
        total_contractors_fee += contractors_fee
        total_contingenecy += contingency

    indirect_cost = total_engineering_cost + total_construction_cost + total_legal_expenses + total_contractors_fee + total_contingenecy

    total_indirect_direct_cost = indirect_cost + direct_cost
    FCI = total_indirect_direct_cost

    working_capital_factor = 0.10
    TCI = FCI * (1 + working_capital_factor)

    breakdown = {
        'Equipment Cost': EC,
        'Direct Costs': direct_cost,
        'Indirect Costs': indirect_cost,
        'Contractors Fee': total_contractors_fee,
        'Fixed Capital Investment (FCI)': FCI,
        'Total Capital Investment (TCI)': TCI
    }

    print(f"\n=== CAPITAL INVESTMENT BREAKDOWN ===")
    for key, value in breakdown.items():
        print(f"{key:.<35} ${value:,.2f}")

    return TCI, FCI, breakdown


def depreciation_schedule(breakdown_dict, equipment_costs, max_years=16):
    """
    Parameters:
    - breakdown_dict: from TCI_calculation
    - equipment_costs: list of [boiler_cost, turbine_cost, fuel_yard_cost]
    - max_years: number of years to compute depreciation for

    Returns:
    - annual_depreciation: list of depreciation by year
    """
    macrs_5yr = [0.2000, 0.3200, 0.1920, 0.1152, 0.1152, 0.0576]

    macrs_7yr = [0.1429, 0.2449, 0.1719, 0.1249, 0.0893, 0.0892, 0.0893, 0.046]

    macrs_15yr_200DB = [
        0.0500, 0.0950, 0.0855, 0.0770, 0.0693, 0.0623,
        0.0590, 0.0590, 0.0591, 0.0590, 0.0591, 0.0590,
        0.0591, 0.0590, 0.0591, 0.0295
    ]

    annual_depreciation = [0] * max_years

    boiler_cost    = equipment_costs[0]
    turbine_cost   = equipment_costs[1]
    fuel_yard_cost = equipment_costs[2]

    for i in range(min(len(macrs_7yr), max_years)):
        annual_depreciation[i] += boiler_cost  * macrs_7yr[i]
        annual_depreciation[i] += turbine_cost * macrs_7yr[i]

    for i in range(min(len(macrs_5yr), max_years)):
        annual_depreciation[i] += fuel_yard_cost * macrs_5yr[i]

    FCI = breakdown_dict['Fixed Capital Investment (FCI)']
    rest_of_plant = FCI - boiler_cost - turbine_cost - fuel_yard_cost

    for i in range(min(len(macrs_15yr_200DB), max_years)):
        annual_depreciation[i] += rest_of_plant * macrs_15yr_200DB[i]

    return annual_depreciation