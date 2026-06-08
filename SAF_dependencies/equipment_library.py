
################### SAF EQUIPMENT LIBRARY (MATCHES EXCEL) ###################

class Equipment:
    def __init__(self, name, base_cost, base_capacity, scalingexponent,
                 baseCEPCI, scale_type, count=1):

        self.name = name
        self.base_cost = base_cost
        self.base_capacity = base_capacity
        self.scalingexponent = scalingexponent
        self.baseCEPCI = baseCEPCI
        self.scale_type = scale_type      # "feedstock" or "fuel"
        self.count = count                # number of units


EQUIPMENT = {

    # ---------------- GASIFICATION ----------------
    "Syngas generation":
        Equipment("Syngas Generation", 31_645_570, 17306, 0.7, 576.1, "feedstock", 1),

    # ---------------- SYNGAS CLEANING ----------------
    "Anime system":
        Equipment("Anime System", 6_050_000, 83333, 0.75, 468.2, "feedstock", 1),

    "LO_CAT Absorber":
        Equipment("LO CAT Absorber", 16_200, 83333, 0.65, 525.4, "feedstock", 1),

    "LO_CAT Oxidizer Vessel":
        Equipment("Lo CAT Oxidizer Vessel", 1_000_000, 83333, 0.65, 525.4, "feedstock", 1),

    "Sulfur separator":
        Equipment("Sulfur Separator", 16_200, 83333, 0.6, 525.4, "feedstock", 1),

    "Carbon Dioxide Compressor":
        Equipment("CO2 Compressor", 1_176_000, 41667, 0.8, 525.4, "feedstock", 1),

    "Direct Quench Recycle Cooling":
        Equipment("Direct Quench", 188_800, 41667, 0.65, 525.4, "feedstock", 1),

    "Venturi Recycle Cooling":
        Equipment("Venture Recycle Cooling", 91_500, 83333, 0.6, 525.4, "feedstock", 1),

    "Venture Scrubber":
        Equipment("Venture Scrubber", 26_800, 83333, 0.65, 525.4, "feedstock", 1),

    "Direct Quench Syngas Cooler":
        Equipment("Syngas Cooler", 188_800, 41667, 0.6, 525.4, "feedstock", 1),

    "Venturi Liquid Collection Tank":
        Equipment("Venturi Tank", 74_500, 83333, 0.6, 525.4, "feedstock", 1),

    # ---------------- FUEL SYNTHESIS ----------------
    "HC production":
        Equipment("HC production", 60_500, 4341, 0.6, 525.4, "fuel", 1),

    "Syngas preheater furnace":
        Equipment("Syngas preheater furnace", 1_949_500, 4341, 0.6, 525.4, "fuel", 1),

    "Reformed syngas waste heat boiler":
        Equipment("Reformed syngas waste heat boiler", 396_600, 4341, 0.6, 525.4, "fuel", 1),

    "Syngas cooler 1":
        Equipment("Syngas cooler", 41_200, 4341, 0.6, 525.4, "fuel", 1),

    "Steam methane reformer":
        Equipment("Steam methane reformer", 1_650_800, 4341, 0.65, 525.4, "fuel", 1),

    "Water gas shift reactor":
        Equipment("Water gas shift reactor", 136_600, 4341, 0.5, 525.4, "fuel", 1),

    "ZnO sulfur removal beds":
        Equipment("ZnO sulfur removal beds", 46_400, 2171, 0.6, 525.4, "fuel", 1),

    "Booster syngas compressor":
        Equipment("Booster syngas compressor", 921_600, 2171, 0.6, 525.4, "fuel", 1),

    "Recycle syngas booster compressor":
        Equipment("Recycle syngas booster compressor", 725_400, 4341, 1.0, 525.4, "fuel", 1),

    "PSA Booster compressor":
        Equipment("PSA Booster compressor", 1_482_100, 4341, 0.65, 525.4, "fuel", 1),

    "PSA knock-out":
        Equipment("PSA knock-out", 1_482_100, 4341, 0.6, 525.4, "fuel", 1),

    "Syngas cooler 2":
        Equipment("Syngas cooler", 165_200, 4341, 0.6, 525.4, "fuel", 1),

    "Recycle syngas preheater":
        Equipment("Recycle syngas preheater", 24_300, 4341, 0.6, 525.4, "fuel", 1),

    "Fischer-Tropsch reactor":
        Equipment("Fischer-Tropsch reactor", 7_303_889, 4341, 0.72, 525.4, "fuel", 1),

    "PSA unit":
        Equipment("PSA unit", 30_500, 362, 0.65, 525.4, "fuel", 1),

    "FT knock-out column":
        Equipment("FT knock-out column", 72_100, 4341, 0.6, 525.4, "fuel", 1),

    "Water separator":
        Equipment("Water separator", 39_200, 4341, 0.6, 525.4, "fuel", 1),

    # ---------------- HYDROPROCESSING ----------------
    "Hydrocracking/Hydrotreating Unit":
        Equipment("Hydrocracking/Hydrotreating Unit", 7_927_152, 4341, 0.5, 525.4, "fuel", 1),

    # ---------------- AIR SEPARATION ----------------
    "Air compressor":
        Equipment("Air compressor", 3_119_600, 41667, 0.34, 525.4, "feedstock", 1),

    "Air cooler":
        Equipment("Air cooler", 24_300, 83333, 0.6, 525.4, "feedstock", 1),

    "Oxygen compressor cooler 1":
        Equipment("Oxygen compressor cooler", 23_300, 83333, 0.7, 525.4, "feedstock", 1),

    "Oxygen compressor cooler 2":
        Equipment("Oxygen compressor cooler", 23_000, 83333, 0.6, 525.4, "feedstock", 1),

    "Oxygen compressor":
        Equipment("Oxygen compressor", 1_514_700, 41667, 0.6, 525.4, "feedstock", 1),

    "High pressure column condenser":
        Equipment("HP column condenser", 20_300, 83333, 0.6, 525.4, "feedstock", 1),

    "HP column condenser accumulator":
        Equipment("HP condenser accumulator", 36_300, 83333, 0.6, 525.4, "feedstock", 1),

    "HP column reflux pump":
        Equipment("HP reflux pump", 14_300, 83333, 0.6, 525.4, "feedstock", 1),

    "HP column tower":
        Equipment("HP column tower", 279_900, 83333, 0.6, 525.4, "feedstock", 1),

    "Air compressor intercooler 1":
        Equipment("Air compressor intercooler", 338_300, 83333, 0.6, 525.4, "feedstock", 1),

    "Air compressor intercooler 2":
        Equipment("Air compressor intercooler", 304_500, 83333, 0.6, 525.4, "feedstock", 1),

    "Air compressor intercooler 3":
        Equipment("Air compressor intercooler", 222_500, 41667, 0.6, 525.4, "feedstock", 1),

    "Low pressure column boiler":
        Equipment("LP column boiler", 19_600, 83333, 0.6, 525.4, "feedstock", 1),

    "Low pressure column tower":
        Equipment("LP column tower", 1_538_900, 83333, 0.6, 525.4, "feedstock", 1),

    "Water knock-out drum":
        Equipment("Water knock-out drum", 30_100, 83333, 0.6, 525.4, "feedstock", 1),

    "Gas expander":
        Equipment("Gas expander", 89_200, 41667, 0.6, 525.4, "feedstock", 1),

    "Water knock-out drum 2":
        Equipment("Water knock-out drum", 64_800, 83333, 0.6, 525.4, "feedstock", 1),
}