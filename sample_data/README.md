# Sample Data for YouTube Crawler

This directory contains sample data that can be imported into a fresh deployment of the YouTube Crawler application.

## Contents

- **channels.json** - Sample YouTube channels (10 channels)
- **videos.json** - Sample videos from those channels (50 videos)
- **sessions.json** - Sample crawl sessions (10 sessions)
- **metadata.json** - Export metadata and statistics

## Usage

### For New Deployments

1. **Install the application** following the main README.md instructions
2. **Import sample data**:
   ```bash
   python import_sample_data.py
   ```
3. **Start the server**:
   ```bash
   python run.py
   ```
4. **Access the application** at http://127.0.0.1:5000

### For Existing Deployments

The import script will skip any existing records, so you can safely run it on an existing database without creating duplicates.

## What Gets Imported

- **Channels**: YouTube channel information including names, URLs, and metadata
- **Videos**: Video details including titles, descriptions, view counts, and AI-generated summaries
- **Sessions**: Historical crawl session data showing past crawling activities

## Notes

- Transcripts are truncated to 500 characters in the sample data to keep file sizes manageable
- All timestamps are preserved from the original export
- The import script automatically handles relationships between channels, videos, and sessions
- Sample data is safe to use for testing and demonstration purposes

## Exporting Your Own Data

To export your current database as sample data:

```bash
python export_sample_data.py
```

This will create/update the JSON files in this directory with data from your database.

## Data Privacy

**Important**: The sample data included in this repository is for demonstration purposes only. If you export your own data:

- Review the exported JSON files before committing to version control
- Remove any sensitive or private information
- Consider using `.gitignore` to exclude `sample_data/` if it contains real user data
- The default export limits data to 10 channels, 50 videos, and 10 sessions

## Troubleshooting

### Import Fails

If the import fails, check:
1. Database is initialized (tables exist)
2. JSON files are valid and not corrupted
3. No foreign key constraint violations

### Duplicate Data

The import script automatically skips existing records based on:
- Channels: `channel_id`
- Videos: `video_id`
- Sessions: `session_name`

### Missing Dependencies

Ensure all required packages are installed:
```bash
pip install -r requirements.txt
```
