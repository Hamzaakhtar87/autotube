# 🤖 Autonomous YouTube Shorts Agent

A fully automated, self-sustaining system that generates and uploads YouTube Shorts with **zero human interaction** after deployment.

## 🎯 What It Does

The agent runs **indefinitely** and performs the following every 24 hours:

1. **Discovers trending topics** from Google Trends & Reddit
2. **Generates viral scripts** using AI (dark psychology, uncomfortable truths)
3. **Creates neural voiceovers** using Edge TTS
4. **Builds 9:16 vertical videos** with burned-in subtitles
5. **Generates optimized metadata** (titles, descriptions, tags)
6. **Uploads to YouTube** as private/scheduled Shorts
7. **Repeats forever** without any human input

## 🏗️ Architecture

```
/agent
├── main.py              # Autonomous orchestrator
├── trend_agent.py       # Topic discovery
├── script_agent.py      # AI script generation
├── voice_agent.py       # Text-to-speech
├── video_agent.py       # FFmpeg video builder
├── metadata_agent.py    # SEO optimization
├── youtube_agent.py     # YouTube API uploader
├── memory.json          # Prevents topic repetition
├── config.py            # Configuration
├── requirements.txt     # Dependencies
└── README.md           # This file
```

## 📋 Prerequisites

### 1. System Requirements
- Python 3.8+
- FFmpeg installed and in PATH
- Linux/Mac (Windows works with WSL)

### 2. API Keys Required

#### YouTube Data API v3
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project
3. Enable **YouTube Data API v3**
4. Create OAuth 2.0 credentials (Desktop app)
5. Download `client_secrets.json` and place in `/agent` folder

