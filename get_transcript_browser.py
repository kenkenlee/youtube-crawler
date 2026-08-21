#!/usr/bin/env python3
"""
YouTube Transcript Extractor (Browser) — Extremely Robust Version

This version uses many aggressive strategies to reliably open the transcript panel
and extract ONLY the real spoken transcript (ytd-transcript-segment-renderer).
"""

import sys
import re
import time
from playwright.sync_api import sync_playwright


def extract_video_id(url_or_id: str) -> str:
    if re.match(r'^[A-Za-z0-9_-]{11}$', url_or_id):
        return url_or_id
    for p in [r'(?:v=|\/)([0-9A-Za-z_-]{11})', r'(?:embed\/)([0-9A-Za-z_-]{11})', r'(?:youtu\.be\/)([0-9A-Za-z_-]{11})']:
        m = re.search(p, url_or_id)
        if m:
            return m.group(1)
    return url_or_id


def get_transcript_browser(video_id: str, headless: bool = True) -> str:
    video_id = extract_video_id(video_id)
    url = f"https://www.youtube.com/watch?v={video_id}"

    print(f"🌐 Robust browser transcript extractor for: {video_id}")

    with sync_playwright() as p:
        browser = p.firefox.launch(headless=headless, slow_mo=60)
        page = browser.new_page(viewport={"width": 1400, "height": 1000})

        try:
            page.goto(url, wait_until="domcontentloaded", timeout=50000)
            time.sleep(4)

            # Scroll a bit so buttons become visible
            page.evaluate("window.scrollBy(0, 300)")
            time.sleep(1.5)

            clicked = False

            # === STRATEGY 1: aria-label button ===
            try:
                btn = page.locator('button[aria-label*="transcript" i]').first
                if btn.is_visible(timeout=4000):
                    btn.click()
                    clicked = True
                    print("   ✓ Clicked aria-label transcript button")
            except:
                pass

            # === STRATEGY 2: Three dots → menu item ===
            if not clicked:
                try:
                    more = page.locator('button[aria-label="More actions"]').first
                    if more.is_visible(timeout=3000):
                        more.click()
                        time.sleep(1.5)
                        for label in ["Show transcript", "Transcript", "Open transcript"]:
                            try:
                                item = page.locator(f'text="{label}"').first
                                if item.is_visible(timeout=2500):
                                    item.click()
                                    clicked = True
                                    print(f"   ✓ Clicked menu → {label}")
                                    break
                            except:
                                continue
                except:
                    pass

            # === STRATEGY 3: Search all buttons on page for "transcript" ===
            if not clicked:
                try:
                    buttons = page.locator('button, tp-yt-paper-button, ytd-button-renderer').all()
                    for b in buttons:
                        try:
                            txt = (b.inner_text() or "").lower()
                            if "transcript" in txt:
                                b.click()
                                clicked = True
                                print("   ✓ Found and clicked transcript button via text search")
                                break
                        except:
                            continue
                except:
                    pass

            if not clicked:
                print("   ⚠️  Could not open transcript panel (will still try to extract)")

            # Wait for segments to appear
            time.sleep(4)
            try:
                page.wait_for_selector("ytd-transcript-segment-renderer", timeout=10000)
                print("   ✓ Transcript segments appeared in DOM")
            except:
                print("   Transcript segments did not appear")

            # === STRICT EXTRACTION ===
            segments = page.locator("ytd-transcript-segment-renderer").all()

            if not segments:
                # Try inside the engagement panel
                try:
                    panel = page.locator("ytd-engagement-panel-section-list-renderer").first
                    if panel.is_visible(timeout=3000):
                        segments = panel.locator("ytd-transcript-segment-renderer").all()
                except:
                    pass

            if segments:
                lines = []
                for seg in segments:
                    try:
                        txt = seg.inner_text().strip()
                        if txt:
                            clean = re.sub(r'^\d+:\d+\s*', '', txt)
                            if clean and len(clean) > 3:
                                lines.append(clean)
                    except:
                        continue

                if lines:
                    transcript = " ".join(lines).strip()
                    print(f"   ✅ SUCCESS — extracted {len(transcript)} chars of REAL transcript")
                    browser.close()
                    return transcript

            print("   ❌ No real transcript segments found")
            browser.close()
            return ""

        except Exception as e:
            print(f"   ❌ Error: {e}")
            browser.close()
            return ""


def main():
    if len(sys.argv) < 2:
        print("Usage: python get_transcript_browser.py <video_id> [--visible]")
        sys.exit(1)

    vid = sys.argv[1]
    headless = "--visible" not in sys.argv

    text = get_transcript_browser(vid, headless=headless)

    if text:
        print("\n" + "=" * 70)
        print("TRANSCRIPT (REAL SEGMENTS ONLY):")
        print("=" * 70)
        print(text[:3500] + ("..." if len(text) > 3500 else ""))
    else:
        print("\n❌ Failed to extract real transcript.")


if __name__ == "__main__":
    main()