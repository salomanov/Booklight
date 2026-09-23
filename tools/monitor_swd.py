import sys
import time
import pylink

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

def main():
    j = pylink.JLink()
    j.open()
    j.set_tif(pylink.enums.JLinkInterfaces.SWD)
    j.set_speed(500)

    print("=" * 60, flush=True)
    print(">>> МОНИТОР ЛИНИИ SWD (В РЕАЛЬНОМ ВРЕМЕНИ) <<<", flush=True)
    print("Отслеживаю состояние SWDIO (tms) и ответ процессора...", flush=True)
    print("=" * 60, flush=True)

    last_tms = None
    start = time.time()

    while time.time() - start < 60:
        hs = j.hardware_status
        v = hs.VTarget
        tms = hs.tms

        if tms != last_tms:
            last_tms = tms
            status_str = "HIGH (3.3V) [ОТЛИЧНО!]" if tms != 0 else "LOW (0V) [ПРИЖАТО К ЗЕМЛЕ!]"
            print(f"[{time.strftime('%H:%M:%S')}] Питание: {v/1000.0:.2f}V | Линия SWDIO: {status_str}", flush=True)

        if tms != 0:
            try:
                j.coresight_configure()
                dpidr = j.coresight_read(0)
                if dpidr and dpidr != 0xFFFFFFFF and dpidr != 0x00000000:
                    print(f"\n🎉 [УСПЕХ!] ПРОЦЕССОР ВЫШЕЛ НА СВЯЗЬ! DPIDR = 0x{dpidr:08X}", flush=True)
                    break
            except Exception:
                pass

        time.sleep(0.1)

    j.close()

if __name__ == '__main__':
    main()
