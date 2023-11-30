"""Simulating lifeform amortisation for miners"""
import pandas as pd
import matplotlib.pyplot as plt
import argparse
import math


LIFEFORM = {1: "Human", 2: "Rock´tal", 3: "Mecha", 4: "Kaelesh"}

CLASSES = {1: "Collector", 2: "Discoverer"}


TECHS = {
    1: {
        1: 3,
        2: 1,
        3: 2,
        4: 2,
        5: 2,
        6: 3,
        7: 2,
        8: 1,
        9: 2,
        10: 2,
        11: 2,
        12: 4,
        13: 3,
        14: 4,
        15: 2,
        16: 2,
        17: 1,
        18: 2,
    },
    2: {
        1: 3,
        2: 1,
        3: 2,
        4: 4,
        5: 4,
        6: 3,
        7: 2,
        8: 1,
        9: 2,
        10: 2,
        11: 4,
        12: 4,
        13: 3,
        14: 4,
        15: 2,
        16: 2,
        17: 1,
        18: 4,
    },
}


LF_COLOR = {1: "g", 2: "r", 3: "b", 4: "m"}

TECH_STYLE = {1: ":", 2: ""}


EXCHANGE = [2.7, 1.7, 1]
NUMBER_OF_PLANETS = 15
MAX_DSE = 250e9

# Percentage of total resource income by expeditions
EXPO_RES_PERCENTAGE = [0.444, 0.611, 0.207]
# Values for low mines [0.646, 0.695, 0.416]
# Percentage of total expedition income by ship findings
EXPO_SHIP_PERCENTAGE = [0.117, 0.257, 0.189]


def min_notna(x, y):
    if pd.notna(x) and pd.notna(y):
        return min(x, y)
    elif pd.notna(x):
        return x
    else:
        return y


def calc_dse(ressources, exchange=EXCHANGE):
    return sum([base / factor for base, factor in zip(ressources, exchange)])


def calc_cost(base_value, increase_factor, level, offset=1):
    return base_value * (increase_factor ** (level - 1 + offset)) * (level + offset)


def calc_tech_bonus(entry, offset=0):
    return min_notna(
        entry["bonus 1 max"] * 100,
        calc_cost(
            entry["bonus 1 base value"],
            entry["bonus 1 increase factor"],
            entry["level"],
            offset=offset,
        ),
    )


