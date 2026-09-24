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
        if 2350 <= step <= 2390:
            src = d.get('source')
            typ = d.get('type')
            content = d.get('content', '')
            if typ == 'USER_INPUT':
                print(f"\n>>> USER (Step {step}): {content.strip()}")
            elif typ == 'PLANNER_RESPONSE':
                # find text or reasoning
                th = d.get('thinking', '')
                if '04' in th or 'offset' in th or 'бит' in th or 'display' in th:
                    print(f"\n[AI Thinking Step {step}]: {th[:300]}...")
            elif typ == 'MODEL' or typ == 'GENERIC':
                if '04' in content or 'сдвиг' in content or 'бит' in content:
                    print(f"[Content Step {step}]: {content[:300]}...")
