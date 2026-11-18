# 워치코치 홍보계정: 블렌더 릴스 키트

"장면 틀 + 포즈 + 대사 한 줄"을 JSON 한 장에 적으면 세로 1080x1920, 30fps 릴스(.blend + .mp4)가 나온다.
블렌더 5.2를 화면 없이(백그라운드로) 돌린다. 원본 design 폴더는 건드리지 않고 복사본만 쓴다.

## Windows와 macOS에서 열기

워치코치 저장소를 받은 뒤 Blender 5.2에서 `promo/scenes/scene_gym.blend`를 열면 현재 헬스장 씬을 편집할 수 있어. `scenes/reels/`에는 릴스 편집 원본이 있고, 캐릭터·포즈·사진·로고·폰트는 `promo` 안에 있어. 저장소에서 폴더 전체를 받으면 연결된 파일도 같이 따라와.

## 스크립트로 릴스 만들기

`promo` 폴더에서 실행해. Windows PowerShell에서는 `blender`가 PATH에 없으면 그 자리에 `& 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe'`처럼 설치한 Blender 실행 파일을 넣어.

```bash
# 릴스 한 편 만들기 (mp4는 renders/reels/, 편집용 .blend는 scenes/reels/)
blender -b --factory-startup -P tools/make_reel.py -- shots/test_plate_meme.json
# 빠른 확인: 4.0초 지점 한 장만, 절반 해상도
blender -b --factory-startup -P tools/make_reel.py -- shots/test_plate_meme.json --preview --still 4.0
```

새 영상은 `shots/test_plate_meme.json`을 복사해서 고치면 된다.
렌더 이미지·영상과 자동 저장 백업은 각 PC에만 남는다. `build_assets.py`로 부품을 다시 만들 때는 Blender 에셋 QA 스킬이 필요하다. 다른 위치에 설치했다면 `WATCHCOACH_BLENDER_QA`에 그 스킬의 `scripts` 폴더를 지정해.

## 샷 파일(JSON) 필드

| 필드 | 뜻 |
|---|---|
| `scene` | `flat`(단색 무배경, `bg`: yellow/mint/pink/blue/gray) 또는 `gym`(로우폴리 헬스장) |
| `camera` | 시작 카메라: `Cam_Front`(정면) / `Cam_Side`(측면) / `Cam_Low`(로우앵글) |
| `cuts` | `[{"t": 초, "camera": 이름}]` 카메라 컷 전환 |
| `seconds` | 영상 길이 |
| `interp` | **`smooth`(기본)**: 포즈 유지 후 `blend` 프레임(기본 6) 동안 스윽 전환 / `constant`: 뚝뚝 스톱모션 / `linear` |
| `hold` | 걷기·달리기 같은 반복(`seq`)에서 포즈 한 장 길이(기본 6프레임 = 초당 5장) |
| `cast` | `{"id", "kind": "hero"|"extra", "role", "at": [x,y], "face": 각도}` 주인공/엑스트라 배치 |
| `poses` | `{"who", "t", "pose"}` 또는 `{"who", "t", "seq": [...], "until"}` |
| `moves` | `{"who", "t", "dur", "from", "to"}` 캐릭터 이동 (부드러우면 등속, constant면 뚝뚝) |
| `props` | `{"kind", "at", "rot"}` 또는 `{"kind", "attach": 캐릭터id, "bone": "hand_r"}` |
| `cameos` | `{"who", "move", "t", "dur", "side", "at", "float"}` 사진판·로고판 등장 |
| `fx` | `{"type", "t", ...}` 효과 (아래 목록) |
| `lines` | `{"t", "dur", "text", "color"}` 자막(대사 한 줄). TTS 음성은 편집 단계에서 붙인다 |

좌표: 미터, 캐릭터는 원점 근처에서 정면 카메라(-Y 방향)를 본다. 캐릭터의 왼쪽이 화면 오른쪽.

## 에셋 목록

**장면 틀** (`scenes/scene_flat.blend`, `scenes/scene_gym.blend`)
- 조명(키·필·림) 각도 고정, 카메라 3종 고정. 단색 배경은 둥근 그릇 모양이라 어느 각도에서도 경계선이 안 보인다.
- 헬스장: 벽·바닥·천장 조명·거울 벽·기둥, 파워랙+바벨, 랫풀다운, 케이블 크로스오버, 벤치, 덤벨 선반(12개), 원판 트리. 기구는 워치코치 기구 빌더 복사본(`tools/vendor/`)으로 만든다.

