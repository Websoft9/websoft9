# Developer Guide

## Prerequisites

- **Python 3.11+** — for AppHub backend
- **Node.js 22+** — for Console frontend
- **Docker & Docker Compose** — for local runtime
- **Go 1.24+** — for Portainer init helper (optional)

## Project Structure

```
websoft9/
├── apphub/          # Backend API (Python/FastAPI)
│   ├── src/         # Application source
│   └── tests/       # Test suite
├── console/         # Frontend UI (React/TypeScript/Vite)
│   └── src/         # Application source
├── docker/          # Container build & runtime
│   ├── Dockerfile   # Single-container image build
│   └── docker-compose.yml
├── install/         # Installation scripts
├── cli/             # CLI tools
├── scripts/         # Utility scripts
└── docs/            # Documentation
```

## Development Setup

### 1. Backend (AppHub)

```bash
cd apphub

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Run tests
pytest --cov=src

# Run development server
uvicorn src.main:app --reload --port 8000
```

### 2. Frontend (Console)

```bash
cd console

# Install dependencies
npm ci

# Start development server
npm run dev
```

### 3. Full Stack (Docker Compose)

```bash
cd docker

# Start with dev compose file
docker compose -f docker-compose.dev.yml up -d --build
```

## Application SFTP

The SFTP action beside an application's volume browser opens the Terminal file
view using an independent, restricted file session. It does not start a shell or
overwrite the ordinary terminal workspace. A usable local connection opens files
directly. At the application SFTP entry, missing connections show a confirmation
only, not an embedded credential form. Its manual action opens `/terminal?new_connection=1`, which
opens Terminal's existing new-connection form. The automatic action first shows
a second confirmation with three short bulleted statements covering connection
reuse, account permissions, and server-side key storage. The confirmation states
that no operating-system account is created: installation prepares an SSH
public key for the selected existing host account. Its private key is stored on
the server; deleting an automatic local connection revokes its host public key
and removes the prepared private key and metadata files.
The entry briefly explains
why host SSH/SFTP access is needed. Both steps retain the original white dialog
style, with a responsive 680px width and smaller explanatory text, without extra
tables or notice panels. The second step requires an acknowledgement checkbox;
returning to the first step resets it. Only explicit confirmation verifies
and activates or creates an ordinary local SSH connection before opening the
restricted file view. Authorization, authentication, network, and directory
permission failures have distinct messages. Directory permission errors do not
offer another connection as a remedy.
Invalid file sessions remain in the original file panel with its standard directory
error display; they do not redirect
through the application page or automatically open a connection confirmation.
Removing a saved host closes its terminal channels and invalidates its application
file sessions for the current operator. The corresponding tabs remain selectable
but show an ended state without recreating sessions or changing position. File
panels immediately stop loading, display their connection error, and disable file
operations, including creation and upload. Browser reload preserves ended terminal
and file tabs and terminal output; deleted profiles are never automatically
reconnected. Browser transport disconnects do not terminate the server PTY:
refresh reattaches the same terminal ID and profile, synchronizes its server
snapshot, and resumes output without duplicating history. Temporary transport
loss can be restored on refresh; an explicitly exited or deleted session is not
automatically restarted. Detached PTYs expire after the configured idle timeout;
API/process restarts do not preserve in-memory PTYs. Disconnected terminals clear
the current shell prompt, hide the input cursor, and disable input. The original
bottom notice and right-aligned reconnect button remain; the notice is not
duplicated inside the terminal. Reconnect validates unavailable profile records:
an existing profile reattaches the same session ID, while a deleted profile shows
an explanation rather than opening a new connection form. Deleting
a local connection records an operator-scoped revocation in SQLite: installer
credentials cannot implicitly recreate it. Explicitly confirming the automatic
connection action may prepare a new authorization when credentials are absent and
create a new profile with a new ID; successful verification clears the revocation
record. Missing authorization or authentication failures leave the revocation
record intact. Manually saving a new local connection also restores access.
Deleting an automatic local profile removes the matching public
key even if other connections use it; subsequent authentication with that key
fails. Unrelated public-key entries are preserved. Cleanup failures are reported
instead of claiming that the connection was deleted. Manual connections do not
remove user-supplied host public keys.
The platform never enables SSH, changes SSH login policy, or changes application
volume ownership to make a connection succeed.

### Automatic Local Connection

