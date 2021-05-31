import json, os
from pathlib import Path

SCRIPT_PATH = os.path.dirname(os.path.realpath(__file__)) + "/"

def getJsonFile(name):
    if not Path(SCRIPT_PATH + name).is_file():
        raise ValueError("Missing " + name)
    try:
        with open(SCRIPT_PATH + name, "r") as f:
            return json.loads(f.read())
    except Exception as e:
        print("Failed to get file: " + name + " because of exception: " + str(e))
        raise e

entries = getJsonFile("prices.log")
totalWeight = 0.0
sumOfWeightedPrices = 0.0
for entry in entries:
    weight = entry["weight"]
    price = entry["price"]
    totalWeight = round(totalWeight + weight, 2)
    sumOfWeightedPrices = round(sumOfWeightedPrices + (weight * price), 2)

print(round(sumOfWeightedPrices / totalWeight, 2))
