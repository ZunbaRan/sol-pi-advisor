#!/bin/sh

set -eu

fail() {
  printf '%s\n' "ERROR: $*" >&2
  exit 1
}

path_exists() {
  [ -e "$1" ] || [ -L "$1" ]
}

usage() {
  printf '%s\n' 'Usage: install-agent.sh [--target-dir PATH] [--check]'
}

script_dir=$(CDPATH= cd "$(dirname "$0")" && pwd) || exit 1
template=$script_dir/../agents/sol-pi-advisor-sol-reviewer.toml

if [ -n "${CODEX_HOME-}" ]; then
  target_dir=$CODEX_HOME/agents
else
  [ -n "${HOME-}" ] || fail 'HOME is unset; pass --target-dir.'
  target_dir=$HOME/.codex/agents
fi

check_only=0
while [ "$#" -gt 0 ]; do
  case "$1" in
    --target-dir)
      [ "$#" -ge 2 ] && [ -n "$2" ] || fail '--target-dir requires a path.'
      target_dir=$2
      shift 2
      ;;
    --check)
      check_only=1
      shift
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      fail "unknown argument: $1"
      ;;
  esac
done

case "$target_dir" in
  /*) ;;
  *) target_dir=$(pwd -P)/$target_dir ;;
esac

[ "$target_dir" != / ] || fail 'refusing to use the filesystem root.'
[ -f "$template" ] && [ ! -L "$template" ] || fail "invalid template: $template"

destination=$target_dir/sol-pi-advisor-sol-reviewer.toml

if path_exists "$destination"; then
  [ -f "$destination" ] && [ ! -L "$destination" ] ||
    fail "destination is not a regular file: $destination"
  cmp -s "$template" "$destination" ||
    fail "destination differs and will not be overwritten: $destination"
  printf '%s\n' "CURRENT: $destination"
  exit 0
fi

[ "$check_only" -eq 0 ] || fail "reviewer is not installed: $destination"

if path_exists "$target_dir"; then
  [ -d "$target_dir" ] && [ ! -L "$target_dir" ] ||
    fail "target is not a real directory: $target_dir"
else
  mkdir -p "$target_dir" || fail "could not create target: $target_dir"
fi

staged=$(mktemp "$target_dir/.sol-pi-advisor-agent.XXXXXX") ||
  fail "could not stage installation in: $target_dir"
trap 'rm -f "$staged"' EXIT HUP INT TERM
cp "$template" "$staged" || fail 'could not copy reviewer template.'

if ! ln "$staged" "$destination"; then
  fail "destination appeared during installation and was not overwritten: $destination"
fi

rm -f "$staged"
trap - EXIT HUP INT TERM
printf '%s\n' "INSTALLED: $destination"
