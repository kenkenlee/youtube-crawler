"""
YouTube Summariser - Interactive Installation Wizard

Guides the user through the full deployment configuration during install:
  1. Python / dependency setup (virtual environment)
  2. Database location
  3. YouTube Data API key (validated against the live API if requested)
  4. AI summarisation provider + API key
  5. Crawler / scheduler options

Everything the user enters is written directly to .env, so there is no
need to hand-edit configuration files afterwards.

Usage:
    python install.py            # interactive wizard
    python install.py --yes      # accept all defaults, no prompts
"""

import os
import shutil
import subprocess
import sys
import urllib.request
import urllib.error

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
VENV_DIR = os.path.join(PROJECT_ROOT, ".venv")
ENV_FILE = os.path.join(PROJECT_ROOT, ".env")

IS_WINDOWS = os.name == "nt"


# --------------------------------------------------------------------------
# Small console helpers
# --------------------------------------------------------------------------

def print_header(text):
    print()
    print("=" * 62)
    print(f"  {text}")
    print("=" * 62)


def print_step(index, total, text):
    print()
    print(f"[{index}/{total}] {text}")
    print("-" * 62)


def ask(prompt, default="", secret=False):
    """Prompt for a value, returning the default on empty input."""
    if secret and default:
        hint = default[:6] + "..." if len(default) > 6 else "***"
        suffix = f" [{hint}]"
    elif default:
        suffix = f" [{default}]"
    else:
        suffix = ""
    try:
        value = input(f"{prompt}{suffix}: ").strip()
    except EOFError:
        value = ""
    return value or default


def ask_bool(prompt, default=True):
    suffix = " [Y/n]" if default else " [y/N]"
    while True:
        try:
            value = input(f"{prompt}{suffix}: ").strip().lower()
        except EOFError:
            value = ""
        if value in ("", "y", "yes"):
            return default if value == "" else True
        if value in ("n", "no"):
            return default if value == "" else False
        print("  Please answer 'y' or 'n'.")


def ask_int(prompt, default):
    while True:
        raw = ask(prompt, str(default))
        try:
            return int(raw)
        except ValueError:
            print("  Please enter a whole number.")


# --------------------------------------------------------------------------
# Step 1: Python environment & dependencies
# --------------------------------------------------------------------------

def find_python():
    """Locate a suitable Python interpreter (3.9+)."""
    candidates = [sys.executable, "python", "python3", "py"]
    for candidate in candidates:
        if not candidate:
            continue
        try:
            result = subprocess.run(
                [candidate, "--version"],
                capture_output=True, text=True, timeout=15,
                shell=False,
            )
            version_line = (result.stdout or result.stderr).strip()
            if result.returncode == 0 and "Python 3" in version_line:
                minor = int(version_line.split(".")[1])
                if minor >= 9:
                    return candidate, version_line
        except (OSError, subprocess.TimeoutExpired, ValueError):
            continue
    return None, None


def create_venv(python):
    if os.path.isdir(os.path.join(VENV_DIR, ("Scripts" if IS_WINDOWS else "bin"))):
        print("  Virtual environment already exists - reusing it.")
        return True
    print(f"  Creating virtual environment in {VENV_DIR} ...")
    result = subprocess.run([python, "-m", "venv", VENV_DIR])
    if result.returncode != 0:
        print("  ERROR: Failed to create the virtual environment.")
        return False
    return True


def venv_python():
    name = "python.exe" if IS_WINDOWS else "python"
    return os.path.join(VENV_DIR, "Scripts" if IS_WINDOWS else "bin", name)


def install_dependencies():
    print("  Installing dependencies from requirements.txt ...")
    result = subprocess.run(
        [venv_python(), "-m", "pip", "install", "-r",
         os.path.join(PROJECT_ROOT, "requirements.txt")]
    )
    if result.returncode != 0:
        print("  ERROR: Dependency installation failed. Check your network")
        print("  connection and try running the installer again.")
        return False
    print("  Dependencies installed successfully.")
    return True


# --------------------------------------------------------------------------
# Step 2: Database configuration
# --------------------------------------------------------------------------

