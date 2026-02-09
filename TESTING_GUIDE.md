# Testing Guide - All New Features

## 🎯 Features to Test

### ✅ Option 1: Search & Sort in "Start New Crawl"
### ✅ Option 2: SQLite Database Manager
### ✅ Option 3: Multi-Platform Support (YouTube, Twitter, Instagram)

---

## Option 1: Test Search & Sort in "Start New Crawl"

### Step 1: Open Dashboard
1. Go to: http://127.0.0.1:5000/dashboard
2. Click **"Start New Crawl"** button

### Step 2: Test Search Function
1. In the **"Search Channels"** box, type a channel name
2. Watch the channel list filter in real-time
3. Try partial matches (e.g., "tech" to find "My Tech Channel")

### Step 3: Test Sort Function
1. Click the **"Sort By"** dropdown
2. Try each option:
   - **Name (A-Z)** - Alphabetical ascending
   - **Name (Z-A)** - Alphabetical descending
   - **Most Videos** - Channels with most content first
   - **Least Videos** - Channels with least content first
   - **Recently Crawled** - Most recently updated first

### Step 4: Test Bulk Selection
1. Click **"Select All"** button - All channels should be selected
2. Click **"Clear"** button - All selections should be cleared
3. Manually select a few channels
4. Check the counter: "X channel(s) selected"

### Step 5: Start a Crawl
1. Select 2-3 channels
2. Set max videos (e.g., 5)
3. Click **"Start Crawl"**
4. Verify it works!

**Expected Results:**
- ✅ Search filters channels instantly
- ✅ Sort reorders the list correctly
- ✅ Select All/Clear buttons work
- ✅ Counter shows correct number
- ✅ Crawl starts successfully

---

## Option 2: Test SQLite Database Manager

### Step 1: Launch Database Manager
```bash
cd "C:\Users\Ken Acer Swift 5\youtube-crawler"
python run_db_manager.py
```

### Step 2: Access Web Interface
1. Open browser: http://127.0.0.1:8080
2. You should see the SQLite-web interface

### Step 3: Browse Tables
1. Click on **"channels"** table
2. View all your channels with platform info
3. Click on **"videos"** table
4. Browse your 294 videos

### Step 4: Run a Query
1. Click **"Query"** tab
2. Try this query:
```sql
SELECT 
    c.channel_name,
    c.platform,
    COUNT(v.id) as video_count
FROM channels c
LEFT JOIN videos v ON c.id = v.channel_id
GROUP BY c.id
ORDER BY video_count DESC;
```
3. Click **"Execute"**
4. See results!

### Step 5: Export Data
1. Click **"Export"** button
2. Download CSV of any table
3. Open in Excel/Sheets

**Expected Results:**
- ✅ Database manager opens at port 8080
- ✅ Can browse all tables
- ✅ Can run SQL queries
- ✅ Can export data to CSV
- ✅ Both apps run simultaneously (5000 + 8080)

---

## Option 3: Test Multi-Platform Support

### Test 3A: Add a YouTube Channel

1. Go to: http://127.0.0.1:5000/channels
2. Click **"Add Channel"**
3. Select Platform: **YouTube**
4. Paste URL: `https://www.youtube.com/@mkbhd`
5. Click **"Add Channel"**

**Expected:**
- ✅ Channel info auto-fills
- ✅ Shows YouTube badge (red)
- ✅ YouTube icon displayed

### Test 3B: Add a Twitter/X.com Profile

1. Click **"Add Channel"** again
2. Select Platform: **X.com (Twitter)**
3. Notice URL placeholder changes
4. Paste URL: `https://twitter.com/elonmusk`
   OR: `https://x.com/elonmusk`
5. Click **"Add Channel"**

**Expected:**
- ✅ Profile added successfully
- ✅ Shows Twitter/X badge (blue)
- ✅ Twitter icon displayed
- ✅ Username extracted from URL

### Test 3C: Add an Instagram Profile

