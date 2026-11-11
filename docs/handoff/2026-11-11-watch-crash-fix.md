# 워치 반복 종료 수정 인계 — 2026-11-11

**코드 수정과 좁은 회귀 검증 완료. 32개 통과, 실패·건너뜀 0. APK 생성·배포·설치 안 함. 실제 Watch8에서 1시간 운동하며 종료가 사라졌는지는 미확인.**

## 근거와 한계

- 작업 지시 및 옵시디언 `projects/개인용 스마트폰·갤럭시워치 운동기록 앱 개발 계획.md`의 32·33번을 읽었다. 기록에는 시작 시간 초과와 `EXCESSIVE_RESOURCE_USAGE` 종료가 별도로 존재한다. 작업본·Downloads·해당 vault에서 11/11 진단 원본을 찾지 못했고, 저장된 10/20 자료는 폰 자료라 이번 워치 원인 증명에 쓰지 않았다.
- 현재 코드에는 이미 매 `onStartCommand` 재승격과 최신 startId에 대한 `stopSelfResult`가 있었다. 과거의 같은 인스턴스 재시작 경주가 오늘도 미수정이라고 단정하지 않았다. 기존 `WearForegroundStartTest` 3개도 통과했다.
- 조사 순서는 ① 승격 거부 뒤에도 명령 처리·sticky 복원이 이어지는지 ② 대기 중 연결 인사가 복원/종료를 반복시키는지 ③ 센서 기록 재전송이 시작 처리와 CPU·메모리에 불필요한 부담을 주는지였다. 별도로 서비스 재사용 뒤 연결 감시와 서비스 유형을 확인했다.
- 아래 결함은 실제 서비스·리스너를 거치는 Robolectric 테스트로 재현했다. **기록된 삼성 OS CPU 종료 자체나 1시간에 두 번 종료되는 현상을 재현한 것은 아니다. 재시작 반복과 CPU 종료 사이의 인과관계, 실제 CPU 절감량은 미확인이다.**

## 변경 파일과 동작

1. `wear/src/main/kotlin/dev/kyungmin/kcoach/wear/WearCommandService.kt`
   - 운동도 미전송 기록도 없는 워치에서는 폰 연결 인사로 운동 서비스를 시작하지 않는다. 기존 heartbeat의 소유권 판정을 공유한다.
   - 세션·미확인 완료·센서 기록·수동 입력·운동 요청과 최신 chunk journal이 있으면 복원을 계속 허용한다. 연결 기능 안내 저장과 화면 갱신 방송은 유지한다.
2. `wear/src/main/kotlin/dev/kyungmin/kcoach/wear/WearWorkoutService.kt`
   - 센서 검색보다 먼저 포그라운드로 승격한다. 승격 거부 시 명령 적용/적용 ACK 없이 최신 startId로 정지하고 `START_NOT_STICKY`를 반환한다. 초기 복원 실패 시 기존 저장 상태를 덮어쓰지 않는 보호도 유지한다.
   - 대기 정지 직후 같은 인스턴스로 새 시작이 들어오면 끊겼던 폰 연결 감시를 다시 건다. 정지가 수락되면 세트 타이머도 중지한다.
   - Android 14+ 실물에서는 `health`만 명시한다. 기존 두 인자 호출은 manifest의 `health|dataSync`를 모두 사용하므로 불필요한 dataSync 제한까지 받는 경로였다. 에뮬레이터는 기존 dataSync 경로를 유지한다. 이 변경을 과거 CPU 종료의 원인 확정으로 해석하면 안 된다.
   - 센서 기록 재전송은 중복 예약을 막은 뒤, 기존의 크기가 제한된 전송 작업 큐에서 파일을 읽는다. 실물에서 사용하지 않는 Base64 전체 변환을 제거하고 에뮬레이터 변환도 전송 작업으로 옮겼다.
   - 전송 실패는 원본과 pending을 유지한다. 원본이 없는 경우에는 5초 간격의 자동 파일 재시도 루프를 만들지 않는다. 폰 ACK 뒤 정리 절차를 유지하고, 파괴된 서비스의 전송 콜백이 재시도 타이머를 살리지 않게 한다.
3. `wear/src/test/kotlin/dev/kyungmin/kcoach/wear/WatchCrashLifecycleTest.kt`
   - 새 테스트 8개: 승격 거부 시 미적용, 대기 인사 7회에도 서비스 미생성, 소유 세션 복원, 거부된 초기 복원 데이터 보존, 세션 없는 미전송 자료/journal 복원, 같은 인스턴스의 연결 감시 재개, 실물 health 유형, 파일 읽기 지연/중복 방지/누락 원본 보존 및 반복 방지.
