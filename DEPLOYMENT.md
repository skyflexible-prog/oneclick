# Deployment Instructions

## Prerequisites

1. **GitHub Account** - To host your code
2. **Render.com Account** - For hosting the bot
3. **MongoDB Atlas Account** - For database (free tier available)
4. **Telegram Bot Token** - From @BotFather
5. **Delta Exchange API Credentials** - From Delta Exchange India

## Step 1: Setup MongoDB Atlas

1. Go to [MongoDB Atlas](https://www.mongodb.com/cloud/atlas)
2. Create a free cluster
3. Create a database user with password
4. Whitelist all IP addresses (0.0.0.0/0) for Render.com
5. Get your connection string:
   mongodb+srv://username:password@cluster.mongodb.net/straddle_bot?retryWrites=true&w=majority


## Step 2: Create Telegram Bot

1. Open Telegram and search for @BotFather
2. Send `/newbot` command
3. Follow instructions to create your bot
4. Save the bot token (looks like: `1234567890:ABCdefGHIjklMNOpqrsTUVwxyz`)
5. Get your Telegram user ID from @userinfobot

## Step 3: Generate Encryption Key

python scripts/generate_encryption_key.py

Save the generated key for environment variables.

## Step 4: Push Code to GitHub
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/yourusername/telegram-straddle-bot.git
git push -u origin main


## Step 5: Deploy to Render.com

1. Go to [Render.com](https://render.com)
2. Click "New +" → "Web Service"
3. Connect your GitHub repository
4. Configure:
   - **Name**: telegram-straddle-bot
   - **Environment**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn main:app -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:10000 --workers 1 --timeout 120`
   - **Plan**: Free

5. Add Environment Variables:
TELEGRAM_BOT_TOKEN=your_bot_token_here
MONGODB_URI=your_mongodb_connection_string
ENCRYPTION_KEY=your_generated_encryption_key
ADMIN_TELEGRAM_IDS=your_telegram_id
WEBHOOK_URL=https://your-app-name.onrender.com/webhook
ENVIRONMENT=production


6. Click "Create Web Service"

## Step 6: Setup Uptime Monitoring

### Option A: UptimeRobot

1. Go to [UptimeRobot](https://uptimerobot.com)
2. Add New Monitor:
- Type: HTTP(s)
- URL: `https://your-app-name.onrender.com/health`
- Interval: 5 minutes

### Option B: Freshping

1. Go to [Freshping](https://www.freshworks.com/website-monitoring/)
2. Add New Check:
- URL: `https://your-app-name.onrender.com/health`
- Interval: 1 minute (free tier)

## Step 7: Initialize Database

After deployment, run:

