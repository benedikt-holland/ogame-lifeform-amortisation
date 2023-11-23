"""Simulating lifeform amortisation for miners"""
import pandas as pd
import matplotlib.pyplot as plt


LIFEFORM = {1: "Human", 2: "Rock´tal", 3: "Mecha", 4: "Kaelesh"}


TECHS = {
    "Production": {
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
    "Expedition": {
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

EXPEDITIONS = True
# Percentage of total resource income by expeditions
EXPO_RES_PERCENTAGE = [0.444, 0.611, 0.207]
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


def calc_bonus(entry, offset=0, tech_bonus=0):
    bonus_list = [0, 0, 0, 0]
    bonus_idx = 1
    for idx, has_bonus in enumerate(
        entry[["metal", "crystal", "deuterium", "expeditions"]]
    ):
        if has_bonus:
            bonus_list[idx] = min_notna(
                entry[f"bonus {bonus_idx} max"],
                calc_cost(
                    entry[f"bonus {bonus_idx} base value"],
                    entry[f"bonus {bonus_idx} increase factor"],
                    entry["level"],
                    offset=offset,
                )
                / 100,
            ) * (1 + tech_bonus if entry["Type"] != "Building" else 1)
            if idx == 3:
                # Expedition bonus applies to all resources
                bonus_list = [bonus_list[3]] * len(bonus_list)
            if f"bonus {bonus_idx+1} base value" in entry.index and pd.notna(
                entry[f"bonus {bonus_idx+1} base value"]
            ):
                bonus_idx += 1
    bonus_list = bonus_list[:3]
    if EXPEDITIONS:
        if entry["expeditions"]:
            bonus_list = [
                bonus * ratio for bonus, ratio in zip(bonus_list, EXPO_RES_PERCENTAGE)
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
            # TODO Discoverer Boost Tech (Bonus = Boost * Normal Bonus)
        else:
            bonus_list = [
                bonus * (1 - ratio)
                for bonus, ratio in zip(bonus_list, EXPO_RES_PERCENTAGE)
            ]
    return calc_dse(bonus_list)


def calc_tech_bonus(entry, offset=0):
    return min_notna(
        entry["bonus 1 max"],
        calc_cost(
            entry["bonus 1 base value"],
            entry["bonus 1 increase factor"],
            entry["level"],
            offset=offset,
        )
        / 100,
    )


class LifeformAmortisation:
    def __init__(self, lifeform, techs, debug):
        self.lifeform = lifeform
        self.debug = debug
        self.data = pd.read_excel("lf_data.xlsx", sheet_name=1)
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
        # Calculate dse bonus
        self.data["dse_base_bonus"] = self.data.apply(
            lambda x: calc_bonus(x, offset=1), axis=1
        )

    def step(self):
        tech_bonus = 0
        if self.data["technology bonus"].any():
            tech_bonus = sum(
                self.data[self.data["technology bonus"]].apply(calc_tech_bonus, axis=1)
            )
        self.data["current_dse_bonus"] = self.data.apply(
            lambda x: calc_bonus(x, tech_bonus=tech_bonus), axis=1
        )
        self.data["new_dse_bonus"] = self.data.apply(
            lambda x: calc_bonus(x, tech_bonus=tech_bonus, offset=1), axis=1
        )
        if self.data["technology bonus"].any():
            self.data.loc[self.data["technology bonus"], "new_dse_bonus"] = self.data[
                self.data["technology bonus"]
            ].apply(lambda x: calc_tech_bonus(x, offset=1), axis=1) - self.data[
                self.data["technology bonus"]
            ].apply(
                lambda x: calc_tech_bonus(x), axis=1
            )
            tech = self.data[self.data["technology bonus"]].apply(
                lambda x: self.data.apply(
                    lambda y: calc_bonus(
                        y, tech_bonus=(x["new_dse_bonus"] + tech_bonus)
                    ),
                    axis=1,
                ),
                axis=1,
            )
            self.data.loc[self.data["technology bonus"], "new_dse_bonus"] = (
                (tech - self.data["current_dse_bonus"])
                .loc[
                    :,
                    (self.data["Type"] != "Building")
                    & (~self.data["technology bonus"]),
                ]
                .sum(axis=1)
            )
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
        if self.data["technology bonus"].any():
            tech_bonus = sum(
                self.data[self.data["technology bonus"]].apply(calc_tech_bonus, axis=1)
            )
        self.data["current_dse_bonus"] = self.data.apply(
            lambda x: calc_bonus(x, tech_bonus=tech_bonus), axis=1
        )
        if debug:
            print(
                f"Upgrading {self.data.loc[index, 'Name EN']} to level {self.data.loc[index, 'level']}, new bonus: {self.data['current_dse_bonus'].sum()}"
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
            cummulative_dse_cost[-1],
            self.data["current_dse_bonus"].sum(),
        )
        print(self.data[["Name EN", "level"]])
        return plot


if __name__ == "__main__":
    max_dse = 1e12
    debug = False
    for tech_i, techs in enumerate(TECHS.values()):
        for lf_i, lifeform in enumerate(LIFEFORM.values()):
            simulation = LifeformAmortisation(lifeform, techs, debug)
            plot = simulation.simulate(max_dse)
            plt.plot(
                plot["cummulative_dse_cost"],
                plot["total_dse_bonus"],
                LF_COLOR[lf_i + 1] + TECH_STYLE[tech_i + 1],
            )
    plt.xlabel("Investierte Deuterium Standard Einheiten (DSE)")
    plt.ylabel("Bonus auf DSE Einkommen")
    plt.legend(
        [
            selected_class + "-" + lifeform
            for selected_class in TECHS
            for lifeform in LIFEFORM.values()
        ],
        loc="lower right",
    )

    plt.show()
