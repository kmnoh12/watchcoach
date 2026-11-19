# 워치코치 (3D 설계 · 앱 빌드·배포 통합 저장소)

## 이 폴더 하나에서 전부 한다 (브랜치 `main`)
- 예전에 나뉘어 있던 3D 설계 작업장(`design/`)과 폰·워치 앱 빌드·배포(`core/`, `phone/`, `wear/`, `updates/`, `tools/`)를 이 `워치코치` 폴더 하나로 합쳤다.
- 다만 3D 설계물(`design/`)이나 PC 뷰어에서 고친 결과가 **저절로 폰 앱에 들어가지는 않는다.** 아래 절차로 앱 묶음(`phone/src/main/assets/viewer3d/`)에 반영해야 폰에 들어간다.

## 3D 모델/동작을 고친 뒤 폰에 반영하는 법
폰의 3D는 V5 사람 모델이고, `phone/src/main/assets/viewer3d/`에 압축(WGP2, 손실 없음)된 묶음으로 들어 있다. 이 폴더는 git에 없고 도구로 다시 만든다.
1. PC에서 고친 결과는 `~/Library/Application Support/__PROTECTED_WATCHCOACH_VIEWER__/v5-catalog/`에 게시된다. 확인 주소: `http://127.0.0.1:8765/v5-catalog/?human=v5-guide&front=moderate&clip=<운동id>`
2. 고친 운동 몇 개만 앱 묶음에 반영: `python3 tools/update_app3d_v5_clips.py --update <운동id> ...` (앱에서 빠진 운동은 `--remove <id>`)
3. 전체를 처음부터 다시 만들 때만: `python3 tools/build_app3d_v5.py --extra design/exercise-figure/lowpoly-remake/gemini_job/v5_arm_rebuild/app_rollout_20261109/rolling_trial`
4. 반영 확인 후 앱을 빌드한다. 폰 반영(`tools/update_app3d_v5_clips.py`)까지가 "내 폰에 반영"이고, 폰 배포(`tools/release.sh`)는 사용자가 말할 때만 한다.
- 운동을 앱 목록에서 빼면: `WorkoutData.kt`(목록) + `WorkoutDataTest.kt`(개수) + `tools/viewer3d/camera_views.json` + `phone/src/main/assets/previews/<id>.webp` + 위 `--remove`.
- 구도 `tools/gen_camera_views.py`, 썸네일 촬영 `tools/preview_capture.py`.

## 변경 완료와 GitHub 반영
- 워치코치 수정 요청(앱 코드, Blender 씬·모델, 생성 코드·에셋 등)은 결과를 확인한 뒤 해당 요청의 변경만 커밋하고 GitHub의 `main`에 푸시한다. 원격 반영을 확인하고 커밋 링크를 보고한다. 사용자가 로컬 작업만 요청하면 푸시를 생략한다.

## 하지 말 것
- 사용자가 말하기 전에 배포하지 않는다. 다른 작업(결과 화면 등)의 미커밋 변경을 같이 커밋하지 않는다.
