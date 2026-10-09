#!/bin/bash
# 巡检脚本片段：只在【状态发生变化】时往播报队列里追加一行，
# 这样既不会每隔几分钟骚扰一次，也不会有任何大模型开销。
QUEUE="$HOME/logs/notify_queue.txt"
STATE="$HOME/logs/netwatch_state"
mkdir -p "$(dirname "$QUEUE")"

fail=""
ping -c 2 -W 2 192.168.1.1     >/dev/null 2>&1 || fail="$fail 网关"
ping -c 2 -W 2 223.5.5.5      >/dev/null 2>&1 || fail="$fail 外网"
getent hosts api.deepseek.com >/dev/null 2>&1 || fail="$fail DNS"

if [ -z "$fail" ]; then cur="ok"; else cur="$(echo $fail)"; fi
prev="$(cat "$STATE" 2>/dev/null)"

if [ "$cur" != "$prev" ]; then
  if [ "$cur" = "ok" ]; then
    echo "$(date '+%F %T')  网络已恢复正常" >> "$QUEUE"
  else
    echo "$(date '+%F %T')  网络异常，失败项：$fail" >> "$QUEUE"
  fi
  echo "$cur" > "$STATE"
fi
