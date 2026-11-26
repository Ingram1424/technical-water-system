#!/usr/bin/env python3
import sys
import time
import json
import ssl
import urllib.request

COOLIFY_URL = "https://coolify-pricedee.langkaamulets.com/api/v1"
ROOT_TOKEN = "8|w4NOuX3AX44RXlzfcM37g2Gz46ArW9P2j0ezLxZVd75a19e3"

APPS = {
    "tw": "l33ihcvrp6oc39u3rriar3aw",        # technical-water-web (project.technical-water.com)
    "permpoon": "09o3dfhsevqv4fqomrgeasag",  # permpoon-web (project.phoemphoon.com)
}
DEFAULT_APP_UUID = APPS["tw"]

ctx = ssl._create_unverified_context()
headers = {
    "Authorization": f"Bearer {ROOT_TOKEN}",
    "User-Agent": "curl/8.7.1",
    "Content-Type": "application/json"
}

def api_call(path, method="GET", data=None, timeout=30):
    url = f"{COOLIFY_URL}{path}"
    req = urllib.request.Request(url, headers=headers, method=method)
    body = json.dumps(data).encode("utf-8") if data else None
    with urllib.request.urlopen(req, data=body, context=ctx, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))

def trigger_deploy(app_uuid):
    resolved_uuid = APPS.get(app_uuid, app_uuid)
    print(f"[*] Triggering deployment for App UUID: {resolved_uuid}...")
    res = api_call(f"/deploy?uuid={resolved_uuid}", method="POST")
    deployments = res.get("deployments", [])
    if not deployments:
        print(f"[!] Warning: No deployment created in response: {res}")
        return None
    dep_uuid = deployments[0].get("deployment_uuid")
    print(f"[+] Deployment queued with UUID: {dep_uuid}")
    return dep_uuid

def wait_for_deployment(dep_uuid, max_wait=360):
    print(f"[*] Waiting for deployment {dep_uuid} to finish...")
    start_time = time.time()
    last_status = None
    while time.time() - start_time < max_wait:
        try:
            dep_info = api_call(f"/deployments/{dep_uuid}", timeout=15)
            status = dep_info.get("status")
            if status != last_status:
                print(f"[*] Status: {status} ({int(time.time() - start_time)}s elapsed)")
                last_status = status
            if status in ["finished", "success"]:
                print(f"[+] Deployment finished successfully!")
                return True
            elif status in ["failed", "error", "cancelled"]:
                print(f"[-] Deployment {status}!")
                return False
        except Exception as e:
            print(f"[!] Polling warning: {e}")
        time.sleep(5)
    print(f"[-] Deployment timed out after {max_wait} seconds.")
    return False

if __name__ == "__main__":
    app_target = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_APP_UUID
    dep_uuid = trigger_deploy(app_target)
    if dep_uuid:
        success = wait_for_deployment(dep_uuid)
        sys.exit(0 if success else 1)
    else:
        sys.exit(1)
