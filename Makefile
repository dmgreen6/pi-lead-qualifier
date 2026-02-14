# Pflug Qualifier (P3) - Makefile
# Minimal entrypoints for project navigation

.PHONY: dev run status deploy test help

help:
	@echo "Pflug Qualifier (P3) Commands:"
	@echo "  make dev      - Start development server"
	@echo "  make run      - Run the qualifier"
	@echo "  make status   - Show service status"
	@echo "  make deploy   - Deploy systemd service"
	@echo "  make test     - Run tests"

dev:
	python run_local.py

run: dev

status:
	@echo "Pflug Qualifier Status:"
	@systemctl --user status pflug-qualifier 2>/dev/null || echo "  Not running as systemd service"
	@ps aux | grep -E 'python.*run_local' | grep -v grep || echo "  Not running locally"

deploy:
	@echo "Deploy as systemd service:"
	@echo "  sudo cp pflug-qualifier.service /etc/systemd/system/"
	@echo "  sudo systemctl enable pflug-qualifier"
	@echo "  sudo systemctl start pflug-qualifier"

test:
	python -m pytest tests/ -v
