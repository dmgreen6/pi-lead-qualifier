# PI Lead Qualifier - Public Template Design

**Date:** 2026-02-14
**Status:** Approved
**Goal:** Open-source template for PI attorneys in SC and WA to qualify leads with AI

---

## Overview

Transform the Pflug Lead Qualifier into `pi-lead-qualifier`, a free open-source template that other PI attorneys can deploy to automate lead qualification. The goal is to build goodwill and referral relationships in the PI community.

### Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Target user | Non-technical | Maximizes reach, biggest need |
| Feature tiers | Starter + Pro | Low barrier to entry, upgrade path |
| Setup experience | Web-based wizard | Familiar UI for non-technical users |
| Deployment | Local + Cloud | Test locally, deploy to cloud when serious |
| State support | SC and WA built-in | Initial release for two key markets |
| Customization | Wizard only | Users never touch config files |

---

## Repository Structure

```
pi-lead-qualifier/
├── README.md                    # Overview, quick start, screenshots
├── LICENSE                      # MIT license
├── CONTRIBUTING.md              # How to add states, report bugs
│
├── setup/                       # Web-based setup wizard
│   ├── app.py                   # Flask app serving setup UI
│   ├── templates/
│   │   ├── index.html           # Welcome + mode selection
│   │   ├── starter.html         # Starter mode wizard (3 steps)
│   │   └── pro.html             # Pro mode wizard (6 steps)
│   ├── static/                  # CSS, JS, images
│   └── validators.py            # API key validation helpers
│
├── data/
│   └── states/                  # 50 state JSON files
│       ├── SC.json              # {sol_years: 3, counties: [...]}
│       ├── CA.json
│       └── ...
│
├── src/                         # Core application (from P3)
├── templates/                   # Email templates
├── deploy/
│   ├── local/                   # Local run scripts
│   │   ├── start-mac.sh
│   │   └── start-windows.bat
│   └── railway/                 # One-click Railway deploy
│       ├── railway.json
│       └── Procfile
│
└── docs/
    ├── video-setup.md           # Links to YouTube walkthrough
    └── find-a-developer.md      # How to hire help if stuck
```

---

## Setup Wizard Flow

### Welcome Screen
- Logo, one-paragraph description
- Two buttons: "Starter Mode" and "Pro Mode"
- Comparison table showing features of each

### Starter Mode (3 steps)

**Step 1: Your Firm**
- Firm name (text input)
- Your name (text input)
- State (dropdown, all 50 states)
- Preferred counties (checkboxes, auto-populated from state, pre-selects major metro)

**Step 2: Airtable Connection**
- API key input
- "How to get this" expandable section with screenshots
- "Validate" button tests connection, shows green checkmark or specific error

**Step 3: AI Provider**
- Radio buttons: Claude or OpenAI (with cost comparison)
- API key input
- "Validate" button

→ "Generate My System" → Creates config, shows "Ready to Run" screen

### Pro Mode (3 additional steps)

**Step 4: Clio Integration**
- Client ID, Client Secret inputs
- OAuth flow walkthrough
- "Test Connection" validates

**Step 5: Gmail Setup**
- Sender email, intake email, notification email
- OAuth flow for Gmail API

**Step 6: Google Drive (optional)**
- For case comparison search
- Prominent "Skip" button

---

## State Data Files

Each state has a JSON file with all required data:

```json
{
  "name": "South Carolina",
  "abbreviation": "SC",
  "sol_years": 3,
  "sol_notes": "3 years from date of injury for personal injury",
  "counties": ["Abbeville", "Aiken", "Allendale", ...],
  "major_metros": {
    "Charleston": ["Charleston", "Berkeley", "Dorchester"],
    "Columbia": ["Richland", "Lexington"],
    "Greenville": ["Greenville", "Spartanburg", "Anderson"]
  },
  "default_preferred_counties": ["Charleston", "Berkeley", "Dorchester"]
}
```

### Wizard Behavior
- User selects state → loads that state's JSON
- County checkboxes pre-select `default_preferred_counties`
- "Select Metro Area" shortcuts available
- SOL is automatic - user never enters it

---

## Tiered Runtime Behavior

### Starter Mode (`"mode": "starter"`)
- Polls Airtable for new leads
- Scores with AI (Claude or OpenAI)
- Updates Airtable with: score, tier, recommendation, AI analysis
- **No Clio, no emails** - attorney reviews in Airtable manually

### Pro Mode (`"mode": "pro"`)
- Everything in Starter, plus:
- Tier 1 leads → auto-create Clio matter
- Tier 2 leads → email notification to attorney
- Tier 3 leads → polite decline email to lead (configurable)

### Upgrade Path
- Re-run wizard anytime
- Select "Pro Mode"
- Wizard detects existing config, preserves Starter settings
- Only prompts for new Clio/Gmail credentials

### Dashboard
- Shows current mode with upgrade banner
- Links back to wizard for upgrades

---

## Deployment Options

### Local Mode (Testing)

**Mac:**
```
1. Open Terminal (Spotlight → "Terminal")
2. Paste: ./start-mac.sh
3. Leave Terminal open
4. Visit http://localhost:8080
```

**Windows:**
```
1. Double-click "Start PI Qualifier.bat"
2. Leave window open
3. Visit http://localhost:8080
```

Warning: "Stops when you close laptop. For 24/7, see Cloud Deploy."

### Cloud Mode (Production)

One-click deploy buttons for:
- **Railway** (recommended) - ~$5/month
- **Render** - Alternative option

Flow:
1. Click deploy button
2. Forks repo to user's GitHub
3. Connects to Railway/Render
4. Prompts for environment variables
5. Deploys automatically

---

## Documentation Strategy

### README.md
- 30-second value prop with dashboard screenshot
- "Watch 5-minute setup video" link
- Feature comparison table (Starter vs Pro)
- "Get Started" button → wizard
- Simplified architecture diagram

### Video Content (YouTube)
1. **Overview** (2 min) - What it does, who it's for
2. **Starter Setup** (5 min) - Wizard walkthrough
3. **Pro Upgrade** (5 min) - Adding Clio + Gmail
4. **Cloud Deploy** (3 min) - Railway flow

### find-a-developer.md
- How to get help if stuck
- Upwork/Fiverr search terms
- Budget expectation: $100-300
- Contact for referrals

### Support Model
- GitHub Discussions (not Issues)
- Lower expectation of response
- Community-driven help

---

## Implementation Scope

### New Work Required

| Component | Effort | Notes |
|-----------|--------|-------|
| Setup wizard (Flask) | 4-6 hours | 6 screens, validation, config gen |
| State data files | 3-4 hours | SOL research + county lists |
| Mode-aware runtime | 1-2 hours | Feature flags in existing code |
| Local run scripts | 1 hour | .bat + .sh |
| Railway deploy config | 1 hour | railway.json, Procfile |
| README + docs | 2-3 hours | Screenshots, tables |
| Videos | 2-3 hours | Recording + editing |

**Total: 14-20 hours**

### Reusing from P3
- Core scoring engine ✓
- Airtable/Clio/Gmail clients ✓
- Claude/OpenAI integration ✓
- Dashboard ✓
- Config system ✓

### Not Building (YAGNI)
- User accounts / multi-tenant
- Payment processing
- Automatic updates
- Mobile app

---

## Next Steps

1. Create `pi-lead-qualifier` repo from P3
2. Build state data files (can parallelize)
3. Implement setup wizard
4. Add mode-aware feature flags
5. Create deploy scripts
6. Write documentation
7. Record videos
8. Publish and announce
