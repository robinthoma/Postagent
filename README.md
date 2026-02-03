# LinkedIn Post Agent

A human-in-the-loop autonomous agent that collects tech articles from RSS feeds, generates LinkedIn-ready post drafts, and posts to LinkedIn via the official API **only after manual approval**.

## Features

- 🔄 **Automated RSS Feed Monitoring**: Polls configured feeds on a schedule
- 🤖 **AI-Powered Draft Generation**: Creates engaging LinkedIn posts from articles
- 👁️ **Human-in-the-Loop**: Requires manual approval before posting
- 🔐 **Official LinkedIn API**: Uses OAuth 2.0 and UGC Posts API (no scraping)
- 🗄️ **SQLite Database**: Tracks drafts, posts, and tokens
- 📅 **Background Scheduler**: APScheduler for automated feed polling
- 🧪 **Tested**: Unit tests with pytest
- 🐳 **Docker Support**: Containerized deployment ready

## Tech Stack

- **Python**: 3.11+
- **Web Framework**: FastAPI + Jinja2 templates
- **Scheduler**: APScheduler
- **Database**: SQLite
- **HTTP**: requests
- **RSS Parsing**: feedparser
- **Testing**: pytest

## Project Structure

```
linkedin-post-agent/
├── README.md
├── .env.example
├── .gitignore
├── pyproject.toml
├── Dockerfile
├── docker-compose.yml
├── data/                     # Database (created at runtime)
├── src/
│   └── linkedin_agent/
│       ├── __init__.py
│       ├── main.py           # FastAPI application
│       ├── config.py         # Configuration management
│       ├── db.py             # Database operations
│       ├── models.py         # Data models
│       ├── scheduler.py      # Background scheduler
│       ├── feeds/            # RSS feed parsing
│       ├── drafting/         # Post generation
│       ├── linkedin/         # LinkedIn API integration
│       ├── web/              # Web UI routes & templates
│       └── utils/            # Utility functions
└── tests/                    # Unit tests
```

## Setup

### Prerequisites

1. **Python 3.11+** installed
2. **LinkedIn Developer App** with OAuth 2.0 credentials
   - Create an app at: https://www.linkedin.com/developers/apps
   - Add redirect URI: `http://localhost:8000/oauth/linkedin/callback`
   - Request permissions: `w_member_social` (required), `r_liteprofile` (optional)

### Installation

1. **Clone or download the project**:
   ```bash
   cd linkedin-post-agent
   ```

2. **Create virtual environment**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -e .
   ```

   Or for development with testing tools:
   ```bash
   pip install -e ".[dev]"
   ```

4. **Configure environment variables**:
   ```bash
   cp .env.example .env
   ```

   Edit `.env` with your settings:
   ```bash
   # LinkedIn OAuth credentials from your LinkedIn Developer App
   LINKEDIN_CLIENT_ID=your_client_id_here
   LINKEDIN_CLIENT_SECRET=your_client_secret_here
   LINKEDIN_REDIRECT_URI=http://localhost:8000/oauth/linkedin/callback
   LINKEDIN_SCOPES=w_member_social r_liteprofile

   # Optional: Manually provide person URN if /v2/me API fails
   # Format: urn:li:person:YOUR_ID
   LINKEDIN_PERSON_URN=

   # RSS feeds to monitor (comma-separated)
   FEEDS=https://news.ycombinator.com/rss,https://techcrunch.com/feed/

   # Polling interval (in seconds)
   POLL_SECONDS=1800

   # Database path
   DB_PATH=./data/agent.db

   # Base URL for OAuth callbacks
   BASE_URL=http://localhost:8000
   ```

## Usage

### Running Locally

1. **Start the application**:
   ```bash
   uvicorn linkedin_agent.main:app --reload
   ```

   The app will be available at: http://localhost:8000

2. **Follow the "Happy Path" workflow**:

   **Step 1: Authenticate with LinkedIn**
   - Navigate to http://localhost:8000
   - Click "Login with LinkedIn"
   - Authorize the application
   - You'll be redirected back with a success message

   **Step 2: Poll RSS Feeds**
   - Return to home page
   - Click "Poll Feeds Now"
   - The app will fetch articles and create drafts

   **Step 3: Review Drafts**
   - Navigate to "Pending Drafts" or http://localhost:8000/drafts?status=PENDING
   - Review each generated post

   **Step 4: Approve & Post**
   - Click "✓ Approve & Post" on any draft you want to publish
   - Confirm the action
   - The post will be published to your LinkedIn profile

3. **Automatic polling**:
   - Once started, the app automatically polls feeds every `POLL_SECONDS`
   - New drafts are created automatically
   - You still need to manually approve each post

### Running with Docker

1. **Build and start**:
   ```bash
   docker-compose up -d
   ```

2. **Access the app**:
   - Open http://localhost:8000

3. **Stop the app**:
   ```bash
   docker-compose down
   ```

## Running Tests

```bash
pytest
```

Run with coverage:
```bash
pytest --cov=linkedin_agent --cov-report=html
```

## LinkedIn API Details

### OAuth 2.0 Authorization Code Flow

1. **Authorization Request**: User clicks "Login" → redirected to LinkedIn
   - Endpoint: `https://www.linkedin.com/oauth/v2/authorization`
   - Parameters: `response_type=code`, `client_id`, `redirect_uri`, `scope`, `state`

