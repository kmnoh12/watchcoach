# 통계 탭 반영 결과 — 2026-11-12

## 바뀐 것
- 브라우저로 `stats-tab-design.html`을 열어 확인하고, StatsScreen을 Compose로 구성했다: 근육 피로도 → 이번 주/지난주 누적 선 그래프 → kg 레이더 → 새 기록 → 누적 기록/루틴별 세트. 기존 KColors·글꼴·간격을 사용한다.
- 피로도 슬라이더는 지금 중심 ±4일, 3시간 간격 65개 값이다. 값이 바뀌면 Android slider tick 햅틱을 요청한다. 시작 시각을 쓰고, 없는 옛 기록은 기기 시간대의 당일 정오로 계산하며, 선택 시각보다 늦은 세션은 제외한다. 기존 회복 곡선·부위 가중치·15세트 기준은 유지했다.
- WebView는 최신 피로도 맵을 보관하고 페이지 준비 후 전달한다. `setFatigue(map)`는 모델 로딩 전에도 값을 보관하며, 로딩 후 색만 갱신한다. 두 모델의 개별 회전은 유지한다. `tools/viewer3d/human_stats.html`과 앱 assets 사본은 동일하다. 전완 색칠을 제거했고 3D 모델 원본은 수정하지 않았다.
- 레이더는 7/30/90/전체와 직전 동기간 비교, 기간 전환 애니메이션을 제공한다. 누적 기록의 기간 선택은 독립적이다. 실제 저장 이력을 사용하며 미래 날짜는 집계하지 않는다. 레이더는 종목의 대표 부위로 kg 볼륨을 합산하고, 전신 운동만 기존 부위 가중치를 정규화해 나눈다(중복 볼륨 방지).
- PR은 완료·횟수 입력된 중량 세트의 중량×횟수 최고값을 시간순으로 비교한다. 첫 기록/동률/시간 유지 세트는 제외하고, 종목별 최신 갱신 중 최근 3개를 표시한다. 중량과 횟수가 함께 바뀌면 증가량은 kg·회로 표시한다.
- 기존 하단 탭바를 고정 유지하고, 통계 본문만 아래까지 한 번에 스크롤하도록 통계 화면의 바깥 빈 공간을 본문 하단 여백으로 옮겼다. 다른 탭 레이아웃은 유지했다.
- 기존 미커밋 변경을 보존했다. 커밋·push·배포·기기 설치는 하지 않았다.

## 검증 / 못 한 것
- `:phone:compileDebugKotlin :phone:compileDebugUnitTestKotlin`: 최종 코드 통과.
- `BodyLoadTest` 9개 + `StatsAnalyticsTest` 4개: 통과. 임의 시각/정오 대체/미래 세션/미완료 세트/기간 경계/주간 비교/부위별 kg/PR을 확인했다.
- 요청한 `:core:test` 실행: 총 478개 중 467개 통과, 10개 skip, 1개 실패. 기존 `LateralRaisePhaseInvestigationTest.reportAllAvailableMmFitSets`가 `work/datasets/mmfit-probe` CSV 자료 부재로 실패했다(`MM-Fit probe CSVs required for this investigation`). 해당 테스트나 자료 조건을 바꾸거나 우회하지 않았다. 따라서 전체 테스트 통과 조건은 미충족이다.
- 실제 Three.js 기하 데이터를 사용한 JS 검증: 초기 로딩 전 값 전달, 색 갱신/초기화, 개별 회전 유지, 재다운로드 없음, 전완 제외, HTML 사본 일치 통과. 렌더러를 대체한 코드 검증이며 실제 WebView 렌더링 검증은 아니다.
- 실제 Android 화면의 시안 일치, 손가락 드래그/스크롤 충돌, 햅틱 감촉은 미검증이다. APK 생성·설치는 하지 않았다.

검증 명령은 설치된 Gradle 8.11.1과 `JAVA_HOME=$HOME/.local/share/android-tooling/jdk17/Contents/Home`으로 실행했다. 로그: `work/stats-tab/core-targeted.log`, `required-checks.log`, `phone-compile.log`, `viewer-check.log`.
