#!/usr/bin/env python3
import json
import time
import urllib.request
import ssl
import sys

BACKUP_FILE = "/Users/ingram/Documents/ระบบจัดการโครงการ/technical-water-system/scratch/railway_projects_backup.json"
TARGET_URL = "https://project.technical-water.com/api/db/upload_backup_batch"
AUTH_SECRET = "tw-project-management-super-secret-key-2026"

ctx = ssl._create_unverified_context()
headers = {
    "Authorization": f"Bearer {AUTH_SECRET}",
    "Content-Type": "application/json",
    "User-Agent": "curl/8.7.1"
}

def upload_batch(batch):
    data = json.dumps({"items": batch}).encode("utf-8")
    req = urllib.request.Request(TARGET_URL, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req, context=ctx, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))

def main():
    print(f"[*] Loading backup data from {BACKUP_FILE}...")
    with open(BACKUP_FILE, "r") as f:
        items = json.load(f)
    
    total = len(items)
    print(f"[+] Loaded {total} items to migrate.")
    
    # 1. First, upload all main projects (non-FILE)
    main_projects = [x for x in items if not x['code'].startswith('FILE:')]
    file_items = [x for x in items if x['code'].startswith('FILE:')]
    print(f"[*] Main projects count: {len(main_projects)}, File attachments count: {len(file_items)}")
    
    BATCH_SIZE = 15
    uploaded = 0
    start_time = time.time()
    
    # Upload main projects first in batches
    for i in range(0, len(main_projects), BATCH_SIZE):
        batch = main_projects[i:i + BATCH_SIZE]
        res = upload_batch(batch)
        uploaded += len(batch)
        print(f"[+] Main projects: {uploaded}/{len(main_projects)} uploaded.")
    
    # Upload file attachments in batches
    files_uploaded = 0
    for i in range(0, len(file_items), BATCH_SIZE):
        batch = file_items[i:i + BATCH_SIZE]
        retries = 3
        while retries > 0:
            try:
                res = upload_batch(batch)
                files_uploaded += len(batch)
                elapsed = time.time() - start_time
                percent = (files_uploaded / len(file_items)) * 100
                print(f"[+] Files: {files_uploaded}/{len(file_items)} ({percent:.1f}%) uploaded. [{int(elapsed)}s]")
                break
            except Exception as e:
                retries -= 1
                print(f"[!] Error on batch {i}-{i+len(batch)}: {e}. Retries left: {retries}")
                time.sleep(2)
                if retries == 0:
                    raise
    
    print(f"\n[SUCCESS] Completed migration of {uploaded + files_uploaded} total records in {int(time.time() - start_time)}s!")

if __name__ == "__main__":
    main()