4. 이 인계 문서.

폰·core·3D·카탈로그는 수정하지 않았다. 시작 시 저장한 diff와 현재의 wear 외 기존 tracked diff가 바이트 단위로 같음을 확인했다. 기존 미추적 자산 스크립트도 유지했다. 커밋·push·Obsidian 수정·에이전트/작업자 실행은 하지 않았다.

## 좁은 검증

| 테스트 클래스 | 결과 |
|---|---:|
| WatchCrashLifecycleTest | 8/8 |
| WearForegroundStartTest | 3/3 |
| ReconnectionTest | 14/14 |
| WatchStorageBoundaryTest | 6/6 |
| CurlCaptureTest | 1/1 |
| 합계 | **32/32** |

첫 신규 테스트 실행은 3개 중 2개 실패했고 수정 후 통과했다. 추가 경계 테스트에서는 연결 감시 누락·실물 유형·파일 읽기 시점 3개가 수정 전 실패했다. 작업 중 누락 파일의 재시도 반복도 테스트로 잡아 수정했다. 최종 8개와 위 기존 클래스들을 각각 따로 실행했다. 각 실행에 필요한 wear Kotlin 컴파일도 성공했다. 별도의 전체 빌드·전체 테스트·lint·UI 검증은 안 했다.

실행한 명령(각 클래스 개별 순차 실행, 공통 JDK·Gradle):

```sh
export JAVA_HOME=/Users/kmnoh/.local/share/android-tooling/jdk17/Contents/Home
watch_crash_gradle=/Users/kmnoh/.local/share/android-tooling/gradle-8.11.1/bin/gradle
"$watch_crash_gradle" --offline :wear:testDebugUnitTest --tests '*WatchCrashLifecycleTest' > work/watch-crash-20261111/lifecycle-final.log 2>&1
"$watch_crash_gradle" --offline :wear:testDebugUnitTest --tests '*WearForegroundStartTest' > work/watch-crash-20261111/WearForegroundStartTest.log 2>&1
"$watch_crash_gradle" --offline :wear:testDebugUnitTest --tests '*ReconnectionTest' > work/watch-crash-20261111/ReconnectionTest.log 2>&1
"$watch_crash_gradle" --offline :wear:testDebugUnitTest --tests '*WatchStorageBoundaryTest' > work/watch-crash-20261111/WatchStorageBoundaryTest.log 2>&1
"$watch_crash_gradle" --offline :wear:testDebugUnitTest --tests '*CurlCaptureTest' > work/watch-crash-20261111/CurlCaptureTest.log 2>&1
```

클래스별 XML 집계는 `work/watch-crash-20261111/test-results.json`, 실패 재현 출력은 같은 폴더의 `lifecycle-red.log`, `resource-red.log`, `missing-capture-red.log`에 있다. 기존 폰 46개 검증은 반복하지 않았다.

## 남은 Watch8 확인 — 이후 배포가 승인되면

- 새 APK의 실제 설치 버전을 확인한 뒤 1시간 이상 운동한다. 화면 꺼짐, 운동/휴식/일시정지, 폰 연결 끊김·재연결을 포함한다.
- 운동 전 대기 중에는 인사/heartbeat 때문에 복원→파괴가 반복되지 않는지 확인한다. 종료 뒤 heartbeat가 운동을 살리지 않는지도 확인한다.
- 미전송 센서 기록을 둔 채 재연결해 기록이 한 번 전달되고 폰 ACK 뒤에만 정리되는지 확인한다.
- 같은 구간의 OS 종료 이력·서비스 이벤트·CPU 자료를 함께 수집한다. 소프트웨어 테스트 통과만으로 시작 시간 초과나 CPU 과다 종료가 실물에서 해결됐다고 표시하지 않는다.

유형 선택 근거: [Android Service API](https://developer.android.com/reference/android/app/Service#startForeground(int,%20android.app.Notification,%20int)), [AOSP의 두 인자 startForeground 구현](https://android.googlesource.com/platform/frameworks/base/+/refs/heads/main/core/java/android/app/Service.java), [dataSync 시간 제한](https://developer.android.com/develop/background-work/services/fgs/timeout). 시간 제한을 CPU 과다 사용 종료와 동일한 것으로 취급하지 않는다.
