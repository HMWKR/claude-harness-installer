# AGENTS.md

이 레포는 Claude Code 하네스 배포판입니다. 사용자가 설치를 요청하면:

1. 레포 루트에서 `./install.sh`를 실행합니다(MCP까지 원하면 `--with-mcp`).
2. 종료 코드가 0인지 확인하고, 아니면 `실패:` 줄과 로그 경로를 그대로 보고합니다.
3. Claude Code를 새로 시작해야 적용된다고 알립니다.

`payload/` 안의 파일을 직접 `~/.claude`로 복사하지 마세요. `__HOME__` 자리표시자 치환과 백업은 `install.sh`가 합니다. 자세한 내용은 README.md를 보세요.