#### Anthropic API
1. Get API key from [Anthropic Console](https://console.anthropic.com/)
2. Set environment variable:
   ```bash
   export ANTHROPIC_API_KEY="your-api-key-here"
   ```

## 🚀 Installation

```bash
# Clone or create the directory
mkdir agent && cd agent

# Install dependencies
pip install -r requirements.txt

# Verify FFmpeg is installed
ffmpeg -version

# Set API keys
export ANTHROPIC_API_KEY="sk-ant-..."
export YOUTUBE_API_KEY="your-youtube-api-key"  # Optional
```

## ⚙️ Configuration

Edit `config.py` to customize:

```python
# Video settings
VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920
VIDEO_FPS = 30

# Voice settings
VOICE_NAME = "en-US-ChristopherNeural"  # Change voice
VOICE_RATE = "+5%"  # Speed adjustment

# Scheduling
UPLOAD_HOUR = 14  # Upload time (2 PM)
LOOP_INTERVAL_HOURS = 24  # Generate every 24 hours

# Content categories
TOPIC_CATEGORIES = [
    "psychology",
    "dark psychology",
    "money psychology",
    "uncomfortable truths"
]
```

## 🎬 Usage

### First-Time Setup (Authentication)

```bash
# Run once to authenticate with YouTube
python main.py --once
```

This will:
1. Open browser for Google OAuth
2. Grant YouTube upload permissions
3. Save credentials to `credentials.json`
4. Generate and upload one test Short

### Run Autonomously Forever

```bash
# Start the autonomous agent
python main.py
```

The agent will:
- Generate 1 Short immediately
- Upload it as **private** (safe for review)
- Schedule it for next day at 2 PM
- Repeat every 24 hours **forever**

### Background Execution (Production)

```bash
# Run as background process
nohup python main.py > agent.log 2>&1 &

# Or use systemd (recommended)
sudo nano /etc/systemd/system/youtube-agent.service
```

Example systemd service:

```ini
[Unit]
Description=YouTube Shorts Agent
After=network.target

[Service]
Type=simple
User=youruser
WorkingDirectory=/path/to/agent
Environment="ANTHROPIC_API_KEY=sk-ant-..."
ExecStart=/usr/bin/python3 /path/to/agent/main.py
Restart=always
RestartSec=60

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable youtube-agent
sudo systemctl start youtube-agent
sudo systemctl status youtube-agent
```

## 📊 Monitoring

### View Logs
```bash
# Real-time logs
tail -f agent.log

# Or check systemd logs
journalctl -u youtube-agent -f
```

### Check Memory
```bash
# View used topics
cat memory.json
```

### Verify Uploads
```bash
# Check output directory
ls -lh output/
```

## 🔒 Safety Features

### Account Protection
- Videos upload as **PRIVATE** by default
- Never edits after upload (YouTube TOS compliant)
- Max 1 upload per day (quota-safe)
- Uses official YouTube Data API (no scraping)

### Content Safety
- Avoids repetition via `memory.json`
- Keeps last 100 topics in memory
- Filters for appropriate content
- No browser automation (TOS compliant)

### Error Handling
- Auto-retries on failure
- Logs all errors
- Continues on single failure
- Never crashes the loop

## 🛠️ Troubleshooting

### "FFmpeg not found"
```bash
# Ubuntu/Debian
sudo apt install ffmpeg

# Mac
brew install ffmpeg

# Verify
ffmpeg -version
```

### "YouTube API quota exceeded"
- Default quota: 10,000 units/day
- One upload costs ~1,600 units
- Max ~6 uploads/day
- This agent uploads 1/day (safe)

### "Authentication failed"
```bash
# Delete old credentials and re-authenticate
rm credentials.json
python main.py --once
```

### "No topics found"
- Check internet connection
- Verify Google Trends/Reddit are accessible
- Agent will generate synthetic topics as fallback

## 📈 Expected Results

### Timeline
- **Day 1-7**: Build foundation (7 Shorts)
- **Week 2-4**: Algorithm recognition
- **Month 2-3**: First viral Short likely
- **Month 6+**: Consistent growth

### Growth Factors
- Consistency (daily uploads)
- Topic quality (trending + evergreen)
- Hook effectiveness (first 3 seconds)
- Subtitle readability
- Upload timing (2 PM optimal)

## 🎨 Customization

### Change Voice
```python
# In config.py
VOICE_NAME = "en-GB-SoniaNeural"  # British female
VOICE_NAME = "en-US-GuyNeural"    # American male
```

[Full voice list](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/language-support?tabs=tts)

### Change Background
Replace the background video URL in `config.py`:
```python
BACKGROUND_VIDEO_URL = "https://your-stock-video-url.mp4"
```

Or use custom gradient colors in `video_agent.py`.

### Change Content Niche
```python
# In config.py
TOPIC_CATEGORIES = [
    "fitness myths",
    "productivity hacks",
    "money mindset",
    "stoicism"
]
```

## 📝 Folder Structure

```
agent/
├── main.py                 # Main orchestrator
├── trend_agent.py          # Topic discovery
├── script_agent.py         # Script generation
├── voice_agent.py          # TTS conversion
├── video_agent.py          # Video creation
├── metadata_agent.py       # SEO metadata
├── youtube_agent.py        # Upload handler
├── config.py               # Settings
├── requirements.txt        # Dependencies
├── memory.json            # Used topics (auto-created)
├── credentials.json       # YouTube auth (auto-created)
├── client_secrets.json    # OAuth credentials (you provide)
├── agent.log              # Logs (auto-created)
├── output/                # Final videos
│   └── short_*.mp4
└── temp/                  # Temporary files
    ├── audio_*.mp3
    ├── subtitles.srt
    └── background.mp4
```

## ⚖️ Legal & Ethics

### YouTube TOS Compliance
✅ Uses official API  
✅ No automation/bots  
✅ No spam or manipulation  
✅ Original content only  
✅ Proper rate limiting  

### Content Guidelines
- Generates factual psychological content
- No misinformation or harmful advice
- Educational/entertainment purpose
- Complies with YouTube Community Guidelines

### Responsibility
- Review first few uploads manually
- Monitor for any issues
- Ensure content aligns with your brand
- Use ethically and responsibly

## 🤝 Contributing

This is a production-ready autonomous system. Improvements welcome:
- Additional trend sources
- Better video templates
- Advanced scheduling logic
- Analytics integration

## 📄 License

MIT License - Use freely, modify as needed.

## 🆘 Support

For issues:
1. Check logs: `tail -f agent.log`
2. Verify API keys are set
3. Ensure FFmpeg is installed
4. Test with `--once` flag first

---

**Built for creators who want to scale content production autonomously.**

*Let the agent run. Let the growth compound. Focus on what matters.*