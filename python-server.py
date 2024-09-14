import os
from flask import Flask, request, jsonify, send_from_directory
import redis
import json
import random
from werkzeug.utils import secure_filename
import threading
import time
import requests
import hashlib
from openai import OpenAI


app = Flask(__name__)
redis_client = redis.Redis(host='localhost', port=6379, db=0)

client = OpenAI(
    # This is the default and can be omitted
    api_key=api_key,
)


UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
APP_ID = "0x767308b4c9815c9fd756ad287379b26fa1af9c984490f969aca032da9de21a41"


UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER


# Initialize users in Redis if they don't exist
def init_users():
    users = {
        1: {"password": "pass1", "userName": "user1", "chain_address": "0x762c5FF246dCc2A31a319bcC754E0d3874F8bD77"},
        2: {"password": "pass2", "userName": "user2", "chain_address": "0xf077b491b355E64048cE21E3A6Fc4751eEeA77fa"},
        3: {"password": "pass3", "userName": "user3", "chain_address": "0x762c5FF246dCc2A31a319bcC754E0d3874F8bD77"},
        4: {"password": "pass4", "userName": "user4", "chain_address": "0xf077b491b355E64048cE21E3A6Fc4751eEeA77fa"},
        5: {"password": "pass5", "userName": "user5", "chain_address": "0x762c5FF246dCc2A31a319bcC754E0d3874F8bD77"},
        6: {"password": "pass6", "userName": "user6", "chain_address": "0xf077b491b355E64048cE21E3A6Fc4751eEeA77fa"}
    }
    for user_id, user_data in users.items():
        if not redis_client.exists(f'user:{user_id}'):
            redis_client.hmset(f'user:{user_id}', {
                'password': user_data['password'],
                'userName': user_data['userName'],
                'chain_address': user_data['chain_address']
            })

@app.route('/login', methods=['GET'])
def login():
    username = request.args.get('user')
    password = request.args.get('password')
    
    for user_id in range(1, 100):
        user_data = redis_client.hgetall(f'user:{user_id}')
        if not user_data:
            break
        if user_data[b'userName'].decode() == username and user_data[b'password'].decode() == password:
            return jsonify({"userID": user_id, "chain_address": user_data[b'chain_address'].decode()})
    
    return jsonify({"error": "Invalid credentials"}), 401


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/upload_photo', methods=['POST'])
def upload_photo():
    if 'photo' not in request.files:
        return jsonify({'success': False, 'error': 'No file part'})
    
    file = request.files['photo']
    
    if file.filename == '':
        return jsonify({'success': False, 'error': 'No selected file'})
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        return jsonify({'success': True, 'filename': f'@/{filepath}'})
    
    return jsonify({'success': False, 'error': 'File type not allowed'})


@app.route('/list', methods=['POST'])
def list_item():
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
    
    if file:
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
    
    item = {
        "name": request.form.get('name'),
        "userID": int(request.form.get('userID')),
        "description": request.form.get('description'),
        "price": float(request.form.get('price')),
        "terms": json.dumps(json.loads(request.form.get('terms'))),
        "file": file_path,
        "itemStatus": 0,  # Initially set to Unbought
        "buyerID": -1  # Initially set to -1
    }
    
    item_id = redis_client.incr('next_item_id')
    redis_client.hmset(f'item:{item_id}', item)
    redis_client.sadd('items', item_id)
    
    return jsonify({"itemID": item_id})

@app.route('/listAll', methods=['GET'])
def list_all():
    item_ids = redis_client.smembers('items')
    items = []
    for item_id in item_ids:
        item = redis_client.hgetall(f'item:{item_id.decode()}')
        item = {k.decode(): v.decode() for k, v in item.items()}
        if 'userID' in item:
            item['ID'] = int(item_id)
            item['userID'] = int(item['userID'])
            item['price'] = float(item['price'])
            item['terms'] = json.loads(item['terms'])
            item['itemStatus'] = int(item['itemStatus'])
            if "buyerID" in item:
                item['buyerID'] = int(item['buyerID'])
            user_data = redis_client.hgetall(f'user:{item["userID"]}')
            item['userName'] = user_data[b'userName'].decode()
            items.append(item)
    return jsonify(items)

