# Push gst-scanner-logged-in to git@github.com:vihaan69-420/GST-scanner.git on branch GST_Front
# Run from inside gst-scanner-logged-in folder (where this script lives).

$ErrorActionPreference = "Stop"
$remote = "git@github.com:vihaan69-420/GST-scanner.git"
$branch = "GST_Front"

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Host "Git not found. Run the commands in PUSH-TO-GITHUB.md manually in Git Bash or a terminal with git."
    exit 1
}

if (-not (Test-Path .git)) {
    git init
    git add .
    git commit -m "Initial: chat, history, help, settings, auth"
    git branch -M $branch
    git remote add origin $remote
    Write-Host "Pushing to $remote branch $branch ..."
    git push -u origin $branch
} else {
    git remote remove origin 2>$null
    git remote add origin $remote
    git push -u origin $branch
}

Write-Host "Done. Branch GST_Front: https://github.com/vihaan69-420/GST-scanner/tree/GST_Front"
