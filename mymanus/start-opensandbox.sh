#!/bin/bash
# OpenSandbox 启动脚本
# 用于启动本地 OpenSandbox 服务

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OPEN_SANDBOX_SERVER_DIR="$SCRIPT_DIR/../OpenSandbox/server"

echo "=== OpenSandbox 启动脚本 ==="
echo ""

# 检查 OpenSandbox 目录是否存在
if [ ! -d "$OPEN_SANDBOX_SERVER_DIR" ]; then
    echo "错误: OpenSandbox 目录不存在: $OPEN_SANDBOX_SERVER_DIR"
    exit 1
fi

# 检查 Docker 是否运行
if ! docker ps > /dev/null 2>&1; then
    echo "错误: Docker 未运行，请先启动 Docker"
    exit 1
fi

echo "✓ Docker 运行中"

# 检查配置文件
CONFIG_FILE="$HOME/.sandbox.toml"
if [ ! -f "$CONFIG_FILE" ]; then
    echo "创建 OpenSandbox 配置文件..."
    mkdir -p "$HOME/.sandbox"
    cat > "$CONFIG_FILE" << 'EOF'
[server]
host = "127.0.0.1"
port = 8082
log_level = "INFO"
api_key = ""

[runtime]
type = "docker"
execd_image = "sandbox-registry.cn-zhangjiakou.cr.aliyuncs.com/opensandbox/execd:v1.0.3"

[docker]
network_mode = "bridge"
drop_capabilities = ["AUDIT_WRITE", "MKNOD", "NET_ADMIN", "NET_RAW", "SYS_ADMIN", "SYS_MODULE", "SYS_PTRACE", "SYS_TIME", "SYS_TTY_CONFIG"]
no_new_privileges = true
apparmor_profile = ""
pids_limit = 512
seccomp_profile = ""
EOF
    echo "✓ 配置文件已创建: $CONFIG_FILE"
else
    echo "✓ 配置文件已存在: $CONFIG_FILE"
fi

# 检查端口是否被占用
PORT=8082
if lsof -Pi :$PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo "⚠️  端口 $PORT 已被占用"
    echo "正在终止现有进程..."
    lsof -ti:$PORT | xargs kill -9 2>/dev/null || true
    sleep 2
fi

cd "$OPEN_SANDBOX_SERVER_DIR"
echo ""
echo "启动 OpenSandbox 服务..."
echo "目录: $OPEN_SANDBOX_SERVER_DIR"
echo ""

# 使用 uv 启动服务
uv run python -m src.main
