# 워치짐 앱 (이 폴더가 실제 앱·배포 저장소)

## 폴더 두 개, 역할이 다르다
- `워치짐-앱수정` (이 폴더, main): 폰·워치 앱을 빌드하고 배포하는 곳. **폰에 들어가는 모든 것은 여기서 만든다.**
- `워치짐` (브랜치 codex/deformation-hardening): 3D 모델·동작을 만들고 고치는 설계 작업장. 여기서 고친 건 **저절로 폰에 안 들어간다.**

## 3D 모델/동작을 고친 뒤 폰에 반영하는 법
폰의 3D는 V5 사람 모델이고, `phone/src/main/assets/viewer3d/`에 압축(WGP2, 손실 없음)된 묶음으로 들어 있다. 이 폴더는 git에 없고 도구로 다시 만든다.
1. PC에서 고친 결과는 `~/Library/Application Support/WatchGymViewer/v5-catalog/`에 게시된다. 확인 주소: `http://127.0.0.1:8765/v5-catalog/?human=v5-guide&front=moderate&clip=<운동id>`
2. 고친 운동 몇 개만 앱 묶음에 반영: `python3 tools/update_app3d_v5_clips.py --update <운동id> ...` (앱에서 빠진 운동은 `--remove <id>`)
3. 전체를 처음부터 다시 만들 때만: `python3 tools/build_app3d_v5.py --extra <롤링 트라이셉스 변환 폴더>`
4. 반영 확인 후 앱을 빌드한다. 폰 배포는 사용자가 말할 때만 한다(`tools/release.sh`).
- 운동을 앱 목록에서 빼면: `WorkoutData.kt`(목록) + `WorkoutDataTest.kt`(개수) + `tools/viewer3d/camera_views.json` + `phone/src/main/assets/previews/<id>.webp` + 위 `--remove`.
- 구도 `tools/gen_camera_views.py`, 썸네일 촬영 `tools/preview_capture.py`.

## 하지 말 것
- `워치짐` 폴더의 `phone/src/main/assets/viewer3d`는 옛 사람 모델(구형)이다. 거기에 반영하고 끝내지 않는다.
- 사용자가 말하기 전에 배포하지 않는다. 다른 작업(결과 화면 등)의 미커밋 변경을 같이 커밋하지 않는다.
