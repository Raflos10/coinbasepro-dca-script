# dependent on requests package (pip install requests)
# and Path (pip install pathlib)

import json, hmac, hashlib, time, requests, base64, math, os, sys
from requests.auth import AuthBase
from pathlib import Path
from datetime import datetime

# Create custom authentication for Exchange
class CoinbaseExchangeAuth(AuthBase):
    def __init__(self, api_key, secret_key, passphrase):
        self.api_key = api_key
        self.secret_key = secret_key
        self.passphrase = passphrase

    def __call__(self, request):
        timestamp = str(time.time())
        message = timestamp + request.method + request.path_url + (request.body or '')
        message = message.encode('ascii')
        hmac_key = base64.b64decode(self.secret_key)
        signature = hmac.new(hmac_key, message, hashlib.sha256)
        signature_b64 = base64.b64encode(signature.digest()).decode('utf-8')

        request.headers.update({
            'CB-ACCESS-SIGN': signature_b64,
            'CB-ACCESS-TIMESTAMP': timestamp,
            'CB-ACCESS-KEY': self.api_key,
            'CB-ACCESS-PASSPHRASE': self.passphrase,
            'Content-Type': 'application/json'
        })
        return request

api_url = 'https://api.pro.coinbase.com/'

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
    
def setJsonFile(name, text):
    try:
        with open(SCRIPT_PATH + name, "w+") as f:
            f.write(json.dumps(text))
    except Exception as e:
        print("Failed to write file: " + name + "because of exception: " + str(e))
        raise e
    
def logNormal(message):
    with open(SCRIPT_PATH + "log.log", "a") as f:
        f.write(message + "\n")

def logError(message):
    with open(SCRIPT_PATH + "error.log", "a") as f:
        f.write(message + "\n")


def recordUsdSpent(spent, filled):
    filename = "usd_spent.log"
    prev = { "usd_spent" : 0, "usd_filled" : 0.0 }
    if Path(SCRIPT_PATH + filename).is_file():
        prev = getJsonFile(filename)
    spent = spent + prev["usd_spent"]
    filled = round(filled + prev["usd_filled"], 2)
    final = { "usd_spent" : spent, "usd_filled" : filled }
    setJsonFile(filename, final)
    
def recordPrice(weight, price):
    filename = "prices.log"
    prev = []
    if Path(SCRIPT_PATH + filename).is_file():
        prev = getJsonFile(filename)
    entry = {"weight" : weight, "price" : price}
    prev.append(entry)
    setJsonFile(filename, prev)

def getUsdBalance():
    print("Getting USD balance.")
    r = requests.get(api_url + 'accounts', auth=auth)
    if r.status_code == 200:
        for currency in r.json():
            if currency["currency"] == "USD":
                balance = round(float(currency["balance"]), 2)
                print("USD balance is: " + str(balance))
                return float(currency["balance"])
    else:
        raise Exception("Failed to get USD balance.")

def tryDepositFromBank(amount):
    r = requests.get(api_url + 'payment-methods', auth=auth).json()
    bankId = ""
    for bank in r:
        if settings["bankIdentifier"] in bank["name"]:
            print("Using payment method: " + bank["name"])
            bankId = bank["id"]
            break
    if bankId == "":
        raise Exception("Bank Identifier not found in payment methods")
    
    print("Requesting deposit...")
    sendData = {"amount":round(amount, 2), "currency":"USD", "payment_method_id":bankId}
    r = requests.post(api_url + 'deposits/payment-method', auth=auth, data=json.dumps(sendData))
    
    if r.status_code == 200 and "amount" in r.json():
        print("Successful deposit.")
        logNormal(str(datetime.now()) + ": " + "Successfully deposited $" + str(r.json()["amount"]) + " into Coinbase Pro.")
        return True
    else:
        print("Failed deposit.")
        print(r.text)
        logNormal(str(datetime.now()) + ": " + "Failed deposit: "+ r.text)
        return False

def tryPlaceOrder(sendData):
    return requests.post(api_url + 'orders', auth=auth, data=json.dumps(sendData))

def tryGetFinishedOrder(id):
    r = requests.get(api_url + 'orders/' + id, auth=auth)
    response = r.json()
    tryCount = 1
    while tryCount <= settings["retryOrderCount"]:
        if r.status_code == 200 and "status" in response and response["status"] == "done":
            value = float(response["executed_value"])
            price = round(value / float(response["filled_size"]), 2)
            recordPrice(round(value,2), price)
            break
        elif tryCount+1 <= settings["retryOrderCount"]:
            if "status" in response or ("message" in response and response["message"] == "NotFound"):
                time.sleep(settings["retryOrderWaitSeconds"])
                tryCount+=1
                continue
        logError("Failed to get order " + id + ".\n" + r.text)
        break
        
def placeOrder(amount):
    print("Ordering $" + str(amount) + " of Bitcoin")
    tryCount = 1
    sendData = {"type":"market", "side":"buy", "product_id":"BTC-USD", "funds":amount}
    while tryCount <= settings["retryOrderCount"]:
        r = tryPlaceOrder(sendData)
        response = r.json()
        if r.status_code == 200 and "funds" in response:
            print("Successful order.")
            spentAmountUsd = response["specified_funds"]
            filledAmountUsd = response["funds"]
            logNormal(str(datetime.now()) + ": " + "Successfully bought $" + filledAmountUsd + " of BTC.")
            recordUsdSpent(int(spentAmountUsd), float(filledAmountUsd))
            tryGetFinishedOrder(response["id"])
            return
        elif tryCount+1 <= settings["retryOrderCount"] and r.status_code == 400 and "message" in response and response["message"] == "Insufficient funds":
            print("Order failed on attempt #" + str(tryCount) + ". Trying again in " + str(settings["retryOrderWaitSeconds"]) + " seconds.")
            time.sleep(settings["retryOrderWaitSeconds"])
            tryCount += 1
        else:
            print("Order failed on attempt #" + str(tryCount) + ".")
            print(r.status_code)
            print(r.text)
            logError(str(r.status_code) + ": " + r.text)
            break


# Start
if len(sys.argv) != 2:
    print("Useage: python coinbasepro-dca.py [dollar amount]")
else:
    dollar_amount = int(sys.argv[1])

    try:
        auth_info = getJsonFile("auth.json")
        auth = CoinbaseExchangeAuth(auth_info["key"], auth_info["secret"], auth_info["password"])
        settings = getJsonFile("app.conf.json")

        # Step 1. Get USD Balance
        usd_balance = getUsdBalance()
                
        # Step 2. If USD balance is lower than the purchase amount, top up
        balance_order_diff = dollar_amount - usd_balance
        balance_order_diff = round(balance_order_diff, 2) + 0.01 # add a penny in case of rounding down
        hasEnough = balance_order_diff <= 0
        if not hasEnough:
            if settings["bankDepositAmount"] <= balance_order_diff:
                logNormal(str(datetime.now()) + ": " + "Bank Deposit amount is lower than order amount. Increase this amount if you want to continue.")
            else:
                print("Balance is " + str(balance_order_diff) + " lower than order amount, attempting to top up")
                hasEnough = tryDepositFromBank(settings["bankDepositAmount"])
        
        # Step 3. Order Bitcoin
        if hasEnough:
            placeOrder(dollar_amount)
            
        print("End")

    except Exception as e:
        logError(str(datetime.now()) + ": " + str(e))
        raise e
