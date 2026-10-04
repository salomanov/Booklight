import pylink, time, sys

j = pylink.JLink()
j.open('774496021')
j.set_tif(pylink.enums.JLinkInterfaces.SWD)
j.set_speed(1000)
j.coresight_configure()
j.coresight_write(0, 0x1E, ap=False)
j.coresight_write(1, 0x50000000, ap=False)
j.coresight_write(2, 0x00000000, ap=False)
j.coresight_write(0, 0x23000002, ap=True)

base = 0x2000000C

def write_mem(addr, val):
    j.coresight_write(1, addr, ap=True)
    j.coresight_write(3, val, ap=True)

# Known 5 pins: 0 (PB0), 1 (PB1), 2 (PB2), 3 (PB3), 4 (PB5)
known_pins = [0, 1, 2, 3, 4]

# All 20 pairs between known 5 pins (the 19 found segments)
base_pairs = []
for h in known_pins:
    for l in known_pins:
        if h != l:
            base_pairs.append((h, l))

candidates = [
    (8,  "PA3"),
    (9,  "PA4"),
    (10, "PA5"),
    (11, "PA6"),
    (12, "PA7"),
    (13, "PC1"),
    (14, "PB7"),
    (5,  "PB4"),
    (6,  "PA0"),
    (7,  "PA1"),
]

def activate_candidate(cand_idx, cand_name):
    pairs = list(base_pairs) # 20 known pairs
    for k in known_pins:
        pairs.append((cand_idx, k)) # Cand (+) -> Known (-)
        pairs.append((k, cand_idx)) # Known (+) -> Cand (-)
    
    # Write mux_count (up to 30)
    write_mem(base + 0x44, min(len(pairs), 32))
    for idx, (h, l) in enumerate(pairs[:32]):
        packed = ((h & 0xFF) << 8) | (l & 0xFF)
        write_mem(base + 0x48 + idx * 4, packed)
    
    # Mode 4: Multiplex
    write_mem(base + 0x04, 4)
    print(f"\n[*] АКТИВИРОВАН КАНДИДАТ: {cand_name} (индекс {cand_idx})")
    print(f"     Включено 30 комбинаций ({len(base_pairs)} базовых + 10 с {cand_name})")

if __name__ == '__main__':
    target = sys.argv[1] if len(sys.argv) > 1 else None
    if target:
        for idx, name in candidates:
            if name.upper() == target.upper():
                activate_candidate(idx, name)
                break
        else:
            print("Кандидат не найден:", target)
    else:
        print("Автоматический перебор кандидатов по 4 секунды на каждый...")
        for idx, name in candidates:
            activate_candidate(idx, name)
            time.sleep(4)
    j.close()
