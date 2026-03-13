#!/bin/bash
# Deploy project from GitHub to project server via SSH.
# 1. Clone repo, generate configs (MySQL/Redis/Kafka IPs), build
# 2. Rsync to project server
# 3. Project on server connects to MySQL/Redis/Kafka
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PERF_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
CONFIG_FILE="${PERF_CONFIG:-$PERF_DIR/config/infra.json}"
WORKSPACE="$PERF_DIR/workspace"

if [ ! -f "$CONFIG_FILE" ]; then
  echo "Config not found. Save config from dashboard first."
  exit 1
fi

eval $(python3 -c "
import json, os, base64
c = json.load(open('$CONFIG_FILE'))
g = c.get('github', {})
a = c.get('app_server', {})
m = c.get('mysql', {})
print('REPO_URL=\"%s\"' % g.get('repo_url','').strip())
print('BRANCH=\"%s\"' % g.get('branch','main').strip())
print('SUBPATH=\"%s\"' % g.get('subpath','').strip())
print('APP_HOST=\"%s\"' % a.get('host','').strip())
print('APP_SSH_PORT=\"%s\"' % str(a.get('ssh_port',22)))
print('APP_SSH_USER=\"%s\"' % a.get('ssh_user','root').strip())
print('APP_DEPLOY_PATH=\"%s\"' % a.get('deploy_path','/opt/dex').strip())
p = os.environ.get('PERF_SSH_PASSWORD','')
print('APP_SSH_PASSWORD=\"%s\"' % p.replace('\"','\\\\\"'))
# MySQL DSN for simple projects (base64 to avoid escaping)
if m.get('host'):
    dsn = '%s:%s@tcp(%s:%s)/%s?charset=utf8mb4&parseTime=True&allowNativePasswords=true' % (
        m.get('user','root'), m.get('password',''),
        m.get('host','127.0.0.1'), str(m.get('port',3306)), m.get('database','jmeter_test')
    )
    print('MYSQL_DSN_B64=\"%s\"' % base64.b64encode(dsn.encode()).decode())
else:
    print('MYSQL_DSN_B64=\"\"')
" 2>/dev/null)

if [ -z "$REPO_URL" ]; then
  echo "ERROR: GitHub Repository URL is required."
  exit 1
fi
if [ -z "$APP_HOST" ]; then
  echo "ERROR: Project server IP is required."
  exit 1
fi

SSH_OPTS="-o StrictHostKeyChecking=no -o ConnectTimeout=10"
[ -n "$APP_SSH_PORT" ] && [ "$APP_SSH_PORT" != "22" ] && SSH_OPTS="$SSH_OPTS -p $APP_SSH_PORT"
# BatchMode=yes: 测试时禁用密码认证，避免 ssh 在终端上阻塞等待输入
SSH_TEST_OPTS="$SSH_OPTS -o BatchMode=yes"
SSH_CMD="ssh $SSH_OPTS ${APP_SSH_USER}@${APP_HOST}"
SSH_TEST_CMD="ssh $SSH_TEST_OPTS ${APP_SSH_USER}@${APP_HOST}"
RSYNC_SSH="ssh $SSH_OPTS"

REPO_NAME=$(basename "$REPO_URL" .git)
CLONE_DIR="$WORKSPACE/$REPO_NAME"

echo "=== Deploy to project server ==="
echo "Repo: $REPO_URL (branch: $BRANCH)"
echo "Target: ${APP_SSH_USER}@${APP_HOST}:${APP_DEPLOY_PATH}"

# Clone or pull
mkdir -p "$WORKSPACE"
if [ -d "$CLONE_DIR/.git" ]; then
  echo "Pulling..."
  (cd "$CLONE_DIR" && git fetch origin && git checkout "$BRANCH" 2>/dev/null; git pull origin "$BRANCH" 2>/dev/null) || true
else
  echo "Cloning..."
  git clone -b "$BRANCH" --single-branch "$REPO_URL" "$CLONE_DIR" || exit 1
fi

# Project root
if [ -n "$SUBPATH" ]; then
  PROJECT_ROOT="$CLONE_DIR/$SUBPATH"
else
  PROJECT_ROOT="$CLONE_DIR"
fi

# Detect project type: DEX (apps/) or simple Go (main.go)
PROJECT_TYPE=""
if [ -d "$PROJECT_ROOT/apps" ]; then
  DEX_APPS="$PROJECT_ROOT/apps"
  MAKE_DIR="$PROJECT_ROOT"
  PROJECT_TYPE="dex"
elif [ -d "$PROJECT_ROOT/dex_full/apps" ]; then
  DEX_APPS="$PROJECT_ROOT/dex_full/apps"
  MAKE_DIR="$PROJECT_ROOT/dex_full"
  PROJECT_TYPE="dex"
elif [ -f "$PROJECT_ROOT/main.go" ] && [ -f "$PROJECT_ROOT/go.mod" ]; then
  MAKE_DIR="$PROJECT_ROOT"
  PROJECT_TYPE="simple"
else
  echo "ERROR: Cannot find apps/ (DEX) or main.go+go.mod (simple Go) under $PROJECT_ROOT"
  exit 1
fi

echo "Project: $MAKE_DIR (type: $PROJECT_TYPE)"

if [ "$PROJECT_TYPE" = "dex" ]; then
  # Generate configs with MySQL/Redis/Kafka IPs for DEX apps
  python3 -c "
import json, sys
sys.path.insert(0, '$PERF_DIR/backend')
from config_generator import generate_perf_yaml
with open('$CONFIG_FILE') as f:
    config = json.load(f)
for name, content in generate_perf_yaml(config).items():
    service = name.replace('-perf.yaml', '')
    path = '$DEX_APPS/{}/etc/{}.yaml'.format(service, service)
    import os
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w') as f:
        f.write(content)
    print('Written:', path)
" || { echo "Config generation failed."; exit 1; }
fi

# Build
if [ "$PROJECT_TYPE" = "dex" ]; then
  if [ -f "$MAKE_DIR/Makefile" ]; then
    echo "Building (DEX)..."
    (cd "$MAKE_DIR" && make build 2>/dev/null) || echo "Build failed, continuing..."
  fi
  if [ ! -d "$MAKE_DIR/build" ]; then
    echo "ERROR: No build/ output. Check Makefile."
    exit 1
  fi
elif [ "$PROJECT_TYPE" = "simple" ]; then
  echo "Building (simple Go)..."
  mkdir -p "$MAKE_DIR/build"
  (cd "$MAKE_DIR" && go build -o build/main . 2>/dev/null) || {
    echo "Build failed."
    exit 1
  }
  # Copy config dir if exists
  [ -d "$MAKE_DIR/config" ] && cp -r "$MAKE_DIR/config" "$MAKE_DIR/build/" 2>/dev/null || true
fi

# Deploy to server via rsync
echo "Deploying to ${APP_HOST}..."

# Ensure we have an SSH key (for Docker/fresh env where none exists)
if [ ! -f ~/.ssh/id_rsa ] && [ ! -f ~/.ssh/id_ed25519 ]; then
  echo "Generating SSH key for deploy..."
  mkdir -p ~/.ssh
  ssh-keygen -t ed25519 -N "" -f ~/.ssh/id_ed25519 -q 2>/dev/null || \
  ssh-keygen -t rsa -N "" -f ~/.ssh/id_rsa -q 2>/dev/null
fi

# Ensure SSH key auth: if key fails and password provided, auto setup
# 用 BatchMode 测试，避免 ssh 回退到密码认证时在终端阻塞
if ! $SSH_TEST_CMD "true" 2>/dev/null; then
  if [ -n "$APP_SSH_PASSWORD" ]; then
    echo "SSH key auth failed. Using password to configure key (one-time)..."
    if command -v sshpass >/dev/null 2>&1; then
      SSHPASS="$APP_SSH_PASSWORD" sshpass -e ssh-copy-id $SSH_OPTS "${APP_SSH_USER}@${APP_HOST}" 2>/dev/null && \
        echo "SSH key configured. Future deploys will use key auth." || {
        echo "ssh-copy-id failed. Install sshpass if missing: apt install sshpass"
        exit 1
      }
    else
      echo "sshpass not installed. Run: sudo apt install sshpass"
      echo "Or manually: ssh-copy-id ${APP_SSH_USER}@${APP_HOST}"
      exit 1
    fi
  else
    echo "SSH key auth failed. Either:"
    echo "  1. Add SSH password above and click Deploy (auto-configure key, one-time)"
    echo "  2. Or run: ssh-copy-id ${APP_SSH_USER}@${APP_HOST}"
    exit 1
  fi
fi

$SSH_CMD "mkdir -p $APP_DEPLOY_PATH" 2>/dev/null || true

# Rsync build to server
rsync -az --delete -e "$RSYNC_SSH" \
  "$MAKE_DIR/build/" "${APP_SSH_USER}@${APP_HOST}:${APP_DEPLOY_PATH}/build/" || {
  echo "Rsync failed. Ensure SSH key auth: ssh-copy-id ${APP_SSH_USER}@${APP_HOST}"
  exit 1
}

# Copy model if exists
[ -d "$MAKE_DIR/model" ] && rsync -az -e "$RSYNC_SSH" \
  "$MAKE_DIR/model/" "${APP_SSH_USER}@${APP_HOST}:${APP_DEPLOY_PATH}/model/" 2>/dev/null || true

# Simple project: decode MySQL DSN locally and rsync to server (avoids remote base64/variable issues)
if [ "$PROJECT_TYPE" = "simple" ] && [ -n "$MYSQL_DSN_B64" ]; then
  _DSN_TMP=$(mktemp)
  printf '%s' "$MYSQL_DSN_B64" | tr -d '\n' | base64 -d 2>/dev/null > "$_DSN_TMP" || true
  [ -s "$_DSN_TMP" ] && rsync -az -e "$RSYNC_SSH" "$_DSN_TMP" "${APP_SSH_USER}@${APP_HOST}:${APP_DEPLOY_PATH}/.mysql_dsn" 2>/dev/null || true
  rm -f "$_DSN_TMP"
fi

# Generate start script on server
if [ "$PROJECT_TYPE" = "dex" ]; then
  $SSH_CMD "cat > $APP_DEPLOY_PATH/start.sh << EOF
#!/bin/bash
cd $APP_DEPLOY_PATH/build
for s in gateway trade market consumer websocket; do
  [ -f \$s/\$s ] && (pkill -f \"build/\$s/\$s\" 2>/dev/null; nohup ./\$s/\$s -f ./\$s/etc/\$s.yaml > /tmp/\$s.log 2>&1 &)
done
echo Started. Check /tmp/*.log
EOF
chmod +x $APP_DEPLOY_PATH/start.sh"
else
  # Simple project: DSN file is rsync'd above; start.sh reads it if present
  MYSQL_EXPORT=""
  if [ -n "$MYSQL_DSN_B64" ]; then
    MYSQL_EXPORT="[ -f $APP_DEPLOY_PATH/.mysql_dsn ] && export MYSQL_DSN=\"\$(cat $APP_DEPLOY_PATH/.mysql_dsn)\"
"
  fi
  $SSH_CMD "cat > $APP_DEPLOY_PATH/start.sh << EOF
#!/bin/bash
cd $APP_DEPLOY_PATH/build
${MYSQL_EXPORT}pkill -f 'build/main' 2>/dev/null || fuser -k 8080/tcp 2>/dev/null || true
nohup $APP_DEPLOY_PATH/build/main > /tmp/main.log 2>&1 &
echo Started. Check /tmp/main.log
EOF
chmod +x $APP_DEPLOY_PATH/start.sh"
fi

# Start services on target server
echo "Starting services on ${APP_HOST}..."
$SSH_CMD "$APP_DEPLOY_PATH/start.sh" || echo "Warning: start.sh failed (check services manually)"

echo "Done. Files at ${APP_HOST}:${APP_DEPLOY_PATH}/"
