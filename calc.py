import math

PLASTIC_PRICE = 129
HOUR_PRICE = 5
PROFIT = 0.40

def round5(x):
    return int(math.ceil(x / 5.0)) * 5

def calculate_price(weight, hours):
    plastic = (weight / 1000) * PLASTIC_PRICE
    time_cost = hours * HOUR_PRICE

    cost = plastic + time_cost
    profit = cost * PROFIT
    total = cost + profit

    total_rounded = round5(total)

    return {
        "plastic": round(plastic, 2),
        "time_cost": round(time_cost, 2),
        "cost": round(cost, 2),
        "profit": round(profit, 2),
        "total": total_rounded
    }
