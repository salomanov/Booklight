import json
import sys
import glob
import os

sys.stdout.reconfigure(encoding='utf-8')

for p in glob.glob(r'C:\Users\Salomanov\.gemini\antigravity\brain\*\.system_generated\logs\transcript.jsonl'):
    conv_id = p.split(os.sep)[-4]
    # Check if this conversation is about vape / fh8016
    has_fh8016 = False
    display_matches = []
    
    with open(p, 'r', encoding='utf-8') as f:
        for line in f:
            try:
                d = json.loads(line)
            except Exception:
                continue
            txt = d.get('content', '')
            if 'fh8016' in txt.lower():
                has_fh8016 = True
            if d.get('type') == 'USER_INPUT':
                low = txt.lower()
                if any(w in low for w in ['fh8016', 'диспл', 'экран']):
                    step = d.get('step_index')
                    lines = [l for l in txt.splitlines() if not l.startswith('<') and not l.endswith('>')]
                    clean = '\n'.join(lines).strip()
                    if clean:
                        display_matches.append((step, clean))
                        
    if has_fh8016:
        print(f"\n=======================================================")
        print(f"FOUND CONVERSATION: {conv_id} (matches: {len(display_matches)})")
        print(f"=======================================================")
        for step, msg in display_matches[:15]:
            print(f"[{conv_id} Step {step}]: {msg}\n")
