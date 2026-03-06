# 🚀 AutoTube: The Zero-Dollar Deployment Guide

As a bootstrapped startup, we are deploying this powerful AI SaaS for exactly **$0.00/month**. Since our stack is built around Next.js and FastAPI Docker containers, we can heavily leverage the best free-tier cloud providers.

## The Production Infrastructure (Free Tier)

| Component | Provider | Why? | Cost |
| :--- | :--- | :--- | :--- |
| **Frontend (Next.js)** | [Vercel](https://vercel.com) | Native Next.js hosting. Connects directly to our GitHub. Gives us a free `autotube.vercel.app` SSL domain. | $0/mo |
| **Backend API (FastAPI)** | [Render.com](https://render.com) | Free "Web Service" tier. Connects to our GitHub repo to run our FastAPI Python server. Gives us `autotube-api.onrender.com`. | $0/mo |
| **Celery Worker** | [Render.com](https://render.com) | Free "Background Worker" tier. We can run our heavy FFmpeg video generation tasks here smoothly. | $0/mo |
| **Database (PostgreSQL)** | [Supabase](https://supabase.com) | Best-in-class free tier Postgres database. Massive 500MB free storage (enough for 50,000+ users). | $0/mo |
| **Message Broker (Redis)** | [Upstash](https://upstash.com) | Serverless Redis. Generous free tier (10,000 commands/day). Perfect for our Celery tasks. | $0/mo |

---

## 🛠️ Step-by-Step Deployment Walkthrough

### Step 1: Set up the Database & Redis (The Brains)
1. **PostgreSQL:** Go to [Supabase](https://supabase.com). Create a new project. 
   - Go to `Project Settings` -> `Database` and copy the `Database URL`.
   - Update `autotube_db` to your new Supabase URL.
2. **Redis:** Go to [Upstash](https://upstash.com). Create a new Redis database.
   - Copy the `REDIS_URL`. We need this for Celery.

### Step 2: Deploy the Backend (The Engine)
1. Go to [Render.com](https://render.com) and create a new **Web Service**.
2. Connect your GitHub repository (`Hamzaakhtar87/autotube`).
3. Set the Root Directory to `backend`.
4. Set the Start Command to: `uvicorn app.main:app --host 0.0.0.0 --port 10000`.
5. Add your Environment Variables:
   - `DATABASE_URL` = (From Supabase)
   - `CELERY_BROKER_URL` = (From Upstash)
   - `CELERY_RESULT_BACKEND` = (From Upstash)
   - `SECRET_KEY`, `JWT_SECRET`, `JWT_REFRESH_SECRET` = (Copy these from your local `PRODUCTION_SECRETS.md` or `.env` file)
   - `GEMINI_API_KEY`, etc.
6. **Deploy!** Render will give you a URL like `https://autotube.onrender.com`.

### Step 3: Deploy the Worker (The Factory)
1. In Render, create a new **Background Worker**.
2. Connect the same GitHub repo, set root directory to `backend`.
3. Set the Start Command to: `celery -A app.worker.celery worker --beat --loglevel=info --concurrency=2`
4. Copy the exact same Environment Variables from the Web Service!
5. **Deploy!** 

### Step 4: Deploy the Frontend (The Face)
1. Go to [Vercel](https://vercel.com) and click **Add New Project**.
2. Connect your GitHub repository.
3. Set the Root Directory to `frontend`.
4. Vercel will auto-detect Next.js! Just add your Environment Variables:
   - `NEXT_PUBLIC_API_URL` = `https://autotube.onrender.com` (Your Render URL)
   - `NEXT_PUBLIC_APP_URL` = The auto-generated Vercel URL (we'll update this once deployed).
5. **Deploy!**

You now have a globally distributed, highly available SaaS application running in production for $0.00! You can share your Vercel URL with the world.