@app.route('/buy', methods=['GET'])
def buy():
    item_id = int(request.args.get('id'))
    buyer_id = int(request.args.get('userID'))
    
    # Change the item status to "Pending for Payment" and set the buyer ID
    redis_client.hmset(f'item:{item_id}', {
        'itemStatus': 1,
        'buyerID': buyer_id
    })
    
    # Get the seller's chain address
    item_data = redis_client.hgetall(f'item:{item_id}')
    seller_id = int(item_data[b'userID'].decode())
    seller_data = redis_client.hgetall(f'user:{seller_id}')
    seller_address = seller_data[b'chain_address'].decode()
    
    return jsonify({"status": "OK", "seller_address": seller_address})

@app.route('/checkBuy', methods=['GET'])
def check_buy():
    item_id = request.args.get('id')
    item_status = redis_client.hget(f'item:{item_id}', 'itemStatus')
    return jsonify({"itemStatus": int(item_status)})

def all_judges_decided(item_id):
    dispute_key = f'dispute:{item_id}'
    judges_conversation = json.loads(redis_client.hget(dispute_key, 'JUDGES_CONVERSATION'))
    
    for term_verdicts in judges_conversation:
        for judge_verdict in term_verdicts.values():
            if judge_verdict['verdict'] == 'PENDING':
                return False
    return True

def get_gpt_verdict(item_id):
    dispute_key = f'dispute:{item_id}'
    dispute_info = redis_client.hgetall(dispute_key)
    dispute_info = {k.decode(): v.decode() for k, v in dispute_info.items()}
    
    item_data = redis_client.hgetall(f'item:{item_id}')
    item_data = {k.decode(): v.decode() for k, v in item_data.items()}
    
    seller_data = redis_client.hgetall(f'user:{dispute_info["seller_id"]}')
    seller_data = {k.decode(): v.decode() for k, v in seller_data.items()}
    
    buyer_data = redis_client.hgetall(f'user:{dispute_info["buyer_id"]}')
    buyer_data = {k.decode(): v.decode() for k, v in buyer_data.items()}
    
    chat_history = json.loads(dispute_info['BUYER_SELLER_CONVERSATION'])
    judges_conversation = json.loads(dispute_info['JUDGES_CONVERSATION'])
    
    prompt = f"""
    Merchant Information:
    Seller: {seller_data['userName']} (ID: {dispute_info['seller_id']})
    Buyer: {buyer_data['userName']} (ID: {dispute_info['buyer_id']})
    Item: {item_data['name']} (Price: {item_data['price']})
    
    Chat History:
    {json.dumps(chat_history, indent=2)}
    
    Judge Verdicts:
    {json.dumps(judges_conversation, indent=2)}
    
    Based on the information above, please provide a final verdict for each clause in the format [True, False, ...]. True means the clause was fulfilled, False means it was not. Also, provide a brief explanation for each decision.
    Do not output any other information then the verdict string, which is a python parsable value.
    """

    stream = client.chat.completions.create(
        messages=[
                {"role": "system", "content": "You are an AI arbitrator tasked with making final decisions in e-commerce disputes."},
                {"role": "user", "content": prompt}
            ],
        model="gpt-4-turbo",
        stream=True,
    )

    result = ""

    for chunk in stream:
        if chunk.choices[0].delta.content is not None:
            result += chunk.choices[0].delta.content

    return result

@app.route('/checkMyBuy', methods=['GET'])
def check_my_buy():
    user_id = int(request.args.get('userID'))
    item_ids = redis_client.smembers('items')
    bought_items = []
    for item_id in item_ids:
        item = redis_client.hgetall(f'item:{item_id.decode()}')
        item = {k.decode(): v.decode() for k, v in item.items()}
        if 'userID' in item and 'buyerID' in item and int(item['buyerID']) == user_id:
            item['ID'] = int(item_id)
            item['userID'] = int(item['userID'])
            item['buyerID'] = int(item['buyerID'])
            item['price'] = float(item['price'])
            item['terms'] = json.loads(item['terms'])
            item['itemStatus'] = int(item['itemStatus'])
            user_data = redis_client.hgetall(f'user:{item["userID"]}')
            item['userName'] = user_data[b'userName'].decode()
            bought_items.append(item)
    return jsonify(bought_items)

