import time
from pyocd.core.helpers import ConnectHelper

session = ConnectHelper.session_with_chosen_probe(target_override='py32f002bx5')
# Do not init board
session.open(init_board=False)

target = session.target
# DHCSR = 0xE000EDF0
target.dp.write_ap(0x04, 0xE000EDF0)
# C_DEBUGEN | C_HALT = 0xA05F0003
target.dp.write_ap(0x0C, 0xA05F0003)

print("HALT SENT!")

# Now mass erase
print("Mass erasing...")
target.mass_erase()
print("Erased!")
session.close()
