# Contributing to PI Lead Qualifier

Thank you for your interest in contributing!

## How to Contribute

### Reporting Bugs

1. Check [existing issues](https://github.com/dmgreen6/pi-lead-qualifier/issues) first
2. Create a new issue with:
   - What you expected to happen
   - What actually happened
   - Steps to reproduce
   - Your environment (OS, Python version)

### Adding State Support

Currently we support South Carolina and Washington. To add a new state:

1. Fork the repository
2. Create `data/states/XX.json` using SC.json as a template
3. Research and fill in:
   - State name and abbreviation
   - Personal injury statute of limitations (years)
   - SOL notes/exceptions
   - Complete county list
   - Major metro areas with their counties
   - Default preferred counties (largest metro)
4. Include citations for SOL data
5. Add tests in `tests/test_state_data.py`
6. Submit a pull request

### Code Contributions

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Make your changes
4. Run tests: `pytest tests/`
5. Submit a pull request

## Code Style

- Python code follows PEP 8
- Use type hints where practical
- Add tests for new features

## Questions?

Open a [Discussion](https://github.com/dmgreen6/pi-lead-qualifier/discussions) for questions.
