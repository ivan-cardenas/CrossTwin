@echo off
REM ===========================================================================
REM  CrossTwin - first-time database setup
REM
REM  Creates the PostgreSQL/PostGIS database and login role for CrossTwin,
REM  grants the privileges you choose, and writes .env from .env_template.
REM  Double-click it or run it from a terminal in the project folder.
REM
REM  Prerequisite: PostgreSQL with PostGIS installed locally (Stack Builder ->
REM  Spatial Extensions -> PostGIS), and the password of a superuser such as
REM  "postgres".
REM
REM  The batch part below only launches PowerShell; the actual setup is the
REM  PowerShell script at the end of this same file, so that passwords with
REM  characters that are special to cmd survive intact.
REM ===========================================================================
setlocal
cd /d "%~dp0"
set "CT_SELF=%~f0"
powershell -NoProfile -ExecutionPolicy Bypass -Command "$c = [IO.File]::ReadAllText($env:CT_SELF); $i = $c.LastIndexOf('##' + 'PS-START'); & ([ScriptBlock]::Create($c.Substring($i)))"
set "RC=%ERRORLEVEL%"
echo.
pause
exit /b %RC%

##PS-START
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath (Split-Path -Parent $env:CT_SELF)
$Root = $PWD.ProviderPath

$IdentPattern = '^[a-z_][a-z0-9_]{0,62}$'
$IdentHint    = 'Use lowercase letters, digits and underscores, starting with a letter or underscore (max 63).'

# ---------------------------------------------------------------- helpers ---

function Write-Step([string]$Text) {
    Write-Host ''
    Write-Host "== $Text ==" -ForegroundColor Cyan
}

function Stop-Setup([string]$Text) {
    Write-Host ''
    Write-Host "ERROR: $Text" -ForegroundColor Red
    exit 1
}

function Read-Value([string]$Prompt, [string]$Default = '', [string]$Pattern = '', [string]$Hint = '', [switch]$AllowEmpty) {
    while ($true) {
        $label = if ($Default) { "$Prompt [$Default]" } else { $Prompt }
        $value = (Read-Host $label).Trim()
        if (-not $value) { $value = $Default }
        if (-not $value) {
            if ($AllowEmpty) { return '' }
            Write-Host '  A value is required.' -ForegroundColor Yellow
            continue
        }
        if ($Pattern -and $value -cnotmatch $Pattern) {
            Write-Host "  $Hint" -ForegroundColor Yellow
            continue
        }
        return $value
    }
}

function Read-Secret([string]$Prompt, [switch]$Confirm) {
    while ($true) {
        $value = ConvertFrom-SecureText (Read-Host $Prompt -AsSecureString)
        if (-not $value) {
            Write-Host '  A value is required.' -ForegroundColor Yellow
            continue
        }
        if ($Confirm) {
            $again = ConvertFrom-SecureText (Read-Host "$Prompt (again)" -AsSecureString)
            if ($again -cne $value) {
                Write-Host '  The two entries do not match, try again.' -ForegroundColor Yellow
                continue
            }
        }
        return $value
    }
}

function ConvertFrom-SecureText([Security.SecureString]$Secure) {
    $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($Secure)
    try { [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr) }
    finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr) }
}

function Read-YesNo([string]$Prompt, [bool]$Default = $true) {
    $suffix = if ($Default) { '[Y/n]' } else { '[y/N]' }
    while ($true) {
        $answer = (Read-Host "$Prompt $suffix").Trim().ToLower()
        if (-not $answer) { return $Default }
        if ($answer -in 'y', 'yes', 'j', 'ja') { return $true }
        if ($answer -in 'n', 'no', 'nee') { return $false }
    }
}

