import requests
import json
import os

# Server URL
BASE_URL = "http://localhost:5000"

def test_server():
    print("Testing Selling/Buying Server")

    # Test login
    print("\n1. Testing login")
    login_response = requests.get(f"{BASE_URL}/login", params={"user": "user1", "password": "pass1"})
    print(f"Login response: {login_response.json()}")
    user_id = login_response.json()['userID']

    # Test listing an item
    print("\n2. Testing item listing")
    test_image_path = "test.jpg"
    if not os.path.exists(test_image_path):
        print(f"Warning: {test_image_path} does not exist. Creating a dummy file.")
        with open(test_image_path, "wb") as f:
            f.write(b"dummy image content")

    with open(test_image_path, "rb") as image_file:
        files = {"file": ("test.jpg", image_file, "image/jpeg")}
        data = {
            "name": "Test Item",
            "userID": user_id,
            "description": "This is a test item",
            "price": 100,
            "terms": json.dumps([{"termName": "condition", "termConditions": "Like new", "termCompensation": 0.1}])
        }
        list_response = requests.post(f"{BASE_URL}/list", files=files, data=data)
    print(f"List item response: {list_response.json()}")
    item_id = list_response.json()['itemID']

    # Test listing all items
    print("\n3. Testing list all items")
    list_all_response = requests.get(f"{BASE_URL}/listAll")
    print(f"List all items response: {json.dumps(list_all_response.json(), indent=2)}")

    # Test buying an item
    print("\n4. Testing buy item")
    buy_response = requests.get(f"{BASE_URL}/buy", params={"id": item_id, "userID": user_id})
    print(f"Buy item response: {buy_response.json()}")

    # Test checking buy status
    print("\n5. Testing check buy status")
    check_buy_response = requests.get(f"{BASE_URL}/checkBuy", params={"id": item_id})
    print(f"Check buy status response: {check_buy_response.json()}")

    # Test checking user's bought items
    print("\n6. Testing check my buy")
    check_my_buy_response = requests.get(f"{BASE_URL}/checkMyBuy", params={"userID": user_id})
    print(f"Check my buy response: {json.dumps(check_my_buy_response.json(), indent=2)}")

    # Test updating item status
    print("\n7. Testing update item status")
    update_status_response = requests.post(f"{BASE_URL}/updateItemStatus", data={"id": item_id, "status": 2})
    print(f"Update item status response: {update_status_response.json()}")

    # Check the updated status
    print("\n8. Checking updated status")
    check_buy_response = requests.get(f"{BASE_URL}/checkBuy", params={"id": item_id})
    print(f"Updated status: {check_buy_response.json()}")

    print("\nTest completed!")

if __name__ == "__main__":
    test_server()