# 워치코치 (3D 설계 · 앱 빌드·배포 통합 저장소)

## 이 폴더 하나에서 전부 한다 (브랜치 `main`)
- 예전에 나뉘어 있던 3D 설계 작업장(`design/`)과 폰·워치 앱 빌드·배포(`core/`, `phone/`, `wear/`, `updates/`, `tools/`)를 이 `워치코치` 폴더 하나로 합쳤다.
- 다만 3D 설계물(`design/`)이나 PC 뷰어에서 고친 결과가 **저절로 폰 앱에 들어가지는 않는다.** 아래 절차로 앱 묶음(`phone/src/main/assets/viewer3d/`)에 반영해야 폰에 들어간다.

## 3D 모델/동작을 고친 뒤 폰에 반영하는 법
폰의 3D는 V5 사람 모델(새 손, 정점 1,401개)과 왼손목 워치이고, `phone/src/main/assets/viewer3d/`에 압축(WGP2, 손실 없음)된 묶음으로 들어 있다. PC 카탈로그와 클립 도구는 아직 옛 손(정점 893개) 기준이라, **옛 손 원본 묶음(`work/viewer3d-oldhand/`)을 고친 뒤 마지막에 새 손으로 변환**한다. 두 폴더 모두 git에 없고 도구로 다시 만든다.
1. PC에서 고친 결과는 `~/Library/Application Support/__PROTECTED_WATCHCOACH_VIEWER__/v5-catalog/`에 게시된다. 확인 주소: `http://127.0.0.1:8765/v5-catalog/?human=v5-guide&front=moderate&clip=<운동id>`
2. 고친 운동 몇 개만 옛 손 원본 묶음에 반영: `python3 tools/update_app3d_v5_clips.py --update <운동id> ...` (앱에서 빠진 운동은 `--remove <id>`). 기본 대상이 `work/viewer3d-oldhand`다. 새 손 묶음(폰 폴더)에 직접 돌리면 삼각형 검사에서 멈추는 게 정상이다.
3. 전체를 처음부터 다시 만들 때만: `python3 tools/build_app3d_v5.py --extra design/exercise-figure/lowpoly-remake/gemini_job/v5_arm_rebuild/app_rollout_20261109/rolling_trial --output work/viewer3d-oldhand`
4. **항상 마지막에** 새 손 변환: `python3 tools/refresh_app3d_newhand.py` (Blender 5.2, numpy, scipy 필요, 맥 약 3분). 원본 묶음 247개를 새 손으로 바꾸고 손가락을 손잡이에 맞춘 뒤 워치(`tools/viewer3d/watch_v5.json`)를 넣어 폰 폴더를 교체한다. 손가락이 손잡이를 1mm 넘게 파고드는 운동이 있으면 WARNING을 띄우니, 그 운동은 카탈로그에서 동작을 고친다. 손잡이가 손바닥에 살짝 박힌 경우만 손잡이를 최대 8mm 비키고, 결과는 `hand_fit_report.json`에 남는다.
5. `work/viewer3d-oldhand`가 없는 PC에서는 3번(전체 재생성)부터 한다. `tools/sync_v5_to_app.sh`도 3번→4번 순서로 돈다.
6. 반영 확인 후 앱을 빌드한다. 4번까지가 "내 폰에 반영"이고, 폰 배포(`tools/release.sh`)는 사용자가 말할 때만 한다.
- 새 손 모델 자체를 다시 만들 때: `promo/models/fix_v5_hands.py`(옛 손 blend에만 적용), 워치 위치는 `promo/models/build_v5_with_watch.py`, 워치 묶음 파일은 `python3 tools/build_v5_watch_asset.py`.
- 폰 뷰어는 기구 움직임을 사람과 같은 시간축(`acts`)으로 재생한다. 사람 프레임마다 저장한 기구는 그 시각에 맞고, 다른 개수로 저장한 기구만 균등 간격으로 재생한다.
- 운동을 앱 목록에서 빼면: `WorkoutData.kt`(목록) + `WorkoutDataTest.kt`(개수) + `tools/viewer3d/camera_views.json` + `phone/src/main/assets/previews/<id>.webp` + 위 `--remove`.
- 구도 `tools/gen_camera_views.py`, 썸네일 촬영 `tools/preview_capture.py`.

## 작업 시작 전 GitHub 최신화
- 워치코치 작업이나 확인(최신 버전 조회, 렌더, 코드·씬 수정 등)을 시작하기 전에 먼저 `git fetch origin main`으로 원격 상태를 확인한다.
- 로컬 `main`이 `origin/main`보다 뒤처져 있고 워킹 트리가 깨끗하면 `git pull --ff-only origin main`으로 최신본을 먼저 내려받은 뒤 진행한다.
- 로컬에 미커밋 변경이 있거나 fast-forward가 안 되면 강제로 덮어쓰지 말고 상태를 먼저 알린다. 오프라인이면 로컬 기준임을 알리고 진행한다.

## 변경 완료와 GitHub 반영
- 워치코치 수정 요청(앱 코드, Blender 씬·모델, 생성 코드·에셋 등)은 결과를 확인한 뒤 해당 요청의 변경만 커밋하고 GitHub의 `main`에 푸시한다. 원격 반영을 확인하고 커밋 링크를 보고한다. 사용자가 로컬 작업만 요청하면 푸시를 생략한다.

## 하지 말 것
- 사용자가 말하기 전에 배포하지 않는다. 다른 작업(결과 화면 등)의 미커밋 변경을 같이 커밋하지 않는다.
- 씬 디테일 스크립트가 기존 오브젝트를 교체할 때 옛 원본을 숨겨 두지 않는다. 지운다(용량 낭비, 시뮬레이터 내보내기에 딸려 나옴). 남은 숨긴 원본 정리는 `promo/tools/cleanup_hidden_originals.py`.
