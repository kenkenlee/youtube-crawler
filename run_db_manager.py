"""
SQLite Database Manager
Launch a web interface to view and manage the YouTube Crawler database
"""
import os
import sys

def main():
    # Get database path
    db_path = os.path.join(os.path.dirname(__file__), 'data', 'database.db')
    
    if not os.path.exists(db_path):
        print(f"Error: Database not found at {db_path}")
        sys.exit(1)
    
    print("=" * 60)
    print("YouTube Crawler - Database Manager")
    print("=" * 60)
    print(f"Database: {db_path}")
    print()
    print("Starting SQLite-web on http://127.0.0.1:8080")
    print()
    print("Features:")
    print("  - View all tables and data")
    print("  - Run SQL queries")
    print("  - Export data")
    print("  - Edit records (use with caution!)")
    print()
    print("Press Ctrl+C to stop the database manager")
    print("=" * 60)
    print()
    
    # Launch sqlite-web
    os.system(f'python -m sqlite_web "{db_path}" --host 127.0.0.1 --port 8080')

if __name__ == "__main__":
    main()
