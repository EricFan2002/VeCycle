from flask import Flask, request, jsonify
from thor_requests.connect import Connect
from thor_requests.wallet import Wallet
from thor_requests.contract import Contract
import requests

app = Flask(__name__)

# Connect to VeChain Thor testnet
connector = Connect("https://testnet.veblocks.net")

# Your private key (be cautious with this in a real application)
private_key = bytes([
    26, 130, 116, 141, 64, 157, 215, 239,
    232, 51, 163, 227, 63, 178, 87, 108,
    202, 180, 62, 148, 47, 111, 17, 57,
    66, 79, 213, 21, 195, 148, 216, 226
])

# Create wallet from private key
wallet = Wallet.fromPrivateKey(priv=private_key)

@app.route('/check_balance/<address>', methods=['GET'])
def check_balance(address):
    try:
        account = connector.get_account(address)
        vet_balance = float(int(account['balance'], 16)) / 10 ** 18
        print("vet_balance", vet_balance)
        return jsonify({"address": address, "balance": vet_balance})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route('/transfer', methods=['POST'])
def transfer_vet():
    data = request.json
    to_address = data.get('to')
    amount = data.get('amount')  # amount in VET

    if not to_address or not amount:
        return jsonify({"error": "Missing to_address or amount"}), 400

    try:
        amount_wei = int(float(amount) * 10 ** 18)  # Convert VET to WEI
        tx = connector.transfer_vet(wallet, to=to_address, value=amount_wei)
        return jsonify({"transaction_id": tx['id']})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

if __name__ == '__main__':
    app.run(debug=True, port=6666)
