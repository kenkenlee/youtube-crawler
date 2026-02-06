"""
Demo script to showcase YouTube Crawler functionality
Run this after starting the server to see the app in action
"""
import requests
import json
import time

BASE_URL = "http://127.0.0.1:5000"

def print_section(title):
    """Print a section header"""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)

def demo_health_check():
    """Demo: Health check"""
    print_section("1. Health Check")
    response = requests.get(f"{BASE_URL}/health")
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")

def demo_dashboard_stats():
    """Demo: Dashboard statistics"""
    print_section("2. Dashboard Statistics")
    response = requests.get(f"{BASE_URL}/api/dashboard/stats")
    stats = response.json()

    print(f"Total Channels: {stats['total_channels']}")
    print(f"Active Channels: {stats['active_channels']}")
    print(f"Total Videos: {stats['total_videos']}")
    print(f"Summarized Videos: {stats['summarized_videos']}")
    print(f"Active Sessions: {stats['active_sessions']}")
    print(f"Completed Sessions: {stats['completed_sessions']}")

def demo_add_channel():
    """Demo: Add a YouTube channel"""
    print_section("3. Add YouTube Channel")

    # Example: Add Veritasium channel
    channel_data = {
        "channel_id": "UCHnyfMqiRRG1u-2MsSQLbXA",
        "channel_name": "Veritasium",
        "channel_url": "https://www.youtube.com/@veritasium",
        "description": "Science and engineering videos",
        "keywords": ["science", "physics", "engineering"],
        "crawl_enabled": True,
        "crawl_frequency": "manual"
    }

    print(f"Adding channel: {channel_data['channel_name']}")
    print(f"URL: {channel_data['channel_url']}")
    print(f"Keywords: {', '.join(channel_data['keywords'])}")

    response = requests.post(f"{BASE_URL}/api/channels", json=channel_data)

    if response.status_code == 201:
        print(f"\n✓ Channel added successfully!")
        channel = response.json()
        print(f"  ID: {channel['id']}")
        print(f"  Name: {channel['channel_name']}")
        return channel['id']
    elif response.status_code == 400:
        print(f"\n✓ Channel already exists (that's okay!)")
        # Get existing channel
        response = requests.get(f"{BASE_URL}/api/channels")
        channels = response.json()
        for ch in channels:
            if ch['channel_id'] == channel_data['channel_id']:
                return ch['id']
    else:
        print(f"\n✗ Error: {response.status_code}")
        print(response.text)
        return None

def demo_list_channels():
    """Demo: List all channels"""
    print_section("4. List All Channels")
    response = requests.get(f"{BASE_URL}/api/channels")
    channels = response.json()

    print(f"Found {len(channels)} channel(s):\n")
    for ch in channels:
        print(f"  • {ch['channel_name']}")
        print(f"    URL: {ch['channel_url']}")
        print(f"    Videos: {ch['video_count']} (Summarized: {ch['summarized_count']})")
        print(f"    Keywords: {', '.join(ch['keywords']) if ch['keywords'] else 'None'}")
        print(f"    Status: {'Active' if ch['crawl_enabled'] else 'Inactive'}")
        print()

def demo_create_session(channel_id):
    """Demo: Create a crawl session"""
    print_section("5. Create Crawl Session")

    session_data = {
        "session_name": f"Demo Crawl - {time.strftime('%Y-%m-%d %H:%M')}",
        "session_type": "manual",
        "channel_ids": [channel_id],
        "filter_keywords": ["science", "physics"]
    }

    print(f"Creating session: {session_data['session_name']}")
    print(f"Channels: {session_data['channel_ids']}")
    print(f"Keywords: {', '.join(session_data['filter_keywords'])}")

    response = requests.post(f"{BASE_URL}/api/sessions", json=session_data)

    if response.status_code == 201:
        session = response.json()
        print(f"\n✓ Session created successfully!")
        print(f"  ID: {session['id']}")
        print(f"  Status: {session['status']}")
        return session['id']
    else:
        print(f"\n✗ Error: {response.status_code}")
        print(response.text)
        return None

