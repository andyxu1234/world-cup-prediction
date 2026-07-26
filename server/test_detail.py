import urllib.request as u
import json
import sys
import time

def get(path):
    r = u.Request(f'http://localhost:8000{path}', headers={'X-Access-Token': '123456'})
    t0 = time.time()
    try:
        b = u.urlopen(r, timeout=20).read().decode()
        dt = time.time() - t0
        return json.loads(b), dt
    except Exception as e:
        return None, f'ERR after {time.time()-t0:.1f}s: {e}'

# Step 1: get matches with predictions
data, dt = get('/api/v1/odds/matches?limit=500')
if data is None:
    print('LIST FAILED:', dt); sys.exit(1)
print(f'LIST: {len(data)} matches in {dt:.2f}s')
hits = [d for d in data if (d.get('predictions_summary') or {}).get('total', 0) > 0]
print(f'  with predictions: {len(hits)}')
if not hits:
    print('NO matches with predictions in DB. Cannot test /match/{id} detail.')
    sys.exit(0)

# Step 2: pick a match and test detail
mid = hits[0]['match_id']
print(f'\nTesting /match/{mid}:')
print(f'  summary: {hits[0]["predictions_summary"]}')
d2, dt2 = get(f'/api/v1/odds/match/{mid}')
if d2 is None:
    print(f'  DETAIL FAILED: {dt2}')
else:
    print(f'  detail in {dt2:.2f}s')
    print(f'  keys: {list(d2.keys())}')
    if d2.get('predictions'):
        ps = d2['predictions']
        print(f'  predictions: {len(ps)}')
        p0 = ps[0]
        print(f'  first pred keys: {list(p0.keys())}')
        print(f'  first pred model_name: {p0.get("model_name")}')
        print(f'  first pred result: {p0.get("result")}')
        print(f'  first pred score: {p0.get("score_home")}:{p0.get("score_away")}')
        print(f'  first pred confidence: {p0.get("confidence")}')
        al = p0.get('analysis') or ''
        print(f'  first pred analysis length: {len(al)}')
        av = p0.get('model_avatar') or ''
        print(f'  first pred avatar length: {len(av)}')
        if av and av.startswith('data:'):
            print(f'  first pred avatar starts with: {av[:60]}...')
    else:
        print('  NO predictions in response body')
