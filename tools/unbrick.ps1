Write-Host ">>> ВНИМАНИЕ! ПРОЦЕДУРА ВОССТАНОВЛЕНИЯ <<<" -ForegroundColor Red
Write-Host "Плата зависла так быстро при старте, что программатор не успевает зацепиться."
Write-Host "СЕЙЧАС ВЫТАЩИ USB ИЗ КОМПЬЮТЕРА." -ForegroundColor Yellow
Write-Host "Потом нажми Enter в этом окне. Скрипт начнет спамить попытки подключения."
Write-Host "КАК ТОЛЬКО нажмешь Enter, СРАЗУ ЖЕ быстро втыкай USB обратно." -ForegroundColor Yellow
Read-Host "Нажми Enter когда готов"

while ($true) {
    Write-Host "Пытаюсь зацепиться и стереть чип..."
    pyocd erase -t py32f002bx5 --chip 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "УСПЕХ! ЧИП СТЕРТ И РАЗБЛОКИРОВАН!" -ForegroundColor Green
        break
    }
}
