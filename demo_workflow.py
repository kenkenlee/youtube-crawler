"""
Complete workflow demonstration
This script demonstrates the entire YouTube Crawler workflow
"""
import requests
import json
import time

BASE_URL = "http://127.0.0.1:5000"

def print_header(text):
    print("\n" + "=" * 70)
    print(f"  {text}")
    print("=" * 70 + "\n")

def demo_complete_workflow():
    """Demonstrate complete workflow from adding channel to viewing summaries"""

    print_header("YouTube Channel Crawler - Complete Workflow Demo")

    # Step 1: Check server health
    print("Step 1: Checking server health...")
    response = requests.get(f"{BASE_URL}/health")
    print(f"✓ Server is healthy: {response.json()}")

    # Step 2: Add a channel
    print_header("Step 2: Adding YouTube Channel")

    channel_data = {
        "channel_id": "UCHnyfMqiRRG1u-2MsSQLbXA",
        "channel_name": "Veritasium",
        "channel_url": "https://www.youtube.com/@veritasium",
        "description": "An element of truth - videos about science, education, and anything else",
        "keywords": ["science", "physics", "education", "engineering"],
        "crawl_enabled": True,
        "crawl_frequency": "manual"
    }

    print(f"Adding channel: {channel_data['channel_name']}")
    print(f"URL: {channel_data['channel_url']}")
    print(f"Keywords: {', '.join(channel_data['keywords'])}")

    response = requests.post(f"{BASE_URL}/api/channels", json=channel_data)

    if response.status_code == 201:
        channel = response.json()
        print(f"\n✓ Channel added successfully!")
        print(f"  Channel ID: {channel['id']}")
        print(f"  Name: {channel['channel_name']}")
        channel_id = channel['id']
    elif response.status_code == 400:
        print(f"\n✓ Channel already exists")
        # Get existing channel
        response = requests.get(f"{BASE_URL}/api/channels")
        channels = response.json()
        channel = next((c for c in channels if c['channel_id'] == channel_data['channel_id']), None)
        channel_id = channel['id'] if channel else None
        print(f"  Using existing channel ID: {channel_id}")
    else:
        print(f"\n✗ Error adding channel: {response.status_code}")
        return

    # Step 3: View channel details
    print_header("Step 3: Viewing Channel Details")

    response = requests.get(f"{BASE_URL}/api/channels/{channel_id}")
    channel = response.json()

    print(f"Channel: {channel['channel_name']}")
    print(f"Description: {channel['description']}")
    print(f"Keywords: {', '.join(channel['keywords'])}")
    print(f"Crawl Enabled: {channel['crawl_enabled']}")
    print(f"Crawl Frequency: {channel['crawl_frequency']}")
    print(f"Video Count: {channel['video_count']}")
    print(f"Summarized: {channel['summarized_count']}")

    # Step 4: Create crawl session
    print_header("Step 4: Creating Crawl Session")

    session_data = {
        "session_name": f"Demo Crawl - {time.strftime('%Y-%m-%d %H:%M:%S')}",
        "session_type": "manual",
        "channel_ids": [channel_id],
        "filter_keywords": ["science", "physics"]
    }

    print(f"Session Name: {session_data['session_name']}")
    print(f"Channels: {session_data['channel_ids']}")
    print(f"Filter Keywords: {', '.join(session_data['filter_keywords'])}")
    print("\nStarting crawl session...")

    response = requests.post(f"{BASE_URL}/api/sessions", json=session_data)

    if response.status_code == 201:
        session = response.json()
        session_id = session['id']
        print(f"\n✓ Session created successfully!")
        print(f"  Session ID: {session_id}")
        print(f"  Status: {session['status']}")
    else:
        print(f"\n✗ Error creating session: {response.status_code}")
        print(response.text)
        return

    # Step 5: Monitor session progress
    print_header("Step 5: Monitoring Session Progress")

    print("Monitoring session (this may take a minute)...\n")

    max_checks = 30  # Check for up to 30 seconds
    for i in range(max_checks):
        response = requests.get(f"{BASE_URL}/api/sessions/{session_id}/progress")
        progress = response.json()

        print(f"[{i+1}/{max_checks}] Status: {progress['status']} | "
              f"Progress: {progress['progress_percentage']:.1f}% | "
              f"Channels: {progress['channels_progress']} | "
              f"Videos: {progress['videos_progress']}")

        if progress['status'] in ['completed', 'failed', 'cancelled']:
            print(f"\n✓ Session {progress['status']}!")
            break

        time.sleep(1)

    # Step 6: View session results
    print_header("Step 6: Viewing Session Results")

    response = requests.get(f"{BASE_URL}/api/sessions/{session_id}")
    session = response.json()

    print(f"Session: {session['session_name']}")
    print(f"Status: {session['status']}")
    print(f"Channels Processed: {session['processed_channels']}/{session['total_channels']}")
    print(f"Videos Found: {session['total_videos_found']}")
    print(f"Videos Processed: {session['videos_processed']}")
    print(f"Videos Summarized: {session['videos_summarized']}")
    print(f"Errors: {session['error_count']}")

    if session['started_at']:
        print(f"Started: {session['started_at']}")
    if session['completed_at']:
        print(f"Completed: {session['completed_at']}")

    # Step 7: List videos
    print_header("Step 7: Listing Crawled Videos")

    response = requests.get(f"{BASE_URL}/api/videos?channel_id={channel_id}&limit=5")
    videos = response.json()

    print(f"Found {len(videos)} video(s) from this channel:\n")

    for idx, video in enumerate(videos, 1):
        print(f"{idx}. {video['title']}")
        print(f"   Video ID: {video['video_id']}")
        print(f"   Published: {video.get('published_at', 'Unknown')}")
        print(f"   Views: {video['view_count']:,}")
        print(f"   Duration: {video['duration']} seconds")

        if video.get('matched_keywords'):
            print(f"   Matched Keywords: {', '.join(video['matched_keywords'])}")

        if video.get('summary_text'):
            summary = video['summary_text']
            if len(summary) > 150:
                summary = summary[:150] + "..."
            print(f"   Summary: {summary}")
        else:
            print(f"   Summary: Not yet generated")

        print()

    # Step 8: Search videos
    print_header("Step 8: Searching Videos")

    search_term = "science"
    print(f"Searching for: '{search_term}'\n")

    response = requests.get(f"{BASE_URL}/api/videos/search?q={search_term}&limit=3")
    videos = response.json()

    print(f"Found {len(videos)} result(s):\n")

    for idx, video in enumerate(videos, 1):
        print(f"{idx}. {video['title']}")
        print(f"   Channel: {video.get('channel_name', 'Unknown')}")
        print(f"   URL: https://www.youtube.com/watch?v={video['video_id']}")

        if video.get('summary_text'):
            summary = video['summary_text']
            if len(summary) > 100:
                summary = summary[:100] + "..."
            print(f"   Summary: {summary}")

        print()

    # Step 9: Dashboard statistics
    print_header("Step 9: Dashboard Statistics")

    response = requests.get(f"{BASE_URL}/api/dashboard/stats")
    stats = response.json()

    print("Current Statistics:")
    print(f"  Total Channels: {stats['total_channels']}")
    print(f"  Active Channels: {stats['active_channels']}")
    print(f"  Total Videos: {stats['total_videos']}")
    print(f"  Summarized Videos: {stats['summarized_videos']}")
    print(f"  Active Sessions: {stats['active_sessions']}")
    print(f"  Completed Sessions: {stats['completed_sessions']}")
    print(f"  Failed Sessions: {stats['failed_sessions']}")

    # Step 10: Daily summary
    print_header("Step 10: Daily Activity Summary")

    response = requests.get(f"{BASE_URL}/api/dashboard/daily-summary?days=3")
    summaries = response.json()

    print("Last 3 days activity:\n")

    for summary in summaries:
        print(f"Date: {summary['date']}")
        print(f"  Sessions Completed: {summary['sessions_completed']}")
        print(f"  Videos Crawled: {summary['videos_crawled']}")
        print(f"  Videos Summarized: {summary['videos_summarized']}")
        print(f"  Channels Crawled: {summary['channels_crawled']}")
        print(f"  Errors: {summary['errors']}")
        print()

    # Final summary
    print_header("Workflow Complete!")

    print("✓ Successfully demonstrated:")
    print("  1. Server health check")
    print("  2. Adding a YouTube channel")
    print("  3. Viewing channel details")
    print("  4. Creating a crawl session")
    print("  5. Monitoring session progress")
    print("  6. Viewing session results")
    print("  7. Listing crawled videos")
    print("  8. Searching videos")
    print("  9. Dashboard statistics")
    print("  10. Daily activity summary")

    print("\n" + "=" * 70)
    print("  Your YouTube Channel Crawler is fully operational!")
    print("=" * 70)

    print("\nAccess your application:")
    print(f"  Dashboard: http://127.0.0.1:5000/dashboard")
    print(f"  Channels:  http://127.0.0.1:5000/channels")
    print(f"  Videos:    http://127.0.0.1:5000/videos")
    print(f"  Sessions:  http://127.0.0.1:5000/sessions")
    print(f"  API Docs:  http://127.0.0.1:5000/docs")

    print("\nNext steps:")
    print("  1. Add your YouTube API key to .env")
    print("  2. Add your OpenAI API key to .env")
    print("  3. Add more channels you want to monitor")
    print("  4. Enable daily crawling for automatic updates")
    print("  5. Explore the web interface!")

if __name__ == "__main__":
    try:
        demo_complete_workflow()
    except requests.exceptions.ConnectionError:
        print("\n✗ Error: Could not connect to the server.")
        print("Make sure the server is running at: http://127.0.0.1:5000")
        print("Run: python run.py")
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
