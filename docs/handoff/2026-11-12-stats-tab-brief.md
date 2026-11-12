# 통계탭 개편 — 앱 반영 지시서

디자인 정답 = `docs/handoff/stats-tab-design.html` (브라우저로 열어 보고, 실제 앱 레이아웃·토큰으로 그린 시안. ui 코드는 그 파일 안의 script/style). 이 시안을 `StatsScreen`(phone/.../ui/TabScreens.kt)에 안드로이드 네이티브(Compose)로 똑같이 옮겨라. 3D 인체는 지금처럼 `Exercise3DView` + `human_stats.html`(tools/viewer3d 와 phone assets 두 곳 동일 유지).

## 구성 (위→아래)
1. 근육 피로도 3D 인체(앞/뒤 두 모델, 가로 꽉 채움, 각각 따로 좌우 드래그 회전) + **시간 슬라이더**: 가운데=지금, 앞뒤 ±4일, 3시간 간격(총 65칸). 칸이 바뀔 때마다 햅틱(안드로이드 슬라이더 틱). 시각에 따라 부위별 피로를 다시 계산해 인체 색 갱신 → `human_stats.html`에 쿼리 일회성 대신 JS 함수(예: setFatigue(map))를 두고 WebView evaluateJavascript로 갱신.
2. 이번 주 vs 지난 주 선 그래프.
3. 부위별 볼륨 레이더(kg 기준) + 자체 기간 버튼 7/30/90/전체, 바뀔 때 애니메이션.
4. 새 기록 카드(PR). 앱에 PR 기능이 아직 없으니 기록 이력에서 종목별 최고 중량×횟수 갱신을 계산해 만든다.
5. 누적 기록(자체 기간 버튼 7/30/90/전체) + 루틴별 세트.
- 하단 탭바는 화면 아래 고정(떠 있는 형태), 본문은 한 번에 스크롤.
- **없앤 것(넣지 말 것)**: 부위별 남은 회복일 목록, 기간별 볼륨, 세트 기준 레이더, 설명 문장, "앞/뒤" 글자, 전완.

## 피로 계산 (이미 있음)
`core/.../BodyLoad.kt`의 `fatigueByPart`/`partWeights`/RECOVERY_DAYS/FULL_FATIGUE_SETS(15). 임의 시각에서 계산하게 확장(세션 시작시각 `startedAtMs`, 0이면 그날 정오로 대체). 테스트 `BodyLoadTest` 유지·보강.

## 규칙
- 색·간격·글꼴은 앱 기존 토큰(KColors 등) 그대로. 시안 숫자·문구는 시안을 따르되 데이터는 실제 기록에서.
- 커밋·배포·push 금지. 작업 폴더는 이 저장소(워치짐-앱수정)만, 3D 모델 파일(human_v5 등)은 건드리지 말 것.
- 끝나면: `:core:test` 와 `:phone:compileDebugKotlin :phone:compileDebugUnitTestKotlin` 통과 확인(명령은 CLAUDE.md 참고), 바뀐 것/못 한 것을 `docs/handoff/2026-11-12-stats-tab-report.md`에 짧게.
