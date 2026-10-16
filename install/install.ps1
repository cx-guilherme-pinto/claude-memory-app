# Instalador da Memoria para Windows 10/11. Nao precisa de admin. PowerShell 5.1 ou mais recente.
#
# Uso:
#   powershell -ExecutionPolicy Bypass -c "irm <repo>/releases/download/<versao>/install.ps1 | iex"
#
# Faz isto:
#   1. instala o WebView2 Runtime por utilizador, se faltar (sem admin);
#   2. instala o uv (versao fixada) em %USERPROFILE%\.local\bin, se faltar;
#   3. descarrega o wheel e o constraints.txt desta versao e verifica o SHA-256;
#   4. corre "uv tool install" com o Python 3.12 gerido pelo uv;
#   5. cria um atalho no menu Iniciar.
#
# Repositorio privado (so em desenvolvimento): define $env:MEMORIA_DOWNLOAD_TOKEN.
# O token nunca e impresso.
#
# Este ficheiro tem de ser so ASCII (o PowerShell 5.1 le ficheiros sem BOM como ANSI).

# >>> config: gerado a partir de release.conf por scripts/render_installers.py. Nao editar a mao.
$MemoryAppRepoUrl = 'https://gitea.guilhermepinto.pt/guilherme/claude-memory-app.git'
$MemoryAppVersion = 'v0.2.0'
$ReleaseDownloadUrl = '{repo}/releases/download/{version}/{file}'
$UvVersion = '0.13.1'
$PythonVersion = '3.12'
$BuildVersion = 'v0.2.0'
$WheelSha256 = ''
# <<< config

