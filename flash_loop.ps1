while ($true) {
    $output = python flash_direct.py custom_firmware\build\battery_firmware.bin 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "Success! Launching GUI..."
        Start-Process python -ArgumentList "lamp_controller.py"
        break
    }
    Write-Host "Waiting for device reset..."
    Start-Sleep -Seconds 1
}