1. Click **"Add Channel"** again
2. Select Platform: **Instagram**
3. Notice URL placeholder changes
4. Paste URL: `https://www.instagram.com/instagram`
5. Click **"Add Channel"**

**Expected:**
- ✅ Profile added successfully
- ✅ Shows Instagram badge (gradient)
- ✅ Instagram icon displayed
- ✅ Username extracted from URL

### Test 3D: View Mixed Platform Channels

1. Go to Channels page
2. You should see:
   - YouTube channels with red YouTube badge
   - Twitter profiles with blue X badge
   - Instagram profiles with gradient badge
3. Each has appropriate icon
4. Click external link - opens correct platform

**Expected Results:**
- ✅ All 3 platforms supported
- ✅ Different badges for each platform
- ✅ Correct icons displayed
- ✅ Platform-specific URLs work
- ✅ Can add multiple profiles per platform

---

## Verification Checklist

### Database Verification
```bash
python run_db_manager.py
```

Then run this query:
```sql
SELECT 
    platform,
    COUNT(*) as count
FROM channels
GROUP BY platform;
```

**Expected Output:**
```
platform  | count
----------|------
youtube   | 6 (or more)
twitter   | 1 (if you added one)
instagram | 1 (if you added one)
```

### UI Verification

**Channels Page:**
- [ ] Platform badges visible
- [ ] Correct icons for each platform
- [ ] External links work
- [ ] Can filter/search all platforms

**Start New Crawl:**
- [ ] Search box filters channels
- [ ] Sort dropdown works
- [ ] Select All/Clear buttons work
- [ ] Counter shows correct number
- [ ] Can select mixed platforms

**Add Channel Form:**
- [ ] Platform dropdown has 3 options
- [ ] URL placeholder changes per platform
- [ ] YouTube auto-fills (Twitter/Instagram don't yet)
- [ ] All platforms can be added

---

## Known Limitations (Simplified Version)

### Current Features:
✅ Store YouTube, Twitter, Instagram URLs
✅ Display platform badges and icons
✅ Basic profile information
✅ Manual content addition

### Not Yet Implemented:
❌ Automatic Twitter crawling (requires API)
❌ Automatic Instagram crawling (requires API)
❌ Auto-fill for Twitter/Instagram (manual entry)
❌ Platform-specific summarization

### Future Enhancements:
- Twitter API integration for automatic tweet fetching
- Instagram API integration for automatic post fetching
- Platform-specific content summarization
- Cross-platform analytics

---

## Troubleshooting

### Issue: Database Manager Won't Start
**Solution:** Make sure port 8080 is not in use
```bash
# Check if port is in use
netstat -ano | findstr :8080

# If in use, kill the process or use different port
python -m sqlite_web data/database.db --port 8081
```

### Issue: Platform Badge Not Showing
**Solution:** Hard refresh browser (Ctrl+F5)

### Issue: Can't Add Twitter/Instagram
**Solution:** 
1. Check URL format is correct
2. Make sure username is valid
3. Try with different profile

### Issue: Search Not Working in Crawl Modal
**Solution:** 
1. Refresh page (Ctrl+F5)
2. Check browser console for errors
3. Make sure JavaScript loaded

---

## Success Criteria

### ✅ All Features Working When:

**Option 1 (Search & Sort):**
- Can search channels by name
- Can sort by all 5 options
- Select All/Clear buttons work
- Counter updates correctly

**Option 2 (Database Manager):**
- Opens at http://127.0.0.1:8080
- Can browse all tables
- Can run SQL queries
- Can export data

**Option 3 (Multi-Platform):**
- Can add YouTube channels
- Can add Twitter profiles
- Can add Instagram profiles
- Platform badges display correctly
- Icons show for each platform

---

## Next Steps After Testing

1. **Report Issues:** Let me know what's not working
2. **Request Features:** What else do you need?
3. **API Integration:** Ready to add Twitter/Instagram APIs?
4. **Customization:** Want to change colors, layouts, etc.?

---

**Happy Testing! 🎉**
