import os
import sys
import subprocess

TOOLCHAIN_BIN = r"C:\Users\Salomanov\AppData\Local\Programs\arm-toolchain\xpack-arm-none-eabi-gcc-13.2.1-1.1\bin"
CC = os.path.join(TOOLCHAIN_BIN, "arm-none-eabi-gcc.exe")
OBJCOPY = os.path.join(TOOLCHAIN_BIN, "arm-none-eabi-objcopy.exe")

REPO_DIR = r"c:\Users\Salomanov\Desktop\ВЕЙП\py32c642_vape"
CUSTOM_DIR = r"c:\Users\Salomanov\Desktop\ВЕЙП\custom_firmware"
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
    f"-Wl,-Map={os.path.join(BUILD_DIR, 'firmware.map')}",
    "-Wl,--gc-sections",
    "-Wl,--print-memory-usage",
    f"-T{LDSCRIPT}"
]

INC_FLAGS = []
for inc in INCLUDES:
    INC_FLAGS.extend(["-I", inc])

SRC_FILES = [
    os.path.join(CUSTOM_DIR, "main.c"),
    os.path.join(CUSTOM_DIR, "book_light.c"),
    os.path.join(CUSTOM_DIR, "gyver_ubutton.c"),
    os.path.join(CUSTOM_DIR, "gyver_rgbmath.c"),
    os.path.join(CUSTOM_DIR, "gyver_led.c"),
    os.path.join(CUSTOM_DIR, "fh8016_py32.c"),
    os.path.join(CUSTOM_DIR, "py32f002b_it.c"),
    os.path.join(CUSTOM_DIR, "py32f002b_hal_msp.c"),
    # HAL
    os.path.join(TOP, "Libraries", "PY32F002B_HAL_Driver", "Src", "py32f002b_hal.c"),
    os.path.join(TOP, "Libraries", "PY32F002B_HAL_Driver", "Src", "py32f002b_hal_cortex.c"),
    os.path.join(TOP, "Libraries", "PY32F002B_HAL_Driver", "Src", "py32f002b_hal_rcc.c"),
    os.path.join(TOP, "Libraries", "PY32F002B_HAL_Driver", "Src", "py32f002b_hal_rcc_ex.c"),
    os.path.join(TOP, "Libraries", "PY32F002B_HAL_Driver", "Src", "py32f002b_hal_gpio.c"),
    os.path.join(TOP, "Libraries", "PY32F002B_HAL_Driver", "Src", "py32f002b_hal_adc.c"),
    os.path.join(TOP, "Libraries", "PY32F002B_HAL_Driver", "Src", "py32f002b_hal_pwr.c"),
    # CMSIS
    os.path.join(TOP, "Libraries", "CMSIS", "Device", "PY32F0xx", "Source", "system_py32f002b.c"),
    os.path.join(TOP, "Libraries", "CMSIS", "Device", "PY32F0xx", "Source", "gcc", "startup_py32f002b.s"),
]

def main():
    print("--- КОМПИЛЯЦИЯ КАСТОМНОЙ ПРОШИВКИ (BATTERY & CHARGE) ---")
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
            
    elf_path = os.path.join(BUILD_DIR, "battery_firmware.elf")
    bin_path = os.path.join(BUILD_DIR, "battery_firmware.bin")
    
    print("Linking battery_firmware.elf...")
    link_cmd = [CC] + LDFLAGS + obj_files + ["-o", elf_path]
    res = subprocess.run(link_cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print("Link error:")
        print(res.stderr)
        sys.exit(1)
    print(res.stdout)
    
    print("Generating binary battery_firmware.bin...")
    objcopy_cmd = [OBJCOPY, "-I", "elf32-littlearm", "-O", "binary", elf_path, bin_path]
    res = subprocess.run(objcopy_cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print("Objcopy error:")
        print(res.stderr)
        sys.exit(1)
        
    bin_size = os.path.getsize(bin_path)
    print(f"SUCCESS! Created {bin_path} ({bin_size} bytes)")

if __name__ == '__main__':
    main()
