#!/bin/bash
set -e

echo "🔄 Updating ngrok URLs..."

# Wait for ngrok to start
sleep 3

# Get URLs
NATS_URL_RAW=$(curl -s http://localhost:4040/api/tunnels | jq -r '.tunnels[] | select(.name=="nats") | .public_url')
HTTP_URL=$(curl -s http://localhost:4040/api/tunnels | jq -r '.tunnels[] | select(.name=="orchestrator") | .public_url')

# Remove tcp:// prefix from NATS URL since our code doesn't use it
NATS_URL=$(echo "$NATS_URL_RAW" | sed 's|tcp://||')

if [[ "$NATS_URL" == "null" || "$HTTP_URL" == "null" ]]; then
    echo "❌ Failed to get ngrok URLs. Is ngrok running?"
    echo "   Make sure to run 'ngrok start --all &' first"
    exit 1
fi

echo "📡 NATS: $NATS_URL"
echo "🌐 HTTP: $HTTP_URL"

# Update files
sed -i '' "s|nats://0.tcp.in.ngrok.io:[0-9]*|${NATS_URL}|g" apps/orchestrator/main.go
sed -i '' "s|nats://0.tcp.in.ngrok.io:[0-9]*|${NATS_URL}|g" apps/agent/src/main.rs
sed -i '' "s|https://[a-z0-9]*.ngrok-free.app|${HTTP_URL}|g" apps/agent/src/main.rs
sed -i '' "s|nats://0.tcp.in.ngrok.io:[0-9]*|${NATS_URL}|g" setup_runpod.sh
sed -i '' "s|https://[a-z0-9]*.ngrok-free.app|${HTTP_URL}|g" setup_runpod.sh

echo "✅ URLs updated locally in all files"
echo "💡 Next steps:"
echo "   1. git add -A && git commit -m 'Update ngrok URLs'"
echo "   2. git push"
echo "   3. On RunPod: git pull && cargo run --release"