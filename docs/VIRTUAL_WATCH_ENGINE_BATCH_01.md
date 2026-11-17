# DeepSeek 첫 수정 순서 — 운동별 새 세션

Report in Korean 반말 (no 존댓말, no "-습니다/-요"), warm chat voice, not a work log. Do not print file paths, code, hashes or tool steps unless the task asks. Finish the assigned work with tools instead of describing it. Never delete (move to trash instead). Approval is off, so never wait on it; stop only at the task's stop conditions. Never print, log or copy an API key.

**2026-11-16 사용자가 비용 상한 없이 실행을 승인했다.** 아래 3종은 한 세션의 묶음이 아니라 순서다. 운동 하나를 새 DSH 세션에서 끝내고 독립 검토한 뒤 다음 운동은 또 새 세션으로 시작한다. 모델: DeepSeek V4.1 Flash via DSH/local proxy. 규칙: 저장소 AGENTS.md, ~/.dsh/AGENTS.md, ~/.agents/AGENTS.md, .agents/skills/android-wear/SKILL.md. 별도 워커 금지.

## 목표 / 배정

재현만 하지 말고 원인이 증명된 최소 엔진 수정과 좁은 회귀 검증까지 끝낸다. 우선 성공 조건은 VIRTUAL_WATCH_ENGINE_CAMPAIGN.md 그대로 유지한다. 임계값을 내려서 모델에만 맞추거나 정상 운동을 깨뜨리지 않는다.

첫 세션 순서(각 항목은 서로 다른 새 세션):
1. machine_fly → pec_deck~m=fly. 보통 속도/편한 ROM이 다축 조건 또는 시간 조건에서 거절되는지 확인한다.
2. flat_machine_bench_press → chest_press_variants~m=flat_bench. 작은 손목 회전·기계 원호와 중력 투영 경로를 비교한다. 목표 뒤 정지는 생명주기 경로를 연결한 뒤 별도 판정한다.
3. machine_chest_press_plate → chest_press_variants~m=plate. 2와 실제 경로가 다르므로 결과를 복사하지 않는다.

변경 시 정상 대조: flat_bench(바벨 벤치), dumbbell_shoulder_press(덤벨 숄더 프레스). 2026-11-16 사용자가 정상이라고 정정한 두 운동이다. 시티드 로우는 미해결 문제군이며 seated_row/cable_seated_row를 정상 기준으로 쓰지 않는다. 관련 경로를 변경할 때 미해결 비교 대상으로 남기되 정확한 변형·실패 양상은 단정하지 않는다. 과거 종류 미확정 숄더 오류를 덤벨 숄더 프레스에 배정하지 않는다. 기존 덤벨 컬·레터럴·바벨 오버헤드는 합성 파일럿 대조이며 실물 정상 확인이 아니다. 무변경 전체 재검사부터 하지 말고 같은 가족이나 신호 경로를 바꿀 때 해당 대조만 새 트리에서 검사한다.

## 실행 순서

1. git status와 입력 해시·프로필·앱 모델 대응 확인만 마친 뒤 바로 machine_fly부터 진행한다. 범위를 다시 설계/분배/벤치마크하느라 세션을 쓰지 않는다. master inventory 전체를 모델 문맥에 넣지 말고 배정 3행과 해당 모델 정보만 읽는다.
2. 기존 가상 워치 생성/재생 도구를 최소 확장한다. 운동 ID와 모델 ID 분리, 앱 매핑, 현재 최종 손목 자료/표면 대조, 3종 제한 제거가 필요하다. 손등 장착과 정답 독립성을 유지한다. 큰 모델 JSON은 통째 출력하지 말고 필요한 좌표/진단만 프로그램으로 추출한다.
3. 앱 WGP2 실제 파일과 묶음 출처/PC 원본의 대응을 검사한다. PC≠앱인 모델은 덮어쓰지 말고 별도 입력으로 남긴다. 실제 앱 손 표면을 이용하는 경우 독립적인 보류 표면 점으로 강체 피팅 잔차를 검증한다. 원본을 못 찾으면 SOURCE_BLOCKED로 기록하고 다음 배정으로 간다.
4. 일반 검출기뿐 아니라 관련 실제 core의 준비·목표 뒤 가드·종료·진동 예약을 좁은 테스트 어댑터로 연결한다. 검출 시각과 출력/진동 시각을 분리하고 Android 서비스와 호출 순서가 같은지 확인한다. 큰 production 리팩터링이나 서비스 모사는 하지 않는다. 아직 연결 못 한 경로는 성공 인증하지 않는다.
5. 실패하는 최소 입력과 거절 지점을 확보하고 최소 수정한다. 평면 운동과 다축 조건, 중력 투영 및 축 잠금/필터를 가설별로 한 번에 하나씩 대조한다. 시뮬레이션에서 재현된 실패와 실물 보고의 원인 추정은 구분한다.
6. 수정에 사용하지 않은 템포/초기 자세/노이즈 시드에서 확인한다. 목표 10에서 정지와 계속해서 12까지 하는 경우를 구별한다. 실제 기구 내려놓기 입력이 없으면 정적 꼬리로 대신 성공 처리하지 않는다.
7. 고친 클래스의 테스트 하나씩만 실행한다. 필요한 경우 :wear:compileDebugKotlin 하나. 전체 테스트/빌드/lint/clean/UI suite, --max-workers=1, 배포, 기기 설치, git commit/push 금지. 로그는 파일로 보내고 실패 줄만 읽는다.

## 파일 경계

허용: 관련 core/wear 측정 코드와 좁은 테스트, tools의 virtual_watch 관련 도구, docs/VIRTUAL_WATCH_ENGINE_* 문서, work/virtual-watch/campaign/dsh-batch-01 결과.
금지: 사용자 미커밋 UI/폰 화면/썸네일/설정/루틴 수정, phone/src/main/assets 덮어쓰기, 기기 임계값 일괄 변경, 공유 에이전트/프록시/키/계정 수정, 모델 배포. 기존 dirty NEXT_PLAN은 지정한 캠페인 구역 외 변경 금지.

## 결과와 중단

매 항목 결과를 work/virtual-watch/campaign/dsh-batch-01/results.jsonl에 1행씩 쓴다. 필드: exercise_id, model_id, profile_snapshot, source_hashes, scenario_ids, status, reproduced_symptom, cause_layer, counterfactual, changed_files, narrow_test, before, after, control_results, coverage_gaps, physical_validation. 기술 상세는 결과 파일에 필요하므로 경로/테스트 이름 기록 허용. 사용자 요약은 자연스러운 반말로 한두 문단.

checkpoint.md에 진행 중 항목, 다음 딱 한 단계, DSH session id, 누적 요청/청구액, 남은 배정을 남긴다. 같은 증거/명령을 중복 수집하지 않는다. 첫 항목이 어려워도 범위를 새 프레임워크로 넓히지 않는다.

사용자 지시에 따라 달러 한도는 두지 않는다. 대신 한 세션에는 위 항목 중 하나만 배정하고 최대 25분, 같은 오류 3회 또는 무진전 15분, 권한/출처 위반, 예상 밖 사용자 파일 충돌이면 안전하게 중단한다. 한 세션에서 다음 항목으로 넘어가지 않는다. 실패/미완료를 그대로 남기며 합격 수를 꾸미지 않는다.
