# Git Workflow Guide

## Repository Information
- **GitHub Repository**: https://github.com/vihaan69-420/GST-scanner
- **Branch**: main
- **Remote**: origin

## Daily Workflow for Updates and Commits

### 1. Check Current Status
```bash
git status
```
This shows you what files have been modified, added, or deleted.

### 2. Stage Your Changes

**Stage specific files:**
```bash
git add path/to/file.py
```

**Stage all changes:**
```bash
git add .
```

**Stage multiple specific files:**
```bash
git add file1.py file2.py src/bot/telegram_bot.py
```

### 3. Commit Your Changes
```bash
git commit -m "Brief description of what you changed"
```

**Example commit messages:**
- `git commit -m "Add new OCR feature for handwritten text"`
- `git commit -m "Fix bug in GST validation logic"`
- `git commit -m "Update documentation for setup process"`
- `git commit -m "Refactor sheets manager for better performance"`

**For multi-line commits:**
```bash
git commit -m "Add batch processing feature" -m "Implemented batch processing to handle multiple invoices. Added progress tracking and error handling for failed batches."
```

### 4. Push to GitHub
```bash
git push
```
or
```bash
git push origin main
```

### 5. Complete Workflow Example
```bash
# Check what changed
git status

# Stage all changes
git add .

# Commit with message
git commit -m "Update telegram bot with new commands"

# Push to GitHub
git push
```

## Common Scenarios

### Scenario 1: Made changes to multiple files
```bash
git add .
git commit -m "Update multiple modules for feature X"
git push
```

### Scenario 2: Fixed a bug
```bash
git add path/to/buggy/file.py
git commit -m "Fix: Correct invoice date parsing error"
git push
```

### Scenario 3: Added new feature
```bash
git add src/features/new_feature.py
git add docs/guides/NEW_FEATURE.md
git commit -m "Add new feature: Automated invoice categorization"
git push
```

### Scenario 4: Updated documentation
```bash
git add README.md docs/guides/SETUP_GUIDE.md
git commit -m "docs: Update setup and installation instructions"
git push
```

## Viewing History

### See recent commits
```bash
git log --oneline -10
```

### See what changed in last commit
```bash
git show
```

### See differences before committing
```bash
git diff
```

## Useful Tips

1. **Commit often**: Make small, focused commits rather than large ones
2. **Write clear messages**: Future you will thank present you
3. **Check before pushing**: Always run `git status` and `git diff` before committing
4. **Pull before push**: If working from multiple machines, pull first:
   ```bash
   git pull
   ```

## Ignoring Files

Files listed in `.gitignore` are automatically ignored:
- `.env` (your credentials)
- `credentials.json` (Google API credentials)
- `*.log` (log files)
- `*.pyc` and `__pycache__/` (Python cache)
- `*.jpg`, `*.png`, `*.pdf` (invoice images)
- `temp_invoices/` and `exports/` (temporary directories)

## Quick Commands Reference

| Command | Description |
|---------|-------------|
| `git status` | Show current status |
| `git add .` | Stage all changes |
| `git commit -m "message"` | Commit with message |
| `git push` | Push to GitHub |
| `git pull` | Get latest changes from GitHub |
| `git log` | View commit history |
| `git diff` | Show unstaged changes |
| `gh repo view --web` | Open repo in browser |

## Getting Help

- View git help: `git help <command>`
- View GitHub CLI help: `gh help`
- Check repo status online: https://github.com/vihaan69-420/GST-scanner

## Emergency: Undo Last Commit (Not Pushed)

If you made a mistake in your last commit and haven't pushed yet:
```bash
# Undo commit but keep changes
git reset --soft HEAD~1

# Make corrections
git add .
git commit -m "Corrected commit message"
```

## Authentication

Your git is configured to use GitHub CLI for authentication. If you encounter authentication issues:
```bash
gh auth status
gh auth refresh
```

---

**Remember**: Commit early, commit often, and always write meaningful commit messages!
