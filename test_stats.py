import requests

BASE_URL = "http://localhost:8000"
USERNAME = "testuser"
PASSWORD = "SecurePass123!"

# Get token
response = requests.post(
    f"{BASE_URL}/api/auth/token/",
    json={"username": USERNAME, "password": PASSWORD}
)
token = response.json()["access"]
headers = {"Authorization": f"Bearer {token}"}

# List all cities
print("=== All Cities ===")
response = requests.get(f"{BASE_URL}/api/cities/", headers=headers)
print(f"Response: {response.json()}")

# Get statistics for first city
print("\n=== City Statistics (CITY_0001) ===")
response = requests.get(
    f"{BASE_URL}/api/cities/CITY_0001/statistics/",
    headers=headers
)
print(f"Response: {response.json()}")

# List uploads
print("\n=== Upload History ===")
response = requests.get(f"{BASE_URL}/api/uploads/", headers=headers)
uploads = response.json()
print(f"Total uploads: {uploads.get('count', 0)}")
if uploads.get('results'):
    for upload in uploads['results']:
        print(f"  - {upload['filename']}: {upload['status']} ({upload['progress_percentage']}%)")