function Install-Memoria {
    $ErrorActionPreference = 'Stop'
    $ProgressPreference = 'SilentlyContinue'
    [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
    try {
        # Proxy corporativo com autenticacao do Windows.
        [Net.WebRequest]::DefaultWebProxy.Credentials = [Net.CredentialCache]::DefaultNetworkCredentials
    } catch { }

    # Variaveis de ambiente com o mesmo nome sobrepoem a configuracao.
    $repoUrl = if ($env:MEMORY_APP_REPO_URL) { $env:MEMORY_APP_REPO_URL } else { $MemoryAppRepoUrl }
    $version = if ($env:MEMORY_APP_VERSION) { $env:MEMORY_APP_VERSION } else { $MemoryAppVersion }
    $pattern = if ($env:RELEASE_DOWNLOAD_URL) { $env:RELEASE_DOWNLOAD_URL } else { $ReleaseDownloadUrl }
    $uvVer = if ($env:UV_VERSION) { $env:UV_VERSION } else { $UvVersion }
    $pyVer = if ($env:PYTHON_VERSION) { $env:PYTHON_VERSION } else { $PythonVersion }

    $repo = $repoUrl.TrimEnd('/')
    if ($repo.EndsWith('.git')) { $repo = $repo.Substring(0, $repo.Length - 4) }
    $uri = [Uri]$repo
    $segs = $uri.AbsolutePath.Trim('/').Split('/')
    $name = $segs[$segs.Length - 1]
    $owner = if ($segs.Length -ge 2) { $segs[$segs.Length - 2] } else { '' }

    function Get-AssetUrl([string]$File) {
        return $pattern.Replace('{repo}', $repo).Replace('{host}', $uri.Host).Replace('{owner}', $owner).Replace('{name}', $name).Replace('{version}', $version).Replace('{file}', $File)
    }

    function Get-Asset([string]$Url, [string]$OutFile) {
        $headers = @{}
        if ($env:MEMORIA_DOWNLOAD_TOKEN) { $headers['Authorization'] = 'token ' + $env:MEMORIA_DOWNLOAD_TOKEN }
        try {
            Invoke-WebRequest -Uri $Url -OutFile $OutFile -UseBasicParsing -Headers $headers
        } catch {
            throw ('Nao consegui descarregar ' + $Url + ': ' + $_.Exception.Message)
        }
    }

    function Test-WebView2 {
        $guid = '{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}'
        $keys = @(
            ('HKLM:\SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\' + $guid),
            ('HKCU:\Software\Microsoft\EdgeUpdate\Clients\' + $guid),
            ('HKLM:\SOFTWARE\Microsoft\EdgeUpdate\Clients\' + $guid)
        )
        foreach ($k in $keys) {
            try {
                $pv = (Get-ItemProperty -Path $k -Name pv -ErrorAction Stop).pv
                if ($pv -and $pv -ne '0.0.0.0') { return $true }
            } catch { }
        }
        return $false
    }

    $tmp = Join-Path ([IO.Path]::GetTempPath()) ('memoria-' + [Guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $tmp | Out-Null
    try {
        # --- 1. WebView2 ---------------------------------------------------
        if (Test-WebView2) {
            Write-Host 'WebView2: instalado.'
        } else {
            Write-Host 'A instalar o WebView2 Runtime (por utilizador)...'
            $wv = Join-Path $tmp 'MicrosoftEdgeWebview2Setup.exe'
            Invoke-WebRequest -Uri 'https://go.microsoft.com/fwlink/p/?LinkId=2124703' -OutFile $wv -UseBasicParsing
            $p = Start-Process -FilePath $wv -ArgumentList '/silent', '/install' -Wait -PassThru
            if (Test-WebView2) {
                Write-Host 'WebView2: instalado.'
            } else {
                Write-Host ('Aviso: o WebView2 nao ficou instalado (codigo ' + $p.ExitCode + '). A Memoria abre no browser.')
            }
        }

        # --- 2. uv ------------------------------------------------------------
        $uv = $null
        $cmd = Get-Command uv -ErrorAction SilentlyContinue
        if ($cmd) { $uv = $cmd.Source }
        $uvLocal = Join-Path $env:USERPROFILE '.local\bin\uv.exe'
        if (-not $uv -and (Test-Path $uvLocal)) { $uv = $uvLocal }
        if (-not $uv) {
            Write-Host ('A instalar o uv ' + $uvVer + '...')
            $inst = Join-Path $tmp 'uv-installer.ps1'
            Invoke-WebRequest -Uri ('https://github.com/astral-sh/uv/releases/download/' + $uvVer + '/uv-installer.ps1') -OutFile $inst -UseBasicParsing
            & powershell -NoProfile -ExecutionPolicy Bypass -File $inst
            if ($LASTEXITCODE -ne 0) { throw 'A instalacao do uv falhou.' }
            $uv = $uvLocal
            if (-not (Test-Path $uv)) { throw ('Nao encontrei o uv em ' + $uv) }
        }
        Write-Host ('uv: ' + (& $uv --version))

        # --- 3. download e verificacao -----------------------------------
        $wheel = 'memoria-' + $version.TrimStart('v') + '-py3-none-any.whl'
        Write-Host ('A descarregar a Memoria ' + $version + '...')
        Get-Asset (Get-AssetUrl 'SHA256SUMS') (Join-Path $tmp 'SHA256SUMS')
        $sums = @{}
        foreach ($line in Get-Content (Join-Path $tmp 'SHA256SUMS')) {
            $parts = $line.Trim() -split '\s+', 2
            if ($parts.Length -eq 2) { $sums[$parts[1].TrimStart('*')] = $parts[0].ToLower() }
        }
        foreach ($f in @($wheel, 'constraints.txt')) {
            $out = Join-Path $tmp $f
            Get-Asset (Get-AssetUrl $f) $out
            if (-not $sums.ContainsKey($f)) { throw ($f + ' nao esta no SHA256SUMS.') }
            $real = (Get-FileHash -Algorithm SHA256 -Path $out).Hash.ToLower()
            if ($real -ne $sums[$f]) { throw ('SHA-256 nao confere: ' + $f) }
        }
        if ($WheelSha256 -and $version -eq $BuildVersion) {
            $real = (Get-FileHash -Algorithm SHA256 -Path (Join-Path $tmp $wheel)).Hash.ToLower()
            if ($real -ne $WheelSha256) { throw 'SHA-256 do wheel diferente do esperado por este instalador.' }
        }
        Write-Host 'SHA-256 verificado.'

        # --- 4. instalar ----------------------------------------------------
        & $uv tool install --force --managed-python --python $pyVer (Join-Path $tmp $wheel) --constraints (Join-Path $tmp 'constraints.txt')
        if ($LASTEXITCODE -ne 0) { throw 'uv tool install falhou.' }
        $bin = (& $uv tool dir --bin).Trim()
        $memoria = Join-Path $bin 'memoria.exe'
        $memoriaGui = Join-Path $bin 'memoria-gui.exe'
        if (-not (Test-Path $memoria)) { throw ('Nao encontrei ' + $memoria) }

        # --- 5. atalho no menu Iniciar ------------------------------------
        $alvo = if (Test-Path $memoriaGui) { $memoriaGui } else { $memoria }
        $programs = [Environment]::GetFolderPath('Programs')
        $lnkName = 'Mem' + [char]0x00F3 + 'ria.lnk'
        $shell = New-Object -ComObject WScript.Shell
        $lnk = $shell.CreateShortcut((Join-Path $programs $lnkName))
        $lnk.TargetPath = $alvo
        $lnk.WorkingDirectory = $env:USERPROFILE
        $lnk.Description = 'Memorias do Claude Code'
        $lnk.Save()
        Write-Host ('Atalho: ' + (Join-Path $programs $lnkName))

        # --- verificacao ---------------------------------------------------
        & $memoria selftest | Out-Null
        if ($LASTEXITCODE -ne 0) { throw ('O selftest falhou. Corre: "' + $memoria + '" selftest') }

        Write-Host ''
        Write-Host ('Memoria ' + $version + ' instalada.')
        Write-Host 'Para ligar ao Claude Code:'
        Write-Host ('  claude mcp add --scope user memoria -- "' + $memoria + '" mcp')
        $pathUser = [Environment]::GetEnvironmentVariable('Path', 'User')
        if (($env:Path + ';' + $pathUser) -notlike ('*' + $bin + '*')) {
            Write-Host ('Nota: ' + $bin + ' nao esta no PATH. Abre um terminal novo.')
        }
    } finally {
        Remove-Item -Recurse -Force $tmp -ErrorAction SilentlyContinue
    }
}

try {
    Install-Memoria
} catch {
    Write-Host ('Erro: ' + $_.Exception.Message) -ForegroundColor Red
}
