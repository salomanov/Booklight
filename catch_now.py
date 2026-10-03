import sys
import os

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT_DIR, "tools"))

import flash_puya_direct

if __name__ == '__main__':
    ok = flash_puya_direct.main()
    sys.exit(0 if ok else 1)
