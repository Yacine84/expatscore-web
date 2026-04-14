# =============================================================================
# main.py — ExpatScore.de Sniper Coordinator
# Version: 1.2 | Groq-Aware Edition
# Changes from 1.1:
#   - Checks GROQ_API_KEY in env validation (warns but does not block startup)
#   - Version bumps logged for both workers
# =============================================================================

import threading
import logging
import time
import sys
import os

# =============================================================================
# LOAD .env FIRST — Before any worker module imports os.getenv()
# =============================================================================

try:
    from dotenv import load_dotenv
    load_dotenv()
    print("[Coordinator] ✅ .env loaded")
except ImportError:
    print("[Coordinator] ⚠  python-dotenv not installed — using system env vars")

# =============================================================================
# SHARED LOGGING
# =============================================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  [%(levelname)s]  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("expatscorebot.log", encoding="utf-8"),
    ],
)

log = logging.getLogger("Coordinator")

# =============================================================================
# IMPORT WORKERS — After .env is loaded and logging is configured
# =============================================================================

import reddit_worker
import youtube_worker

# =============================================================================
# THREAD FACTORY
# =============================================================================

def make_thread(target_fn, name: str) -> threading.Thread:
    return threading.Thread(target=target_fn, name=name, daemon=True)

# =============================================================================
# WORKER WRAPPERS
# =============================================================================

def run_reddit():
    log.info("🟠 [Reddit Worker] Thread started.")
    try:
        reddit_worker.main()
    except Exception as e:
        log.critical(f"💥 [Reddit Worker] Fatal crash: {e}", exc_info=True)

def run_youtube():
    log.info("🔴 [YouTube Worker] Thread started.")
    try:
        youtube_worker.main()
    except Exception as e:
        log.critical(f"💥 [YouTube Worker] Fatal crash: {e}", exc_info=True)

# =============================================================================
# COORDINATOR MAIN
# =============================================================================

def main():
    log.info("=" * 65)
    log.info("🚀 ExpatScore Sniper Coordinator v1.2 — Groq-Aware — Online")
    log.info("   Workers  : RedditWorker 5.3 + YouTubeWorker 1.1")
    log.info("   Scoring  : Groq llama3-8b-8192 (fallback: keyword heuristic)")
    log.info("   Watchdog : Auto-restarts dead threads every 5 min")
    log.info("   Log file : expatscorebot.log")
    log.info("=" * 65)

    # --- Environment validation ---
    missing_critical = []
    missing_warned   = []

    if not os.getenv("N8N_WEBHOOK_URL"):
        missing_critical.append("N8N_WEBHOOK_URL")
    if not os.getenv("YOUTUBE_API_KEY"):
        missing_critical.append("YOUTUBE_API_KEY")
    if not os.getenv("GROQ_API_KEY"):
        # Not critical — fallback scoring kicks in automatically
        missing_warned.append("GROQ_API_KEY")

    if missing_critical:
        log.critical(f"🚫 Missing required .env variables: {missing_critical}")
        log.critical("   Add them to your .env file and restart.")
        sys.exit(1)

    if missing_warned:
        log.warning(f"⚠  GROQ_API_KEY not set — fallback keyword scoring active. "
                    f"Leads will still flow but groq_score will be heuristic-only.")

    log.info("✅ Environment check passed")

    # --- Start Reddit thread ---
    reddit_thread = make_thread(run_reddit, "RedditWorker")
    reddit_thread.start()
    log.info("🟠 Reddit worker launched")

    time.sleep(15)

    youtube_thread = make_thread(run_youtube, "YouTubeWorker")
    youtube_thread.start()
    log.info("🔴 YouTube worker launched")

    log.info("✅ Both workers running. Press Ctrl+C to stop all.")

    # --- Watchdog: auto-restart dead threads ---
    try:
        while True:
            time.sleep(300)

            if not reddit_thread.is_alive():
                log.critical("🟠 [Watchdog] Reddit thread dead — RESTARTING")
                reddit_thread = make_thread(run_reddit, "RedditWorker")
                reddit_thread.start()

            if not youtube_thread.is_alive():
                log.critical("🔴 [Watchdog] YouTube thread dead — RESTARTING")
                youtube_thread = make_thread(run_youtube, "YouTubeWorker")
                youtube_thread.start()

    except KeyboardInterrupt:
        log.info("🔴 Ctrl+C received — shutting down. Goodbye.")
        sys.exit(0)

# =============================================================================
# ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    main()