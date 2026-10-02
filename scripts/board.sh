#!/usr/bin/env bash
# Project ボードで Issue のステータスを変える。
# 使い方: scripts/board.sh <Issue番号> <Todo|"In Progress"|Done>
set -euo pipefail

OWNER="Shohei-U"
PROJECT_NUM=1

issue="${1:?Issue番号を指定}"
status="${2:?ステータス（Todo / \"In Progress\" / Done）を指定}"

project_id="$(gh project view "$PROJECT_NUM" --owner "$OWNER" --format json -q .id)"
field_json="$(gh project field-list "$PROJECT_NUM" --owner "$OWNER" --format json \
  -q '.fields[] | select(.name == "Status")')"
field_id="$(jq -r .id <<<"$field_json")"
option_id="$(jq -r --arg s "$status" '.options[] | select(.name == $s) | .id' <<<"$field_json")"
item_id="$(gh project item-list "$PROJECT_NUM" --owner "$OWNER" --format json --limit 200 \
  -q ".items[] | select(.content.number == ${issue}) | .id")"

[[ -n "$option_id" ]] || { echo "ステータス '${status}' がありません（Todo / In Progress / Done）" >&2; exit 1; }
[[ -n "$item_id" ]] || { echo "Issue #${issue} がボードにありません" >&2; exit 1; }

gh project item-edit --project-id "$project_id" --id "$item_id" \
  --field-id "$field_id" --single-select-option-id "$option_id" >/dev/null
echo "#${issue} → ${status}"