class LifeformAmortisation:
    def __init__(self, lifeform, techs, debug, expeditions, step_mode):
        self.tech_bonus = 0
        self.expo_bonus = 0
        self.expeditions = expeditions
        self.lifeform = lifeform
        self.debug = debug
        self.step_mode = step_mode
        self.data = pd.read_excel("lf_data.xlsx", sheet_name=1)
        self.data["Name EN"] = self.data["Name EN"].apply(lambda x: x.strip())
        # Move high performance transformer tech bonus to column bonus 1
        self.data.loc[
            self.data["Name EN"] == "High-Performance Transformer",
            ["bonus 1 base value", "bonus 1 increase factor", "bonus 1 max"],
        ] = self.data.loc[
            self.data["Name EN"] == "High-Performance Transformer",
            ["bonus 2 base value", "bonus 2 increase factor", "bonus 2 max"],
        ].values
        # Remove buildings not available to lifeform
        self.data = self.data[
            (self.data["Lifeform"] == lifeform) | (self.data["Type"] != "Building")
        ]
        # Remove techs not selected
        self.data = self.data[
            self.data.apply(
                lambda x: x["Type"] == "Building"
                or LIFEFORM[techs[int(x["Type"].split(" ")[-1])]] == x["Lifeform"],
                axis=1,
            )
        ]
        # Initialise level
        self.data["level"] = 0
        # Flag resource bonus type
        resource_types = [
            "metal",
            "crystal",
            "deuterium",
            "expeditions",
            "technology bonus",
        ]
        for ressource in resource_types:
            self.data[ressource] = self.data["Description EN"].apply(
                lambda x: ressource in x
            )
        # Set bonuses for collector enhancement
        self.data.loc[
            self.data["Name EN"] == "Rock’tal Collector Enhancement", resource_types
        ] = [True, True, True, False, False]
        # Collector bonus +25% flat, Crawler bonus is negated by hard limit
        self.data.loc[
            self.data["Name EN"] == "Rock’tal Collector Enhancement",
            "bonus 1 base value",
        ] *= 0.25
        # Metropolis description does not include 'technology bonus'
        self.data.loc[self.data["Name EN"] == "Metropolis", "technology bonus"] = True
        # These techs do notsignificantly impact ressource gain on expeditions
        self.data.loc[
            self.data["Name EN"].isin(
                ["Psionic Network", "Telekinetic Drive", "Gravitation Sensors"]
            ),
            "expeditions",
        ] = False
        # Remove entries without bonuses
        self.data = self.data[self.data[resource_types].any(axis=1)]
        # Calculate dse base cost
        self.data["dse_base_cost"] = self.data[
            ["metal base cost", "crystal base cost", "deut base cost"]
        ].apply(calc_dse, axis=1)

    def calc_bonus(self, entry, offset=0, tech_bonus=None, expo_bonus=None):
        if not tech_bonus:
            tech_bonus = self.tech_bonus
        if not expo_bonus:
            expo_bonus = self.expo_bonus
        bonus_list = [0, 0, 0, 0]
        bonus_idx = 1
        for idx, has_bonus in enumerate(
            entry[["metal", "crystal", "deuterium", "expeditions"]]
        ):
            if has_bonus:
                bonus_list[idx] = (
                    min_notna(
                        entry[f"bonus {bonus_idx} max"] * 100,
                        calc_cost(
                            entry[f"bonus {bonus_idx} base value"],
                            entry[f"bonus {bonus_idx} increase factor"],
                            entry["level"],
                            offset=offset,
                        ),
                    )
                    * (1 + tech_bonus / 100 if entry["Type"] != "Building" else 1)
                    * (1 + expo_bonus / 100 if entry["expeditions"] else 1)
                )
                if idx == 3:
                    # Expedition bonus applies to all resources
                    bonus_list = [bonus_list[3]] * len(bonus_list)
                if f"bonus {bonus_idx+1} base value" in entry.index and pd.notna(
                    entry[f"bonus {bonus_idx+1} base value"]
                ):
                    bonus_idx += 1
        bonus_list = bonus_list[:3]
        if self.expeditions:
            if entry["expeditions"]:
                bonus_list = [
                    bonus * ratio
                    for bonus, ratio in zip(bonus_list, EXPO_RES_PERCENTAGE)
                ]
                if "ships" in entry["Description EN"]:
                    bonus_list = [
                        bonus * ratio
                        for bonus, ratio in zip(bonus_list, EXPO_SHIP_PERCENTAGE)
                    ]
                else:
                    bonus_list = [
                        bonus * (1 - ratio)
                        for bonus, ratio in zip(bonus_list, EXPO_SHIP_PERCENTAGE)
                    ]
            else:
                bonus_list = [
                    bonus * (1 - ratio)
                    for bonus, ratio in zip(bonus_list, EXPO_RES_PERCENTAGE)
                ]
        return calc_dse(bonus_list)

    def calc_tech_amortisation(self):
        for i, (applies_from, applies_to) in enumerate(
            zip(
                [
                    self.data["technology bonus"],
                    self.data["Name EN"] == "Kaelesh Discoverer Enhancement",
                ],
                [self.data["Type"] != "Building", self.data["expeditions"]],
            )
        ):
            if not applies_from.any():
                continue
            # Tech bonus has no native bonus
            if i == 0:
                self.data.loc[applies_from, "new_dse_bonus"] = 0
            self.data.loc[applies_from, "tech_dse_bonus"] = self.data[
                applies_from
            ].apply(lambda x: calc_tech_bonus(x, offset=1), axis=1) - self.data[
                applies_from
            ].apply(
                calc_tech_bonus, axis=1
            )
            tech = self.data[applies_from].apply(
                lambda x: self.data.apply(
                    lambda y: self.calc_bonus(
                        y,
                        tech_bonus=(x["tech_dse_bonus"] + self.tech_bonus)
                        if i == 0
                        else self.tech_bonus,
                        expo_bonus=(x["tech_dse_bonus"] + self.expo_bonus)
                        if i == 1
                        else self.expo_bonus,
                    ),
                    axis=1,
                ),
                axis=1,
            )
            self.data.loc[applies_from, "new_dse_bonus"] += (
                (tech - self.data["current_dse_bonus"])
                .loc[
                    :,
                    applies_to & (~applies_from),
                ]
                .sum(axis=1)
            )

    def recalculate_tech_bonus(self):
        if self.data["technology bonus"].any():
            self.tech_bonus = sum(
                self.data[self.data["technology bonus"]].apply(calc_tech_bonus, axis=1)
            )
        if "Kaelesh Discoverer Enhancement" in self.data["Name EN"].values:
            self.expo_bonus = calc_tech_bonus(
                self.data[
                    self.data["Name EN"] == "Kaelesh Discoverer Enhancement"
                ].iloc[0]
            ) * (1 + (self.tech_bonus / 100))

    def step(self):
        self.recalculate_tech_bonus()
        self.data["current_dse_bonus"] = self.data.apply(self.calc_bonus, axis=1)
        self.data["new_dse_bonus"] = self.data.apply(
            lambda x: self.calc_bonus(x, offset=1), axis=1
        )
        self.calc_tech_amortisation()

        self.data["new_dse_cost"] = self.data.apply(
            lambda x: calc_cost(
                x["dse_base_cost"], x["metal increase factor"], x["level"]
            ),
            axis=1,
        )
        self.data["new_bonus_cost_ratio"] = (
            self.data["new_dse_cost"] / self.data["new_dse_bonus"]
        )
        index = self.data["new_bonus_cost_ratio"].idxmin()
        self.data.loc[index, "level"] += 1
        self.recalculate_tech_bonus()
        self.data["current_dse_bonus"] = self.data.apply(self.calc_bonus, axis=1)
        if self.debug or self.step_mode:
            print(
                f"Upgrading {self.data.loc[index, 'Name EN']} to level {self.data.loc[index, 'level']}, new bonus: {round(self.data['current_dse_bonus'].sum(), 2)}%, cost: 10^{round(math.log10(self.data.loc[index, 'new_dse_cost']))} tech bonus: {round(self.tech_bonus, 1)}%, expo bonus: {round(self.expo_bonus, 1)}%"
            )
        if self.step_mode:    
            input(
                self.data.sort_values("new_bonus_cost_ratio")[
                    ["Name EN", "level", "new_dse_bonus", "new_dse_cost"]
                ]
            )
        return index

    def simulate(self, max_dse):
        cummulative_dse_cost = [0]
        total_dse_bonus = [0]
        while cummulative_dse_cost[-1] <= max_dse:
            index = self.step()
            cummulative_dse_cost.append(
                cummulative_dse_cost[-1] + self.data.loc[index]["new_dse_cost"]
            )
            total_dse_bonus.append(self.data["current_dse_bonus"].sum())
        plot = pd.DataFrame()
        plot["cummulative_dse_cost"] = cummulative_dse_cost
        plot["total_dse_bonus"] = total_dse_bonus
        print(
            self.lifeform,
            CLASSES[2 if self.expeditions else 1],
            cummulative_dse_cost[-1],
            self.data["current_dse_bonus"].sum(),
        )
        print(self.data[["Name EN", "level"]])
        return plot


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-m", "--max-dse", type=int, help="How many DSE to invest in a single planet")
    parser.add_argument("-d", "--debug", action="store_true", help="Show step by step upgrading")
    parser.add_argument("-c", "--selected_class", type=int, help="Select class: 1=Collector, 2=Discoverer")
    parser.add_argument("-l", "--lifeform", type=int, help="Select lifeform: 1=Human, 2=Rock, 3=Mecha, 4=Kaelesh")
    parser.add_argument("-r", "--rebase", action="store_true", help="Rebase all results based on Collector base production instead of class base production")
    parser.add_argument("-s", "--step-mode", action="store_true", help="Requires input after every upgrading step")
    parser.add_argument("-i", "--input", action="store_true", help="Manually input your levels and simulate next step")
    args = parser.parse_args()
    max_dse = args.max_dse if args.max_dse else MAX_DSE
    debug = args.debug if args.debug else False
    levels = None
    legend = []
    for tech_i, techs in TECHS.items():
        if args.selected_class and args.selected_class != tech_i:
            continue
        for lf_i, lifeform in LIFEFORM.items():
            if args.lifeform and args.lifeform != lf_i:
                continue
            expeditions = CLASSES[tech_i] == "Discoverer"
            simulation = LifeformAmortisation(lifeform, techs, debug, expeditions, args.step_mode)
            if args.input:
                if levels is None:
                    levels = simulation.data["Name EN"].apply(lambda x: input(f"{x}: ")).apply(lambda x: int(x) if x != "" else 0)
                simulation.data["level"] = levels
                simulation.data["level"].fillna(0, inplace=True)
            plot = simulation.simulate(max_dse)
            plot["total_dse_bonus"] /= ((calc_dse(EXPO_RES_PERCENTAGE)/3) if args.rebase and expeditions else 1
            )
            plt.plot(
                plot["cummulative_dse_cost"],
                plot["total_dse_bonus"],
                LF_COLOR[lf_i] + TECH_STYLE[tech_i],
            )
            legend.append(f"{CLASSES[tech_i]}-{lifeform}")
    plt.xlabel("Investierte Deuterium Standard Einheiten (DSE)")
    plt.ylabel("Bonus auf DSE Einkommen in %")
    plt.legend(legend,
        loc="lower right",
    )
    plt.show()
