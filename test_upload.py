import requests

# Configuration
BASE_URL = "http://localhost:8000"
USERNAME = "testuser"
PASSWORD = "SecurePass123!"
CSV_FILE = "test_data.csv"

# Step 1: Get JWT Token
print("Getting JWT token...")
response = requests.post(
    f"{BASE_URL}/api/auth/token/",
    json={"username": USERNAME, "password": PASSWORD}
)

if response.status_code != 200:
    print(f"Failed to get token: {response.text}")
    exit(1)

token = response.json()["access"]
print(f"Token received: {token[:50]}...")

# Step 2: Upload File
print(f"\nUploading {CSV_FILE}...")
headers = {"Authorization": f"Bearer {token}"}

with open(CSV_FILE, "rb") as f:
    files = {"file": (CSV_FILE, f, "text/csv")}
    response = requests.post(
        f"{BASE_URL}/api/upload/",
        headers=headers,
        files=files
    )

print(f"Status Code: {response.status_code}")
print(f"Response: {response.json()}")

if response.status_code == 202:
    upload_id = response.json()["upload_id"]
    print(f"\n✓ Upload successful!")
    print(f"Upload ID: {upload_id}")
    
    # Step 3: Check Status
    print(f"\nChecking upload status...")
    status_response = requests.get(
        f"{BASE_URL}/api/upload/{upload_id}/status/",
        headers=headers
    )
    print(f"Status: {status_response.json()}")