The production and development Compose definitions do not enable privileged
mode for the product container. Automatic SSH uses
ordinary TCP authentication and platform credentials in the existing data mount,
not host namespaces or extra Linux capabilities. It also works with
`privileged: false`, `cap_drop: [ALL]`, and `no-new-privileges`, provided the
container's service user can read the owner-only credentials and the host's SSH
port is reachable. Preparing missing authorization requires the existing Docker
management socket and a short-lived privileged helper with host PID access.
The helper reuses the installed product image and enters the host namespaces to
run the fixed Python preparation program shipped with AppHub; no image is downloaded.
The program is passed directly to the helper command, so the host does not need
an updated installer or any newly installed preparation script. Cloud marketplace
images and their boot-time installation scripts remain unchanged; updating the
product Docker image delivers this behavior through the existing AppHub copy.
The main product container need not be privileged, but the Docker daemon must
permit this explicitly confirmed preparation operation. The helper is removed
on completion or failure. This verifies automatic SSH only, not all product
services. No host SSH directory mount or permanent helper is required. Changing
the running container's privilege setting requires recreation and ends existing
terminal/file sessions. The Docker management socket still permits host-level
operations; removing product-container privileged mode does not sandbox platform
operators. The temporary preparation helper remains privileged.

Authenticated `POST /api/host-access/profile/local` verifies and activates a local
profile belonging to the current operator. This explicit action permits recreation
after deletion, but never bypasses actual SSH authentication. If platform
credentials are absent, it runs the host preparation step through the existing
Docker management channel, then validates and saves the new SSH connection.
Deletion retains only the previous account and port in an owner-only
`local-ssh-account.json` record so re-preparation uses the same existing account;
no deleted key is retained. It first tries the runtime connection,
including credentials that were not remembered, then the saved local profiles.
Remote profiles are not attempted, stored credentials are not overwritten, and
temporary credentials remain temporary. Authentication or connection failures
retain their original error details and direct the user to Terminal's existing
connection form. When no existing connection works, the backend reads the
previously prepared `local-ssh.json` and `local-ssh.key` in the existing
`data/config/host-access` directory, verifies SSH, and saves a normal connection
for the current operator. Files must be regular, single-link, owner-only files
in an owner-only directory; the key is never returned to the browser. An existing
manual connection for the same account is not silently overwritten.

Installation and upgrades do not prepare SSH authorization. When the user explicitly
confirms automatic connection and usable credentials are absent, AppHub runs its
own preparation program through the temporary helper. It selects a previously
recorded account, the non-root `SUDO_USER`, or a single detected non-root SSH
account, in that order. Only when no non-root account is detected does it consider
root, and the existing SSH policy must allow root key login. Ambiguous accounts
require a manual connection instead of guessing an account.
Preparation appends a dedicated public key to the account's standard
`.ssh/authorized_keys`, preserves existing entries and key restrictions, verifies
login, and writes owner-only credentials through the existing data mount. It is
idempotent and removes a newly appended authorization if verification or
metadata storage fails. SSH is not installed, enabled, or reconfigured.
Preparation failure is reported by the connection action and does not affect
product installation. Existing credentials remain usable across product updates.
The host
needs Python 3, `ssh`, `ssh-keygen`, and an already running SSH service. Custom
authorization paths require a manual connection. If authorization is absent
or unsafe, automatic setup must succeed before a connection is saved; otherwise
the action reports an error and the user can connect manually. Privileged mode
alone does not authorize SSH. Platform operators must be trusted:
the prepared key grants the selected host account's access. Deleting an automatic
local connection authenticates to the host, locks and validates its authorization
file, removes only the matching public-key entry, and deletes both prepared
credential files. Metadata records the authorization path; older metadata resolves
the account's standard authorization path. Re-preparation is required to restore
installer authorization after its key has been deleted; the explicitly confirmed
automatic action now performs that re-preparation through Docker.

AWS and Azure images may use a non-root account, such as `ubuntu`, `ec2-user`,
or a user selected during provisioning. These accounts follow the same ordinary
connection workflow; no root account is assumed and no cloud login policy is
changed. For non-root accounts, host preparation configures passwordless `sudo`
solely for the host's `sftp-server` binary, and application SFTP opens an
elevated `sftp-server` channel strictly confined to the target Docker volume
while keeping ordinary terminal and host file sessions under the non-root
account's permissions.

