#!/bin/bash
# verify-marketplace-divergence.sh — codex(gpt-5.6-sol)가 저작한 DoD의 판정 구현체.
# 정본 DoD: ~/.claude/verification-templates/claude-templates-marketplace-update-divergence.md
#
# 원칙 4(검증 주권): 이 파일의 판정 predicate는 피검 모델(Claude) 밖에서 저작됐다.
# 실행 중 수정 금지 — verify-lock으로 해시가 잠긴다.
#
# 사용: verify-marketplace-divergence.sh <safety|baseline|support|run|post|verdictA|verdictB|verdictC|verdictD|final|scope>
set -uo pipefail

REPO="$HOME/.claude/plugins/marketplaces/claude-templates"
E="$HOME/.claude/verification-evidence/claude-templates-marketplace-update"
SENTINEL="$REPO/.git/cross-vendor-update-sentinel-8248e32"
ORIGIN_URL="https://github.com/HMWKR/CLAUDE-TEMPLATES.git"

step_safety() {
  set -e
  test ! -e "$E"
  mkdir -p "$E"
  test -d "$REPO/.git"
  git -C "$REPO" rev-parse '8248e32^{commit}' > "$E/expected-commit"
  test "$(git -C "$REPO" rev-parse HEAD)" = "$(cat "$E/expected-commit")"
  # [2026-07-25 접근 변경 — 기준은 불변] codex 원안은 git bundle을 안전장치로 지정했으나,
  # 이 저장소는 shallow clone(depth 1, .git/shallow 존재)이라 `bundle create --all`이
  # 경계 밖 부모 객체를 참조해 **clone 불가한 번들**을 만든다(실측: "remote did not send
  # all necessary objects"). 마켓플레이스 13곳 전부 shallow다.
  # 요구 기준("실험 전 8248e32의 복구 가능성을 실제 복원으로 증명")은 그대로 두고
  # 방법만 tar 전체 백업으로 바꾼다 — 기준 하향이 아니다.
  tar -czf "$E/repo-full-backup.tar.gz" -C "$(dirname "$REPO")" "$(basename "$REPO")"
  test -s "$E/repo-full-backup.tar.gz"
  rm -rf "$E/recovery-proof"
  mkdir -p "$E/recovery-proof"
  tar -xzf "$E/repo-full-backup.tar.gz" -C "$E/recovery-proof"
  git -C "$E/recovery-proof/$(basename "$REPO")" cat-file -e '8248e32^{commit}'
  test "$(git -C "$E/recovery-proof/$(basename "$REPO")" rev-parse HEAD)" = "$(cat "$E/expected-commit")"
  printf 'RECOVERY_OK %s\n' "$(cat "$E/expected-commit")" | tee "$E/recovery-proof.txt"
}

step_baseline() {
  set -e
  test ! -e "$E/pre.head"
  test "$(git -C "$REPO" rev-parse HEAD)" = "$(git -C "$REPO" rev-parse '8248e32^{commit}')"
  test "$(git -C "$REPO" rev-list --count origin/main..HEAD)" = 1
  test -z "$(git -C "$REPO" status --porcelain)"
  test "$(git -C "$REPO" config --get remote.origin.url)" = "$ORIGIN_URL"
  git -C "$REPO" log -1 --format=%s | grep -E '^fix\(local\):'
  test -f "$REPO/plugins/jusan-harness/skills/playwright-qa-expert/SKILL.md"
  git -C "$REPO" diff-tree --no-commit-id --name-only -r 8248e32 > "$E/pre.changed-files"
  grep -Fx 'plugins/jusan-harness/skills/playwright-qa-expert/SKILL.md' "$E/pre.changed-files"
  git -C "$REPO" rev-parse HEAD > "$E/pre.head"
  git -C "$REPO" rev-parse 'HEAD^{tree}' > "$E/pre.tree"
  git -C "$REPO" rev-parse origin/main > "$E/pre.origin-main"
  git -C "$REPO" status --porcelain > "$E/pre.status"
  git -C "$REPO" for-each-ref --format='%(refname) %(objectname)' | LC_ALL=C sort > "$E/pre.refs"
  git -C "$REPO" config --get remote.origin.url > "$E/pre.origin-url"
  git -C "$REPO" log -1 --format=%s > "$E/pre.subject"
  printf 'cross-vendor-update-sentinel-8248e32\n' > "$SENTINEL"
  shasum -a 256 "$SENTINEL" > "$E/sentinel.sha256"
  stat -f '%d:%i' "$REPO/.git" > "$E/pre.gitdir-stat"
  test -z "$(git -C "$REPO" status --porcelain)"
  printf 'BASELINE_OK head=%s ahead=1 clean=yes\n' "$(cat "$E/pre.head")"
}