def configure_database():
    print()
    print("  The database stores channels, videos, transcripts and summaries.")
    print("  SQLite is the built-in option and needs no extra setup.")
    print()
    use_default = ask_bool(
        "  Use the default SQLite location (data/database.db)?", True)
    if use_default:
        db_url = "sqlite:///./data/database.db"
        db_dir = os.path.join(PROJECT_ROOT, "data")
        os.makedirs(db_dir, exist_ok=True)
    else:
        raw = ask("  Full path to the SQLite database file",
                  os.path.join(PROJECT_ROOT, "data", "database.db"))
        raw = os.path.expanduser(raw)
        db_dir = os.path.dirname(raw)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
        if not raw.lower().endswith((".db", ".sqlite", ".sqlite3")):
            raw = os.path.join(raw, "database.db")
        # Normalise to a relative path when the DB lives inside the project
        abs_path = os.path.abspath(raw)
        try:
            rel = os.path.relpath(abs_path, PROJECT_ROOT)
            outside = rel.startswith("..")
        except ValueError:
            outside = True
        if not outside:
            raw = "./" + rel.replace("\\", "/")
        db_url = f"sqlite:///{raw.replace(os.sep, '/')}"
    print(f"  Database: {db_url}")
    return db_url


# --------------------------------------------------------------------------
# Step 3: YouTube API key
# --------------------------------------------------------------------------

def validate_youtube_key(api_key):
    """Check the key against the YouTube Data API (cheap 1-unit call)."""
    url = ("https://www.googleapis.com/youtube/v3/videoCategories"
           f"?part=snippet&regionCode=US&key={api_key}")
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            return resp.status == 200
    except urllib.error.HTTPError as e:
        print(f"  Validation failed (HTTP {e.code}). Common causes:")
        print("   - key is wrong or has leading/trailing spaces")
        print("   - YouTube Data API v3 is not enabled for this key's project")
        return False
    except urllib.error.URLError:
        print("  Could not reach Google (network issue) - skipping validation.")
        return True  # allow offline installs to continue


def configure_youtube():
    print()
    print("  The YouTube Data API key is required for crawling videos.")
    print("  Get one at: https://console.cloud.google.com/")
    print("  (APIs & Services -> Credentials -> Create API key, then enable")
    print("   'YouTube Data API v3' for the project.)")
    print()
    key = ask("  YouTube Data API key", "", secret=True)
    if key and key.startswith("your_"):
        key = ""
    while key and ask_bool("  Test this key against the YouTube API now?", True):
        if validate_youtube_key(key):
            print("  Key works.")
            break
        key = ask("  YouTube Data API key (leave empty to skip)", "", secret=True)
    if not key:
        print("  Skipping - you can add the key later via 'Configuration' below.")
    return key


# --------------------------------------------------------------------------
# Step 4: AI summarisation provider
# --------------------------------------------------------------------------

PROVIDERS = {
    "1": {
        "name": "OpenRouter (recommended - works globally, cheap)",
        "key_var": "OPENROUTER_API_KEY",
        "key_hint": "sk-or-...",
        "base_url_var": "OPENROUTER_BASE_URL",
        "base_url": "https://openrouter.ai/api/v1",
        "model_var": "OPENROUTER_MODEL",
        "model": "deepseek/deepseek-chat-v3-0324:free",
        "flag": "USE_OPENROUTER",
        "url_hint": "https://openrouter.ai/keys",
    },
    "2": {
        "name": "DeepSeek (direct)",
        "key_var": "DEEPSEEK_API_KEY",
        "key_hint": "sk-...",
        "base_url_var": "DEEPSEEK_BASE_URL",
        "base_url": "https://api.deepseek.com",
        "model_var": "DEEPSEEK_MODEL",
        "model": "deepseek-chat",
        "flag": "USE_DEEPSEEK",
        "url_hint": "https://platform.deepseek.com/api_keys",
    },
    "3": {
        "name": "OpenAI",
        "key_var": "OPENAI_API_KEY",
        "key_hint": "sk-...",
        "base_url_var": None,
        "base_url": None,
        "model_var": "OPENAI_MODEL",
        "model": "gpt-4",
        "flag": None,
        "url_hint": "https://platform.openai.com/api-keys",
    },
    "4": {
        "name": "None - skip AI summarisation for now",
        "key_var": None,
    },
}