@app.route('/itemDetail', methods=['GET'])
def item_detail():
    item_id = request.args.get('id')
    item = redis_client.hgetall(f'item:{item_id}')
    if not item:
        return jsonify({"error": "Item not found"}), 404
    item = {k.decode(): v.decode() for k, v in item.items()}
    if 'userID' in item:
        item['ID'] = int(item_id)
        item['userID'] = int(item['userID'])
        item['buyerID'] = int(item['buyerID'])
        item['price'] = float(item['price'])
        item['terms'] = json.loads(item['terms'])
        item['itemStatus'] = int(item['itemStatus'])
        user_data = redis_client.hgetall(f'user:{item["userID"]}')
        item['userName'] = user_data[b'userName'].decode()
        if item['buyerID'] != -1:
            buyer_data = redis_client.hgetall(f'user:{item["buyerID"]}')
            item['buyerName'] = buyer_data[b'userName'].decode()
            item['buyerAddress'] = buyer_data[b'chain_address'].decode()
    return jsonify(item)

@app.route('/listMySold', methods=['GET'])
def list_my_sold():
    user_id = int(request.args.get('userID'))
    
    item_ids = redis_client.smembers('items')
    sold_items = []
    
    for item_id in item_ids:
        item = redis_client.hgetall(f'item:{item_id.decode()}')
        item = {k.decode(): v.decode() for k, v in item.items()}
        
        if 'userID' in item and 'buyerID' in item and int(item['userID']) == user_id and int(item['buyerID']) != -1:
            item['ID'] = int(item_id)
            item['userID'] = int(item['userID'])
            item['buyerID'] = int(item['buyerID'])
            item['price'] = float(item['price'])
            item['terms'] = json.loads(item['terms'])
            item['itemStatus'] = int(item['itemStatus'])
            
            buyer_data = redis_client.hgetall(f'user:{item["buyerID"]}')
            item['buyerName'] = buyer_data[b'userName'].decode()
            item['buyerAddress'] = buyer_data[b'chain_address'].decode()
            
            sold_items.append(item)
    
    return jsonify(sold_items)

@app.route('/uploads/<filename>')
def serve_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/public/<filename>')
def serve_public_file(filename):
    return send_from_directory("./public", filename)

@app.route('/updateItemStatus', methods=['POST'])
def update_item_status():
    item_id = int(request.form.get('id'))
    new_status = int(request.form.get('status'))
    
    if new_status not in range(5):  # Validate the new status
        return jsonify({"error": "Invalid status"}), 400
    
    redis_client.hset(f'item:{item_id}', 'itemStatus', new_status)
    return jsonify({"status": "OK"})

def get_available_funds():
    try:
        address = "0x762c5ff246dcc2a31a319bcc754e0d3874f8bd77"
        response = requests.get(f'http://localhost:6666/check_balance/{address}')
        response.raise_for_status()
        funds_data = float(response.json()["balance"])
        return funds_data
    except requests.RequestException as e:
        print(f"Error fetching available funds: {str(e)}")
        return None

# def get_available_funds():
#     try:
#         response = requests.get(f'http://localhost:3000/available-funds/{APP_ID}')
#         response.raise_for_status()
#         funds_data = int(response.json()["availableB3TR"])
#         return funds_data
#     except requests.RequestException as e:
#         print(f"Error fetching available funds: {str(e)}")
#         return None

received_amounts = []

def mark_item_as_sold(new_amount=None):
    global received_amounts
    if new_amount is not None:
        received_amounts.append(new_amount)
    
    pending_items = []
    # print(redis_client.smembers('items'))
    for item_id in redis_client.smembers('items'):
        item_id = item_id.decode()
        item_status = redis_client.hget(f'item:{item_id}', 'itemStatus')
        if item_status is not None:
            item_status = int(item_status)
            if item_status == 1:  # Pending status
                # print("Pending", item_id)
                item_price = float(redis_client.hget(f'item:{item_id}', 'price'))
                for amount in received_amounts:
                    if abs(item_price - amount) < 1:
                        pending_items.append((item_id, item_price, amount))
                    # print(item_price,end=" | ")
        # else:
        #     print("Not Found Key:", item_id)
    
    for item_id, item_price, matched_amount in pending_items:
        redis_client.hset(f'item:{item_id}', 'itemStatus', 2)  # Mark as sold
        print(f"Marked item {item_id} as sold for {item_price}")
        received_amounts.remove(matched_amount)
    
    if new_amount is not None:
        if pending_items:
            print(f"Processed {len(pending_items)} items. Remaining unmatched amounts: {received_amounts}")
        else:
            print(f"No matching items found. Current unmatched amounts: {received_amounts}")