step_support() {
  set -e
  set +e
  claude plugin marketplace --help > "$E/help.stdout" 2> "$E/help.stderr"
  rc=$?
  set -e
  printf '%s\n' "$rc" > "$E/help.exit"
  test "$rc" -eq 0
  cat "$E/help.stdout" "$E/help.stderr" > "$E/help.combined"
  test -s "$E/help.combined"
  if grep -Eiq '(^|[[:space:]])update([[:space:]]|$)' "$E/help.combined"; then
    printf 'SUPPORTED\n' | tee "$E/update.support"
  else
    printf 'UNSUPPORTED\n' | tee "$E/update.support"
  fi
}

step_run() {
  set -e
  test ! -e "$E/update.invocation"
  printf '%s\n' 'claude plugin marketplace update claude-templates' > "$E/update.command"
  : > "$E/git-trace.log"
  : > "$E/git-trace2.json"
  if test "$(cat "$E/update.support")" = "SUPPORTED"; then
    ( set -o noclobber; printf 'RAN\n' > "$E/update.invocation" )
    date -u '+%Y-%m-%dT%H:%M:%SZ' > "$E/update.started"
    set +e
    GIT_TRACE="$E/git-trace.log" GIT_TRACE2_EVENT="$E/git-trace2.json" \
      claude plugin marketplace update claude-templates \
      > "$E/update.stdout" 2> "$E/update.stderr"
    rc=$?
    set -e
    printf '%s\n' "$rc" > "$E/update.exit"
    date -u '+%Y-%m-%dT%H:%M:%SZ' > "$E/update.finished"
  else
    ( set -o noclobber; printf 'NOT_RUN\n' > "$E/update.invocation" )
    printf '127\n' > "$E/update.exit"
    : > "$E/update.stdout"
    : > "$E/update.stderr"
  fi
  grep -Ex 'RAN|NOT_RUN' "$E/update.invocation"
  grep -Eq '^[0-9]+$' "$E/update.exit"
  printf 'UPDATE_CAPTURED invocation=%s exit=%s\n' "$(cat "$E/update.invocation")" "$(cat "$E/update.exit")"
}

cmp_delta() { if cmp -s "$1" "$2"; then printf 'SAME\n'; else printf 'CHANGED\n'; fi; }

trace_regex() {
  if grep -Eiq "$1" "$E/git-trace.log" "$E/git-trace2.json" 2>/dev/null; then
    printf 'YES\n'
  else
    printf 'NO\n'
  fi
}

