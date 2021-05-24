# dependent on requests package (pip install requests)
# and Path (pip install pathlib)

import json, hmac, hashlib, time, requests, base64, math, os
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
        with open(SCRIPT_PATH + name, "r+") as f:
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
        f.write(message)

def logError(message):
    with open(SCRIPT_PATH + "error.log", "a") as f:
        f.write(message)


def getUsdBalance():
    print("Getting USD balance.")
    r = requests.get(api_url + 'accounts', auth=auth)
    if(r.status_code == 200):
        for currency in r.json():
            if(currency["currency"] == "USD"):
                balance = round(float(currency["balance"]), 2)
                print("USD balance is: " + str(balance))
                return float(currency["balance"])
    else:
        raise Exception("Failed to get USD balance.")

def depositFromBank(amount):
    r = requests.get(api_url + 'payment-methods', auth=auth).json()
    bankId = ""
    for bank in r:
        if(settings["bankIdentifier"] in bank["name"]):
            print("Using payment method: " + bank["name"])
            bankId = bank["id"]
            break
    if(bankId == ""):
        raise Exception("Bank Identifier not found in payment methods")
    
    print("Requesting deposit...")
    sendData = {"amount":amount, "currency":"USD", "payment_method_id":bankId}
    r = requests.post(api_url + 'deposits/payment-method', auth=auth, data=json.dumps(sendData))
    
    if(r.status_code == 200 and "payout_at" in r.json()):
        print("Successful deposit.")
        logNormal(str(datetime.now()) + ": " + "Successfully deposited $" + str(balance_orderx2_diff) + " into Coinbase Pro." + "\n")
    else:
        print("Failed deposit.")
        print(r.text)
        logNormal(str(datetime.now()) + ": " + "Failed deposit: "+ r.text + "\n")
        
def placeOrder(amount):
    print("Ordering Bitcoin")
    sendData = {"type":"market", "side":"buy", "product_id":"BTC-USD", "funds":amount}
    r = requests.post(api_url + 'orders', auth=auth, data=json.dumps(sendData))
    
    if(r.status_code == 200 and "status" in r.json() and r.json()["status"] == "pending"):
        print("Successful order.")
        logNormal(str(datetime.now()) + ": " + "Successfully bought $" + str(settings["orderInDollars"]) + " worth of BTC." + "\n")
    else:
        print("Order failed.")
        print(r.text)
        logNormal(str(datetime.now()) + ": " + "Failed order: "+ r.text + "\n")


# Start
try:
    auth_info = getJsonFile("auth.json")
    auth = CoinbaseExchangeAuth(auth_info["key"], auth_info["secret"], auth_info["password"])
    settings = getJsonFile("app.conf.json")

    # Step 1. Get USD Balance
    usd_balance = getUsdBalance()
            
    # Step 2. If USD balance is lower than the purchase amount, top up
    balance_order_diff = settings["orderInDollars"] - usd_balance
    balance_order_diff = round(balance_order_diff, 2) + 0.01 # add a penny in case of rounding down
    if(balance_order_diff > 0):
        print("Balance is " + str(balance_order_diff) + " lower than order amount, attempting to top up")
        depositFromBank(balance_order_diff)
    
    # Step 3. Order Bitcoin
    placeOrder(settings["orderInDollars"])
        
    print("End")

except Exception as e:
    logError(str(datetime.now()) + ": " + str(e)+"\n")
    raise e
