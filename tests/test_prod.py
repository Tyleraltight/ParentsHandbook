import httpx, json

r = httpx.get('https://parentshandbook.vercel.app/analyze?title=Perfect+Days', timeout=120)
d = r.json()
print(f"Status: {r.status_code}, source: {d.get('source')}")
for k in ['sex_and_nudity','violence_and_gore','profanity','frightening_scenes']:
    if k in d:
        dim = d[k]
        print(f"  {k}: level={dim['level']}, score={dim['score']}, summary={dim['summary'][:60]}")