# Modify your scheduled_scan function to pass the difference to mark_item_as_sold
def scheduled_scan():
    global received_amounts
    previous_money = 0
    while True:
        try:
            current_money = get_available_funds()
            if current_money and current_money != previous_money:
                diff_amount = current_money - previous_money
                print(f"Available funds changed to {current_money}, Diff is {diff_amount}")
                mark_item_as_sold(diff_amount)
                previous_money = current_money
            
            redis_client.set('latest_funds_amount', current_money or '')
        
        except Exception as e:
            print(f"Error in scheduled scan: {str(e)}")

        mark_item_as_sold()
        
        time.sleep(2)  # Wait for 2 seconds before the next scan
        # if len(received_amounts) != 0:
            # print("received_amounts: ", received_amounts)

@app.route('/sold_confirm', methods=['POST'])
def sold_confirm():
    item_id = int(request.json.get('itemID'))
    
    # Check if the item status is 2 (sold)
    item_status = int(redis_client.hget(f'item:{item_id}', 'itemStatus'))
    if item_status != 2:
        return jsonify({"error": "Item is not in sold status"}), 400
    
    # Update item status to 3 (successful)
    redis_client.hset(f'item:{item_id}', 'itemStatus', 3)
    
    # Get item details
    item_data = redis_client.hgetall(f'item:{item_id}')
    seller_id = int(item_data[b'userID'].decode())
    price = float(item_data[b'price'].decode())
    
    # Get seller's chain address
    seller_data = redis_client.hgetall(f'user:{seller_id}')
    seller_address = seller_data[b'chain_address'].decode()
    
    # Make a transaction to the seller's address
    try:
        transaction_data = {
            "to": seller_address,
            "amount": str(price)
        }
        response = requests.post('http://localhost:6666/transfer', json=transaction_data)
        response.raise_for_status()
        transaction_id = response.json()["transaction_id"]
        return jsonify({"status": "success", "message": f"Item confirmed as sold and payment sent. Transaction ID: {transaction_id}"})
    except requests.RequestException as e:
        return jsonify({"status": "error", "message": f"Failed to send payment: {str(e)}"}), 500

# # New API endpoint for confirming sold items
# @app.route('/sold_confirm', methods=['POST'])
# def sold_confirm():
#     item_id = int(request.json.get('itemID'))
    
#     # Check if the item status is 2 (sold)
#     item_status = int(redis_client.hget(f'item:{item_id}', 'itemStatus'))
#     if item_status != 2:
#         return jsonify({"error": "Item is not in sold status"}), 400
    
#     # Update item status to 3 (successful)
#     redis_client.hset(f'item:{item_id}', 'itemStatus', 3)
    
#     # Get item details
#     item_data = redis_client.hgetall(f'item:{item_id}')
#     seller_id = int(item_data[b'userID'].decode())
#     price = float(item_data[b'price'].decode())
    
#     # Get seller's chain address
#     seller_data = redis_client.hgetall(f'user:{seller_id}')
#     seller_address = seller_data[b'chain_address'].decode()
    
#     # Call API to distribute reward
#     reward_data = {
#         seller_address: str(price)  # Assuming the reward is the full price of the item
#     }
    
#     try:
#         response = requests.post('http://localhost:3000/distribute-rewards', json=reward_data)
#         response.raise_for_status()
#         return jsonify({"status": "success", "message": "Item confirmed as sold and reward distributed"})
#     except requests.RequestException as e:
#         return jsonify({"status": "error", "message": f"Failed to distribute reward: {str(e)}"}), 500
    
@app.route('/QRcode/<filename>')
def serve_qrcode(filename):
    return send_from_directory('QRcode', filename)

