# Push this folder to GitHub (GST-scanner) on branch **GST_Front**

Run these commands **inside this folder** (`gst-scanner-logged-in`) in a terminal where **git** is installed (Git Bash, PowerShell, or CMD with Git in PATH).

## Push to branch **GST_Front**

```bash
git init
git add .
git commit -m "Initial: chat, history, help, settings, auth"
git branch -M GST_Front
git remote add origin git@github.com:vihaan69-420/GST-scanner.git
git push -u origin GST_Front
```

## If the branch GST_Front already exists and you want to overwrite it

```bash
git push -u origin GST_Front --force
```

## Using HTTPS instead of SSH

Use this remote and push the same branch:

```bash
git remote add origin https://github.com/vihaan69-420/GST-scanner.git
git push -u origin GST_Front
```
