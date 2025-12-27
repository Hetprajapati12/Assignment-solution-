import requests
import traceback

BASE_URL = "http://localhost:8000"
USERNAME = "testuser"
PASSWORD = "SecurePass123!"
CSV_FILE = "test_data.csv"

try:
    # Get token
    print("1. Getting JWT token...")
    response = requests.post(
        f"{BASE_URL}/api/auth/token/",
        json={"username": USERNAME, "password": PASSWORD}
    )
    print(f"   Token Status: {response.status_code}")
    token = response.json()["access"]
    
    # Check file exists
    print(f"\n2. Checking file exists...")
    import os
    print(f"   File exists: {os.path.exists(CSV_FILE)}")
    print(f"   File size: {os.path.getsize(CSV_FILE)} bytes")
    
    # Upload
    print(f"\n3. Uploading file...")
    headers = {"Authorization": f"Bearer {token}"}
    
    with open(CSV_FILE, "rb") as f:
        files = {"file": (CSV_FILE, f, "text/csv")}
        response = requests.post(
            f"{BASE_URL}/api/upload/",
            headers=headers,
            files=files
        )
    
    print(f"   Status: {response.status_code}")
    print(f"   Response: {response.text}")
    
except Exception as e:
    print(f"Error: {e}")
    traceback.print_exc()
