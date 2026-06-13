param(
  [Parameter(Position = 0)]
  [string]$Task = "help"
)

$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..")

function Invoke-Python {
  param([string[]]$PythonArgs)

  $prefix = @()
  $pythonPath = $null

  if ($env:COGNIMESH_PYTHON -and (Test-Path -LiteralPath $env:COGNIMESH_PYTHON)) {
    $pythonPath = $env:COGNIMESH_PYTHON
  }

  if (-not $pythonPath) {
    foreach ($candidate in @("python", "python3")) {
      $command = Get-Command $candidate -ErrorAction SilentlyContinue
      if ($command) {
        $pythonPath = $command.Source
        break
      }
    }
  }

  if (-not $pythonPath) {
    $py = Get-Command py -ErrorAction SilentlyContinue
    if ($py) {
      $pythonPath = $py.Source
      $prefix = @("-3")
    }
  }

  if (-not $pythonPath -and $env:USERPROFILE) {
    $bundledPython = Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
    if (Test-Path -LiteralPath $bundledPython) {
      $pythonPath = $bundledPython
    }
  }

  if (-not $pythonPath) {
    throw "Python is required for this task. Set COGNIMESH_PYTHON to a Python 3.12+ executable."
  }

  & $pythonPath @prefix @PythonArgs
  if ($LASTEXITCODE -ne 0) {
    throw "Python command failed with exit code $LASTEXITCODE."
  }
}

function Invoke-Compose {
  param([string[]]$ComposeArgs)

  $docker = Get-Command docker -ErrorAction SilentlyContinue
  $dockerPath = $null
  if ($docker) {
    $dockerPath = $docker.Source
  }
  if (-not $dockerPath) {
    $dockerDesktopPath = "C:\Program Files\Docker\Docker\resources\bin\docker.exe"
    if (Test-Path -LiteralPath $dockerDesktopPath) {
      $dockerPath = $dockerDesktopPath
    }
  }
  if (-not $dockerPath) {
    throw "Docker is required for Compose tasks."
  }

  $dockerConfig = Join-Path $Root ".cognimesh/docker-config"
  New-Item -ItemType Directory -Force -Path $dockerConfig | Out-Null
  $previousDockerConfig = $env:DOCKER_CONFIG
  $env:DOCKER_CONFIG = $dockerConfig
  try {
    & $dockerPath compose -f (Join-Path $Root "infra/compose/docker-compose.yml") @ComposeArgs
  }
  finally {
    $env:DOCKER_CONFIG = $previousDockerConfig
  }
  if ($LASTEXITCODE -ne 0) {
    throw "Docker Compose command failed with exit code $LASTEXITCODE."
  }
}

function Invoke-Module1Check {
  $servicePython = Join-Path $Root "services/object-registry/.venv/Scripts/python.exe"
  if (Test-Path -LiteralPath $servicePython) {
    & $servicePython (Join-Path $Root "scripts/validate_module1.py")
    if ($LASTEXITCODE -ne 0) {
      throw "Module 1 validation failed with exit code $LASTEXITCODE."
    }
  }
  else {
    Invoke-Python -PythonArgs @((Join-Path $Root "scripts/validate_module1.py"))
  }
}

function Invoke-Module2Check {
  $servicePython = Join-Path $Root "services/object-registry/.venv/Scripts/python.exe"
  if (Test-Path -LiteralPath $servicePython) {
    & $servicePython (Join-Path $Root "scripts/validate_module2.py")
    if ($LASTEXITCODE -ne 0) {
      throw "Module 2 validation failed with exit code $LASTEXITCODE."
    }
  }
  else {
    Invoke-Python -PythonArgs @((Join-Path $Root "scripts/validate_module2.py"))
  }
}

function Invoke-Module5Check {
  $servicePython = Join-Path $Root "services/object-registry/.venv/Scripts/python.exe"
  if (Test-Path -LiteralPath $servicePython) {
    & $servicePython (Join-Path $Root "scripts/validate_module5.py")
    if ($LASTEXITCODE -ne 0) {
      throw "Module 5 validation failed with exit code $LASTEXITCODE."
    }
  }
  else {
    Invoke-Python -PythonArgs @((Join-Path $Root "scripts/validate_module5.py"))
  }
}

function Invoke-Module6Check {
  $servicePython = Join-Path $Root "services/object-registry/.venv/Scripts/python.exe"
  if (Test-Path -LiteralPath $servicePython) {
    & $servicePython (Join-Path $Root "scripts/validate_module6.py")
    if ($LASTEXITCODE -ne 0) {
      throw "Module 6 validation failed with exit code $LASTEXITCODE."
    }
  }
  else {
    Invoke-Python -PythonArgs @((Join-Path $Root "scripts/validate_module6.py"))
  }
}

