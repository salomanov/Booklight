import sys
import time
import os

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

from pyocd.core.helpers import ConnectHelper
from pyocd.core.session import Session
from pyocd.flash.file_programmer import FileProgrammer

def log(msg):
    print(msg, flush=True)

bin_file = r"c:\Users\Salomanov\Desktop\ВЕЙП\custom_firmware\build\battery_firmware.bin"
if not os.path.exists(bin_file):
    log(f"Error: {bin_file} not found")
    sys.exit(1)

log("=" * 60)
log("   АВТОМАТИЧЕСКАЯ ПРОШИВКА BOOKLIGHT (ОЖИДАНИЕ USB)")
log("=" * 60)
log("Вставьте программатор (ST-Link / J-Link) в USB-порт компьютера!")

start_time = time.time()
timeout = 90
probe = None

while time.time() - start_time < timeout:
    probes = ConnectHelper.get_all_connected_probes(blocking=False)
    if probes:
        probe = probes[0]
        log(f"\n[✓] Программатор обнаружен в USB: {probe.description}")
        break
    time.sleep(0.5)

if not probe:
    log("\n[X] Таймаут: программатор не был вставлен в USB.")
    sys.exit(1)

log("[*] Подключаюсь к чипу по SWD...")
options = {
    'target_override': 'py32f002bx5',
    'frequency': 500000,
    'connect_mode': 'halt',
    'resume_on_disconnect': False
}

for attempt in range(1, 15):
    try:
        session = Session(probe, options=options, init_board=False)
        session.open(init_board=False)
        session.target.aps.clear()
        session.target.cores.clear()
        seq = session.target.create_init_sequence()
        seq.invoke()
        session.board._inited = True

        log(f"[🔥] Чип успешно захвачен на попытке #{attempt}!")
        log("[*] Заливаю новую прошивку...")
        programmer = FileProgrammer(session)
        programmer.program(bin_file)

        log("\n" + "=" * 60)
        log("   🎉 ПРОШИВКА УСПЕШНО ЗАВЕРШЕНА!")
        log(f"   Записано: {os.path.basename(bin_file)} ({os.path.getsize(bin_file)} байт)")
        log("=" * 60)

        session.target.reset()
        log("[✓] Микроконтроллер перезапущен в рабочий режим!")
        session.close()
        sys.exit(0)

    except Exception as e:
        time.sleep(0.3)

log("\n[X] Не удалось установить связь с чипом по SWD. Проверьте провода GND, CK, DA.")
sys.exit(2)
