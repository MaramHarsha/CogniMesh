.PHONY: setup check test format seed dev compose-up compose-down

setup:
	powershell -ExecutionPolicy Bypass -File ./scripts/of.ps1 setup

check:
	powershell -ExecutionPolicy Bypass -File ./scripts/of.ps1 check

test:
	powershell -ExecutionPolicy Bypass -File ./scripts/of.ps1 test

format:
	powershell -ExecutionPolicy Bypass -File ./scripts/of.ps1 format

seed:
	powershell -ExecutionPolicy Bypass -File ./scripts/of.ps1 seed

dev:
	powershell -ExecutionPolicy Bypass -File ./scripts/of.ps1 dev

compose-up:
	powershell -ExecutionPolicy Bypass -File ./scripts/of.ps1 compose:up

compose-down:
	powershell -ExecutionPolicy Bypass -File ./scripts/of.ps1 compose:down

