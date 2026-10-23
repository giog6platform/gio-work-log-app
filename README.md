# Gio Work Log

Private work log with projects, tasks, completions and a timeline. It's a Node server with no dependencies, password-protected with HTTP Basic Auth, and hosted on Render's free plan.

## Refresh the data
1. Put the latest `task_context.json` in `data/` and the board export in `data/board/`. Both folders are gitignored.
2. Run `python3 scripts/build_data.py`. It writes `data/out/data.json` (gitignored) with emails, phone numbers and tokens stripped.
3. Run `scripts/push_data.sh`. It uploads the file to Render as the secret file `data.json` and redeploys. Task data never goes into git.

## Login
- User: `gio`
- Password: `SITE_PASSWORD` in `~/.env`.

## Local
`node --env-file=$HOME/.env server.js`, then open http://localhost:3000. Credentials live in `~/.env`.

## Code changes
Commit here, then run `scripts/deploy.sh "message"`. It copies the code to the public deploy repo, pushes it and triggers a Render deploy.
