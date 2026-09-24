import json
import sys

sys.stdout.reconfigure(encoding='utf-8')
p = r'C:\Users\Salomanov\.gemini\antigravity\brain\0605278e-5a8b-4a2c-a7ec-7c79c556b0c4\.system_generated\logs\transcript.jsonl'

with open(p, 'r', encoding='utf-8') as f:
    for line in f:
        try:
            d = json.loads(line)
        except Exception:
            continue
        if d.get('type') == 'USER_INPUT':
            txt = d.get('content', '')
            low = txt.lower()
            if any(w in low for w in ['диспл', 'экран', 'fh8016', '1-wire', 'капл', 'молни', 'фары', 'глаз', 'цифр', 'шкал', 'dat']):
                step = d.get('step_index')
                print(f"=== Step {step} ===")
                # Clean up metadata tags
                lines = [l for l in txt.splitlines() if not l.startswith('<') and not l.endswith('>')]
                print('\n'.join(lines).strip())
                print()
