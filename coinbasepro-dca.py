# dependent on requests package (pip install requests)
# and Path (pip install pathlib)

import json, hmac, hashlib, time, requests, base64
from requests.auth import AuthBase
from pathlib import Path

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

def getJsonFile(name):
    if not Path(name).is_file():
        raise ValueError("Missing " + name)
    try:
        with open(name, "r+") as f:
            return json.loads(f.read())
    except Exception as e:
        print("Failed to get file: " + name + " because of exception: " + str(e))
        raise e
    
def setJsonFile(name, text):
    try:
        with open(name, "w+") as f:
            f.write(json.dumps(text))
    except Exception as e:
        print("Failed to write file: " + name + "because of exception: " + str(e))
    
    
auth_info = getJsonFile("auth.json")
auth = CoinbaseExchangeAuth(auth_info["key"], auth_info["secret"], auth_info["password"])
settings = getJsonFile("app.conf.json")

r = requests.get(api_url + 'accounts', auth=auth)
print(r.json())
