"""
Automated test script for YouTube Crawler
Tests all major API endpoints without user interaction
"""
import requests
import json
import sys
import io

# Fix Windows console encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

BASE_URL = "http://127.0.0.1:5000"

def test_api():
    """Run automated API tests"""
    print("=" * 70)
    print("YouTube Channel Crawler - Automated API Tests")
    print("=" * 70)

    results = []

    # Test 1: Health Check
    print("\n[1/8] Testing health endpoint...")
    try:
        response = requests.get(f"{BASE_URL}/health")
        if response.status_code == 200:
            print(f"✓ PASS - Health check: {response.json()}")
            results.append(("Health Check", True))
        else:
            print(f"✗ FAIL - Status: {response.status_code}")
            results.append(("Health Check", False))
    except Exception as e:
        print(f"✗ FAIL - Error: {e}")
        results.append(("Health Check", False))

    # Test 2: Dashboard Stats
    print("\n[2/8] Testing dashboard stats...")
    try:
        response = requests.get(f"{BASE_URL}/api/dashboard/stats")
        if response.status_code == 200:
            stats = response.json()
            print(f"✓ PASS - Stats retrieved:")
            print(f"  - Total Channels: {stats['total_channels']}")
            print(f"  - Total Videos: {stats['total_videos']}")
            print(f"  - Active Sessions: {stats['active_sessions']}")
            results.append(("Dashboard Stats", True))
        else:
            print(f"✗ FAIL - Status: {response.status_code}")
            results.append(("Dashboard Stats", False))
    except Exception as e:
        print(f"✗ FAIL - Error: {e}")
        results.append(("Dashboard Stats", False))

    # Test 3: List Channels
    print("\n[3/8] Testing list channels...")
    try:
        response = requests.get(f"{BASE_URL}/api/channels")
        if response.status_code == 200:
            channels = response.json()
            print(f"✓ PASS - Found {len(channels)} channel(s)")
            results.append(("List Channels", True))
        else:
            print(f"✗ FAIL - Status: {response.status_code}")
            results.append(("List Channels", False))
    except Exception as e:
        print(f"✗ FAIL - Error: {e}")
        results.append(("List Channels", False))

    # Test 4: Add Channel
    print("\n[4/8] Testing add channel...")
    try:
        channel_data = {
            "channel_id": "UCHnyfMqiRRG1u-2MsSQLbXA",
            "channel_name": "Veritasium",
            "channel_url": "https://www.youtube.com/@veritasium",
            "description": "Science and engineering videos",
            "keywords": ["science", "physics", "engineering"],
            "crawl_enabled": True,
            "crawl_frequency": "manual"
        }

        response = requests.post(f"{BASE_URL}/api/channels", json=channel_data)
        if response.status_code == 201:
            channel = response.json()
            print(f"✓ PASS - Channel added: {channel['channel_name']} (ID: {channel['id']})")
            results.append(("Add Channel", True))
            channel_id = channel['id']
        elif response.status_code == 400 and "already exists" in response.json().get('detail', ''):
            print(f"✓ PASS - Channel already exists (expected)")
            results.append(("Add Channel", True))
            # Get existing channel ID
            response = requests.get(f"{BASE_URL}/api/channels")
            channels = response.json()
            channel_id = channels[0]['id'] if channels else None
        else:
            print(f"✗ FAIL - Status: {response.status_code}")
            results.append(("Add Channel", False))
            channel_id = None
    except Exception as e:
        print(f"✗ FAIL - Error: {e}")
        results.append(("Add Channel", False))
        channel_id = None

    # Test 5: Get Channel Details
    if channel_id:
        print("\n[5/8] Testing get channel details...")
        try:
            response = requests.get(f"{BASE_URL}/api/channels/{channel_id}")
            if response.status_code == 200:
                channel = response.json()
                print(f"✓ PASS - Channel details retrieved:")
                print(f"  - Name: {channel['channel_name']}")
                print(f"  - Videos: {channel['video_count']}")
                print(f"  - Keywords: {', '.join(channel['keywords'])}")
                results.append(("Get Channel Details", True))
            else:
                print(f"✗ FAIL - Status: {response.status_code}")
                results.append(("Get Channel Details", False))
        except Exception as e:
            print(f"✗ FAIL - Error: {e}")
            results.append(("Get Channel Details", False))
    else:
        print("\n[5/8] Skipping get channel details (no channel ID)")
        results.append(("Get Channel Details", False))

    # Test 6: List Videos
    print("\n[6/8] Testing list videos...")
    try:
        response = requests.get(f"{BASE_URL}/api/videos?limit=5")
        if response.status_code == 200:
            videos = response.json()
            print(f"✓ PASS - Found {len(videos)} video(s)")
            results.append(("List Videos", True))
        else:
            print(f"✗ FAIL - Status: {response.status_code}")
            results.append(("List Videos", False))
    except Exception as e:
        print(f"✗ FAIL - Error: {e}")
        results.append(("List Videos", False))

    # Test 7: List Sessions
    print("\n[7/8] Testing list sessions...")
    try:
        response = requests.get(f"{BASE_URL}/api/sessions")
        if response.status_code == 200:
            sessions = response.json()
            print(f"✓ PASS - Found {len(sessions)} session(s)")
            results.append(("List Sessions", True))
        else:
            print(f"✗ FAIL - Status: {response.status_code}")
            results.append(("List Sessions", False))
    except Exception as e:
        print(f"✗ FAIL - Error: {e}")
        results.append(("List Sessions", False))

    # Test 8: Daily Summary
    print("\n[8/8] Testing daily summary...")
    try:
        response = requests.get(f"{BASE_URL}/api/dashboard/daily-summary?days=7")
        if response.status_code == 200:
            summary = response.json()
            print(f"✓ PASS - Retrieved {len(summary)} days of data")
            results.append(("Daily Summary", True))
        else:
            print(f"✗ FAIL - Status: {response.status_code}")
            results.append(("Daily Summary", False))
    except Exception as e:
        print(f"✗ FAIL - Error: {e}")
        results.append(("Daily Summary", False))

    # Print Summary
    print("\n" + "=" * 70)
    print("Test Results Summary")
    print("=" * 70)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {name}")

    print(f"\nTotal: {passed}/{total} tests passed ({passed*100//total}%)")
    print("=" * 70)

    if passed == total:
        print("\n🎉 All tests passed! The application is working correctly.")
        print("\nNext steps:")
        print("  1. Open web interface: http://127.0.0.1:5000")
        print("  2. Add your YouTube API key to .env")
        print("  3. Add your OpenAI API key to .env")
        print("  4. Start crawling channels!")
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. Please check the errors above.")

    return passed == total

if __name__ == "__main__":
    try:
        success = test_api()
        exit(0 if success else 1)
    except requests.exceptions.ConnectionError:
        print("\n✗ Error: Could not connect to the server.")
        print("Make sure the server is running at: http://127.0.0.1:5000")
        print("Run: python run.py")
        exit(1)
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        exit(1)
