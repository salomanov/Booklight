import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer
import dm02i_studio

app = QApplication(sys.argv)
win = dm02i_studio.DM02iStudio()

success = False

def check_telem(data):
    global success
    success = True
    print(f"SUCCESS: magic=0x{data['magic']:08X}, step={data['step']}/{data['total']}, pair={data['h_name']}->{data['l_name']}, VDD={data['vdd_mv']}mV, HB={data['hb']}")
    win.worker.stop()
    app.quit()

win.worker.telemetry_updated.connect(check_telem)

def on_timeout():
    if not success:
        print("FAIL: Timeout waiting for telemetry")
    win.worker.stop()
    app.quit()

QTimer.singleShot(7000, on_timeout)
app.exec()
if success:
    sys.exit(0)
else:
    sys.exit(1)
