import os

def fix_file(filename, lines):
    content = "\r\n".join(lines) + "\r\n"
    with open(filename, "wb") as f:
        f.write(content.encode("utf-8"))
    print(f"Fixed {filename} with CRLF line endings.")

fix_file("run_dm02i_studio.bat", [
    "@echo off",
    "chcp 65001 >nul",
    "title DM02i Studio",
    "cd /d \"%~dp0\"",
    "python dm02i_studio.py",
    "if errorlevel 1 pause"
])

fix_file("run_screen_hunter.bat", [
    "@echo off",
    "chcp 65001 >nul",
    "title DM02i Screen Hunter",
    "cd /d \"%~dp0\"",
    "python tools\\screen_hunter.py",
    "pause"
])
