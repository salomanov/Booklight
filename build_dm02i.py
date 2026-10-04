import os
import sys
import subprocess

TOOLCHAIN_BIN = r"C:\Users\Salomanov\AppData\Local\Programs\arm-toolchain\xpack-arm-none-eabi-gcc-13.2.1-1.1\bin"
CC = os.path.join(TOOLCHAIN_BIN, "arm-none-eabi-gcc.exe")
OBJCOPY = os.path.join(TOOLCHAIN_BIN, "arm-none-eabi-objcopy.exe")
SIZE = os.path.join(TOOLCHAIN_BIN, "arm-none-eabi-size.exe")

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_DIR = os.path.join(ROOT_DIR, "py32c642_vape")
CUSTOM_DIR = os.path.join(ROOT_DIR, "custom_firmware")
TOP = REPO_DIR
BUILD_DIR = os.path.join(CUSTOM_DIR, "build")
os.makedirs(BUILD_DIR, exist_ok=True)

INCLUDES = [
    CUSTOM_DIR,
    os.path.join(TOP, "Libraries", "CMSIS", "Core", "Include"),
    os.path.join(TOP, "Libraries", "CMSIS", "Device", "PY32F0xx", "Include"),
    os.path.join(TOP, "Libraries", "PY32F002B_HAL_Driver", "Inc"),
    os.path.join(TOP, "Libraries", "PY32F002B_HAL_BSP", "Inc"),
]

CFLAGS = [
    "-D", "PY32F002Bx5",
    "-mthumb",
    "-mcpu=cortex-m0plus",
    "-std=c99",
    "-Os",
    "-Wall",
    "-ffunction-sections",
    "-fdata-sections"
]

LDSCRIPT = os.path.join(TOP, "Libraries", "LDScripts", "py32f002bx5.ld")

LDFLAGS = [
    "-mthumb",
    "-mcpu=cortex-m0plus",
    "-specs=nano.specs",
    "-specs=nosys.specs",
    "-static",
    "-lc",
    "-lm",
    f"-Wl,-Map={os.path.join(BUILD_DIR, 'dm02i_firmware.map')}",
    "-Wl,--gc-sections",
    "-Wl,--print-memory-usage",
    f"-T{LDSCRIPT}"
]

INC_FLAGS = []
for inc in INCLUDES:
    INC_FLAGS.extend(["-I", inc])

SRC_FILES = [
    os.path.join(CUSTOM_DIR, "main_dm02i.c"),
    os.path.join(CUSTOM_DIR, "dm02i_display.c"),
    os.path.join(CUSTOM_DIR, "py32_dm02i_board.c"),
    os.path.join(CUSTOM_DIR, "dm02i_it.c"),
    os.path.join(CUSTOM_DIR, "py32f002b_hal_msp.c"),
    # HAL Drivers
    os.path.join(TOP, "Libraries", "PY32F002B_HAL_Driver", "Src", "py32f002b_hal.c"),
    os.path.join(TOP, "Libraries", "PY32F002B_HAL_Driver", "Src", "py32f002b_hal_cortex.c"),
    os.path.join(TOP, "Libraries", "PY32F002B_HAL_Driver", "Src", "py32f002b_hal_rcc.c"),
    os.path.join(TOP, "Libraries", "PY32F002B_HAL_Driver", "Src", "py32f002b_hal_rcc_ex.c"),
    os.path.join(TOP, "Libraries", "PY32F002B_HAL_Driver", "Src", "py32f002b_hal_gpio.c"),
    os.path.join(TOP, "Libraries", "PY32F002B_HAL_Driver", "Src", "py32f002b_hal_adc.c"),
    os.path.join(TOP, "Libraries", "PY32F002B_HAL_Driver", "Src", "py32f002b_hal_pwr.c"),
    # CMSIS System & Startup
    os.path.join(TOP, "Libraries", "CMSIS", "Device", "PY32F0xx", "Source", "system_py32f002b.c"),
    os.path.join(TOP, "Libraries", "CMSIS", "Device", "PY32F0xx", "Source", "gcc", "startup_py32f002b.s"),
]

def main():
    print("=======================================================")
    print("  КОМПИЛЯЦИЯ ПРОШИВКИ DM02i V03 (PUYA PY32C642)")
    print("=======================================================")
    obj_files = []
    
    for src in SRC_FILES:
        base_name = os.path.splitext(os.path.basename(src))[0] + ".o"
        obj_path = os.path.join(BUILD_DIR, base_name)
        obj_files.append(obj_path)
        
        cmd = [CC] + CFLAGS + INC_FLAGS + ["-c", src, "-o", obj_path]
        print(f"[*] Compiling {os.path.basename(src)}...")
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            print(f"[!] Ошибка компиляции {src}:")
            print(res.stderr)
            sys.exit(1)
            
    elf_path = os.path.join(BUILD_DIR, "dm02i_firmware.elf")
    bin_path = os.path.join(BUILD_DIR, "dm02i_firmware.bin")
    
    print("\n[*] Линковка dm02i_firmware.elf...")
    link_cmd = [CC] + LDFLAGS + obj_files + ["-o", elf_path]
    res = subprocess.run(link_cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print("[!] Ошибка линковки:")
        print(res.stderr)
        sys.exit(1)
        
    print(f"[*] Генерация бинарника {bin_path}...")
    objcopy_cmd = [OBJCOPY, "-O", "binary", elf_path, bin_path]
    res = subprocess.run(objcopy_cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print("[!] Ошибка objcopy:")
        print(res.stderr)
        sys.exit(1)
        
    print("\n[+] УСПЕШНО! Размер прошивки:")
    subprocess.run([SIZE, elf_path])
    print(f"[+] Бинарный файл готов: {bin_path} ({os.path.getsize(bin_path)} байт)")

if __name__ == "__main__":
    main()