function Invoke-Module7Check {
  $servicePython = Join-Path $Root "services/object-registry/.venv/Scripts/python.exe"
  if (Test-Path -LiteralPath $servicePython) {
    & $servicePython (Join-Path $Root "scripts/validate_module7.py")
    if ($LASTEXITCODE -ne 0) {
      throw "Module 7 validation failed with exit code $LASTEXITCODE."
    }
  }
  else {
    Invoke-Python -PythonArgs @((Join-Path $Root "scripts/validate_module7.py"))
  }
}

function Invoke-Module4Check {
  $servicePython = Join-Path $Root "services/object-registry/.venv/Scripts/python.exe"
  if (Test-Path -LiteralPath $servicePython) {
    & $servicePython (Join-Path $Root "scripts/validate_module4.py")
    if ($LASTEXITCODE -ne 0) {
      throw "Module 4 validation failed with exit code $LASTEXITCODE."
    }
  }
  else {
    Invoke-Python -PythonArgs @((Join-Path $Root "scripts/validate_module4.py"))
  }
}

function Invoke-Module8Check {
  $servicePython = Join-Path $Root "services/object-registry/.venv/Scripts/python.exe"
  if (Test-Path -LiteralPath $servicePython) {
    & $servicePython (Join-Path $Root "scripts/validate_module8.py")
    if ($LASTEXITCODE -ne 0) {
      throw "Module 8 validation failed with exit code $LASTEXITCODE."
    }
  }
  else {
    Invoke-Python -PythonArgs @((Join-Path $Root "scripts/validate_module8.py"))
  }
}

function Invoke-Module9Check {
  $servicePython = Join-Path $Root "services/object-registry/.venv/Scripts/python.exe"
  if (Test-Path -LiteralPath $servicePython) {
    & $servicePython (Join-Path $Root "scripts/validate_module9.py")
    if ($LASTEXITCODE -ne 0) {
      throw "Module 9 validation failed with exit code $LASTEXITCODE."
    }
  }
  else {
    Invoke-Python -PythonArgs @((Join-Path $Root "scripts/validate_module9.py"))
  }
}

function Invoke-Module10Check {
  $servicePython = Join-Path $Root "services/object-registry/.venv/Scripts/python.exe"
  if (Test-Path -LiteralPath $servicePython) {
    & $servicePython (Join-Path $Root "scripts/validate_module10.py")
    if ($LASTEXITCODE -ne 0) {
      throw "Module 10 validation failed with exit code $LASTEXITCODE."
    }
  }
  else {
    Invoke-Python -PythonArgs @((Join-Path $Root "scripts/validate_module10.py"))
  }
}

function Invoke-Module11Check {
  $servicePython = Join-Path $Root "services/object-registry/.venv/Scripts/python.exe"
  if (Test-Path -LiteralPath $servicePython) {
    & $servicePython (Join-Path $Root "scripts/validate_module11.py")
    if ($LASTEXITCODE -ne 0) {
      throw "Module 11 validation failed with exit code $LASTEXITCODE."
    }
  }
  else {
    Invoke-Python -PythonArgs @((Join-Path $Root "scripts/validate_module11.py"))
  }
}