function Find-Psql {
    $cmd = Get-Command psql.exe -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }

    # Default EDB installer location: C:\Program Files\PostgreSQL\<version>\bin
    $roots = @($env:ProgramFiles, ${env:ProgramFiles(x86)}) | Where-Object { $_ }
    $found = foreach ($root in $roots) {
        Get-ChildItem -Path (Join-Path $root 'PostgreSQL\*\bin\psql.exe') -ErrorAction SilentlyContinue
    }
    # Sort by version folder; parse with the invariant culture so "9.6" is not
    # read as 96 on a Dutch (nl-NL) Windows where "." is a thousands separator.
    $best = $found | Sort-Object -Descending {
        $n = 0.0
        [void][double]::TryParse(($_.Directory.Parent.Name -replace '[^\d.]', ''),
            [Globalization.NumberStyles]::Float, [Globalization.CultureInfo]::InvariantCulture, [ref]$n)
        $n
    } | Select-Object -First 1
    if ($best) { return $best.FullName }

    Write-Host 'psql.exe was not found on PATH or under Program Files\PostgreSQL.' -ForegroundColor Yellow
    while ($true) {
        $path = (Read-Host 'Full path to psql.exe or to the PostgreSQL bin folder (empty to abort)').Trim('" ')
        if (-not $path) { Stop-Setup 'psql.exe is required. Install PostgreSQL first.' }
        if (Test-Path -LiteralPath $path -PathType Container) { $path = Join-Path $path 'psql.exe' }
        if (Test-Path -LiteralPath $path -PathType Leaf) { return $path }
        Write-Host "  Not found: $path" -ForegroundColor Yellow
    }
}

# Runs psql as the superuser. Returns @{ Code; Output }.
function Invoke-Psql([string]$Database, [string[]]$Arguments) {
    # psql writes notices to stderr; under 'Stop' Windows PowerShell would turn
    # those into terminating errors, so relax it for the native call.
    $ErrorActionPreference = 'Continue'
    $env:PGPASSWORD = $SuPass
    $env:PGCLIENTENCODING = 'UTF8'
    $out = & $Psql -X -w -q -v ON_ERROR_STOP=1 -h $DbHost -p $DbPort -U $SuUser -d $Database @Arguments 2>&1
    $code = $LASTEXITCODE
    Remove-Item Env:PGPASSWORD -ErrorAction SilentlyContinue
    [pscustomobject]@{ Code = $code; Output = (($out | ForEach-Object { "$_" }) -join "`n").Trim() }
}

function Invoke-Scalar([string]$Database, [string]$Sql) {
    $r = Invoke-Psql $Database @('-tA', '-c', $Sql)
    if ($r.Code -ne 0) { Stop-Setup "Query failed:`n$($r.Output)" }
    $r.Output
}

# Runs SQL from a temp file rather than -c: keeps passwords off the command
# line, and Windows PowerShell 5.1 strips embedded double quotes from native
# arguments, which would unquote identifiers. -1 wraps it in one transaction
# unless -NoTransaction (CREATE DATABASE refuses to run inside one). The file
# is UTF-8 without BOM: psql would choke on a BOM.
function Invoke-SqlScript([string]$Database, [string]$Sql, [switch]$NoTransaction) {
    $tmp = [IO.Path]::Combine([IO.Path]::GetTempPath(), "crosstwin_setup_$([guid]::NewGuid().ToString('N')).sql")
    try {
        [IO.File]::WriteAllText($tmp, $Sql, (New-Object Text.UTF8Encoding $false))
        $psqlArgs = if ($NoTransaction) { @('-f', $tmp) } else { @('-1', '-f', $tmp) }
        Invoke-Psql $Database $psqlArgs
    }
    finally { Remove-Item -LiteralPath $tmp -ErrorAction SilentlyContinue }
}

function Format-SqlLiteral([string]$Value) { "'" + $Value.Replace("'", "''") + "'" }

