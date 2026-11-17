# 05 straight_arm_pulldown — FAILED (no production change)

- 상태: **FAILED** — 범위 위반(허용 목록 밖 `tools/gen_virtual_watch_pilot.py` 수정)이 있었고, 기준선 RED는 재현됐지만 카운터팩추얼이 고치지 못했다.
- 프로덕션 변경: **없음** (CycleAxisRepDetector·ProfiledMotionRepDetector·ExerciseMotionCatalog·TrackingProfileSnapshot 무변경)
- 소스 오라클: 확립됨 (65프레임, acts 0→1, playback_range 0→1, 뷰어 핑퐁 ease, 팔 237 mm 직선, 손 고정 피팅 0.00006 mm)
- 개수 모양(기준선): 10회 진실 케이스 4개 모두 live 0 / flush 0 / missing 1..10, 중복·초과 없음. handle_down_only live 0 / flush 0.
- 개수 모양(최종): 프로덕션 무변경이므로 동일 (live 0 / flush 0)
- first_two_then_stop: false
- 조기/지연 타이밍 범위: 측정할 이벤트가 없어 없음
- 핸들다운 변화량: ten_then_handle_down rep10 이후 live 0 / flush 0, handle_down_only live 0 / flush 0
- 카운터팩추얼: 기존 return-counting 옵션을 켜는 테스트 전용 라우팅 → 역시 0/0, RED를 고치지 못함
- Gradle 호출: 1회 (`:core:test --tests ...VirtualWatchStraightArmPulldownTest --console=plain`)
- 물리 검증: Galaxy Watch8 장착·실센서 노이즈·실제 햅틱 타이밍·실사용 정확도 **UNVERIFIED**. 합성 결과는 Watch8 정확도 근거가 아니다.
- 합성 증거로 전역 임계값·노이즈 플로어·타이밍 상수를 바꾸지 않았다. 다음 운동 잠김: true