step_post() {
  set -e
  expected="$(cat "$E/expected-commit")"
  if git -C "$REPO" rev-parse --git-dir >/dev/null 2>&1; then
    printf 'PRESENT\n' > "$E/post.repo"
    git -C "$REPO" rev-parse HEAD > "$E/post.head"
    git -C "$REPO" rev-parse 'HEAD^{tree}' > "$E/post.tree"
    git -C "$REPO" rev-parse origin/main > "$E/post.origin-main"
    git -C "$REPO" status --porcelain > "$E/post.status"
    git -C "$REPO" diff --name-only --diff-filter=U > "$E/post.conflicts"
    git -C "$REPO" for-each-ref --format='%(refname) %(objectname)' | LC_ALL=C sort > "$E/post.refs"
    git -C "$REPO" config --get remote.origin.url > "$E/post.origin-url"
    stat -f '%d:%i' "$REPO/.git" > "$E/post.gitdir-stat"

    if test ! -e "$SENTINEL"; then
      printf 'MISSING\n' > "$E/post.sentinel"
    elif test "$(shasum -a 256 "$SENTINEL" | awk '{print $1}')" = "$(awk '{print $1}' "$E/sentinel.sha256")"; then
      printf 'SAME\n' > "$E/post.sentinel"
    else
      printf 'CHANGED\n' > "$E/post.sentinel"
    fi

    if git -C "$REPO" cat-file -e "$expected^{commit}" 2>/dev/null; then
      printf 'PRESENT\n' > "$E/post.commit-object"
      set +e
      git -C "$REPO" merge-base --is-ancestor "$expected" HEAD
      arc=$?
      set -e
      case "$arc" in
        0) printf 'YES\n' > "$E/post.commit-ancestor-head" ;;
        1) printf 'NO\n' > "$E/post.commit-ancestor-head" ;;
        *) exit "$arc" ;;
      esac
      git -C "$REPO" for-each-ref --contains "$expected" --format='%(refname)' refs/heads refs/tags > "$E/post.local-refs-containing"
    else
      printf 'MISSING\n' > "$E/post.commit-object"
      printf 'NO\n' > "$E/post.commit-ancestor-head"
      : > "$E/post.local-refs-containing"
    fi

    wc -l < "$E/post.local-refs-containing" | tr -d '[:space:]' > "$E/post.local-ref-count"; printf '\n' >> "$E/post.local-ref-count"
    wc -l < "$E/post.conflicts" | tr -d '[:space:]' > "$E/post.conflict-count"; printf '\n' >> "$E/post.conflict-count"

    cmp_delta "$E/pre.head" "$E/post.head" > "$E/delta.head"
    cmp_delta "$E/pre.tree" "$E/post.tree" > "$E/delta.tree"
    cmp_delta "$E/pre.origin-main" "$E/post.origin-main" > "$E/delta.origin-main"
    cmp_delta "$E/pre.refs" "$E/post.refs" > "$E/delta.refs"
    cmp_delta "$E/pre.status" "$E/post.status" > "$E/delta.status"
    cmp_delta "$E/pre.origin-url" "$E/post.origin-url" > "$E/delta.origin-url"
    cmp_delta "$E/pre.gitdir-stat" "$E/post.gitdir-stat" > "$E/delta.gitdir"
    if cmp -s "$E/post.head" "$E/post.origin-main"; then printf 'YES\n'; else printf 'NO\n'; fi > "$E/post.head-equals-origin"
  else
    printf 'MISSING\n' > "$E/post.repo"
    for n in head tree origin-main status conflicts refs origin-url gitdir-stat local-refs-containing; do : > "$E/post.$n"; done
    for n in sentinel commit-object commit-ancestor-head head-equals-origin; do printf 'UNAVAILABLE\n' > "$E/post.$n"; done
    printf '0\n' > "$E/post.local-ref-count"
    printf '0\n' > "$E/post.conflict-count"
    for n in head tree origin-main refs status origin-url gitdir; do printf 'UNAVAILABLE\n' > "$E/delta.$n"; done
  fi

  trace_regex '(^|[[:space:]",/])(pull|merge|rebase)([[:space:]",]|$)' > "$E/trace.preserve-action"
  trace_regex '(^|[[:space:]",/])fetch([[:space:]",]|$)' > "$E/trace.fetch-action"
  trace_regex '(^|[[:space:]",/])clone([[:space:]",]|$)' > "$E/trace.clone-action"
  trace_regex '(^|[[:space:]",/])(reset|checkout|switch)([[:space:]",]|$)' > "$E/trace.destructive-action"

  printf 'POST_CAPTURED repo=%s sentinel=%s ancestor=%s\n' \
    "$(cat "$E/post.repo")" "$(cat "$E/post.sentinel")" "$(cat "$E/post.commit-ancestor-head")"
}

step_verdictA() {
  match=0
  rc="$(cat "$E/update.exit")"
  conflicts="$(cat "$E/post.conflict-count")"
  if test "$(cat "$E/update.support")" = SUPPORTED &&
     test "$(cat "$E/update.invocation")" = RAN &&
     test "$(cat "$E/post.repo")" = PRESENT &&
     test "$(cat "$E/post.sentinel")" = SAME &&
     test "$(cat "$E/post.commit-ancestor-head")" = YES &&
     test "$(cat "$E/post.origin-url")" = "$ORIGIN_URL"; then
    if { test "$rc" -eq 0 && { test "$(cat "$E/trace.preserve-action")" = YES || test "$(cat "$E/delta.head")" = CHANGED; }; } ||
       { test "$rc" -ne 0 && test "$conflicts" -gt 0 && test "$(cat "$E/trace.preserve-action")" = YES; }; then
      match=1
    fi
  fi
  if test "$match" -eq 1; then printf 'MATCH\n' | tee "$E/verdict.A"; exit 0; fi
  printf 'REJECT\n' | tee "$E/verdict.A"; exit 1
}

step_verdictB() {
  match=0
  if test "$(cat "$E/update.support")" = SUPPORTED &&
     test "$(cat "$E/update.invocation")" = RAN &&
     test "$(cat "$E/update.exit")" -eq 0 &&
     test "$(cat "$E/post.repo")" = PRESENT &&
     test "$(cat "$E/post.sentinel")" = SAME &&
     test "$(cat "$E/post.commit-ancestor-head")" = NO &&
     test "$(cat "$E/post.local-ref-count")" -eq 0 &&
     test "$(cat "$E/post.head-equals-origin")" = YES &&
     test "$(cat "$E/post.conflict-count")" -eq 0 &&
     test "$(cat "$E/delta.head")" = CHANGED &&
     test "$(cat "$E/post.origin-url")" = "$ORIGIN_URL"; then
    match=1
  fi
  if test "$match" -eq 1; then printf 'MATCH\n' | tee "$E/verdict.B"; exit 0; fi
  printf 'REJECT\n' | tee "$E/verdict.B"; exit 1
}

