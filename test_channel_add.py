"""
Test script to verify channel addition works correctly
"""
import requests
import json

BASE_URL = "http://127.0.0.1:5000"

def test_add_channel():
    """Test adding a channel with user-defined reference ID"""

    print("Testing Channel Addition")
    print("=" * 60)

    # Test data
    channel_data = {
        "channel_id": "test-mkbhd",
        "youtube_channel_id": None,
        "channel_name": "MKBHD Test",
        "channel_url": "https://www.youtube.com/@mkbhd",
        "description": "Tech reviews and videos",
        "keywords": ["tech", "review", "smartphone"],
        "crawl_enabled": True,
        "crawl_frequency": "manual"
    }

    print("\nTest Data:")
    print(json.dumps(channel_data, indent=2))

    print("\nSending POST request to /api/channels...")

    try:
        response = requests.post(
            f"{BASE_URL}/api/channels",
            json=channel_data,
            headers={"Content-Type": "application/json"}
        )

        print(f"\nResponse Status: {response.status_code}")
        print(f"Response Headers: {dict(response.headers)}")

        if response.status_code == 201:
            print("\n✓ SUCCESS - Channel added!")
            result = response.json()
            print("\nChannel Details:")
            print(json.dumps(result, indent=2, default=str))
            return True
        elif response.status_code == 400:
            print("\n✗ ERROR 400 - Bad Request")
            print(f"Detail: {response.json()}")
            return False
        elif response.status_code == 404:
            print("\n✗ ERROR 404 - Not Found")
            print(f"Detail: {response.json()}")
            return False
        else:
            print(f"\n✗ ERROR {response.status_code}")
            print(f"Response: {response.text}")
            return False

    except requests.exceptions.ConnectionError:
        print("\n✗ ERROR - Could not connect to server")
        print("Make sure the server is running at http://127.0.0.1:5000")
        return False
    except Exception as e:
        print(f"\n✗ ERROR - {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_add_channel()
    exit(0 if success else 1)
