import math

HOUR_PRICE = 5

def round5(x):
    return int(math.ceil(x / 5.0)) * 5

def calculate_price(weight, hours, plastic_price=129, extra=0, quantity=1, profit_percent=0.4, delivery=0):
    plastic = (weight / 1000) * plastic_price
    time_cost = hours * HOUR_PRICE
    cost = (plastic + time_cost + extra) * quantity + delivery
    profit = cost * profit_percent
    total = cost + profit
    total_rounded = round5(total)

    return {
        "plastic": round(plastic,2),
        "time_cost": round(time_cost,2),
        "cost": round(cost,2),
        "profit": round(profit,2),
        "total": total_rounded
    }