@app.route('/argument', methods=['GET'])
def dispute():
    item_id = int(request.args.get(('itemID')))
    
    # Check if the item status is 2 (sold)
    item_status = int(redis_client.hget(f'item:{item_id}', 'itemStatus'))
    if item_status != 2:
        return jsonify({"error": "Item is not in sold status"}), 400
    
    # Get buyer and seller IDs
    item_data = redis_client.hgetall(f'item:{item_id}')
    seller_id = int(item_data[b'userID'].decode())
    buyer_id = int(item_data[b'buyerID'].decode())
    path = item_data[b'file'].decode()
    
    # Get all user IDs
    all_user_ids = [int(user_id.decode().split(':')[1]) for user_id in redis_client.keys('user:*')]
    
    # Remove buyer and seller from the list
    eligible_users = [uid for uid in all_user_ids if uid not in [buyer_id, seller_id]]
    
    # Randomly select 4 users
    selected_users = random.sample(eligible_users, min(3, len(eligible_users)))
    
    # Store selected users for the dispute in Redis
    dispute_key = f'dispute:{item_id}'
    for i, user_id in enumerate(selected_users, start=1):
        redis_client.hset(dispute_key, f'judge_id_{i}', user_id)
        redis_client.hset(dispute_key, f'judge_id_{i}:response', 'pending')
    
    # Store additional dispute information
    redis_client.hset(dispute_key, 'item_id', item_id)
    redis_client.hset(dispute_key, 'seller_id', seller_id)
    redis_client.hset(dispute_key, 'buyer_id', buyer_id)
    redis_client.hset(dispute_key, 'status', '0')  
    redis_client.hset(dispute_key, 'created_at', int(time.time()))

    system_messages1 = {
        "Name": "SYSTEM",
        "MSG": f"Dispute initiated for item {item_id}. <br>Buyer ID: {buyer_id}, Seller ID: {seller_id}. <br>Four judges have been randomly selected to oversee this dispute."
    }
    system_messages2 = {
        "Name": "SYSTEM",
        "MSG": f"Uploaded a photo: @/{path}"
    }
    messages = []
    messages.append(system_messages1)
    messages.append(system_messages2)
    
    # Initialize BUYER_SELLER_CONVERSATION
    redis_client.hset(dispute_key, 'BUYER_SELLER_CONVERSATION', json.dumps(messages))
    
    # Initialize JUDGES_CONVERSATION based on the item's terms
    terms = json.loads(item_data[b'terms'].decode())
    judges_conversation = []
    for i, term in enumerate(terms):
        judge_verdicts = {}
        for judge_id in selected_users:
            judge_verdicts[str(judge_id)] = {
                "termIndex": i,
                "message": "",
                "verdict": "PENDING"
            }
        judges_conversation.append(judge_verdicts)
    redis_client.hset(dispute_key, 'JUDGES_CONVERSATION', json.dumps(judges_conversation))

    redis_client.hset(f'item:{item_id}', 'itemStatus', 4)

    redirect_url = f"http://45.32.100.36:5000/public/conflict.html?itemID={item_id}"
    
    vals = {
        "status": "success",
        "message": "Dispute initiated",
        "selected_users": selected_users,
        "dispute_key": dispute_key
    }

    return jsonify({
        "result": vals,
        "redirect": redirect_url
    })

@app.route('/addBuyerSellerConversation', methods=['POST'])
def add_buyer_seller_conversation():
    item_id = request.json.get('itemID')
    name = request.json.get('name')
    msg = request.json.get('msg')
    
    dispute_key = f'dispute:{item_id}'
    
    if not redis_client.exists(dispute_key):
        return jsonify({"error": "Dispute not found"}), 404
    
    conversation = json.loads(redis_client.hget(dispute_key, 'BUYER_SELLER_CONVERSATION'))
    conversation.append({"Name": name, "MSG": msg})
    redis_client.hset(dispute_key, 'BUYER_SELLER_CONVERSATION', json.dumps(conversation))
    
    return jsonify({"status": "success", "message": "Conversation updated"})

