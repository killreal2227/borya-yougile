$ErrorActionPreference = 'Stop'
$directory = Join-Path $env:LOCALAPPDATA 'TochkaZvuka\Borya'
$keyPath = Join-Path $directory 'yougile-key.dpapi'
$secure = Get-Content -LiteralPath $keyPath | ConvertTo-SecureString
$pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
try {
    $python = (Get-Command python.exe -ErrorAction Stop).Source
    $pythonw = Join-Path (Split-Path -Parent $python) 'pythonw.exe'
    $env:YOUGILE_TOKEN = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
    $env:YOUGILE_BOT_USER_ID = '01a44c1a-25bb-4d64-b6c8-87631c00eba2'
    $process = Start-Process -FilePath $pythonw -ArgumentList '-B','-m','index' -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -PassThru
    Write-Output "Borya worker requested. Process ID: $($process.Id)"
} finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer)
    $secure.Dispose()
    Remove-Item Env:YOUGILE_TOKEN -ErrorAction SilentlyContinue
    Remove-Item Env:YOUGILE_BOT_USER_ID -ErrorAction SilentlyContinue
}
