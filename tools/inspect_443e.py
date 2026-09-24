import json
import sys

sys.stdout.reconfigure(encoding='utf-8')
p = r'C:\Users\Salomanov\.gemini\antigravity\brain\443e4a15-5da5-4694-852c-9d2f6dbadd30\.system_generated\logs\transcript.jsonl'

with open(p, 'r', encoding='utf-8') as f:
    for line in f:
        try:
            d = json.loads(line)
        except Exception:
            continue
        step = d.get('step_index', 0)
        typ = d.get('type')
        content = d.get('content', '')
        if typ == 'USER_INPUT':
            low = content.lower()
            if any(k in low for k in ['диспл', 'экран', 'сегмент', 'кадр', 'бит', 'протокол', 'д1', 'd1', 'тайминг', 'us', 'мкс', 'wire']):
                lines = [l for l in content.splitlines() if not l.startswith('<') and not l.endswith('>')]
                print(f"[443e... Step {step}]: {' '.join(lines).strip()[:180]}")
