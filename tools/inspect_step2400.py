import json
import sys

sys.stdout.reconfigure(encoding='utf-8')
p = r'C:\Users\Salomanov\.gemini\antigravity\brain\d6639f34-b76e-409c-956b-c6069420c689\.system_generated\logs\transcript.jsonl'

with open(p, 'r', encoding='utf-8') as f:
    for line in f:
        try:
            d = json.loads(line)
        except Exception:
            continue
        step = d.get('step_index', 0)
        if 2390 <= step <= 2485:
            typ = d.get('type')
            content = d.get('content', '')
            if typ == 'USER_INPUT':
                print(f"\n>>> USER (Step {step}): {content.strip()}")
            elif typ == 'PLANNER_RESPONSE':
                th = d.get('thinking', '')
                if any(k in th.lower() for k in ['биты', 'кадр', 'frame', 'протокол', '04', 'сдвиг', 'таблиц', 'decod']):
                    print(f"\n[AI Thinking Step {step}]: {th[:250]}...")
