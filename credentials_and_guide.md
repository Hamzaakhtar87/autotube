# AutoTube: Enterprise Credentials & Quick Start Guide

## 🔐 Enterprise Account Credentials

You can use the following default enterprise account credentials to log into your frontend web application:

- **Email:** `hamza@autotube.com`
- **Password:** `Enterprise2026!`

*(Note: These have been freshly secured for you. I recommend logging in and changing your password or keeping this file secure if needed!)*

---

## 🚀 Application Quick Start Guide

Whenever you want to start up the AutoTube applications components (Frontend, Backend, Database, Redis, and Worker Queue) locally without any hassle, just use these simple commands.

### 1. Starting the Application
Open your terminal and run the following commands:
```bash
# Navigate to the project directory
cd /home/hamza-akhtar/Desktop/autotube

# Start all Docker containers in the background (detached mode)
docker compose up -d
```
*Tip: If you ever make changes to any source code and want to ensure those changes are fully built, you can run `docker compose up -d --build` instead.*

### 2. Stopping the Application
When you are completely done for the day or need to reboot the server, you can cleanly stop it by running:
```bash
# Using 'down' will stop and remove all related containers
docker compose down
```

### 3. Application Access URLs
Once the docker containers are successfully booted up, your application interfaces will be alive at:

- **Frontend Dashboard:** [http://localhost:3000](http://localhost:3000)
- **Backend API Docs:** [http://localhost:8000/docs](http://localhost:8000/docs)

Enjoy operating your newly built autonomous tube engine! Let me know if you need to run any specific task in this session.
