"""Simple test to add a channel"""
import requests
import json

data = {
    'channel_id': 'my-test-channel-1',
    'channel_name': 'My Test Channel',
    'channel_url': 'https://www.youtube.com/@mkbhd',
    'description': 'Test channel',
    'keywords': ['test'],
    'crawl_enabled': True,
    'crawl_frequency': 'manual'
}

print("Sending POST request...")
print(f"Data: {json.dumps(data, indent=2)}")

response = requests.post(
    'http://127.0.0.1:5000/api/channels/',
    json=data,
    headers={'Content-Type': 'application/json'}
)

print(f"\nStatus: {response.status_code}")
print(f"Response: {response.text}")

if response.status_code == 201:
    print("\n✓ SUCCESS!")
    result = response.json()
    print(f"Channel ID: {result['id']}")
    print(f"Reference ID: {result['channel_id']}")
    print(f"Name: {result['channel_name']}")
else:
    print(f"\n✗ FAILED")