**주인공 가이** (V5 모델, 얼굴 없음, 왼손목에 워치)
**포즈 라이브러리** (`poses/pose_library.json`, `poses/poses.blend`에 포즈 에셋으로도 저장, 시트: `renders/pose_sheet_*.png`)
- stand, hands_on_hips, triumph(의기양양), surprise(놀람), despair_kneel / despair_orz / facepalm(절망), scared(겁먹음),
  point / point_r(가리킴), fallen(쓰러짐), walk_a/b/c(걷기), run_a/b(달리기), phone_look, mirror_flex, shrug,
  check_watch(시계 보기), jump_joy, sit, sit_phone, carry_plate, sneak
- 새 포즈는 `poses/pose_spec.py`에 "팔·다리를 어느 방향으로" 식으로 적고 `tools/bake_poses.py`를 돌리면 굽혀지고 시트가 다시 렌더된다.

**엑스트라** (원조 로우폴리맨 `figure.blend` 복사본, 한 사람 한 색, 주인공과 뼈 52개·기본 자세가 같아 포즈 공유)
- red=원판 안 치우는 사람, yellow=거울 앞 폼, gray=폰만 보는 사람, blue=자리 맡고 사라진 사람, green=여분. `height`, `girth`로 체형 변주.

**조연 판** (`cast/cameos.blend`) samsung, altman, amodei(사진판, 1m), gpt, claude, gemini(로고판, 0.75m). 막대기 없이 공중에 둥둥 뜬다(`"float": false`로 끔).
- 등장 `move`: `peek`(화면 가장자리에서 스윽, 이재용) / `pass`(가로질러 지나감, 알트만) / `approach`(천천히 다가옴, 아모데이) / `pop`(톡 튀어나옴, 로고)

**효과** (`fx/fx_parts.blend`): `exclaim` `question` `sweat` `anger` `dots`(머리 위 기호), `speedlines`(집중선), `flash`(1~2프레임 단색 번쩍), `zoom`(확대 펀치), `shake`(화면 흔들림), `watch_glow`(시계 화면 발광), `watch_buzz`(시계 진동+진동선)

**소품** (`props/props.blend`): plate, phone, towel, shaker, bottle, gym_bag, wall_clock(빨리 감기 회전 `"spin"`)

## 아직 없는 에셋 (밈 소재별로 따져본 추가 목록)

| 밈 | 더 필요한 것 |
|---|---|
| 원판 안 치우고 가기 | 원판 줍는 포즈(쪼그려 들기), 원판 잔뜩 꽂힌 레그프레스(빌더 `leg_press_45` 있음, 장면에 배치만), 바닥에 흩어진 원판 묶음 프리셋 |
| 거울 앞 폼 체크 | 거울 셀카 포즈(폰 든 팔 위로), 사이드 체스트·랫 스프레드 같은 보디빌딩 포즈 2~3개, 거울 쪽을 보는 카메라 각도(뒷모습+거울 반사) |
| 세트 사이 폰 10분 | 화면에 크게 뜨는 휴식 타이머 숫자(10:00 → 23:47), 팔짱 끼고 발 구르며 기다리는 포즈(팔 뚫림 주의), 시계 화면 문구 그림(예: "휴식 끝", 횟수 숫자) |
| 자리 맡아놓고 사라진 사람 | "자리 있어요" 쪽지/종이 소품, 빈 벤치에 스포트라이트 연출, 두리번거리는 포즈, 화난 포즈(주먹 부들) |
| 공통 | 로고 대사용 말풍선 판, 효과음·BGM 모음, 캐릭터별 TTS 목소리 설정 파일, 영어 자막 줄, **운동 동작 컷**(V5 운동 파일엔 뼈대 동작이 없어서 V5 리그용 운동 동작을 따로 옮겨와야 함) |

## 파일
- `tools/wc_lib.py` 모든 부품 함수 / `tools/make_reel.py` 샷→영상 / `tools/bake_poses.py` 포즈 굽기 / `tools/build_scenes.py` 장면 틀 / `tools/build_assets.py` 에셋 파일+QA+시트
- `renders/qa/qa_report.json` 에셋 검사 결과
- `cast/src_*.blend`는 캐릭터와 워치 모델을 다시 만들 때 쓰는 원본 복사본