Ordinary terminal and application file sessions share a session tab strip while
retaining independent state and permissions. Switching tabs keeps terminal
connections and rendering alive. Reopening the same application volume validates
and reuses its file session; expired sessions are rebuilt. Each volume remembers
its own directory, and closing a file tab only releases that file session.
File tabs use the normal connected status without an SFTP title suffix or a
special close confirmation. Opening the normal host list keeps the files open.
File tab titles retain the complete Docker volume name, including its application prefix. Long
titles truncate when needed; hovering shows the complete application and volume.
The selected tab scrolls into view. The strip retains its
original layout, hidden scrollbars, and inline new-connection button; it does
not show a connection counter or a separate right-hand button area. The browser
`+` button opens the same saved-connection menu in ordinary and application file
workspaces, refreshing the host list on open. Opening or cancelling the menu or
its new-connection form does not navigate away or deselect the current file tab.
Successful connection from this menu opens a separate ordinary terminal session,
even when an application file tab is selected. It does not reopen, replace, or
close that application's restricted file session, and existing terminal sessions
are retained. New terminal and application file tabs append to the end, without
grouping terminals ahead of file sessions. Tab order and the current selection are
stored in session storage; tabs keep their natural width (220px maximum for inactive
tabs) and shrink only when space is insufficient. The add button remains visible at
the ten-tab workspace limit. File tabs use application and volume identifiers so
renewing a server session does not change their logical identity. Closing the selected tab automatically selects a remaining neighbor
across both workspace types; only closing the last tab shows the empty workspace.
Hidden terminals do not fit or send resize messages; visible terminals fit before
buffer playback to avoid narrow-column wrapping. Disconnected terminals keep their
historical output, show a persistent reconnect notice below the terminal canvas,
and disable input and cursor blinking. New sessions use the verified response's host profile ID rather
than an unsaved form ID. Login requests time out after 30 seconds, clear the busy
state, and show a localized error without treating a timeout as a force-save request.
The browser
workspace permits ten terminal and application file tabs in total, including
in-flight file session creation; existing file sessions can still be reused or
renewed at the limit. This is a console workspace limit, not a server-wide SSH
quota.

SFTP v3 does not expose a reliable creation time, so missing creation times are
displayed as a dash rather than substituted with modification times. Identity
labels reuse Terminal's name-and-ID format, such as `root(0)`, and fall back to
plain numeric IDs when names cannot be resolved. Internal metadata lookup only
reads the remote host's fixed account tables and uses an isolated name cache;
file APIs still reject reads or writes outside the application volume. Host
account names need not match the names inside a container.

- Only the local Docker host and local volumes without driver options are supported.
- The backend verifies the Compose application label and obtains the volume root
	from Docker; frontend paths are not trusted.
- File sessions belong to the authenticated operator and expire after 30 minutes
	or a backend restart. Connection identity and volume ownership are rechecked.
- All file operations validate their source and destination paths. Symbolic links
	and special files are excluded; the volume root cannot be renamed or deleted.
- Copy and permission changes use SFTP rather than arbitrary remote shell commands.
	Owner/group changes are not available in this restricted view.
- SSH account permissions still apply. This API boundary is not an OS-level
	chroot: existing host administrators retain their rights. For hostile processes
	that can race path checks or create hard links, use a dedicated jailed SFTP
	account rather than treating a privileged shared connection as sandboxed.

Run `pytest -q --no-cov tests/test_host_access.py` from `apphub`. The real SFTP
integration test uses a temporary loopback-only SSH daemon and temporary keys;
it is skipped without root, `sshd`, or `ssh-keygen`.
Run `node --test scripts/app-file-sessions.test.mjs` from `console` for the
session reuse, expiry, concurrent entry, and isolated close regression checks.

## Code Standards

### Python (AppHub)
- Formatter: **Black** (line length 100)
- Linter: **Flake8**, **Pylint**
- Import sorting: **isort**
- Type hints required for public APIs
- Test coverage target: ≥70%

### TypeScript (Console)
- Formatter: **ESLint** + **Prettier**
- Strict TypeScript mode enabled
- Component structure: feature-based folders under `src/features/`

## CI/CD

All pull requests must pass:

| Check | Tool |
|-------|------|
| Linting | Black, isort, Flake8, ESLint |
| Tests | Pytest (≥70% coverage) |
| Build | Docker image build |
| Security | Container vulnerability scan |

See [CI/CD Guide](ci-guide.md) for details.

## Contributing

1. Fork the `main` branch
2. Create a feature branch
3. Make changes with tests
4. Ensure all CI checks pass locally
5. Submit a pull request to `main`

See [CONTRIBUTING.md](../CONTRIBUTING.md) for the full contribution workflow.