@app.route('/getDisputeInfo', methods=['GET'])
def get_dispute_info():
    item_id = request.args.get('itemID')
    dispute_key = f'dispute:{item_id}'
    
    if not redis_client.exists(dispute_key):
        return jsonify({"error": "Dispute not found"}), 404
    
    dispute_info = redis_client.hgetall(dispute_key)
    dispute_info = {k.decode(): v.decode() for k, v in dispute_info.items()}
    
    # Parse JSON strings back into Python objects
    dispute_info['BUYER_SELLER_CONVERSATION'] = json.loads(dispute_info['BUYER_SELLER_CONVERSATION'])
    dispute_info['JUDGES_CONVERSATION'] = json.loads(dispute_info['JUDGES_CONVERSATION'])
    
    # Fetch judge IDs
    judge_ids = []
    for i in range(1, 5):
        judge_id = dispute_info.get(f'judge_id_{i}')
        if judge_id:
            judge_ids.append(int(i))
    dispute_info['judge_ids'] = judge_ids
    
    # Add all_judges_decided information
    dispute_info['all_judges_decided'] = all_judges_decided(item_id)
    
    return jsonify(dispute_info)

def distribute_rewards(item_id):
    dispute_key = f'dispute:{item_id}'
    dispute_info = redis_client.hgetall(dispute_key)
    dispute_info = {k.decode(): v.decode() for k, v in dispute_info.items()}

    judge_ids = [dispute_info[f'judge_id_{i}'] for i in range(1, 5) if f'judge_id_{i}' in dispute_info]

    for judge_id in judge_ids:
        judge_data = redis_client.hgetall(f'user:{judge_id}')
        judge_address = judge_data[b'chain_address'].decode()

        reward_data = {
            judge_address: str(1)  # 1 coin reward for each judge
        }

        try:
            response = requests.post('http://localhost:3000/distribute-rewards', json=reward_data)
            response.raise_for_status()
            print(f"Reward distributed to judge {judge_id}")
        except requests.RequestException as e:
            print(f"Failed to distribute reward to judge {judge_id}: {str(e)}")

def transfer_money_to_user(item_id):
    item_data = redis_client.hgetall(f'item:{item_id}')
    seller_id = item_data[b'userID'].decode()
    price = float(item_data[b'price'].decode())

    seller_data = redis_client.hgetall(f'user:{seller_id}')
    seller_address = seller_data[b'chain_address'].decode()

    try:
        transaction_data = {
            "to": seller_address,
            "amount": str(price)
        }
        print("Send:", transaction_data)
        response = requests.post('http://localhost:6666/transfer', json=transaction_data)
        response.raise_for_status()
        transaction_id = response.json()["transaction_id"]
        print(f"Money transferred to seller. Transaction ID: {transaction_id}")
        return transaction_id
    except requests.RequestException as e:
        print(f"Failed to transfer money to seller: {str(e)}")
        return None 


@app.route('/addNewJudgeVerdict', methods=['POST'])
def add_new_judge_verdict():
    item_id = request.json.get('itemID')
    user_id = request.json.get('userID')
    term_index = int(request.json.get('termIndex'))
    verdict = request.json.get('verdict')
    
    dispute_key = f'dispute:{item_id}'
    
    if not redis_client.exists(dispute_key):
        return jsonify({"error": "Dispute not found"}), 404
    
    # Check if the dispute has already ended
    if redis_client.hget(dispute_key, 'status') == '1':
        return jsonify({"error": "Dispute has already ended"}), 400
    
    # Check if the user is a judge for this dispute
    user_found = False
    for i in range(1, 5):
        if int(redis_client.hget(dispute_key, f'judge_id_{i}') or 0) == user_id:
            user_found = True
            break
    
    if not user_found:
        return jsonify({"error": "User not authorized for this dispute"}), 403
    
    judges_conversation = json.loads(redis_client.hget(dispute_key, 'JUDGES_CONVERSATION'))
    if 0 <= term_index < len(judges_conversation):
        judges_conversation[term_index][str(user_id)]["verdict"] = verdict
        redis_client.hset(dispute_key, 'JUDGES_CONVERSATION', json.dumps(judges_conversation))
        
        # Check if all judges have decided
        if all_judges_decided(item_id):
            gpt_verdict = get_gpt_verdict(item_id)
            redis_client.hset(dispute_key, 'GPT_VERDICT', gpt_verdict)
            
            # Add GPT verdict as SYSTEM response
            buyer_seller_conversation = json.loads(redis_client.hget(dispute_key, 'BUYER_SELLER_CONVERSATION'))
            buyer_seller_conversation.append({
                "Name": "SYSTEM",
                "MSG": f"All judges have made their decisions. GPT's final verdict: {gpt_verdict}"
            })
            redis_client.hset(dispute_key, 'BUYER_SELLER_CONVERSATION', json.dumps(buyer_seller_conversation))
            
            # Update dispute status to ended
            redis_client.hset(dispute_key, 'status', '1')
            
            # Distribute rewards to judges
            distribute_rewards(item_id)

            result = transfer_money_to_user(item_id)
            
            # Transfer money to the seller
            if result is not None:
                buyer_seller_conversation.append({
                    "Name": "SYSTEM",
                    "MSG": f"The dispute has been resolved. The payment has been transferred to the seller. Transaction ID: {result}"
                })
            else:
                buyer_seller_conversation.append({
                    "Name": "SYSTEM",
                    "MSG": "The dispute has been resolved, but there was an issue transferring the payment to the seller. Please contact support."
                })
            redis_client.hset(dispute_key, 'BUYER_SELLER_CONVERSATION', json.dumps(buyer_seller_conversation))
            
            print(f"GPT Verdict for item {item_id}:")
            print(gpt_verdict)
        
        return jsonify({"status": "success", "message": "Judge verdict recorded", "all_judges_decided": all_judges_decided(item_id)})
    else:
        return jsonify({"error": "Invalid term index"}), 400

