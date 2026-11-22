#!/usr/bin/env python3
"""Check that the Higgsfield API secrets work, without generating anything (costs nothing).

Prints only status codes and the shape of the secrets, never their values.
"""
import os
import requests

kid = os.environ.get("HF_API_KEY_ID", "").strip()
sec = os.environ.get("HF_API_KEY_SECRET", "").strip()
print(f"HF_API_KEY_ID: {'set' if kid else 'MISSING'}, length {len(kid)}, contains ':' = {':' in kid}")
print(f"HF_API_KEY_SECRET: {'set' if sec else 'MISSING'}, length {len(sec)}, contains ':' = {':' in sec}")
print(f"Both secrets identical: {kid == sec}")

candidates = []
if ":" in kid:
    candidates.append(("ID secret used as full 'id:secret'", kid))
if ":" in sec and sec != kid:
    candidates.append(("SECRET used as full 'id:secret'", sec))
if kid and sec and kid != sec:
    candidates.append(("ID + ':' + SECRET", f"{kid}:{sec}"))

candidates.append(("CONTROL: deliberately wrong key", "wrong-id:wrong-secret"))
fake = "00000000-0000-0000-0000-000000000000"
for label, cred in candidates:
    for host in ("https://platform.higgsfield.ai", "https://api.higgsfield.ai"):
        try:
            r = requests.get(f"{host}/requests/{fake}/status",
                             headers={"Authorization": f"Key {cred}"}, timeout=30)
            note = {401: "rejected (bad key)", 403: "rejected (no access)",
                    404: "ACCEPTED (key works; test request not found)", 422: "ACCEPTED (key works)",
                    400: "key not rejected (bad request)"}.get(r.status_code, "")
            print(f"{label:38} {host:32} -> {r.status_code} {note} {r.text[:120]!r}")
        except Exception as e:  # noqa: BLE001
            print(f"{label:38} {host:32} -> error {type(e).__name__}")
if not candidates:
    print("No usable key combination found.")
