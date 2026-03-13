#!/bin/bash
# Fetch CPU, memory from a host via SSH. Uses /proc (no iostat needed).
# Usage: fetch_metrics.sh <user> <host> [port]
USER="${1:-root}"
HOST="${2}"
PORT="${3:-22}"
[ -z "$HOST" ] && echo '{"error":"no host"}' && exit 1
SSH_OPTS="-o StrictHostKeyChecking=no -o ConnectTimeout=5"
[ -n "$PORT" ] && [ "$PORT" != "22" ] && SSH_OPTS="$SSH_OPTS -p $PORT"

OUT=$(ssh $SSH_OPTS ${USER}@${HOST} '
  # Memory from /proc/meminfo
  mem_total=$(awk "/MemTotal:/{print \$2}" /proc/meminfo)
  mem_avail=$(awk "/MemAvailable:/{print \$2}" /proc/meminfo)
  mem_used=$((mem_total - mem_avail))
  echo "MEM_TOTAL=$((mem_total/1024))"
  echo "MEM_USED=$((mem_used/1024))"
  # CPU load
  read -r cpu user nice sys idle iowait irq softirq steal guest gnice < /proc/stat
  total=$((user+nice+sys+idle+iowait+irq+softirq+steal))
  echo "CPU_IDLE=$idle"
  echo "CPU_TOTAL=$total"
  # Project process check (main binary or gateway/trade etc.)
  proc_count=$(pgrep -c -f "build/main|gateway/gateway|trade/trade|market/market|consumer/consumer" 2>/dev/null || echo "0")
  echo "PROJECT_PROCS=$proc_count"
  # Listening ports (8080, 8081 common for APIs)
  ports=$(ss -tlnp 2>/dev/null | grep -oE ":808[0-9]" | tr -d ":" | sort -u | tr "\n" "," | sed "s/,\$//")
  [ -z "$ports" ] && ports=""
  echo "PORTS_LISTEN=$ports"
' 2>/dev/null) || {
  echo "{\"host\":\"$HOST\",\"error\":\"SSH failed. Ensure: ssh-copy-id ${USER}@${HOST}\"}"
  exit 0
}

MEM_T=$(echo "$OUT" | grep "^MEM_TOTAL=" | cut -d= -f2)
MEM_U=$(echo "$OUT" | grep "^MEM_USED=" | cut -d= -f2)
IDLE=$(echo "$OUT" | grep "^CPU_IDLE=" | cut -d= -f2)
TOTAL=$(echo "$OUT" | grep "^CPU_TOTAL=" | cut -d= -f2)
PROCS=$(echo "$OUT" | grep "^PROJECT_PROCS=" | cut -d= -f2)
PORTS=$(echo "$OUT" | grep "^PORTS_LISTEN=" | cut -d= -f2-)
CPU_PCT="0"
[ -n "$TOTAL" ] && [ "$TOTAL" != "0" ] && CPU_PCT=$(awk "BEGIN {printf \"%.1f\", 100 - 100*$IDLE/$TOTAL}")

echo "{\"host\":\"$HOST\",\"cpu_pct\":\"$CPU_PCT\",\"mem_total_mb\":\"$MEM_T\",\"mem_used_mb\":\"$MEM_U\",\"project_procs\":\"$PROCS\",\"ports_listen\":\"$PORTS\"}"
