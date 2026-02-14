# PI Lead Qualifier

**Free, AI-powered lead qualification for personal injury attorneys in South Carolina and Washington.**

Automatically score and prioritize your intake leads, so you spend time on cases that matter.

---

## What It Does

1. **Connects to your Airtable** where leads come in
2. **Scores each lead** using AI (Claude or ChatGPT)
3. **Assigns a tier** (Accept, Review, or Decline)
4. **Updates your Airtable** with scores and recommendations

**Pro Mode adds:** Automatic Clio matter creation + email notifications.

---

## Quick Start

### 1. Download

```bash
git clone https://github.com/your-username/pi-lead-qualifier.git
cd pi-lead-qualifier
```

### 2. Run Setup Wizard

**Mac:**
```bash
./deploy/local/start-mac.sh
```

**Windows:**
Double-click `deploy\local\start-windows.bat`

### 3. Open Browser

Visit [http://localhost:8080](http://localhost:8080) and follow the wizard.

---

## Features

| Feature | Starter | Pro |
|---------|:-------:|:---:|
| Airtable integration | ✓ | ✓ |
| AI-powered scoring | ✓ | ✓ |
| Lead tier assignment | ✓ | ✓ |
| State SOL awareness | ✓ | ✓ |
| County preferences | ✓ | ✓ |
| Clio matter creation | ✗ | ✓ |
| Email notifications | ✗ | ✓ |
| Auto-decline emails | ✗ | ✓ |

---

## Supported States

Currently supports:
- **South Carolina** (3-year SOL, 46 counties)
- **Washington** (3-year SOL, 39 counties)

Want your state added? See [CONTRIBUTING.md](CONTRIBUTING.md).

---

## Requirements

- **Python 3.9+**
- **Airtable account** (free tier works)
- **AI API key** (Claude or OpenAI)
- **Clio account** (Pro mode only)

---

## Cloud Deployment

For 24/7 operation, deploy to Railway:

[![Deploy on Railway](https://railway.app/button.svg)](https://railway.app/new/template?template=https://github.com/your-username/pi-lead-qualifier)

Estimated cost: ~$5/month

---

## Support

- **Issues:** [GitHub Issues](https://github.com/your-username/pi-lead-qualifier/issues)
- **Discussions:** [GitHub Discussions](https://github.com/your-username/pi-lead-qualifier/discussions)
- **Need help?** See [docs/find-a-developer.md](docs/find-a-developer.md)

---

## License

MIT License - Free to use and modify.

---

Built with care for the PI attorney community.