switch ($Task) {
  "help" {
    Write-Host "CogniMesh task runner"
    Write-Host ""
    Write-Host "Tasks:"
    Write-Host "  setup        Prepare local workspace directories"
    Write-Host "  check        Validate Module 0 foundation files"
    Write-Host "  test         Run current test gate"
    Write-Host "  format       Run formatters when module code exists"
    Write-Host "  seed         Run seed data when modules provide seeds"
    Write-Host "  dev          Start local developer environment"
    Write-Host "  compose:up   Build and start the local CogniMesh stack"
    Write-Host "  compose:down Stop the local Compose stack"
    Write-Host "  module1:check Validate Module 1 files and tests"
    Write-Host "  module1:install Install Module 1 Python dependencies into service venv"
    Write-Host "  module1:seed  Seed the Employee domain"
    Write-Host "  module2:check Validate Module 2 identity and policy foundation"
    Write-Host "  module4:check Validate Module 4 data connection and ingestion"
    Write-Host "  module5:check Validate Module 5 lakehouse storage and versioning"
    Write-Host "  module6:check Validate Module 6 compute and query engines"
    Write-Host "  module7:check Validate Module 7 pipeline builder and code workspaces"
    Write-Host "  module8:check Validate Module 8 semantic modeling and dbt integration"
    Write-Host "  module9:check Validate Module 9 object query service"
    Write-Host "  module10:check Validate Module 10 lineage and provenance ledger"
    Write-Host "  module11:check Validate Module 11 data quality and contracts"
  }
  "setup" {
    New-Item -ItemType Directory -Force -Path (Join-Path $Root ".cognimesh") | Out-Null
    New-Item -ItemType Directory -Force -Path (Join-Path $Root ".cognimesh/tmp") | Out-Null
    Write-Host "CogniMesh local workspace prepared."
  }
  "check" {
    Invoke-Python -PythonArgs @((Join-Path $Root "scripts/validate_foundation.py"))
  }
  "module1:check" {
    Invoke-Module1Check
  }
  "module2:check" {
    Invoke-Module2Check
  }
  "module4:check" {
    Invoke-Module4Check
  }
  "module5:check" {
    Invoke-Module5Check
  }
  "module6:check" {
    Invoke-Module6Check
  }
  "module7:check" {
    Invoke-Module7Check
  }
  "module8:check" {
    Invoke-Module8Check
  }
  "module9:check" {
    Invoke-Module9Check
  }
  "module10:check" {
    Invoke-Module10Check
  }
  "module11:check" {
    Invoke-Module11Check
  }
  "module1:install" {
    $serviceRoot = Join-Path $Root "services/object-registry"
    $venvPython = Join-Path $serviceRoot ".venv/Scripts/python.exe"
    if (-not (Test-Path -LiteralPath $venvPython)) {
      Push-Location $serviceRoot
      try {
        Invoke-Python -PythonArgs @("-m", "venv", ".venv")
      }
      finally {
        Pop-Location
      }
    }
    Push-Location $serviceRoot
    try {
      & $venvPython -m pip install --upgrade pip
      & $venvPython -m pip install -e ".[test]"
    }
    finally {
      Pop-Location
    }
  }
  "test" {
    Invoke-Python -PythonArgs @((Join-Path $Root "scripts/validate_foundation.py"))
    if (Test-Path -LiteralPath (Join-Path $Root "services/object-registry")) {
      Invoke-Module1Check
      if (Test-Path -LiteralPath (Join-Path $Root "services/object-registry/app/models/identity.py")) {
        Invoke-Module2Check
      }
      if (Test-Path -LiteralPath (Join-Path $Root "services/object-registry/app/models/lineage.py")) {
        Invoke-Module10Check
      }
      if (Test-Path -LiteralPath (Join-Path $Root "services/lakehouse-control")) {
        Invoke-Module5Check
      }
      if (Test-Path -LiteralPath (Join-Path $Root "services/ingestion-control")) {
        Invoke-Module4Check
      }
      if (Test-Path -LiteralPath (Join-Path $Root "services/compute-control")) {
        Invoke-Module6Check
      }
      if (Test-Path -LiteralPath (Join-Path $Root "services/pipeline-control")) {
        Invoke-Module7Check
      }
      if (Test-Path -LiteralPath (Join-Path $Root "services/semantic-control")) {
        Invoke-Module8Check
      }
      if (Test-Path -LiteralPath (Join-Path $Root "services/query-service")) {
        Invoke-Module9Check
      }
      if (Test-Path -LiteralPath (Join-Path $Root "services/quality-control")) {
        Invoke-Module11Check
      }
    }
    Write-Host "CogniMesh validation gates completed."
  }
  "format" {
    Write-Host "No source formatter is active until implementation modules add code."
    Write-Host "Foundation files are validated by scripts/validate_foundation.py."
  }
  "seed" {
    Push-Location (Join-Path $Root "services/object-registry")
    try {
      Invoke-Python -PythonArgs @("-m", "app.seed.employee_domain")
    }
    finally {
      Pop-Location
    }
  }
  "module1:seed" {
    Push-Location (Join-Path $Root "services/object-registry")
    try {
      Invoke-Python -PythonArgs @("-m", "app.seed.employee_domain")
    }
    finally {
      Pop-Location
    }
  }
  "dev" {
    Invoke-Compose -ComposeArgs @("up", "-d", "--build", "postgres", "object-registry", "minio", "nessie", "lakehouse-control", "ingestion-control", "compute-control", "pipeline-control", "semantic-control", "query-service", "quality-control")
    Write-Host "CogniMesh developer environment started."
  }
  "compose:up" {
    Invoke-Compose -ComposeArgs @("up", "-d", "--build", "postgres", "object-registry", "minio", "nessie", "lakehouse-control", "ingestion-control", "compute-control", "pipeline-control", "semantic-control", "query-service", "quality-control")
  }
  "compose:down" {
    Invoke-Compose -ComposeArgs @("down")
  }
  default {
    throw "Unknown task '$Task'. Run scripts/of.ps1 help."
  }
}