def configure_ai():
    print()
    print("  Choose the AI provider used to summarise videos:")
    for choice, spec in PROVIDERS.items():
        print(f"    {choice}. {spec['name']}")
    while True:
        choice = ask("  Provider", "1")
        if choice in PROVIDERS:
            break
        print("  Please enter 1, 2, 3 or 4.")

    spec = PROVIDERS[choice]
    result = {k: None for k in (
        "OPENROUTER_API_KEY", "DEEPSEEK_API_KEY", "OPENAI_API_KEY",
        "OPENROUTER_BASE_URL", "DEEPSEEK_BASE_URL",
        "OPENROUTER_MODEL", "DEEPSEEK_MODEL",
        "OPENAI_MODEL")}
    # Booleans must always be "True" or "False" - empty values in .env
    # break pydantic's bool parsing at startup.
    result["USE_OPENROUTER"] = "False"
    result["USE_DEEPSEEK"] = "False"
    if spec["key_var"] is None:
        print("  Skipping AI summarisation - it can be enabled later by")
        print("  editing .env or re-running this installer.")
        return result

    print(f"  Get an API key at: {spec['url_hint']}")
    key = ask(f"  {spec['name'].split(' (')[0]} API key", "", secret=True)
    while not key:
        key = ask("  API key is required for AI summaries (empty = skip AI)",
                  "", secret=True)
        if not key:
            print("  Skipping AI summarisation.")
            return result

    result[spec["key_var"]] = key
    if spec["flag"]:
        result[spec["flag"]] = "True"
    if spec["base_url_var"]:
        result[spec["base_url_var"]] = spec["base_url"]
    result[spec["model_var"]] = ask(
        f"  Model", spec["model"])
    return result


# --------------------------------------------------------------------------
# Step 5: Crawler / scheduler options
# --------------------------------------------------------------------------

def configure_crawler():
    print()
    print("  Crawler behaviour (press Enter to accept the defaults):")
    max_videos = ask_int("  Max videos fetched per channel", 30)
    delay = ask_int("  Delay between API calls (seconds)", 1)
    auto_summarize = ask_bool("  Auto-generate AI summaries after crawling?", True)
    scheduler = ask_bool("  Enable the daily crawl scheduler?", False)
    daily_time = "02:00"
    if scheduler:
        while True:
            daily_time = ask("  Daily crawl time HH:MM (24h)", "02:00")
            parts = daily_time.split(":")
            if (len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit()
                    and 0 <= int(parts[0]) <= 23 and 0 <= int(parts[1]) <= 59):
                break
            print("  Please use HH:MM, e.g. 02:00")
    return {
        "MAX_VIDEOS_PER_CHANNEL": max_videos,
        "CRAWL_DELAY_SECONDS": delay,
        "AUTO_SUMMARIZE": "True" if auto_summarize else "False",
        "ENABLE_SCHEDULER": "True" if scheduler else "False",
        "DAILY_CRAWL_TIME": daily_time,
    }


# --------------------------------------------------------------------------
# .env writing
# --------------------------------------------------------------------------

def write_env(config):
    lines = [
        "# Generated by install.py - edit freely or re-run the installer.",
        "",
        "# Application",
        f"APP_NAME={config['APP_NAME']}",
        f"DEBUG={config['DEBUG']}",
        "",
        "# Database",
        f"DATABASE_URL={config['DATABASE_URL']}",
        "",
        "# YouTube API",
        f"YOUTUBE_API_KEY={config['YOUTUBE_API_KEY'] or ''}",
        "",
        "# AI Summarisation",
    ]
    for var in ("OPENAI_API_KEY", "OPENAI_MODEL",
                "DEEPSEEK_API_KEY", "DEEPSEEK_BASE_URL", "DEEPSEEK_MODEL",
                "OPENROUTER_API_KEY", "OPENROUTER_BASE_URL", "OPENROUTER_MODEL",
                "USE_OPENROUTER", "USE_DEEPSEEK"):
        value = config.get(var)
        lines.append(f"{var}={value if value not in (None, '') else ''}")
    lines += [
        "",
        "# Crawler Settings",
        f"MAX_CONCURRENT_CRAWLS={config['MAX_CONCURRENT_CRAWLS']}",
        f"MAX_VIDEOS_PER_CHANNEL={config['MAX_VIDEOS_PER_CHANNEL']}",
        f"CRAWL_DELAY_SECONDS={config['CRAWL_DELAY_SECONDS']}",
        "",
        "# Summarisation",
        f"AUTO_SUMMARIZE={config['AUTO_SUMMARIZE']}",
        f"SUMMARY_STYLE={config['SUMMARY_STYLE']}",
        "",
        "# Scheduler",
        f"ENABLE_SCHEDULER={config['ENABLE_SCHEDULER']}",
        f"DAILY_CRAWL_TIME={config['DAILY_CRAWL_TIME']}",
    ]
    with open(ENV_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"\n  Configuration written to {ENV_FILE}")


