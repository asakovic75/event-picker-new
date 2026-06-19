import asyncio
import schedule
import time
from datetime import datetime
import threading
from .parser import run_parser

def run_parser_wrapper():
    print(f"[{datetime.now()}] Starting scheduled parser...")
    try:
        run_parser()
        print(f"[{datetime.now()}] Parser completed successfully")
    except Exception as e:
        print(f"[{datetime.now()}] Parser error: {e}")

def start_scheduler():
    schedule.every().monday.at("03:00").do(run_parser_wrapper)
    schedule.every().thursday.at("03:00").do(run_parser_wrapper)
    
    print(f"[{datetime.now()}] Scheduler started!")
    print("Parser will run every Monday and Thursday at 3:00 AM")
    
    while True:
        schedule.run_pending()
        time.sleep(60)

def run_scheduler_in_background():
    thread = threading.Thread(target=start_scheduler, daemon=True)
    thread.start()
    return thread

if __name__ == "__main__":
    start_scheduler()