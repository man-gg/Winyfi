"""
Test script for UniFi API endpoints (using requests)
Run this after starting unifi_api.py server.
"""
import requests

BASE_URL = "http://127.0.0.1:5001/api/unifi"

def test_devices():
    print("Testing /devices endpoint...")
    resp = requests.get(f"{BASE_URL}/devices")
    print("Status:", resp.status_code)
    print("Response:", resp.json())

def test_clients():
    print("Testing /clients endpoint...")
    resp = requests.get(f"{BASE_URL}/clients")
    print("Status:", resp.status_code)
    print("Response:", resp.json())

def test_mock_toggle(mock=True):
    print(f"Toggling mock mode to {mock}...")
    resp = requests.post(f"{BASE_URL}/mock", json={"mock": mock})
    print("Status:", resp.status_code)
    print("Response:", resp.json())

if __name__ == "__main__":
    test_devices()
    test_clients()
    test_mock_toggle(False)
    test_devices()
    test_clients()
    test_mock_toggle(True)
    test_devices()
    test_clients()
