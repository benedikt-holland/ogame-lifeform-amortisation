"""Simulating lifeform amortisation for miners"""
import pandas as pd
import matplotlib.pyplot as plt


LIFEFORM = {
    1: "Human",
    2: "Rock´tal",
    3: "Mecha",
    4: "Kaelesh"
}


TECHS = {
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
    18: 2
}


EXCHANGE = [2.7, 1.7, 1]


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
    return base_value * (increase_factor  ** (level -1 + offset)) * (level + offset)


def calc_bonus(entry, offset=0, tech_bonus=0):
    bonus_list = [0, 0, 0]
    bonus_idx = 1
    for idx, has_bonus in enumerate(entry[["metal", "crystal", "deuterium"]]):
        if has_bonus:
            bonus_list[idx] = min_notna(entry[f"bonus {bonus_idx} max"], calc_cost(entry[f"bonus {bonus_idx} base value"], entry[f"bonus {bonus_idx} increase factor"], entry["level"], offset=offset) / 100) * (1+tech_bonus if entry["Type"] != "Building" else 1)
            if f"bonus {bonus_idx+1} base value" in entry.index and pd.notna(entry[f"bonus {bonus_idx+1} base value"]):
                bonus_idx += 1
    return calc_dse(bonus_list)


def calc_tech_bonus(entry, offset=0):
    return min_notna(entry["bonus 1 max"], calc_cost(entry["bonus 1 base value"], entry["bonus 1 increase factor"], entry["level"], offset=offset) / 100)


def step(data, debug=False):
    tech_bonus = 0
    if data["tech"].any():
        tech_bonus = sum(data[data["tech"]].apply(calc_tech_bonus, axis=1))
    data["current_dse_bonus"] = data.apply(lambda x: calc_bonus(x, tech_bonus=tech_bonus), axis=1)
    data["new_dse_bonus"] = data.apply(lambda x: calc_bonus(x, tech_bonus=tech_bonus, offset=1), axis=1)
    if data["tech"].any():
        data.loc[data["tech"], "new_dse_bonus"] = data[data["tech"]].apply(lambda x: calc_tech_bonus(x, offset=1), axis=1) - data[data["tech"]].apply(lambda x: calc_tech_bonus(x), axis=1)
        tech = data[data["tech"]].apply(lambda x: data.apply(lambda y: calc_bonus(y, tech_bonus=(x["new_dse_bonus"]+tech_bonus)), axis=1), axis=1)
        data.loc[data["tech"], "new_dse_bonus"] = (tech-data["current_dse_bonus"]).loc[:, (data["Type"] != "Building") & (~data["tech"])].sum(axis=1)
    data["new_dse_cost"] = data.apply(lambda x: calc_cost(x["dse_base_cost"], x["metal increase factor"], x["level"]), axis=1)
    data["new_bonus_cost_ratio"] = data["new_dse_cost"] /  data["new_dse_bonus"]
    index = data["new_bonus_cost_ratio"].idxmin()
    data.loc[index, "level"] += 1
    if data["tech"].any():
        tech_bonus = sum(data[data["tech"]].apply(calc_tech_bonus, axis=1))
    data["current_dse_bonus"] = data.apply(lambda x: calc_bonus(x, tech_bonus=tech_bonus), axis=1)
    if debug:
        print(f"Upgrading {data.loc[index, 'Name EN']} to level {data.loc[index, 'level']}, new bonus: {data['current_dse_bonus'].sum()}")
    return index


def build_plot(lifeform, max_dse, debug=False):
    data = pd.read_excel("lf_data.xlsx", sheet_name=1)
    # Move high performance transformer tech bonus to column bonus 1
    data.loc[data["Name EN"] == "High-Performance Transformer", ["bonus 1 base value", "bonus 1 increase factor", "bonus 1 max"]] = data.loc[data["Name EN"] == "High-Performance Transformer", ["bonus 2 base value", "bonus 2 increase factor", "bonus 2 max"]].values
    # Remove buildings not available to lifeform
    data = data[(data["Lifeform"] == lifeform) | (data["Type"] != "Building")]
    # Remove techs not selected
    data = data[data.apply(lambda x: x["Type"] == "Building" or LIFEFORM[TECHS[int(x["Type"].split(" ")[-1])]] == x["Lifeform"], axis=1)]
    # Initialise level
    data["level"] = 0
    # Flag resource bonus type
    for ressource in ["metal", "crystal", "deuterium"]:
        data[ressource] = data["Description EN"].apply(lambda x: ressource in x)
    # Set bonuses for collector enhancement
    data.loc[data["Name EN"] == "Rock’tal Collector Enhancement", ["metal", "crystal", "deuterium"]] = [True, True, True]
    # Collector bonus +25% flat, Crawler bonus is negated by hard limit
    data.loc[data["Name EN"] == "Rock’tal Collector Enhancement", "bonus 1 base value"] *= 0.25
    # Set tech bonus type
    data["tech"] = False
    data.loc[data["Name EN"].isin(["Metropolis", "High-Performance Transformer", "Chip Mass Production"]), "tech"] = True
    # Remove entries without bonuses
    data = data[data[["metal", "crystal", "deuterium", "tech"]].any(axis=1)]
    # Calculate dse base cost
    data["dse_base_cost"] = data[["metal base cost", "crystal base cost", "deut base cost"]].apply(calc_dse, axis=1)
    # Calculate dse bonus
    data["dse_base_bonus"] = data.apply(lambda x: calc_bonus(x, offset=1), axis=1)
    cummulative_dse_cost = [0]
    total_dse_bonus = [0]
    while cummulative_dse_cost[-1] <= max_dse:
        index = step(data, debug)
        cummulative_dse_cost.append(cummulative_dse_cost[-1] + data.loc[index]["new_dse_cost"])
        total_dse_bonus.append(data["current_dse_bonus"].sum())
    plot = pd.DataFrame()
    plot["cummulative_dse_cost"] = cummulative_dse_cost
    plot["total_dse_bonus"] = total_dse_bonus
    print(lifeform, cummulative_dse_cost[-1], data["current_dse_bonus"].sum())
    print(data[["Name EN", "level"]])
    return plot


if __name__ == '__main__':
    max_dse = 1e15
    debug = False
    for lifeform in LIFEFORM.values():
        plot = build_plot(lifeform, max_dse, debug)
        plt.plot(plot["cummulative_dse_cost"], plot["total_dse_bonus"])
    plt.xlabel("Investierte Deuterium Standard Einheiten (DSE)")
    plt.ylabel("Bonus auf DSE Produktion")
    plt.legend(LIFEFORM.values(),loc="lower right")
    plt.show()
