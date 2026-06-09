# Local Development

Module 0 provides only the foundation workflow. Runtime services begin in Module 1.

## Commands

Prepare local directories:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\of.ps1 setup
```

Validate the foundation:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\of.ps1 check
```

Start the placeholder Compose profile:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\of.ps1 dev
```

Stop it:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\of.ps1 compose:down
```

## Module Discipline

Do not start Module 1 implementation until Module 0 validation passes and `plan.md` marks Module 0 complete.

