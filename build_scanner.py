import os
import sys
import subprocess

TOOLCHAIN_BIN = r"C:\Users\Salomanov\AppData\Local\Programs\arm-toolchain\xpack-arm-none-eabi-gcc-13.2.1-1.1\bin"
CC = os.path.join(TOOLCHAIN_BIN, "arm-none-eabi-gcc.exe")
OBJCOPY = os.path.join(TOOLCHAIN_BIN, "arm-none-eabi-objcopy.exe")

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_DIR = os.path.join(ROOT_DIR, "py32c642_vape")
CUSTOM_DIR = os.path.join(ROOT_DIR, "custom_firmware")
BUILD_DIR = os.path.join(CUSTOM_DIR, "build")
os.makedirs(BUILD_DIR, exist_ok=True)

INCLUDES = [
    CUSTOM_DIR,
    os.path.join(REPO_DIR, "Libraries", "CMSIS", "Core", "Include"),
    os.path.join(REPO_DIR, "Libraries", "CMSIS", "Device", "PY32F0xx", "Include"),
    os.path.join(REPO_DIR, "Libraries", "PY32F002B_HAL_Driver", "Inc"),
    os.path.join(REPO_DIR, "Libraries", "PY32F002B_HAL_BSP", "Inc"),
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

LDSCRIPT = os.path.join(REPO_DIR, "Libraries", "LDScripts", "py32f002bx5.ld")

LDFLAGS = [
    "-mthumb",
    "-mcpu=cortex-m0plus",
    "-specs=nano.specs",
    "-specs=nosys.specs",
    "-static",
    "-lc",
    "-lm",
    f"-Wl,-Map={os.path.join(BUILD_DIR, 'scanner.map')}",
    "-Wl,--gc-sections",
    "-Wl,--print-memory-usage",
    f"-T{LDSCRIPT}"
]

INC_FLAGS = []
for inc in INCLUDES:
    INC_FLAGS.extend(["-I", inc])

SRC_FILES = [
    os.path.join(CUSTOM_DIR, "scanner_main.c"),
    os.path.join(CUSTOM_DIR, "py32f002b_it.c"),
    os.path.join(CUSTOM_DIR, "py32f002b_hal_msp.c"),
    os.path.join(REPO_DIR, "Libraries", "PY32F002B_HAL_Driver", "Src", "py32f002b_hal.c"),
    os.path.join(REPO_DIR, "Libraries", "PY32F002B_HAL_Driver", "Src", "py32f002b_hal_cortex.c"),
    os.path.join(REPO_DIR, "Libraries", "PY32F002B_HAL_Driver", "Src", "py32f002b_hal_rcc.c"),
    os.path.join(REPO_DIR, "Libraries", "PY32F002B_HAL_Driver", "Src", "py32f002b_hal_rcc_ex.c"),
    os.path.join(REPO_DIR, "Libraries", "PY32F002B_HAL_Driver", "Src", "py32f002b_hal_gpio.c"),
    os.path.join(REPO_DIR, "Libraries", "PY32F002B_HAL_Driver", "Src", "py32f002b_hal_adc.c"),
    os.path.join(REPO_DIR, "Libraries", "PY32F002B_HAL_Driver", "Src", "py32f002b_hal_pwr.c"),
    os.path.join(REPO_DIR, "Libraries", "CMSIS", "Device", "PY32F0xx", "Source", "system_py32f002b.c"),
    os.path.join(REPO_DIR, "Libraries", "CMSIS", "Device", "PY32F0xx", "Source", "gcc", "startup_py32f002b.s"),
]

def main():
    print("--- КОМПИЛЯЦИЯ СКАНЕРА ЖЕЛЕЗА DM02i V03 (PIN HUNTER) ---")
    obj_files = []
    
    for src in SRC_FILES:
        base_name = os.path.splitext(os.path.basename(src))[0] + ".o"
        obj_path = os.path.join(BUILD_DIR, base_name)
        obj_files.append(obj_path)
        
        cmd = [CC] + CFLAGS + INC_FLAGS + ["-c", src, "-o", obj_path]
        print(f"Compiling {os.path.basename(src)}...")
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            print(f"Error compiling {src}:")
            print(res.stderr)
            sys.exit(1)
            
    elf_path = os.path.join(BUILD_DIR, "scanner.elf")
    bin_path = os.path.join(BUILD_DIR, "scanner.bin")
    
    print("Linking scanner.elf...")
    link_cmd = [CC] + LDFLAGS + obj_files + ["-o", elf_path]
    res = subprocess.run(link_cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print("Link error:")
        print(res.stderr)
        sys.exit(1)
        
    print(res.stdout)
    
    print("Generating scanner.bin...")
    objcopy_cmd = [OBJCOPY, "-O", "binary", elf_path, bin_path]
    res = subprocess.run(objcopy_cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print("Objcopy error:")
        print(res.stderr)
        sys.exit(1)
        
    size = os.path.getsize(bin_path)
    print(f"\n[OK] Сборка завершена успешно!")
    print(f"     Файл: {bin_path}")
    print(f"     Размер: {size} байт")

if __name__ == '__main__':
    main()
