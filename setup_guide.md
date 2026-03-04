# 🚀 COMPLETE SETUP GUIDE

Follow these steps exactly to get your autonomous YouTube Shorts bot running.

---

## 📋 STEP 1: Get Your API Keys

### A) Anthropic API Key (for AI script generation)

1. Go to: https://console.anthropic.com/
2. Sign up or log in
3. Click "Get API Keys"
4. Create a new key
5. Copy it (starts with `sk-ant-...`)

**Save it somewhere safe - you'll need it in Step 4**

---

### B) YouTube API Credentials (for uploading)

1. Go to: https://console.cloud.google.com/
2. Create a new project (name it "YouTube Shorts Bot")
3. Enable the API:
   - Search for "YouTube Data API v3"
   - Click "Enable"
4. Create credentials:
   - Click "Create Credentials" → "OAuth 2.0 Client ID"
   - Configure consent screen (External, add your email)
   - Application type: "Desktop app"
   - Name: "YouTube Shorts Uploader"
   - Click "Create"
5. Download the JSON file
6. **Rename it to `client_secrets.json`**

**Save this file - you'll place it in the bot folder**

---

## 💻 STEP 2: Install Required Software

### A) Install Python (if you don't have it)

**Windows:**
- Download from: https://www.python.org/downloads/
- Run installer
- ✅ CHECK "Add Python to PATH"
- Click "Install Now"

**Mac/Linux:**
```bash
# Mac (using Homebrew)
brew install python3

# Linux (Ubuntu/Debian)
sudo apt update
sudo apt install python3 python3-pip
```

---

### B) Install FFmpeg (for video creation)

**Windows:**
1. Download from: https://www.gyan.dev/ffmpeg/builds/
2. Extract to `C:\ffmpeg`
3. Add to PATH:
   - Search "Environment Variables" in Windows
   - Edit "Path" → Add `C:\ffmpeg\bin`
4. Restart terminal

**Mac:**
```bash
brew install ffmpeg
```

**Linux:**
```bash
sudo apt update
sudo apt install ffmpeg
```

**Verify installation:**
```bash
ffmpeg -version
```

---

## 📁 STEP 3: Setup the Bot

### A) Create folder and download files

```bash
# Create folder
mkdir youtube-shorts-bot
cd youtube-shorts-bot

# Download all Python files (from the artifacts I provided):
# - config.py
# - trend_agent.py
# - script_agent.py
# - voice_agent.py
# - video_agent.py
# - metadata_agent.py
# - youtube_agent.py
# - main.py
# - requirements.txt
```

**Copy each file I provided above into this folder**

---

### B) Place your YouTube credentials

1. Take the `client_secrets.json` you downloaded in Step 1B
2. Place it in the `youtube-shorts-bot` folder
3. Your folder should now look like:

```
youtube-shorts-bot/
├── config.py
├── trend_agent.py
├── script_agent.py
├── voice_agent.py
├── video_agent.py
├── metadata_agent.py
├── youtube_agent.py
├── main.py
├── requirements.txt
└── client_secrets.json  ← Your YouTube credentials
```

---

## ⚙️ STEP 4: Configure Your Bot

Open `config.py` in a text editor and replace these lines:

```python
# Line 19 - Add your Anthropic API key
ANTHROPIC_API_KEY = "sk-ant-YOUR_ACTUAL_KEY_HERE"

# Line 43 - Choose your voice (optional)
VOICE_NAME = "en-US-GuyNeural"  # Male voice (default)
# OR
VOICE_NAME = "en-US-JennyNeural"  # Female voice

# Line 52 - Set upload time (optional)
UPLOAD_TIME_HOUR = 14  # 2 PM (change if you want different time)
```

**Available voices:**
- `en-US-GuyNeural` - Natural male
- `en-US-DavisNeural` - Confident male  
- `en-US-JennyNeural` - Natural female
- `en-US-AriaNeural` - Warm female
- `en-GB-RyanNeural` - British male
- `en-GB-SoniaNeural` - British female

---

## 📦 STEP 5: Install Dependencies

Open terminal in the bot folder and run:

```bash
# Install all required packages
pip install -r requirements.txt
```

Wait for installation to complete (may take 2-3 minutes).

---

## 🧪 STEP 6: Test the Bot

### A) First time: Authenticate with YouTube

```bash
python main.py --show-schedule
```