@app.route('/addNewJudgeMessage', methods=['POST'])
def add_new_judge_message():
    item_id = request.json.get('itemID')
    user_id = request.json.get('userID')
    term_index = int(request.json.get('termIndex'))
    msg = request.json.get('msg')
    
    dispute_key = f'dispute:{item_id}'
    
    if not redis_client.exists(dispute_key):
        return jsonify({"error": "Dispute not found"}), 404
    
    # Check if the user is a judge for this dispute
    user_found = False
    for i in range(1, 5):
        if int(redis_client.hget(dispute_key, f'judge_id_{i}') or 0) == user_id:
            user_found = True
            break
    
    if not user_found:
        return jsonify({"error": "User not authorized for this dispute"}), 403
    
    judges_conversation = json.loads(redis_client.hget(dispute_key, 'JUDGES_CONVERSATION'))
    if 0 <= term_index < len(judges_conversation):
        judges_conversation[term_index][str(user_id)]["message"] = msg
        redis_client.hset(dispute_key, 'JUDGES_CONVERSATION', json.dumps(judges_conversation))
        return jsonify({"status": "success", "message": "Judge message added"})
    else:
        return jsonify({"error": "Invalid term index"}), 400
    
@app.route('/myConflicts', methods=['GET'])
def my_conflicts():
    user_id = int(request.args.get('userID'))
    
    all_disputes = redis_client.keys('dispute:*')
    user_conflicts = []

    for dispute_key in all_disputes:
        dispute_data = redis_client.hgetall(dispute_key)
        dispute_data = {k.decode(): v.decode() for k, v in dispute_data.items()}
        
        item_id = int(dispute_data['item_id'])
        seller_id = int(dispute_data['seller_id'])
        buyer_id = int(dispute_data['buyer_id'])
        
        user_role = None
        if user_id == seller_id:
            user_role = 'seller'
        elif user_id == buyer_id:
            user_role = 'buyer'
        else:
            for i in range(1, 5):
                judge_id_key = f'judge_id_{i}'
                if judge_id_key in dispute_data and int(dispute_data[judge_id_key]) == user_id:
                    user_role = 'judge'
                    break
        
        if user_role:
            item_data = redis_client.hgetall(f'item:{item_id}')
            item_data = {k.decode(): v.decode() for k, v in item_data.items()}
            
            conflict_info = {
                'itemID': item_id,
                'itemName': item_data['name'],
                'userRole': user_role,
                'disputeStatus': '0' if dispute_data['status'] == '0' else '1',
                'createdAt': int(dispute_data['created_at']),
                'all_judges_decided': all_judges_decided(item_id)
            }
            user_conflicts.append(conflict_info)
    
    return jsonify(user_conflicts)

if __name__ == '__main__':
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)
    init_users()  # Initialize users in Redis
    
    # Start the scheduled scan in a separate thread
    scan_thread = threading.Thread(target=scheduled_scan, daemon=True)
    scan_thread.start()
    
    app.run(debug=True, host="0.0.0.0")