def summarise_config(config):
    print_header("Installation summary")
    db = config["DATABASE_URL"]
    yt = "configured" if config["YOUTUBE_API_KEY"] else "not set"
    if config["USE_OPENROUTER"] == "True":
        ai = f"OpenRouter ({config['OPENROUTER_MODEL']})"
    elif config["USE_DEEPSEEK"] == "True":
        ai = f"DeepSeek ({config['DEEPSEEK_MODEL']})"
    elif config["OPENAI_API_KEY"]:
        ai = f"OpenAI ({config['OPENAI_MODEL']})"
    else:
        ai = "disabled"
    scheduler = (f"enabled, daily at {config['DAILY_CRAWL_TIME']}"
                 if config["ENABLE_SCHEDULER"] == "True" else "disabled")
    print(f"  Database        : {db}")
    print(f"  YouTube API key : {yt}")
    print(f"  AI provider     : {ai}")
    print(f"  Max videos/ch.  : {config['MAX_VIDEOS_PER_CHANNEL']}")
    print(f"  Scheduler       : {scheduler}")


# --------------------------------------------------------------------------
# Main wizard
# --------------------------------------------------------------------------

def main():
    print_header("YouTube Summariser - Installation Wizard")
    non_interactive = "--yes" in sys.argv

    # --- Step 1: environment & dependencies -------------------------------
    print_step(1, 5, "Checking Python and installing dependencies")
    python, version = find_python()
    if not python:
        print("  ERROR: Python 3.9+ is required but was not found.")
        print("  Install it from https://www.python.org/downloads/ and")
        print("  make sure 'Add to PATH' is selected, then re-run this script.")
        sys.exit(1)
    print(f"  Found {version}")
    if not create_venv(python):
        sys.exit(1)
    if not install_dependencies():
        sys.exit(1)

    # --- Steps 2-5: configuration -----------------------------------------
    print_header("Deployment configuration")
    print("Press Enter at any prompt to accept the value shown in [brackets].")

    if non_interactive:
        config = {
            "APP_NAME": "YouTube Summariser",
            "DEBUG": "True",
            "DATABASE_URL": "sqlite:///./data/database.db",
            "YOUTUBE_API_KEY": "",
            "MAX_CONCURRENT_CRAWLS": 3,
            "MAX_VIDEOS_PER_CHANNEL": 30,
            "CRAWL_DELAY_SECONDS": 1,
            "AUTO_SUMMARIZE": "True",
            "SUMMARY_STYLE": "concise",
            "ENABLE_SCHEDULER": "False",
            "DAILY_CRAWL_TIME": "02:00",
            "OPENAI_API_KEY": "", "OPENAI_MODEL": "gpt-4",
            "DEEPSEEK_API_KEY": "", "DEEPSEEK_BASE_URL": "",
            "DEEPSEEK_MODEL": "deepseek-chat", "USE_DEEPSEEK": "False",
            "OPENROUTER_API_KEY": "", "OPENROUTER_BASE_URL": "",
            "OPENROUTER_MODEL": "deepseek/deepseek-chat-v3-0324:free",
            "USE_OPENROUTER": "False",
        }
    else:
        config = {
            "APP_NAME": ask("Application name", "YouTube Summariser"),
            "DEBUG": "True" if ask_bool("Enable debug mode?", True) else "False",
            "DATABASE_URL": configure_database(),
            "YOUTUBE_API_KEY": configure_youtube(),
        }
        ai = configure_ai()
        config.update(ai)
        config["MAX_CONCURRENT_CRAWLS"] = 3
        config["SUMMARY_STYLE"] = "concise"
        config.update(configure_crawler())

    write_env(config)
    summarise_config(config)

    print_header("Installation complete")
    print("  Start the application with:")
    if IS_WINDOWS:
        print(f"    {VENV_DIR}\\Scripts\\python.exe run.py")
        print("  or activate the venv first:")
        print(f"    {VENV_DIR}\\Scripts\\activate")
    else:
        print(f"    {VENV_DIR}/bin/python run.py")
    print("  Then open http://127.0.0.1:5000 in your browser.")
    print()
    print("  To change any of these settings later:")
    print("    - edit the .env file, or")
    print("    - re-run:  python install.py")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nInstallation cancelled - nothing was changed except .env")
        print("(if you had got that far). Re-run 'python install.py' to retry.")
        sys.exit(1)
