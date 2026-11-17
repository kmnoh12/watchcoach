# 워치짐 모델 수정 인계 (2026-11-06)

## 상황
- 3D 작업은 Codex2가 하고, 통제 세션은 결과를 눈으로 확인한다.
- 시험 뷰어: http://127.0.0.1:8765/v5-catalog/?human=v5-guide&front=moderate&clip=dumbbell_goblet_squat
- 뷰어는 브라우저 캐시가 남으니 수정 뒤에는 주소 끝에 `&v=새값`을 붙여 연다. 예전 주소로 보면 옛날 모양이 나온다.
- 작업 폴더 `워치짐`, 브랜치 `codex/deformation-hardening`. 미커밋 변경은 Codex 작업이니 유지한다.
- 작업 위치: `design/exercise-figure/lowpoly-remake/gemini_job/v5_arm_rebuild`, `work/v5-finish`. 기록은 `CONVERSION.md`.
- 전체 시험 뷰어 248종: 미변환 0, 검사 문제 0. 승인된 종목은 아직 없다.

## Codex2 실행법
- 세션 ID: `01a1af15-3fb0-79c0-9fa6-ed65f2b4acd2`
- 다음 지시는 같은 대화로 이어간다. `~/.codex2/config.toml`의 Mixin 설정 두 줄을 지워서 아래 `-c` 옵션 두 개는 이제 없어도 된다.
```
export CODEX_HOME=$HOME/.codex2
/Applications/ChatGPT2.app/Contents/Resources/codex-cli/bin/codex exec resume --skip-git-repo-check -m gpt-6.1-sol \
  -c 'model_catalog_json="/Users/kmnoh/.codex/model-catalogs/mixin-models.json"' \
  -c 'openai_base_url="https://chatgpt.com/backend-api/codex"' \
  01a1af15-3fb0-79c0-9fa6-ed65f2b4acd2 "지시" < /dev/null
```
- 터미널 탭에서 보이게 돌리고, 끝을 알 수 있게 tracked 대기 작업을 건다.
- 지시 공통: 앱 코드, `phone/src/main/assets`, 배포, gradle, 커밋 금지. 전체 재변환 금지, 검사 늘리지 않기. 3~5줄로 짧게.

## 다음 할 일
1. 덤벨 고블릿 이두: Codex2가 겨드랑이 쪽 돌출 17~24mm, 이두 중앙 6mm를 줄여 뷰어에 반영했다. Kyungmin의 눈 판정 대기. 다시 지적하면 같은 방향으로 이어간다(삼두는 양호, 건드리지 말 것).
2. 케틀벨 고블릿 스쿼트(`goblet_squat`): 손 위치가 이상하다. 참고 사진 `2026-11-06-kettlebell-goblet-ref.png`처럼 케틀벨 손잡이의 양옆 기둥을 양손으로 잡고 가슴 앞에 둔다. 팔꿈치는 사진처럼 양옆으로 벌려서 몸통에서 떨어뜨리고 살짝 앞에 둔다(팔이 몸과 겹치면 안 된다). 사진은 자세 참고용이고 인물 형태는 따라 하지 않는다.

## 앱 쪽 상태 (건드릴 일 없으면 참고만)
- 앱 수정 폴더는 `워치짐-앱수정`, main, 트리 깨끗. 폰 0.2.26, 워치 0.2.18 배포됨. 실기기 확인은 Kyungmin 몫.
- `phone/src/main/assets/viewer3d`는 git에 없다. 새 worktree 빌드 시 빠지며 release.sh가 막는다. 앱용 3D는 아직 0.2.24 자산이고 V5 시험본은 앱에 안 들어갔다.
