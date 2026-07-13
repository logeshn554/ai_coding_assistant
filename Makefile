ifeq ($(OS),Windows_NT)
    SETUP_CMD = setup.bat
    PYTHON = .\venv\Scripts\python.exe
    TEST_CMD = .\venv\Scripts\pytest.exe
else
    SETUP_CMD = ./setup.sh
    PYTHON = ./venv/bin/python
    TEST_CMD = ./venv/bin/pytest
endif

.PHONY: setup dev build test

setup:
	$(SETUP_CMD)

dev:
	$(PYTHON) backend/launcher.py

build:
	cd frontend && npm run build
	$(PYTHON) -m py_compile backend/app/main.py

test:
	$(TEST_CMD)
	cd frontend && npm test -- --run
