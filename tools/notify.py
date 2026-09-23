#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
import os
import subprocess

def notify(subject: str, message: str) -> bool:
    """Отправляет уведомление на salomanov@ya.ru через систему mail_system"""
    script = r"C:\mail_system\notify_user.py"
    if not os.path.exists(script):
        print(f"Warn: {script} не найден")
        return False
    try:
        res = subprocess.run([sys.executable, script, subject, message], capture_output=True, text=True, timeout=20)
        out = res.stdout.strip() or res.stderr.strip()
        print(f"[Notify] {out}")
        return res.returncode == 0
    except Exception as e:
        print(f"[Notify Error] {e}")
        return False

if __name__ == "__main__":
    subj = sys.argv[1] if len(sys.argv) > 1 else "Booklight: Готово"
    msg = sys.argv[2] if len(sys.argv) > 2 else "Задача успешно выполнена."
    notify(subj, msg)