This will:
1. Open your browser for Google login
2. Ask for YouTube permissions
3. Show you the upload schedule
4. Save credentials for future use

**Click "Allow" to grant permissions**

---

### B) Test video generation (without uploading)

```bash
python main.py --test-single
```

This will:
- Generate 1 complete video (takes 3-5 minutes)
- Save it in the `output/` folder
- NOT upload it yet

**Check the video to make sure everything works!**

---

## 🚀 STEP 7: Run the Full Bot

Once you've tested and everything works:

```bash
python main.py
```

**What happens:**
1. ✅ Generates 7 videos (takes 20-30 minutes)
2. ✅ Uploads Video 1 immediately as PUBLIC
3. ✅ Schedules Videos 2-7 for next 6 days at 2 PM
4. ✅ Shows you all the video links

**After this completes, you're done for the week!**

---

## 📅 STEP 8: Weekly Routine

**Every 7 days:**

```bash
cd youtube-shorts-bot
python main.py
```

That's it! The bot will:
- Generate 7 new videos
- Upload 1 immediately
- Schedule 6 for the week
- Avoid repeating topics

**Set a reminder in your calendar for weekly runs!**

---

## 🎨 CUSTOMIZATION OPTIONS

### Change Content Niche

Edit `config.py` line 58:

```python
TOPIC_CATEGORIES = [
    "fitness tips",        # Your niche
    "workout motivation",  # here
    "health facts",
    "nutrition tips"
]
```

---

### Change Upload Time

Edit `config.py` line 52:

```python
UPLOAD_TIME_HOUR = 18  # 6 PM uploads
```

---

### Change Video Length

Edit `config.py` lines 28-29:

```python
SCRIPT_MIN_DURATION = 30  # Minimum seconds
SCRIPT_MAX_DURATION = 50  # Maximum seconds
```

---

## 🆘 TROUBLESHOOTING

### "ModuleNotFoundError"
```bash
pip install [missing-module-name]
```

### "FFmpeg not found"
- Reinstall FFmpeg
- Make sure it's in PATH
- Restart terminal

### "YouTube API quota exceeded"
- Wait 24 hours (resets daily at midnight PST)
- Or request quota increase in Google Cloud Console

### "Authentication failed"
```bash
# Delete old credentials and re-authenticate
rm credentials.json
python main.py --show-schedule
```

### Videos too short/long
- Edit `SCRIPT_MIN_DURATION` and `SCRIPT_MAX_DURATION` in `config.py`

---

## 📊 Expected Results

### Timeline:
- **Week 1-2:** Building foundation (14 videos)
- **Week 3-4:** Algorithm starts showing your content
- **Month 2-3:** First viral Short likely
- **Month 6+:** Consistent growth

### Key Metrics:
- **Consistency:** Daily uploads = algorithm boost
- **Quality:** 40-60s = optimal engagement
- **Timing:** 2 PM = high viewership time

---

## ✅ CHECKLIST

Before your first run, make sure you have:

- [ ] Python installed and working
- [ ] FFmpeg installed and in PATH
- [ ] Anthropic API key in `config.py`
- [ ] `client_secrets.json` from Google Cloud Console
- [ ] All Python files in one folder
- [ ] `pip install -r requirements.txt` completed
- [ ] Tested with `--test-single` flag
- [ ] Authenticated with YouTube (browser login)

---

## 🎯 NEXT STEPS

1. Run the bot now: `python main.py`
2. Check your YouTube Studio to see the videos
3. Set a weekly reminder for 7 days from now
4. Let the algorithm work its magic
5. Monitor analytics in YouTube Studio

**Pro tip:** Don't change anything for the first 2 weeks. Let the system prove itself first!

---

## 💡 PRO TIPS

1. **Best upload times:** 2 PM, 6 PM, or 9 PM
2. **Consistency > perfection:** Don't skip weeks
3. **Check analytics weekly:** See what's working
4. **First video matters:** Make sure test video looks good
5. **Be patient:** Growth compounds over time

---

## 🤝 SUPPORT

If you get stuck:

1. Check the `agent.log` file for errors
2. Try the test mode first: `python main.py --test-single`
3. Make sure all API keys are correct in `config.py`
4. Verify FFmpeg works: `ffmpeg -version`

---

**You're all set! Run the bot and watch your channel grow on autopilot! 🚀**