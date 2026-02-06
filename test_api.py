"""
Test script to verify YouTube Crawler functionality
"""
import requests
import json

BASE_URL = "http://localhost:8080"

def test_health():
    """Test health endpoint"""
    response = requests.get(f"{BASE_URL}/health")
    print(f"✓ Health check: {response.json()}")
    return response.status_code == 200

def test_dashboard_stats():
    """Test dashboard stats"""
    response = requests.get(f"{BASE_URL}/api/dashboard/stats")
    print(f"✓ Dashboard stats: {response.json()}")
    return response.status_code == 200

def test_list_channels():
    """Test listing channels"""
    response = requests.get(f"{BASE_URL}/api/channels")
    data = response.json()
    print(f"✓ Channels: Found {len(data)} channels")
    return response.status_code == 200

def test_add_channel():
    """Test adding a channel"""
    channel_data = {
        "channel_id": "UCBJycsmduvYEL83R_U4JriQ",  # Example: Marques Brownlee
        "channel_name": "Marques Brownlee",
        "channel_url": "https://www.youtube.com/@mkbhd",
        "description": "Tech reviews and videos",
        "keywords": ["tech", "review", "smartphone"],
        "crawl_enabled": True,
        "crawl_frequency": "manual"
    }

    response = requests.post(
        f"{BASE_URL}/api/channels",
        json=channel_data
    )

    if response.status_code == 201:
        print(f"✓ Channel added successfully: {response.json()['channel_name']}")
        return True
    elif response.status_code == 400 and "already exists" in response.json().get('detail', ''):
        print(f"✓ Channel already exists (expected)")
        return True
    else:
        print(f"✗ Failed to add channel: {response.status_code} - {response.text}")
        return False

def test_list_videos():
    """Test listing videos"""
    response = requests.get(f"{BASE_URL}/api/videos?limit=10")
    data = response.json()
    print(f"✓ Videos: Found {len(data)} videos")
    return response.status_code == 200

def test_list_sessions():
    """Test listing sessions"""
    response = requests.get(f"{BASE_URL}/api/sessions")
    data = response.json()
    print(f"✓ Sessions: Found {len(data)} sessions")
    return response.status_code == 200

def run_all_tests():
    """Run all tests"""
    print("=" * 60)
    print("YouTube Crawler - API Tests")
    print("=" * 60)

    tests = [
        ("Health Check", test_health),
        ("Dashboard Stats", test_dashboard_stats),
        ("List Channels", test_list_channels),
        ("Add Channel", test_add_channel),
        ("List Videos", test_list_videos),
        ("List Sessions", test_list_sessions),
    ]

    results = []
    for name, test_func in tests:
        print(f"\nTesting: {name}")
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"✗ Error: {e}")
            results.append((name, False))

    print("\n" + "=" * 60)
    print("Test Results Summary")
    print("=" * 60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {name}")

    print(f"\nTotal: {passed}/{total} tests passed")
    print("=" * 60)

if __name__ == "__main__":
    run_all_tests()