2. **Token Exchange**: LinkedIn redirects back with `code` → exchange for `access_token`
   - Endpoint: `https://www.linkedin.com/oauth/v2/accessToken`
   - Method: POST with `grant_type=authorization_code`

3. **User Info** (optional): Fetch person URN
   - Endpoint: `https://api.linkedin.com/v2/me`
   - Requires: `r_liteprofile` scope

### Posting via UGC Posts API

- **Endpoint**: `https://api.linkedin.com/v2/ugcPosts`
- **Method**: POST
- **Headers**:
  - `Authorization: Bearer {access_token}`
  - `X-Restli-Protocol-Version: 2.0.0`
  - `Content-Type: application/json`

- **Payload Structure**:
  ```json
  {
    "author": "urn:li:person:XXXX",
    "lifecycleState": "PUBLISHED",
    "specificContent": {
      "com.linkedin.ugc.ShareContent": {
        "shareCommentary": { "text": "Your post text here" },
        "shareMediaCategory": "NONE"
      }
    },
    "visibility": {
      "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
    }
  }
  ```

### Required Permissions

- **w_member_social** (REQUIRED): Post, comment, and react on behalf of the member
- **r_liteprofile** (OPTIONAL): Read basic profile information to get person URN

> **Note**: If you cannot obtain `r_liteprofile` or the `/v2/me` endpoint fails, you can manually set `LINKEDIN_PERSON_URN` in your `.env` file. Find your LinkedIn ID from your profile URL or using developer tools.

## Draft Generation

Posts are automatically generated with:
- **Title**: Used as the hook/headline
- **Takeaways**: 2-4 bullet points from article summary
- **Link**: Direct link to the article
- **Hashtags**: 3-6 relevant hashtags (customizable in code)

**Rules**:
- Maximum 3000 characters (LinkedIn limit)
- No empty posts
- URLs normalized to prevent duplicates
- Tracking parameters removed

## Security & Safety

- ✅ **Human approval required**: No automatic posting without explicit user action
- ✅ **OAuth state validation**: CSRF protection in OAuth flow
- ✅ **Token expiration checking**: Validates tokens before posting
- ✅ **Error handling**: Graceful degradation on API failures
- ✅ **Secure secrets**: All credentials in environment variables
- ✅ **No logging of tokens**: Access tokens never logged

## Database Schema

### `tokens` table
- `id`: Primary key (always 1)
- `access_token`: LinkedIn OAuth access token
- `expires_at`: Unix timestamp
- `person_urn`: LinkedIn person URN

### `drafts` table
- `id`: Primary key (autoincrement)
- `title`: Article title
- `url`: Normalized article URL (unique)
- `summary`: Article summary
- `post_text`: Generated LinkedIn post text
- `status`: PENDING, POSTED, or FAILED
- `created_at`: Unix timestamp
- `posted_at`: Unix timestamp (nullable)
- `linkedin_response`: API response text (nullable)

### `posted` table
- `url`: Normalized URL (primary key)
- `posted_at`: Unix timestamp

## Troubleshooting

### "No person URN available"
- Ensure you have `r_liteprofile` scope enabled
- Or manually set `LINKEDIN_PERSON_URN` in `.env`
- Format: `urn:li:person:YOUR_LINKEDIN_ID`

### "Token expired"
- Click "Login with LinkedIn" again to refresh

### "Failed to post"
- Check LinkedIn API status
- Verify `w_member_social` permission is granted
- Check logs for detailed error messages

### No feeds appearing
- Verify `FEEDS` environment variable is set
- Check feed URLs are valid and accessible
- Review application logs for feed parsing errors

## Development

### Code Style

```bash
# Format code
black src/ tests/

# Lint
ruff check src/ tests/
```

### Adding New Features

- **New feed sources**: Add parsers in `src/linkedin_agent/feeds/`
- **Custom draft templates**: Modify `src/linkedin_agent/drafting/generator.py`
- **UI changes**: Edit Jinja2 templates in `src/linkedin_agent/web/templates/`

## License

This project is provided as-is for educational and personal use.

## Disclaimer

This tool interacts with LinkedIn's official API. Ensure compliance with:
- LinkedIn's Terms of Service
- LinkedIn API Terms of Use
- Your organization's social media policies

**Use responsibly and always review posts before publishing.**

## Support

For issues or questions:
1. Check application logs for detailed error messages
2. Verify environment configuration
3. Ensure LinkedIn OAuth app is properly configured
4. Review LinkedIn API documentation: https://docs.microsoft.com/en-us/linkedin/

---

Built with ❤️ using FastAPI and the LinkedIn Official API