step_verdictC() {
  match=0
  if test "$(cat "$E/update.support")" = SUPPORTED &&
     test "$(cat "$E/update.invocation")" = RAN &&
     test "$(cat "$E/update.exit")" -eq 0 &&
     test "$(cat "$E/post.repo")" = PRESENT &&
     test "$(cat "$E/post.sentinel")" = MISSING &&
     test "$(cat "$E/post.commit-ancestor-head")" = NO &&
     test "$(cat "$E/post.local-ref-count")" -eq 0 &&
     test "$(cat "$E/post.head-equals-origin")" = YES &&
     test "$(cat "$E/post.conflict-count")" -eq 0 &&
     test "$(cat "$E/delta.head")" = CHANGED &&
     test "$(cat "$E/post.origin-url")" = "$ORIGIN_URL" &&
     { test "$(cat "$E/delta.gitdir")" = CHANGED || test "$(cat "$E/trace.clone-action")" = YES; }; then
    match=1
  fi
  if test "$match" -eq 1; then printf 'MATCH\n' | tee "$E/verdict.C"; exit 0; fi
  printf 'REJECT\n' | tee "$E/verdict.C"; exit 1
}

step_verdictD() {
  match=0
  common_unchanged() {
    test "$(cat "$E/post.repo")" = PRESENT &&
    test "$(cat "$E/post.sentinel")" = SAME &&
    test "$(cat "$E/post.commit-ancestor-head")" = YES &&
    test "$(cat "$E/delta.head")" = SAME &&
    test "$(cat "$E/delta.tree")" = SAME &&
    test "$(cat "$E/delta.origin-main")" = SAME &&
    test "$(cat "$E/delta.refs")" = SAME &&
    test "$(cat "$E/delta.status")" = SAME &&
    test "$(cat "$E/delta.origin-url")" = SAME
  }
  if test "$(cat "$E/update.support")" = UNSUPPORTED &&
     test "$(cat "$E/update.invocation")" = NOT_RUN &&
     test "$(cat "$E/update.exit")" -eq 127 &&
     common_unchanged; then
    match=1
  elif test "$(cat "$E/update.support")" = SUPPORTED &&
       test "$(cat "$E/update.invocation")" = RAN &&
       common_unchanged &&
       test "$(cat "$E/trace.preserve-action")" = NO &&
       test "$(cat "$E/trace.destructive-action")" = NO &&
       test "$(cat "$E/trace.clone-action")" = NO; then
    match=1
  fi
  if test "$match" -eq 1; then printf 'MATCH\n' | tee "$E/verdict.D"; exit 0; fi
  printf 'REJECT\n' | tee "$E/verdict.D"; exit 1
}

step_final() {
  set -e
  for h in A B C D; do
    test -f "$E/verdict.$h"
    grep -Ex 'MATCH|REJECT' "$E/verdict.$h" >/dev/null
  done
  matched=0
  for h in A B C D; do
    if test "$(cat "$E/verdict.$h")" = MATCH; then matched=$((matched+1)); fi
  done
  test "$matched" -eq 1
  for h in A B C D; do
    if test "$(cat "$E/verdict.$h")" = MATCH; then
      printf 'FINAL_HYPOTHESIS=%s\n' "$h" | tee "$E/final-verdict.txt"
    fi
  done
  grep -Ex 'FINAL_HYPOTHESIS=[ABCD]' "$E/final-verdict.txt"
}

step_scope() {
  set -e
  test "$(cat "$E/update.command")" = 'claude plugin marketplace update claude-templates'
  ! grep -Eiq 'claude plugin (uninstall|install)' \
      "$E/update.command" "$E/update.stdout" "$E/update.stderr" "$E/git-trace.log" "$E/git-trace2.json"
  printf 'SCOPE_OK no-cache-propagation\n'
}

case "${1:-}" in
  safety)   step_safety ;;
  baseline) step_baseline ;;
  support)  step_support ;;
  run)      step_run ;;
  post)     step_post ;;
  verdictA) step_verdictA ;;
  verdictB) step_verdictB ;;
  verdictC) step_verdictC ;;
  verdictD) step_verdictD ;;
  final)    step_final ;;
  scope)    step_scope ;;
  *) echo "usage: $0 <safety|baseline|support|run|post|verdictA|verdictB|verdictC|verdictD|final|scope>"; exit 2 ;;
esac
