# Third-party notices

## 레포에 포함된 제3자 스킬 (`payload/.claude/skills/`)

| 스킬 | 출처 | 라이선스 | 라이선스 전문 |
|---|---|---|---|
| impeccable | github.com/pbakaus/impeccable, tag skill-v4.8.0 | Apache-2.0 | [third_party/licenses/impeccable.LICENSE](third_party/licenses/impeccable.LICENSE) |
| motiscope-analyze, motiscope-doctor, motiscope-rebuild-site, motiscope-recreate | github.com/KumarSashank/motiscope @ c0ce3dd | MIT | [third_party/licenses/motiscope.LICENSE](third_party/licenses/motiscope.LICENSE) |
| ffmpeg-skill | github.com/kajisho5/ffmpeg-skill v2.8.6 | MIT | 스킬 폴더의 `LICENSE`, [사본](third_party/licenses/ffmpeg-skill.LICENSE) |
| motion | npm `motion-ai@14.2.0` (github.com/motiondivision/ai-kit) | MIT (package.json 선언, 패키지에 LICENSE 파일 없음) | — |
| aside-browser | Aside 브라우저가 배포하는 진입 스킬 | 명시 없음 | — |
| clone-site-from-source | 출처 미상 zip(Codex 환경용)을 하네스에 맞게 고친 것. 원본 zip은 포함하지 않음 | 명시 없음 | — |

일부 스킬은 하네스 규칙에 맞게 수정되어 있습니다. 각 폴더의 `.install-source.txt`·`HARNESS-ADAPTATION.md`에 원본과의 차이가 적혀 있습니다.

## 설치할 때 원본에서 받는 것

`manifest/skills.json`의 외부 스킬과 `manifest/plugins.json`의 플러그인은 이 레포에 들어 있지 않습니다. `install.sh`가 각 원본 레포에서 받아 설치하며, 라이선스는 각 원본을 따릅니다.
