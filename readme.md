# AutoTube

AI-powered video generation and publishing platform. Give it a topic and niche, it handles everything from scriptwriting to uploading the finished video to YouTube.

Built with Next.js, FastAPI, Celery, and Google Gemini AI.

![Python](https://img.shields.io/badge/Python-3.11-blue)
![Next.js](https://img.shields.io/badge/Next.js-14-black)
![FastAPI](https://img.shields.io/badge/FastAPI-0.109-green)
![Docker](https://img.shields.io/badge/Docker-Compose-blue)
![License](https://img.shields.io/badge/License-MIT-yellow)

## How it works

1. **Trend discovery** - The agent scans Google Trends and Reddit for viral topics in your chosen niche
2. **Script generation** - Gemini AI writes a natural, human-sounding script with scene breakdowns
3. **Voice synthesis** - Edge TTS creates a neural voiceover from the script
4. **Video assembly** - FFmpeg composites stock footage, voiceover, and karaoke-style subtitles into a finished video
5. **Publishing** - Uploads directly to your YouTube channel, or schedules it for later

The whole pipeline runs as a background Celery task, so you can queue up multiple videos and let it work.

## Features

**Video formats**
- 9:16 vertical shorts (40-60 seconds) for YouTube Shorts, TikTok, Reels
- 16:9 horizontal videos (3-5 minutes) for standard YouTube

**Creative control**
- Pick from preset niches or type your own custom topic
- Choose your channel style: narration, what-if, explainer, listicle, documentary
- Set the tone: serious, casual, dramatic, educational, humorous
- Select from multiple AI narrator voices
- Background music with volume control

**Publishing options**
- Generate Only: create the video and download it, no upload
- Auto Publish: generate and upload to YouTube immediately
- Schedule: generate and schedule for a specific date and time

**LLM fallback chain**
- Primary: Gemini 2.5 Flash
- Fallback: Gemini 2.0 Flash
- Last resort: Groq (Llama 3.3 70B)

Smart rate limiting keeps you within free tier quotas.

## Tech stack

| Layer | Tech |
|-------|------|
| Frontend | Next.js 14, React, Tailwind CSS, shadcn/ui |
| Backend API | FastAPI, SQLAlchemy, Alembic |
| Task queue | Celery + Redis |
| Database | PostgreSQL |
| AI | Google Gemini API, Groq API |
| Video | FFmpeg, Edge TTS, Pexels API |
| Auth | JWT + OAuth2 (YouTube) |
| Deployment | Docker Compose |

## Project structure

```
autotube/
├── docker-compose.yml
├── backend/
│   ├── app/                  # FastAPI application
│   │   ├── api/              # REST endpoints
│   │   ├── models/           # Database models
│   │   ├── services/         # Auth, YouTube service
│   │   └── worker.py         # Celery task runner
│   ├── core/                 # Video generation engine
│   │   ├── main.py           # Batch agent orchestrator
│   │   ├── trend_agent.py    # Topic discovery
│   │   ├── script_agent.py   # AI script generation
│   │   ├── voice_agent.py    # TTS voiceover
│   │   ├── video_agent.py    # FFmpeg video assembly
│   │   ├── visual_engine.py  # Visual provider cascade
│   │   ├── metadata_agent.py # Title, tags, description
│   │   ├── youtube_agent.py  # YouTube upload + scheduling
│   │   ├── model_manager.py  # LLM provider with fallbacks
│   │   └── providers/        # Pexels, GeminiGen, Coverr, etc.
│   └── requirements.txt
└── frontend/
    ├── app/                  # Next.js pages
    ├── components/           # UI components
    └── lib/                  # API client
```

## Setup

### Prerequisites

- Docker and Docker Compose
- Google Gemini API key ([get one here](https://aistudio.google.com/))
- Pexels API key ([free, get one here](https://www.pexels.com/api/))

### 1. Clone and configure

```bash
git clone https://github.com/Hamzaakhtar87/autotube.git
cd autotube

# Create your environment file
cp .env.example .env
# Edit .env and add your API keys
```

### 2. Start everything

```bash
docker compose up -d
```

This starts 5 containers:
- **frontend** on `localhost:3000`
- **backend** on `localhost:8000`
- **worker** (Celery)
- **redis**
- **postgres**

### 3. Create an account

Open `http://localhost:3000`, register a new account, and you're ready to generate videos.

### 4. Connect YouTube (optional)

Go to Settings > Connect YouTube to enable direct uploading. You'll need to set up OAuth credentials in Google Cloud Console first.

## Environment variables

```bash
# Required
GEMINI_API_KEY=your_key_here

# Optional but recommended
GROQ_API_KEY=your_groq_key        # Fallback LLM
PEXELS_API_KEY=your_pexels_key    # Stock footage
GEMINIGEN_API_KEY=your_key        # AI-generated visuals

# Infrastructure (defaults work with Docker Compose)
DATABASE_URL=postgresql://autotube:autotube@db:5432/autotube
CELERY_BROKER_URL=redis://redis:6379/0
SECRET_KEY=your_secret_key
```

## Development

To run the frontend in dev mode with hot reload:

```bash
cd frontend
npm install
npm run dev
```

Backend changes require a Docker rebuild:

```bash
docker compose up -d --build backend worker
```

## API docs

Once the backend is running, interactive docs are at `http://localhost:8000/docs`.

Key endpoints:
- `POST /auth/register` - Create account
- `POST /auth/login` - Get JWT token
- `POST /jobs` - Start video generation
- `GET /jobs/{id}` - Check job status + logs
- `GET /config/preferences` - User preferences
- `GET /stats/dashboard` - Analytics

## License

MIT