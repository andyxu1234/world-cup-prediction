import os, subprocess

path = "server/app/static/odds.v15.js"

with open(path, 'r', encoding='utf-8-sig') as f:
    content = f.read()

# Replace the corrupted em dashes and other known bad chars
# The corruption from Set-Content created garbled multi-byte sequences
# Strategy: count bad chars and report
bad = [c for c in content if ord(c) > 127 and ord(c) < 0x2000 and c not in ' \n\r\t']
print(f"Found {len(bad)} potentially bad chars (ASCII-range high bytes)")
if bad:
    # Show first 20 unique bad chars
    unique = list(set(bad))[:20]
    print(f"Sample bad chars: {[hex(ord(c)) for c in unique]}")
    print(f"Sample bad chars as text: {unique}")

# The real problem: content was read as UTF-8-SIG but chars were already corrupted
# All non-ASCII chars like — ◆ ✕ got corrupted
# Need to count total non-ASCII to understand scope
all_non_ascii = [c for c in content if ord(c) > 127]
print(f"Total chars > 127: {len(all_non_ascii)} out of {len(content)}")
