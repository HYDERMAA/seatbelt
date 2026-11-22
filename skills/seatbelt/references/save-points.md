# Save points

A save point is a full snapshot of the project you can go back to. Make one before every change,
name it after what is about to change, and tell the user in one line.

## Contents

1. If git is available (preferred)
2. If git is not available
3. In app builders
4. Going back to a save point
5. Saving a copy online (GitHub)

## 1. If git is available (preferred)

Git is a tool that keeps a history of every version of a project. Use it quietly and talk about
"save points", not commits, branches or repositories.

First time only, in the project folder:

```bash
git init
```

Before the first save point, make sure secrets cannot be saved. Create or update `.gitignore`:

```gitignore
# secrets
.env
.env.*
!.env.example
# bulky or generated folders
node_modules/
dist/
build/
.next/
__pycache__/
.venv/
.DS_Store
```

Then check nothing secret is already being tracked:

```bash
git ls-files | grep -Ei '(^|/)\.env($|\.)' | grep -v '\.env\.example$'
```

If that prints anything, stop it being tracked (`git rm --cached <file>`), and treat any keys in
it as leaked: see security-checklist.md, section "If a key leaked".

Make a save point:

```bash
git add -A
git commit -m "Save point: before adding payments"
```

If git asks who you are, set it for this project only:

```bash
git config user.name "Your Name"
git config user.email "you@example.com"
```

Tell the user: "Saved a save point called 'before adding payments'."

List save points (newest first):

```bash
git log --oneline -n 15
```

## 2. If git is not available

Copy the whole project folder, skipping bulky folders, with the date and time in the name.

Mac or Linux:

```bash
mkdir -p ../backups
tar --exclude=node_modules --exclude=.next --exclude=dist -czf "../backups/myapp-$(date +%Y%m%d-%H%M)-before-payments.tar.gz" .
```

Windows (PowerShell):

```powershell
New-Item -ItemType Directory -Force ..\backups | Out-Null
Compress-Archive -Path * -DestinationPath "..\backups\myapp-$(Get-Date -Format yyyyMMdd-HHmm)-before-payments.zip"
```

By hand: right-click the project folder, choose **Compress** (Mac) or **Send to > Compressed
(zipped) folder** (Windows), and rename the zip to include the date and what is about to change.

Note: backups contain `.env`. Keep them on the user's own computer, never upload them anywhere.

## 3. In app builders

Most builders keep their own history. Tell the user where it is and to note the version that works.

- **Lovable:** every change creates a version. Use the version history to view or restore an
  earlier one. Pin or bookmark the last version that worked.
- **Bolt:** use the version history in the project to go back to an earlier version.
- **Replit:** Agent creates checkpoints as it works; use **Rollback to here** on a checkpoint.
- **v0:** each generation is a version; pick an earlier version to go back.
- **Chat only (Claude.ai, ChatGPT):** ask the user to keep a copy of the last working file(s)
  before pasting new code, for example `index-working-before-login.html`.

Menu names change often. If a button is not where you expect, tell them to look for "history",
"versions", "checkpoints" or "restore".

## 4. Going back to a save point

Always explain first: "This takes the project back to how it was at 'before adding payments'.
Anything after that will be set aside, not deleted."

With git, the safe way (keeps everything, nothing is lost):

```bash
git stash push -u -m "set aside: broken attempt"   # only if there are unsaved changes
git log --oneline -n 15                              # find the save point
git switch -c attempt-2 <save-point-id>              # start fresh from it on a new line of work
```

To make the main project match a save point exactly while keeping history, use
`git revert` for the unwanted save points, or ask before using anything destructive. Never run
`git reset --hard` or delete history without the user's clear agreement.

Without git: unzip the backup into a new folder, check it runs, then use that folder.

## 5. Saving a copy online (GitHub)

GitHub is a website that stores copies of projects. Useful as an off-computer backup, but:

1. Check `.gitignore` covers `.env` first.
2. Run `scripts/check_secrets.py` before the first upload.
3. Make the repository **private** unless they deliberately want it public.
4. Remember: anything ever uploaded stays in the history, even if later deleted. A leaked key
   must be replaced, not just removed.
