# GST Scanner â€” Logged-in app (Chat, History, Help, Settings)

This repo contains only the **logged-in experience**: chat, history, help, settings, and full auth (login/register/session). It is exported from the main GST Scanner project.

## What's included

- **Chat** â€” Main dashboard with invoice/order upload and conversation UI
- **History** â€” History list and History & Reports (GSTR-1 / GSTR-3B)
- **Help** â€” FAQ and instructions
- **Settings** â€” Profile, subscription, usage, theme
- **Auth** â€” Login, register, session, middleware protection for \/dashboard\

## Run locally

\\\ash
npm install
cp .env.example .env   # edit if you use Google OAuth or other env vars
npm run dev
\\\

Then open http://localhost:3000 â€” you'll be redirected to login. After logging in you get the dashboard with Chat, History, Help, and Settings.

## Push this to GitHub

\\\ash
cd gst-scanner-logged-in
git init
git add .
git commit -m "Initial: chat, history, help, settings, auth"
# Create a new repository on GitHub (e.g. gst-scanner-logged-in), then:
git remote add origin https://github.com/YOUR_USERNAME/gst-scanner-logged-in.git
git branch -M main
git push -u origin main
\\\
