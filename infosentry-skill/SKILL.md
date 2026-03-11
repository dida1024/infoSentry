---
name: infosentry
description: Access and manage the infoSentry intelligent information tracking platform. Read goals, sources, notifications and more through the infoSentry API.
---

# infoSentry Skill

> Connect to the infoSentry platform to track, match, and push information intelligently.

## First-Time Setup

Before using this skill, you need to configure your API credentials.

### Step 1: Get an API Key

1. Log in to your infoSentry instance
2. Go to **Settings > Developer Center** (设置 > 开发者中心)
3. Click **Create Key** (创建 Key)
4. Select the scopes you need (e.g., `goals:read`, `sources:read`)
5. Copy the generated key (starts with `isk_`)

### Step 2: Run Setup

```bash
python3 scripts/setup.py
```

This will prompt you for:
- **Base URL**: Your infoSentry API endpoint (e.g., `https://your-domain.com/api/v1`)
- **API Key**: The key you created above

Configuration is stored at `~/.infosentry/config.json`.

## Capabilities

This skill enables you to:

1. **Goals** — List, read, create, and manage tracking goals
2. **Sources** — Browse and subscribe to information sources
3. **Notifications** — Read notifications/inbox and provide feedback
4. **Raw API** — Send arbitrary API requests

## Usage

### CLI Tool

Use `scripts/infosentry.py` (pure Python, no dependencies needed):

```bash
# List all active goals
python3 scripts/infosentry.py goals list --status active

# Get a specific goal
python3 scripts/infosentry.py goals get <goal_id>

# List sources
python3 scripts/infosentry.py sources list

# List notifications
python3 scripts/infosentry.py notifications list

# Raw API request
python3 scripts/infosentry.py raw GET /goals
python3 scripts/infosentry.py raw POST /goals '{"name": "test", "description": "test goal"}'
```

### Direct API Calls

You can also call the API directly:

```python
import urllib.request
import json

config_path = os.path.expanduser("~/.infosentry/config.json")
with open(config_path) as f:
    config = json.load(f)

req = urllib.request.Request(
    f"{config['base_url']}/goals",
    headers={"X-API-Key": config["api_key"]}
)
with urllib.request.urlopen(req) as resp:
    data = json.loads(resp.read())
```

## API Reference

See [references/api-reference.md](references/api-reference.md) for the complete API documentation.

## Authentication

All requests use the `X-API-Key` header:

```
X-API-Key: isk_YOUR_KEY_HERE
```

JWT Bearer tokens also work if you have one from the web interface.

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `Config file not found` | Run `python3 scripts/setup.py` |
| `HTTP 401` | Check your API Key is valid and not expired |
| `HTTP 403` | Your API Key is missing the required scope |
| `Connection refused` | Check your Base URL is correct |
