import time
from pyocd.core.helpers import ConnectHelper

def spam_connect():
    print('Start spamming connect...')
    while True:
        try:
            session = ConnectHelper.session_with_chosen_probe(target_override='py32f002bx5', connect_mode='under-reset')
            session.open(init_board=False)
            target = session.target
            target.dp.write_ap(0x04, 0xE000EDF0)
            target.dp.write_ap(0x0C, 0xA05F0003)
            print('HALTED!')
            target.mass_erase()
            print('ERASED!')
            session.close()
            break
        except Exception as e:
            pass
spam_connect()
