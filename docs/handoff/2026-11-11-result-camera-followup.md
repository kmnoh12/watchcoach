# 결과화면·오운완 카메라 후속 인수인계 (2026-11-11 오후)

작업 폴더: `~/Documents/Default Project/워치짐-앱수정` (main 브랜치, 배포는 여기서 `tools/release.sh`).
`워치짐` 폴더(codex/deformation-hardening)는 3D 작업용이다. 거기 남은 결과화면 미커밋 사본은 배포본과 같은 내용이니 손대지 마라.

## 이미 배포됨
p0.2.28-w0.2.19: 새 결과화면 + 오운완 카메라, 워치 반복 종료 수정, 쌓여 있던 작업 전부.

## 배포 후 고친 것 (미커밋·미배포, 빌드 통과, 폰에서 미확인)
모두 `phone/src/main/kotlin/dev/kyungmin/kcoach/phone/ui/` 안.
1. 카메라 틀 위치: 위 여백 56 → 8dp(상수 `ResultCameraTop`, 하단 조작부 `ResultCameraControls = 138`, `DesignedWorkoutResult.kt`). 결과 카드 폭도 같은 식으로 계산. 원인: 앱은 상태바·내비바를 뺀 높이에서 다시 56을 내려서, 높이가 모자라 틀 전체가 비율 축소되며 좌우가 좁아졌다. 사용자 폰 기준 좌우 여백 약 30 → 19 예상.
2. ✕·다시 찍기 위치를 화면 기준(22,66)에서 사진 틀 기준(틀 왼쪽+11, 위+10)으로. `ResultCameraView.kt` `drawControls`.
3. 비율 탭: 글자가 왼쪽 정렬이라 어긋났다. 이제 글자 폭+4dp, 간격 24dp로 중심을 계산하고 선택 탭 중심 = 화면 중심 = 민트 점 = 셔터.
4. 찍은 뒤: 어두운 네모 '다시 찍기' 상자를 없애고 ✕와 같은 반투명 동그라미(검정 45%) 안에 ↺ 화살표(호 300°, 반지름 6.6dp, 선 2dp, 화살촉은 호 시작점)를 그림. 누르면 다시 찍기.

## 남은 일
- **다시 찍기 ↺ 화살표 다듬기**: 사용자가 수정 요청함. 폰에서 보고 모양·크기 조정. (브라우저 캔버스로 같은 계산을 그려 확인하는 방식이 빠르다. file:// 페이지는 프로젝트 폴더 안에 둬야 내장 브라우저가 열림.)
- 위 1~4 커밋 후 배포(사용자가 배포 지시할 때만). 폰 버전 0.2.29/68로 올리고 `tools/release.sh --phone "노트"`. 트리가 깨끗해야 함.
- 앱 말투 통일(코덱스 작업 예정): 버튼·라벨·상태 = 짧은 명사형, 사실·결과·설명·오류 = ~합니다, 묻거나 부탁 = ~요. `core/src/test/.../KoreanToneTest`가 지금은 해요체를 강제하고 합니다를 막으니 규칙도 같이 바꿔야 한다. `docs/DESIGN.md` 문구 규칙, `docs/NEXT_PLAN.md` C절 갱신. 워치 문구 길이 넘침 확인.
- 인스타 스토리 직행: Meta App ID가 없어 일반 인스타 공유로 연결됨. ID를 받으면 manifest `com.facebook.sdk.ApplicationId`.
- 결과화면 '반복 속도 보기'(템포 막대)는 새 디자인에서 빠졌다. 필요하면 사용자에게 물어볼 것.
- 실기 확인 필요: 카드→카메라 펴짐 연출, 블러 0.15초 뒤 0.3초, 화면비 0.42초 전환, 글씨 밝기별 색, 저장 사진, 워치 1시간 운동 중 종료 여부.

## 참고
- 확정 시안: `docs/design/2026-11-10-result-screen-redesign/variants.html` (워치짐 폴더 쪽에 있음, git 밖일 수 있음).
- 구현 지시서/보고: `docs/handoff/2026-11-11-result-screen-android-brief.md`, `...-report.md`.
- 빌드: `T=~/Documents/Default\ Project/안드로이드-에뮬레이터; JAVA_HOME=$T/jdk17/Contents/Home ANDROID_SDK_ROOT=$T/android-sdk $T/gradle-8.11.1/bin/gradle :phone:compileDebugKotlin`. `LateralRaisePhaseInvestigationTest`는 외부 CSV가 없어 원래 실패한다.
- 코덱스2 실행 시 `-m gpt-6.1-sol` 필수(기본 모델 거부됨).
