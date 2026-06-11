#!/usr/bin/env bash
# orchestrator-mechanics.sh — deterministic queue manager for Max Agency
#
# Runs all orchestrator steps that require no judgment:
#   promote, dispatch, reclaim stale, close merged, create CTO review issues,
#   route verdicts, escalate via Telegram.
#
# Stdout: JSON summary consumed by the Hermes orchestrator profile.
# Stderr: verbose log (appended to cron-output.log by the caller).
#
# Usage: PROJECT_REPO=owner/repo orchestrator-mechanics.sh
#        Escalations use Hermes's own Telegram gateway if one is configured
#        (TELEGRAM_BOT_TOKEN + TELEGRAM_HOME_CHANNEL or TELEGRAM_CHAT_ID in
#        ~/.hermes/.env). Max Agency does not set this up itself — if Hermes
#        has no Telegram gateway, escalations go to escalations.log instead.

set -euo pipefail

REPO="${PROJECT_REPO:?PROJECT_REPO not set}"
NOW=$(date -u --iso-8601=seconds)

# Counters for the final status line
promoted=0; dispatched=0; warnings=0; escalations=0; kickoffs_found=0

log() { echo "[$(date -u +%H:%M:%S)] $*" >&2; }

gh_safe() {
  # Run a gh command; on permission error abort the whole script.
  local out
  if ! out=$(gh "$@" 2>&1); then
    if echo "$out" | grep -qi "permission\|403\|401"; then
      echo "TICK_FAIL auth: $out" >&2; exit 1
    fi
    echo "$out" >&2; return 1
  fi
  echo "$out"
}

telegram() {
  local msg="$1"
  local chat_id="${TELEGRAM_CHAT_ID:-${TELEGRAM_HOME_CHANNEL:-}}"
  if [[ -n "${TELEGRAM_BOT_TOKEN:-}" && -n "$chat_id" ]]; then
    curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
      -d chat_id="${chat_id}" -d text="${msg}" >/dev/null
  else
    echo "ESCALATION @ $NOW:" >> ~/.hermes/profiles/orchestrator/escalations.log
    echo "$msg" >> ~/.hermes/profiles/orchestrator/escalations.log
  fi
  ((escalations++))
}

# ── Step 1: Heartbeat ────────────────────────────────────────────────────────
echo "$NOW" > ~/.hermes/profiles/orchestrator/heartbeat.txt
log "heartbeat written"

# ── Step 2: Pull latest state ────────────────────────────────────────────────
CACHE=~/.hermes-cache/${REPO}
if [[ ! -d "$CACHE" ]]; then
  gh repo clone "$REPO" "$CACHE" >&2
fi
git -C "$CACHE" pull --rebase 2>&1 | grep -v "^Already up to date" >&2 || true
log "repo up to date"

# ── Step 3: Detect kickoff issues (LLM handles these — we just flag them) ────
KICKOFFS=$(gh_safe issue list --repo "$REPO" --label kickoff --state open \
  --json number,title --limit 10)
KICKOFF_COUNT=$(echo "$KICKOFFS" | python3 -c "import json,sys; print(len(json.load(sys.stdin)))")
if [[ "$KICKOFF_COUNT" -gt 0 ]]; then
  kickoffs_found=$KICKOFF_COUNT
  log "found $KICKOFF_COUNT kickoff issue(s) — signalling LLM"
fi

# ── Step 5: Promote ready tasks ──────────────────────────────────────────────
log "checking backlog for promotable tasks..."
BACKLOG=$(gh_safe issue list --repo "$REPO" --label backlog --state open \
  --json number,body --limit 100)

