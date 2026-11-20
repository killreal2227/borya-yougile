$ErrorActionPreference = 'Stop'
$companyId = '14589015-7c84-4bb0-bb31-b08c4cf393b8'
$botUserId = '01a44c1a-25bb-4d64-b6c8-87631c00eba2'
$api = 'https://yougile.com/api-v2'
$directory = Join-Path $env:LOCALAPPDATA 'TochkaZvuka\Borya'
$keyFile = Join-Path $directory 'yougile-key.dpapi'

if (Test-Path -LiteralPath $keyFile) {
    Write-Output 'A local Borya key already exists.'
    exit 0
}

$password = Read-Host 'Enter the YouGile password for boryatzvuka@yandex.ru' -AsSecureString
$pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($password)
try {
    $body = @{
        login = 'boryatzvuka@yandex.ru'
        password = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
        companyId = $companyId
    } | ConvertTo-Json -Compress
    $response = Invoke-RestMethod -Uri "$api/auth/keys" -Method Post -ContentType 'application/json' -Body $body -MaximumRedirection 0
} catch {
    throw 'YouGile did not issue a key. Check the YouGile account password and company membership.'
} finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer)
    $body = $null
    $password.Dispose()
}

if ([string]::IsNullOrWhiteSpace($response.key)) {
    throw 'YouGile returned no key.'
}

$headers = @{ Authorization = "Bearer $($response.key)" }
try {
    $user = Invoke-RestMethod -Uri "$api/users/me" -Headers $headers -MaximumRedirection 0
    if ($user.id -ne $botUserId -or $user.isAdmin -ne $false) {
        throw 'The key belongs to an unexpected account.'
    }
    $encryptedKey = ConvertTo-SecureString -String $response.key -AsPlainText -Force | ConvertFrom-SecureString
    New-Item -ItemType Directory -Path $directory -Force | Out-Null
    Set-Content -LiteralPath $keyFile -Value $encryptedKey -Encoding ASCII
} catch {
    throw 'The key could not be verified or saved for this Windows account.'
} finally {
    $headers.Clear()
    $response = $null
}

Write-Output 'Borya key verified and saved locally. The key was not printed.'