def demo_monitor_session(session_id):
    """Demo: Monitor session progress"""
    print_section("6. Monitor Session Progress")

    print(f"Monitoring session {session_id}...")
    print("(This may take a few moments)\n")

    for i in range(10):  # Check for up to 10 seconds
        response = requests.get(f"{BASE_URL}/api/sessions/{session_id}/progress")
        progress = response.json()

        print(f"  Status: {progress['status']}")
        print(f"  Progress: {progress['progress_percentage']:.1f}%")
        print(f"  Channels: {progress['channels_progress']}")
        print(f"  Videos: {progress['videos_progress']}")
        print(f"  Activity: {progress['current_activity']}")

        if progress['status'] in ['completed', 'failed', 'cancelled']:
            break

        time.sleep(1)
        print()

def demo_list_videos():
    """Demo: List videos"""
    print_section("7. List Videos")
    response = requests.get(f"{BASE_URL}/api/videos?limit=5")
    videos = response.json()

    print(f"Found {len(videos)} video(s):\n")
    for video in videos:
        print(f"  • {video['title']}")
        print(f"    Video ID: {video['video_id']}")
        print(f"    Views: {video['view_count']:,}")
        print(f"    Duration: {video['duration']} seconds")
        print(f"    Has Summary: {'Yes' if video.get('summary_text') else 'No'}")
        if video.get('matched_keywords'):
            print(f"    Matched Keywords: {', '.join(video['matched_keywords'])}")
        print()

def demo_search_videos():
    """Demo: Search videos"""
    print_section("8. Search Videos")

    search_term = "science"
    print(f"Searching for: '{search_term}'\n")

    response = requests.get(f"{BASE_URL}/api/videos/search?q={search_term}&limit=3")
    videos = response.json()

    print(f"Found {len(videos)} result(s):\n")
    for video in videos:
        print(f"  • {video['title']}")
        print(f"    Channel: {video.get('channel_name', 'Unknown')}")
        if video.get('summary_text'):
            summary = video['summary_text'][:150] + "..." if len(video['summary_text']) > 150 else video['summary_text']
            print(f"    Summary: {summary}")
        print()

def run_demo():
    """Run the complete demo"""
    print("\n" + "=" * 70)
    print("  YouTube Channel Crawler - Interactive Demo")
    print("=" * 70)
    print("\nThis demo will showcase the main features of the application.")
    print("Make sure the server is running at: http://127.0.0.1:5000")

    input("\nPress Enter to start the demo...")

    try:
        # 1. Health check
        demo_health_check()
        input("\nPress Enter to continue...")

        # 2. Dashboard stats
        demo_dashboard_stats()
        input("\nPress Enter to continue...")

        # 3. Add a channel
        channel_id = demo_add_channel()
        input("\nPress Enter to continue...")

        # 4. List channels
        demo_list_channels()
        input("\nPress Enter to continue...")

        # 5. Create session (if we have a channel)
        if channel_id:
            session_id = demo_create_session(channel_id)
            input("\nPress Enter to continue...")

            # 6. Monitor session
            if session_id:
                demo_monitor_session(session_id)
                input("\nPress Enter to continue...")

        # 7. List videos
        demo_list_videos()
        input("\nPress Enter to continue...")

        # 8. Search videos
        demo_search_videos()

        # Final message
        print_section("Demo Complete!")
        print("\nYou can now:")
        print("  • Open the web interface: http://127.0.0.1:5000")
        print("  • View API docs: http://127.0.0.1:5000/docs")
        print("  • Add more channels and start crawling!")
        print("\nThank you for trying YouTube Channel Crawler!")

    except requests.exceptions.ConnectionError:
        print("\n✗ Error: Could not connect to the server.")
        print("Make sure the server is running at: http://127.0.0.1:5000")
        print("Run: python run.py")
    except Exception as e:
        print(f"\n✗ Error: {e}")

if __name__ == "__main__":
    run_demo()