_py_promoted=$(echo "$BACKLOG" | python3 -c "
import json, sys, subprocess, re
issues = json.load(sys.stdin)
repo = '${REPO}'
n = 0
for issue in issues:
    body = issue.get('body','') or ''
    m = re.search(r'Depends-on:\s*(.+)', body)
    if not m: continue
    deps_raw = m.group(1).strip()
    if deps_raw.lower() in ('none',''): dep_ids = []
    else: dep_ids = [int(x.strip().lstrip('#')) for x in deps_raw.split(',') if x.strip().lstrip('#').isdigit()]
    all_closed = all(
        subprocess.run(['gh','issue','view',str(d),'--repo',repo,'--json','state','--jq','.state'],
            capture_output=True,text=True).stdout.strip().upper() == 'CLOSED'
        for d in dep_ids
    ) if dep_ids else True
    if all_closed:
        subprocess.run(['gh','issue','edit',str(issue['number']),'--repo',repo,
            '--remove-label','backlog','--add-label','ready'], capture_output=True)
        n += 1
print(n)
" 2>/dev/null) || _py_promoted=0
promoted=$(( promoted + _py_promoted ))
log "promoted $promoted tasks backlog→ready"

# ── Step 6: Dispatch ready tasks ─────────────────────────────────────────────
READY=$(gh_safe issue list --repo "$REPO" --label ready --state open \
  --json number,title,labels,assignees --limit 50)

_dispatched=$(echo "$READY" | python3 -c "
import json, sys, subprocess
issues = json.load(sys.stdin)
repo = '${REPO}'
now = '${NOW}'
n = 0
for issue in issues:
    if issue['assignees']: continue
    num = issue['number']
    labels = [l['name'] for l in issue['labels']]
    assigned = next((l for l in labels if l.startswith('assigned:')), None)
    if not assigned: continue
    model = assigned.replace('assigned:', '')
    subprocess.run(['gh','issue','comment',str(num),'--repo',repo,
        '--body', f'Dispatched to {model}. {now}'], capture_output=True)
    subprocess.run(['gh','issue','edit',str(num),'--repo',repo,
        '--remove-label','ready','--add-label','in-progress'], capture_output=True)
    n += 1
    print(f'  dispatched #{num} to {model}', file=sys.stderr)
print(n)
" 2>/dev/null) || _dispatched=0
dispatched=$(( dispatched + _dispatched ))
log "dispatched $_dispatched tasks"

# ── Step 7: Reclaim stale assignments ────────────────────────────────────────
log "checking for stale in-progress issues..."
IN_PROGRESS=$(gh_safe issue list --repo "$REPO" --label in-progress --state open \
  --json number,title,labels,assignees,createdAt --limit 100)

echo "$IN_PROGRESS" | python3 -c "
import json, sys, subprocess
from datetime import datetime, timezone, timedelta
issues = json.load(sys.stdin)
repo = '${REPO}'
now = datetime.now(timezone.utc)
for issue in issues:
    num = issue['number']
    if not issue['assignees']: continue
    label_names = [l['name'] for l in issue.get('labels',[])]
    if 'role:cto' in label_names: continue  # CTO reviews have no branch by design
    assignee = issue['assignees'][0]['login']
    # Check for branch
    branches = subprocess.run(['gh','api',f'repos/{repo}/branches','--jq','.[].name'],
        capture_output=True, text=True).stdout
    branch = next((b.strip() for b in branches.splitlines() if f'/{num}-' in b), None)
    if branch:
        # Check last commit time
        info = subprocess.run(['gh','api',f'repos/{repo}/branches/{branch}','--jq','.commit.commit.committer.date'],
            capture_output=True, text=True).stdout.strip()
        if info:
            last = datetime.fromisoformat(info.replace('Z','+00:00'))
            age = (now - last).total_seconds() / 60
            # Check for open PR
            prs = subprocess.run(['gh','pr','list','--repo',repo,'--head',branch,'--state','open','--json','number'],
                capture_output=True, text=True).stdout
            has_pr = len(json.loads(prs)) > 0
            if age > 60 and not has_pr:
                # Count prior reclaims
                comments = subprocess.run(['gh','issue','view',str(num),'--repo',repo,'--comments','--json','comments','--jq','.[].body'],
                    capture_output=True, text=True).stdout
                reclaims = comments.count('Reclaimed:')
                if reclaims >= 3:
                    print(f'ESCALATE #{num}: reclaimed 3+ times, needs human', file=sys.stderr)
                else:
                    subprocess.run(['gh','issue','edit',str(num),'--repo',repo,
                        '--remove-assignee',assignee,'--remove-label','blocked'], capture_output=True)
                    subprocess.run(['gh','issue','comment',str(num),'--repo',repo,
                        '--body','Reclaimed: branch idle >60m, no PR. Re-dispatching.'], capture_output=True)
                    print(f'  reclaimed #{num} (idle branch, no PR)', file=sys.stderr)
    else:
        # No branch at all — if assigned, it's a dead claim
        subprocess.run(['gh','issue','edit',str(num),'--repo',repo,
            '--remove-assignee',assignee,'--remove-label','blocked'], capture_output=True)
        subprocess.run(['gh','issue','comment',str(num),'--repo',repo,
            '--body','Reclaimed: prior claim produced no branch within the tick. Re-dispatching.'], capture_output=True)
        print(f'  reclaimed #{num} (no branch)', file=sys.stderr)
" 2>&1 | grep -v "^$" >&2 || true

# ── Step 7.5: Close task issues whose PR merged ──────────────────────────────
log "closing issues for merged PRs..."
MERGED=$(gh_safe pr list --repo "$REPO" --state merged --json number,body,mergedAt --limit 30)
echo "$MERGED" | python3 -c "
import json, sys, subprocess, re
prs = json.load(sys.stdin)
repo = '${REPO}'
for pr in prs:
    m = re.search(r'(?:Closes|Fixes)\s+#(\d+)', pr['body'] or '', re.IGNORECASE)
    if not m: continue
    issue_num = m.group(1)
    state = subprocess.run(['gh','issue','view',issue_num,'--repo',repo,'--json','state','--jq','.state'],
        capture_output=True, text=True).stdout.strip()
    if state.upper() == 'OPEN':
        subprocess.run(['gh','issue','close',issue_num,'--repo',repo,
            '--reason','completed','--comment',f'Closed by orchestrator: PR #{pr[\"number\"]} merged.'], capture_output=True)
        print(f'  closed #{issue_num} (PR #{pr[\"number\"]} merged)', file=sys.stderr)
" 2>&1 | grep -v "^$" >&2 || true

# ── Step 8: Promote PRs to review + create CTO review issues ─────────────────
log "scanning open PRs for review promotion..."
OPEN_PRS=$(gh_safe pr list --repo "$REPO" --state open --json number,title,headRefName,body,url --limit 50)
echo "$OPEN_PRS" | python3 -c "
import json, sys, subprocess, re
prs = json.load(sys.stdin)
repo = '${REPO}'
for pr in prs:
    body = pr['body'] or ''
    m = re.search(r'(?:Closes|Fixes)\s+#(\d+)', body, re.IGNORECASE)
    if not m: continue
    task_num = m.group(1)
    pr_num = pr['number']

    # Ensure task issue is labelled 'review'
    issue_labels = subprocess.run(['gh','issue','view',task_num,'--repo',repo,'--json','labels','--jq','[.labels[].name]'],
        capture_output=True, text=True).stdout.strip()
    labels = json.loads(issue_labels) if issue_labels else []
    if 'review' not in labels:
        subprocess.run(['gh','issue','edit',task_num,'--repo',repo,
            '--add-label','review','--remove-label','in-progress'], capture_output=True)

    # Idempotency: check for existing CTO review issue
    existing = subprocess.run(['gh','issue','list','--repo',repo,
        '--search',f'CTO review: PR #{pr_num} in:title','--state','all',
        '--json','number,state,comments'],
        capture_output=True, text=True).stdout.strip()
    found = json.loads(existing) if existing else []

    # Determine phase label from task issue
    phase_labels = [l for l in labels if l.startswith('phase:')]
    phase_label = phase_labels[0] if phase_labels else 'phase:0'

    skip = False
    for f in found:
        if f['state'] == 'OPEN':
            skip = True; break
        # Closed with APPROVED verdict or merged PR
        comments_text = ' '.join(c.get('body','') for c in (f.get('comments') or []))
        if 'VERDICT: APPROVED' in comments_text:
            skip = True; break
        # Closed with ESCALATE verdict
        if 'VERDICT: ESCALATE' in comments_text:
            skip = True; break

    if skip:
        continue

    # Create CTO review issue
    title_short = pr['title'][:80]
    issue_body = f'''Review PR #{pr_num} against the acceptance criteria of the linked task issue and the Plan Acceptance Checklist in your role file (agents/cto.md).

**Linked task issue:** #{task_num}
**PR branch:** {pr[\"headRefName\"]}
**PR URL:** {pr[\"url\"]}

Read the PR diff (gh pr diff {pr_num}), check CI (gh pr checks {pr_num}), the linked issue body, and any needs-adr: true decisions. Post a single comment. The VERY FIRST LINE must be the verdict token:

- VERDICT: APPROVED + HUMAN-REVIEW: NO + REASON: <plain sentence>
- VERDICT: APPROVED + HUMAN-REVIEW: YES + REASON: <plain sentence>
- VERDICT: CHANGES REQUIRED — followed by a numbered list of changes
- VERDICT: ESCALATE — followed by the ambiguity

Do NOT merge the PR. Do NOT close this issue — the Orchestrator routes the verdict.'''

    result = subprocess.run(['gh','issue','create','--repo',repo,
        '--title', f'CTO review: PR #{pr_num} ({title_short})',
        '--body', issue_body,
        '--label', phase_label,
        '--label', 'assigned:claude-opus',
        '--label', 'role:cto',
        '--label', 'in-progress'],
        capture_output=True, text=True)
    if result.returncode == 0:
        print(f'  created CTO review issue for PR #{pr_num} (task #{task_num})', file=sys.stderr)
    else:
        print(f'  WARN: failed to create CTO review for PR #{pr_num}: {result.stderr}', file=sys.stderr)
" 2>&1 | grep -v "^$" >&2 || true

# ── Step 9: Handle CTO verdicts ───────────────────────────────────────────────
log "processing CTO verdicts..."
CTO_ISSUES=$(gh_safe issue list --repo "$REPO" --label role:cto --state open \
  --json number,body,comments,createdAt --limit 50)

echo "$CTO_ISSUES" | python3 -c "
import json, sys, subprocess, re
from datetime import datetime, timezone, timedelta

issues = json.load(sys.stdin)
repo = '${REPO}'
now = datetime.now(timezone.utc)

for issue in issues:
    num = issue['number']
    comments = issue.get('comments') or []
    body = issue.get('body','') or ''

    # Find verdict in comments
    verdict = None
    human_review = None
    verdict_body = ''
    for c in comments:
        ctext = c.get('body','') or ''
        if 'VERDICT:' in ctext:
            lines = ctext.strip().splitlines()
            for i, line in enumerate(lines):
                if line.strip().startswith('VERDICT:'):
                    verdict = line.strip().split('VERDICT:')[1].strip().split()[0]  # APPROVED / CHANGES / ESCALATE
                    verdict_body = ctext
                    # Look for HUMAN-REVIEW on next line
                    for l in lines[i:]:
                        if l.strip().startswith('HUMAN-REVIEW:'):
                            human_review = l.strip().split('HUMAN-REVIEW:')[1].strip()
                            break
                    break
        if verdict: break

    if not verdict:
        # Check if stale (>60 min open with no verdict)
        created = issue.get('createdAt','')
        if created:
            created_dt = datetime.fromisoformat(created.replace('Z','+00:00'))
            age_min = (now - created_dt).total_seconds() / 60
            if age_min > 60:
                subprocess.run(['gh','issue','comment',str(num),'--repo',repo,
                    '--body','WARNING: CTO review has been open >60 min with no VERDICT comment. Claude Code may not have picked this up.'],
                    capture_output=True)
                print(f'  WARN: stale CTO review #{num} ({age_min:.0f} min old)', file=sys.stderr)
        continue

    # Parse linked task issue — body may have markdown bold: **Linked task issue:** #N
    m = re.search(r'Linked task issue:\*{0,2}\s*#(\d+)', body)
    task_num = m.group(1) if m else None

    # Parse linked PR number
    m_pr = re.search(r'Review PR #(\d+)', body)
    pr_num = m_pr.group(1) if m_pr else None

    if verdict == 'APPROVED':
        hr = (human_review or 'YES').upper()
        if hr == 'NO' and pr_num:
            # Auto-merge
            result = subprocess.run(['gh','pr','merge',pr_num,'--repo',repo,'--squash','--delete-branch'],
                capture_output=True, text=True)
            if result.returncode == 0:
                if task_num:
                    subprocess.run(['gh','issue','comment',task_num,'--repo',repo,
                        '--body',f'Auto-merged by orchestrator: CTO approved, no human review required. PR #{pr_num} merged.'],
                        capture_output=True)
                subprocess.run(['gh','issue','close',str(num),'--repo',repo,
                    '--comment','Routed: APPROVED + HUMAN-REVIEW: NO — auto-merged.'], capture_output=True)
                print(f'  auto-merged PR #{pr_num}, closed CTO review #{num}', file=sys.stderr)
            else:
                print(f'  WARN: merge failed for PR #{pr_num}: {result.stderr}', file=sys.stderr)
        elif pr_num:
            # PR merge needs human sign-off — escalate
            pr_url = f'https://github.com/{repo}/pull/{pr_num}'
            msg = f'👀 YOUR EYES NEEDED — {repo}\n\nThe AI completed a task and it passed quality review.\nI need you to approve the final merge — this change may affect the UI or is hard to reverse.\n\n📸 See the changes here: {pr_url}\n🤖 AI quality check: Passed ✅\n\nReply with a number:\n1️⃣ MERGE — looks good, ship it\n2️⃣ REJECT — send it back\n3️⃣ EXPLAIN — break it down for me'
            with open('/home/hermes/.hermes/profiles/orchestrator/escalations.log','a') as f:
                f.write(f'ESCALATION @ {now.isoformat()}:\n{msg}\n\n')
            subprocess.run(['gh','issue','close',str(num),'--repo',repo,
                '--comment','Routed: APPROVED, waiting for human sign-off on merge.'], capture_output=True)
            print(f'  escalated PR #{pr_num} for human merge (HUMAN-REVIEW: YES)', file=sys.stderr)
        else:
            # Plan review approved — no PR to merge; needs human go-ahead to start building
            issue_url = f'https://github.com/{repo}/issues/{num}'
            msg = f'👀 YOUR GO-AHEAD NEEDED — {repo}\n\nThe CTO has approved the project PLAN. Before the team starts building, you need to give the green light.\n\n📋 Review the approved plan + CTO notes here: {issue_url}\n🤖 CTO verdict: APPROVED ✅\n\nReply with a number:\n1️⃣ START — plan looks good, begin the work\n2️⃣ CHANGES — I want something adjusted first\n3️⃣ EXPLAIN — walk me through the plan'
            with open('/home/hermes/.hermes/profiles/orchestrator/escalations.log','a') as f:
                f.write(f'ESCALATION @ {now.isoformat()}:\n{msg}\n\n')
            subprocess.run(['gh','issue','close',str(num),'--repo',repo,
                '--comment','Routed: PLAN APPROVED by CTO — waiting for human go-ahead to begin work.'], capture_output=True)
            print(f'  escalated plan review #{num} for human go-ahead (HUMAN-REVIEW: YES)', file=sys.stderr)

    elif verdict.startswith('CHANGES'):
        if task_num:
            # Get current assignee to clear
            assignee_info = subprocess.run(['gh','issue','view',task_num,'--repo',repo,
                '--json','assignees','--jq','.[assignees[].login]'],
                capture_output=True, text=True).stdout.strip()
            cmd = ['gh','issue','edit',task_num,'--repo',repo,
                   '--remove-label','review','--remove-label','blocked','--add-label','in-progress']
            subprocess.run(cmd, capture_output=True)
            subprocess.run(['gh','issue','comment',task_num,'--repo',repo,
                '--body', verdict_body], capture_output=True)
            print(f'  CHANGES REQUIRED routed to task #{task_num}', file=sys.stderr)
        subprocess.run(['gh','issue','close',str(num),'--repo',repo,
            '--comment','Routed: CHANGES REQUIRED sent to task issue.'], capture_output=True)

    elif verdict.startswith('ESCALATE'):
        with open('/home/hermes/.hermes/profiles/orchestrator/escalations.log','a') as f:
            f.write(f'[PROJECT] {repo}\n[LEVEL] ESCALATE\n[CONTEXT] CTO review #{num}\n[VERDICT] {verdict_body[:200]}\n\n')
        subprocess.run(['gh','issue','close',str(num),'--repo',repo,
            '--comment','Routed: ESCALATE — logged for human.'], capture_output=True)
        print(f'  ESCALATE on CTO review #{num}', file=sys.stderr)
" 2>&1 | grep -v "^$" >&2 || true

# ── Final status line (JSON for LLM consumption) ─────────────────────────────
echo "{\"status\":\"MECHANICS_OK\",\"kickoffs\":$kickoffs_found,\"promoted\":$promoted,\"dispatched\":$dispatched,\"warnings\":$warnings,\"escalations\":$escalations,\"ts\":\"$NOW\"}"