# python-dotenv single-quoted value: only \\ and \' are escape sequences.
function Format-EnvValue([string]$Value) { "'" + $Value.Replace('\', '\\').Replace("'", "\'") + "'" }

function New-SecretKey([int]$Length = 50) {
    $chars = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_+*=@()[]{}~'.ToCharArray()
    $bytes = New-Object byte[] $Length
    $rng = [Security.Cryptography.RandomNumberGenerator]::Create()
    try { $rng.GetBytes($bytes) } finally { $rng.Dispose() }
    -join ($bytes | ForEach-Object { $chars[$_ % $chars.Length] })
}

# ------------------------------------------------------------------ start ---

Write-Host ''
Write-Host '  CrossTwin - database setup' -ForegroundColor Green
Write-Host '  Creates the PostGIS database + user and writes your .env file.'

if (-not (Test-Path -LiteralPath '.env_template')) {
    Stop-Setup '.env_template was not found. Run this script from the CrossTwin project folder.'
}

Write-Step 'PostgreSQL connection'
$Psql = Find-Psql
Write-Host "Using $Psql"

$DbHost = Read-Value 'PostgreSQL host' 'localhost'
$DbPort = Read-Value 'PostgreSQL port' '5432' '^\d{1,5}$' 'Enter a port number, e.g. 5432.'
$SuUser = Read-Value 'Admin (superuser) name, used only for this setup' 'postgres'

for ($attempt = 1; ; $attempt++) {
    $SuPass = Read-Secret "Password for '$SuUser'"
    $check = Invoke-Psql 'postgres' @('-tA', '-c', 'SELECT rolsuper FROM pg_roles WHERE rolname = current_user')
    if ($check.Code -eq 0) { break }
    Write-Host "Could not connect:`n$($check.Output)" -ForegroundColor Yellow
    if ($attempt -ge 3) { Stop-Setup 'Could not connect to PostgreSQL. Check that the server is running and the credentials are correct.' }
}
if ($check.Output -ne 't') {
    Write-Host "Warning: '$SuUser' is not a superuser; creating extensions may fail." -ForegroundColor Yellow
}
Write-Host 'Connected.' -ForegroundColor Green

if (-not (Invoke-Scalar 'postgres' "SELECT 1 FROM pg_available_extensions WHERE name = 'postgis'")) {
    Stop-Setup 'PostGIS is not installed on this server. Install it with Stack Builder (Spatial Extensions -> PostGIS) and run this script again.'
}

# ------------------------------------------------------------- questions ---

Write-Step 'New database and user for CrossTwin'
$DbName  = Read-Value 'Database name' 'crosstwin' $IdentPattern $IdentHint
$AppUser = Read-Value 'Database user name' 'crosstwin_user' $IdentPattern $IdentHint
if ($AppUser -eq $SuUser) {
    Stop-Setup "Choose an application user other than the admin user '$SuUser'."
}

$RoleExists = [bool](Invoke-Scalar 'postgres' "SELECT 1 FROM pg_roles WHERE rolname = '$AppUser'")
$SetPassword = $true
if ($RoleExists) {
    Write-Host "User '$AppUser' already exists." -ForegroundColor Yellow
    $SetPassword = Read-YesNo "Set a new password for '$AppUser'?" $true
}
$AppPass = if ($SetPassword) {
    Read-Secret "Password for '$AppUser'" -Confirm
} else {
    Read-Secret "Current password of '$AppUser' (written to .env)"
}

Write-Host ''
Write-Host 'Privileges for this user:'
Write-Host '  1) Full   - owns the database; can run migrations and import data (recommended)'
Write-Host '  2) Write  - read and write data only; an admin must run migrations'
Write-Host '  3) Read   - read-only; for viewers or dashboards'
$Level = [int](Read-Value 'Choose 1, 2 or 3' '1' '^[123]$' 'Enter 1, 2 or 3.')
$CreateDb = Read-YesNo 'Allow the user to create databases (needed to run the test suite)?' ($Level -eq 1)

$DbExists = [bool](Invoke-Scalar 'postgres' "SELECT 1 FROM pg_database WHERE datname = '$DbName'")
if ($DbExists) {
    Write-Host "Database '$DbName' already exists." -ForegroundColor Yellow
    if (-not (Read-YesNo 'Keep it and only update the user, privileges and extensions?' $true)) {
        Stop-Setup 'Aborted. Choose another database name or drop the existing database first.'
    }
}

Write-Host ''
Write-Host 'Mapbox access token (optional, needed for the map; press Enter to fill it in later).'
$MapboxToken = Read-Value 'Mapbox token' '' -AllowEmpty

# ------------------------------------------------------- server-level SQL ---

Write-Step 'Creating user and database'
$Owner     = if ($Level -eq 1) { $AppUser } else { $SuUser }
$CreateOpt = if ($CreateDb) { 'CREATEDB' } else { 'NOCREATEDB' }
$PassOpt   = if ($SetPassword) { " PASSWORD $(Format-SqlLiteral $AppPass)" } else { '' }

$sql = if ($RoleExists) { "ALTER ROLE `"$AppUser`" LOGIN $CreateOpt$PassOpt;" }
       else             { "CREATE ROLE `"$AppUser`" LOGIN $CreateOpt$PassOpt;" }
$r = Invoke-SqlScript 'postgres' $sql
if ($r.Code -ne 0) { Stop-Setup "Creating the user failed:`n$($r.Output)" }
Write-Host "User '$AppUser' ready."

# CREATE DATABASE cannot run inside a transaction, so it gets its own call.
if (-not $DbExists) {
    $r = Invoke-SqlScript 'postgres' "CREATE DATABASE `"$DbName`" OWNER `"$Owner`" ENCODING 'UTF8' TEMPLATE template0;" -NoTransaction
    if ($r.Code -ne 0) { Stop-Setup "Creating the database failed:`n$($r.Output)" }
    Write-Host "Database '$DbName' created."
} elseif ($Level -eq 1) {
    $r = Invoke-SqlScript 'postgres' "ALTER DATABASE `"$DbName`" OWNER TO `"$AppUser`";"
    if ($r.Code -ne 0) { Stop-Setup "Changing the database owner failed:`n$($r.Output)" }
}

$dbGrant = if ($Level -eq 1) { 'ALL PRIVILEGES' } elseif ($Level -eq 2) { 'CONNECT, TEMPORARY' } else { 'CONNECT' }
$r = Invoke-SqlScript 'postgres' "GRANT $dbGrant ON DATABASE `"$DbName`" TO `"$AppUser`";"
if ($r.Code -ne 0) { Stop-Setup "Granting database privileges failed:`n$($r.Output)" }

# ------------------------------------------------------------- extensions ---

Write-Step 'Installing PostGIS extensions'
# postgis + postgis_raster are required (vector + raster models); the rest are
# used by optional features and the test runner, so a failure only warns.
$extensions = [ordered]@{
    postgis           = $true
    postgis_raster    = $true
    postgis_topology  = $false
    postgis_sfcgal    = $false
    pgrouting         = $false
    fuzzystrmatch     = $false
}
foreach ($ext in $extensions.Keys) {
    $r = Invoke-Psql $DbName @('-c', "CREATE EXTENSION IF NOT EXISTS $ext")
    if ($r.Code -eq 0) {
        Write-Host "  [ok]   $ext" -ForegroundColor Green
    } elseif ($extensions[$ext]) {
        Stop-Setup "Required extension '$ext' could not be installed:`n$($r.Output)"
    } else {
        Write-Host "  [skip] $ext (not available on this server, optional)" -ForegroundColor Yellow
    }
}

# ------------------------------------------------------ schema privileges ---

Write-Step 'Granting privileges'
$u  = "`"$AppUser`""
$su = "`"$SuUser`""
switch ($Level) {
    1 {
        $grants = @"
ALTER SCHEMA public OWNER TO $u;
GRANT ALL ON SCHEMA public TO $u;
GRANT ALL ON ALL TABLES IN SCHEMA public TO $u;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO $u;
GRANT ALL ON ALL FUNCTIONS IN SCHEMA public TO $u;
ALTER DEFAULT PRIVILEGES FOR ROLE $su IN SCHEMA public GRANT ALL ON TABLES TO $u;
ALTER DEFAULT PRIVILEGES FOR ROLE $su IN SCHEMA public GRANT ALL ON SEQUENCES TO $u;
"@
        $topologyGrant = 'GRANT USAGE ON SCHEMA topology TO {0}; GRANT ALL ON ALL TABLES IN SCHEMA topology TO {0}; GRANT ALL ON ALL SEQUENCES IN SCHEMA topology TO {0};'
    }
    2 {
        $grants = @"
GRANT USAGE ON SCHEMA public TO $u;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO $u;
GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA public TO $u;
ALTER DEFAULT PRIVILEGES FOR ROLE $su IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO $u;
ALTER DEFAULT PRIVILEGES FOR ROLE $su IN SCHEMA public GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO $u;
"@
        $topologyGrant = 'GRANT USAGE ON SCHEMA topology TO {0}; GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA topology TO {0}; GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA topology TO {0};'
    }
    3 {
        $grants = @"
GRANT USAGE ON SCHEMA public TO $u;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO $u;
GRANT SELECT ON ALL SEQUENCES IN SCHEMA public TO $u;
ALTER DEFAULT PRIVILEGES FOR ROLE $su IN SCHEMA public GRANT SELECT ON TABLES TO $u;
ALTER DEFAULT PRIVILEGES FOR ROLE $su IN SCHEMA public GRANT SELECT ON SEQUENCES TO $u;
"@
        $topologyGrant = 'GRANT USAGE ON SCHEMA topology TO {0}; GRANT SELECT ON ALL TABLES IN SCHEMA topology TO {0};'
    }
}
# The topology schema only exists when postgis_topology was installed.
$grants += "`nDO `$do`$ BEGIN IF EXISTS (SELECT 1 FROM pg_namespace WHERE nspname = 'topology') THEN EXECUTE $(Format-SqlLiteral ($topologyGrant -f $u)); END IF; END `$do`$;`n"

$r = Invoke-SqlScript $DbName $grants
if ($r.Code -ne 0) { Stop-Setup "Granting schema privileges failed:`n$($r.Output)" }
Write-Host 'Privileges granted.' -ForegroundColor Green

# ------------------------------------------------------------------- .env ---

Write-Step 'Writing .env'
$writeEnv = $true
if (Test-Path -LiteralPath '.env') {
    if (Read-YesNo '.env already exists. Replace it (a backup copy is kept)?' $true) {
        $backup = ".env.backup-$(Get-Date -Format 'yyyyMMdd-HHmmss')"
        Copy-Item -LiteralPath '.env' -Destination $backup
        Write-Host "Previous .env saved as $backup"
    } else {
        $writeEnv = $false
        Write-Host 'Kept the existing .env; update DATABASE_* in it yourself.' -ForegroundColor Yellow
    }
}

if ($writeEnv) {
    $values = [ordered]@{
        SECRET_KEY        = New-SecretKey
        DEBUG             = 'True'
        DATABASE_NAME     = $DbName
        DATABASE_USER     = $AppUser
        DATABASE_PASSWORD = $AppPass
        DATABASE_HOST     = $DbHost
        DATABASE_PORT     = $DbPort
    }
    if ($MapboxToken) { $values['MAPBOX_ACCESS_TOKEN'] = $MapboxToken }

    $text = [IO.File]::ReadAllText((Join-Path $Root '.env_template'))
    $newline = if ($text.Contains("`r`n")) { "`r`n" } else { "`n" }
    foreach ($key in $values.Keys) {
        $line = "$key=$(Format-EnvValue $values[$key])"
        $pattern = "(?m)^[ \t]*$key[ \t]*=[^\r\n]*"
        if ([regex]::IsMatch($text, $pattern)) {
            # A MatchEvaluator keeps "$1"-style sequences in passwords literal.
            $text = ([regex]$pattern).Replace($text, [Text.RegularExpressions.MatchEvaluator] { param($m) $line }, 1)
        } else {
            $text = $text.TrimEnd() + $newline + $line + $newline
        }
    }
    # No BOM: python-dotenv would otherwise read the first key as "\ufeffSECRET_KEY".
    [IO.File]::WriteAllText((Join-Path $Root '.env'), $text, (New-Object Text.UTF8Encoding $false))
    Write-Host '.env written from .env_template.' -ForegroundColor Green
}

# ------------------------------------------------------------- migrations ---

$python = Join-Path $Root '.venv\Scripts\python.exe'
if ($Level -eq 1 -and $writeEnv -and (Test-Path -LiteralPath $python)) {
    Write-Step 'Django migrations'
    if (Read-YesNo 'Run "python manage.py migrate" now?' $true) {
        $ErrorActionPreference = 'Continue'
        & $python manage.py migrate
        if ($LASTEXITCODE -ne 0) {
            Write-Host 'Migrations failed; fix the error above and run "python manage.py migrate" again.' -ForegroundColor Yellow
        } else {
            Write-Host 'Migrations applied.' -ForegroundColor Green
        }
        $ErrorActionPreference = 'Stop'
    }
}

# ---------------------------------------------------------------- summary ---

$levelName = @{ 1 = 'Full (owner)'; 2 = 'Read/write'; 3 = 'Read-only' }[$Level]
Write-Host ''
Write-Host '======================================================' -ForegroundColor Green
Write-Host '  Setup complete' -ForegroundColor Green
Write-Host "  Database   : $DbName on ${DbHost}:$DbPort"
Write-Host "  User       : $AppUser ($levelName$(if ($CreateDb) { ', can create databases' }))"
Write-Host '======================================================' -ForegroundColor Green
Write-Host 'Next steps:'
if (-not (Test-Path -LiteralPath $python)) {
    Write-Host '  python -m venv .venv'
    Write-Host '  .venv\Scripts\Activate'
    Write-Host '  pip install -r requirements.txt'
}
if ($Level -eq 1) {
    Write-Host '  python manage.py migrate          (if not done above)'
} else {
    Write-Host "  Migrations must be run by a user with schema rights (e.g. '$SuUser')."
}
Write-Host '  python manage.py createsuperuser'
if (-not $MapboxToken) { Write-Host '  Add your MAPBOX_ACCESS_TOKEN to .env' }
Write-Host '  start.bat'
exit 0
