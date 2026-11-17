# 전 세계 운동기록 앱: 운동 후 화면 레퍼런스

조사: 2026-11-01 KST. 범위: 서로 다른 앱 32개 공식 스토어·공식 문서 조사. 이 중 **18개 앱, 실제 이미지 파일 27개** (이 중 3개 앱은 세션 전체가 아닌 단일 종목 과거 세트 이력) 확보. 화면 유형별로 구분해 [오프라인 갤러리](index.html)에서 볼 수 있다. 앱을 설치하거나 로그인해 현재 동작을 검증하지 않았다. 이 문서는 설계 결정이 아니다.

## 읽기 전에

- 구글 플레이 다운로드는 해당 앱의 **누적 설치 구간**이며 국가별 설치/활성 사용자 수가 아니다. 별도 설명이 없는 리뷰 수는 스토어 표시 수치로, 지역·기기·시점에 따라 달라진다. iOS 평가는 지정한 국가 스토어의 평가 건수다. 두 수치를 직접 합산하거나 순위로 쓰지 않는다. 조회일은 모두 2026-11-01, 원본 스크린샷 촬영일과 앱 버전은 대부분 불명이다. 웹에 따라 수치가 갱신·캐시될 수 있다.
- 국가명은 **개발사 소재, 해당 국가 스토어, 혹은 명시된 서비스 대상**을 뜻한다. 그 국가에서 인기 순위가 높다는 뜻이 아니다. 특히 중국 Keep과 국제판 Keep Trainer가 동일 앱인지 확인하지 못했으므로 합치지 않았다.
- 이미지 분류: **완료 직후**, **저장된 운동/피드 상세**, **공유 결과·공유 편집**, **단계 불명 단일 운동 요약**. 광고용 기기 프레임이 붙은 스토어 이미지는 합성 홍보물로 표시했다. 정기 월간 보고서와 운동 중 기록 화면은 제외했다.
- 기재한 '미확보'는 이번 공개 자료 탐색에서 해당 화면 이미지를 확보하지 못했다는 뜻이며, 그 앱에 기능이 없다는 뜻이 아니다. 알려지지 않은 칸은 모두 **미확인**이다. 일부 영상/스크린샷 자료는 로그인 또는 유료 접근이 필요해 우회하지 않았다.

## 검토한 32개 앱과 근거

이미지 미확보 앱은 아래 공식 스토어 설명을 열어 운동 기록·규모를 확인했으나, 공개된 이미지에서 해당 화면을 명확하게 식별·확보하지 못했다. ‘상세 미확인’은 종목·세트 배열, 비교·PR, 수정·확정, 저장·공유 버튼, 화면 길이 및 단계 모두의 미확인을 뜻한다. 관련 이미지가 있는 18개 앱의 관찰은 다음 표에 따로 정리했다.

| # | 앱 | 규모 근거 / 지역 단서 | 결과 이미지와 자료 |
|---|---|---|---|
| 1 | Hevy | Play 500만+ / 스페인 등록 개발사, 영어 서비스 | **확보**. [Play](https://play.google.com/store/apps/details?id=com.hevy), [공유·기록 상세 공식 도움말](https://help.hevyapp.com/hc/en-us/articles/35688036014231-Hevy-App-Social-Guide-Connect-Follow-and-Share-Your-Workouts) |
| 2 | Strong | Play 100만+, 개발사 설명 누적 300만+ / 싱가포르 등록 | **축하 요약 이미지 확보, 진입 단계 불명**. [Play](https://play.google.com/store/apps/details?id=io.strongapp.strong), [2024 개인 사용기](https://www.lemon8-app.com/@emfosho/7420191192186864133?region=id) |
| 3 | Fitbod | Play 100만+ / 영어권 서비스 | **워치 완료 요약 확보**. [Play](https://play.google.com/store/apps/details?id=com.fitbod.fitbod), [공식 Wear OS 안내](https://help.fitbod.me/hc/en-us/sections/35305345636375-Integrations) |
| 4 | JEFIT | Play 500만+ / 영어권 서비스 | **완료·공유 이미지 확보**. [Play](https://play.google.com/store/apps/details?id=je.fit), [공개 쇼케이스](https://screensdesign.com/showcase/jefit-workout-planner-gym-log); 저장 전/공유 화면은 아래 표 참조 |
| 5 | 번핏 | Play 50만+ / 한국 개발사 | **저장 상세·공유 확보**. [Play](https://play.google.com/store/apps/details?id=com.bunnit.haja.android), [2023 개인 사용기](https://leedebutant.tistory.com/41) |
| 6 | 플랜핏 | Play 100만+ / 서울 개발사 | **2023 저장 기록 상세 확보**. [Play](https://play.google.com/store/apps/details?id=com.mih.planfit), [UI 기록](https://wwit.design/2023/07/24/planfit/) |
| 7 | 플릭 | Play 10만+ / 서울 개발사 | **단일 운동 요약 확보, 단계 불명**. [Play](https://play.google.com/store/apps/details?id=com.primero.fleekfrontend), [미국 App Store](https://apps.apple.com/us/app/fleek-workout-tracker-log/id1576993198) |
| 8 | 짐워크 | Play 10만+ / 서울 개발사 | **공유 화면 확보**. [Play](https://play.google.com/store/apps/details?id=pro.godok.gymwork), [미국 App Store](https://apps.apple.com/us/app/gymwork-workout-tracker-log/id1563624436) |
| 9 | StrengthLog | Play 10만+ / 스웨덴 등록 개발사 | **과거 완료 요약·공유 확보**. [Play](https://play.google.com/store/apps/details?id=com.styrkelabbet.Styrkelabbet), [공식 공유 문서](https://help.strengthlog.com/help-article/share-your-workout-on-social-media/) |
| 10 | Alpha Progression | Play 100만+ / 영어·독일어 서비스 | **단일 운동 요약 확보, 단계 불명**. [Play](https://play.google.com/store/apps/details?id=com.alphaprogression.alphaprogression), [미국 App Store](https://apps.apple.com/us/app/alpha-progression-gym-tracker/id1462277793) |
| 11 | GymRun | Play 100만+ / 영어 서비스. 이름이 같은 별도 앱과 구별 | 미확보. [Play: GymRun Team](https://play.google.com/store/apps/details?id=com.imperon.android.gymapp); 상세 미확인 |
| 12 | FitNotes | Play 100만+ / 영어 서비스. Android 원본과 별도 iOS 앱을 혼동하지 않음 | **단일 종목 과거 세트 확보**. [Play](https://play.google.com/store/apps/details?id=com.github.jamesgay.fitnotes), [공식 문서](https://www.fitnotesapp.com/release_1_21/); 전체 세션 완료 화면 미확보 |
| 13 | StrongLifts | Play 100만+ / 개발사는 홍콩 등록 | **2024 완료 요약 확보**. [Play](https://play.google.com/store/apps/details?id=com.stronglifts.app), [공식 문서](https://stronglifts.com/stronglifts-5x5/top-back-off-sets/) |
| 14 | Boostcamp | Play 50만+ / 영어권 서비스 | **완료 후 공유 중심 요약 확보**. [Play](https://play.google.com/store/apps/details?id=com.bpmhealth.boostcamp), [공식 사이트](https://www.boostcamp.app/) |
| 15 | Lyfta | Play 100만+ / 노르웨이 등록 개발사 | **2026 공유 결과 확보**. [Play](https://play.google.com/store/apps/details?id=com.lyfta), [사용자 게시물](https://www.lemon8-app.com/@thatneurodteacher/7633633824366133773?region=us) |
| 16 | Caliber | Play 50만+ / 미국 등록 개발사 | 미확보. [Play](https://play.google.com/store/apps/details?id=com.caliberfitness.app); 상세 미확인 |
| 17 | TrainHeroic | Play 10만+ / 영어권 서비스 | 미확보. [Play](https://play.google.com/store/apps/details?id=com.TrainHeroic.TrainHeroic); 상세 미확인 |
| 18 | FITTR | Play 100만+ / [인도 푸네 회사](https://www.fittr.com/terms-and-conditions/) | 미확보. [Play](https://play.google.com/store/apps/details?id=com.squats.fittr); 코칭·영양도 포함, 세트 결과 화면 상세 미확인 |
| 19 | MuscleWiki | Play 100만+ / 영어 서비스 | 미확보. [Play](https://play.google.com/store/apps/details?id=com.musclewiki.macro); 상세 미확인 |
| 20 | Freeletics | Play 1,000만+ / 유럽 서비스 표방 | 미확보. [Play](https://play.google.com/store/apps/details?id=com.freeletics.lite); 맨몸·코칭 중심의 보조 비교, 상세 미확인 |
| 21 | RepCount | Play 50만+ / 영어·독일어 서비스 | **단일 종목 이력 확보**. [Play](https://play.google.com/store/apps/details?id=sp.repcount), [공식 문서](https://support.repcountapp.com/article/50-what-is-included-in-repcount-premium); 전체 세션 완료 화면 미확보 |
| 22 | Liftin’ | 호주 App Store 평가 130건 / 영어 서비스 | **저장 기록 상세 확보**. [호주 App Store](https://apps.apple.com/au/app/liftin-gym-workout-tracker/id1445041669), [공식](https://liftinapp.co/) |
| 23 | Nike Training Club | [Play](https://play.google.com/store/apps/details?id=com.nike.ntc), 미국·한국·일본 등 VOD 제공 명시. **정량 인기 수치 이번 조사 미확인** | 미확보. 안내·근력 수업 및 활동 기록 중심, 세트별 결과 상세 미확인 |
| 24 | Gym WP | Play 1,000만+ / 브라질 등록 개발사 | 미확보. [Play](https://play.google.com/store/apps/details?id=com.lealApps.pedro.gymWorkoutPlan); 스토어 이미지의 28일 통계는 단일 운동 결과가 아니라서 제외 |
| 25 | Fitify | Play 1,000만+ / 유럽 개발사 표기 | 미확보. [Play](https://play.google.com/store/apps/details?id=com.fitifyworkouts.bodyweight.workoutapp); 맨몸·도구 기반 보조 비교, 상세 미확인 |
| 26 | Gym Workout Tracker (Leap) | Play 1,000만+ / 영어 서비스 | 미확보. [Play](https://play.google.com/store/apps/details?id=gymworkout.gym.gymlog.gymtrainer); 상세 미확인 |
| 27 | GymBook | 미국 App Store 평가 2,400건 / 영어·독일어·일본어 등 | **완료 요약 확보**. [미국 App Store](https://apps.apple.com/us/app/gymbook-strength-training/id650113307), [스토어 이미지 재게시](https://mwm.ai/apps/gymbook-strength-training/650113307) |
| 28 | SmartGym | 미국 App Store 평가 3.5만 건 | 미확보. [미국 App Store](https://apps.apple.com/us/app/smartgym-gym-home-workouts/id922744883); 상세 미확인 |
| 29 | HeavySet | 미국 App Store, [평가 수](https://apps.apple.com/us/app/heavyset-gym-workout-log/id1171500310)는 변동 가능해 정량 미확인 | **단일 종목 이력 확보**. [스페인 기사](https://www.xataka.com/basics/14-apps-para-disenar-tu-rutina-semanal-rastrear-tus-ejercicios-casa-gimnasio); 전체 세션 완료 화면 미확보 |
| 30 | Gravitus | 공급자 Play 설명: 수십만 사용자·1,000만 운동 기록, 검증되지 않은 자체 주장 | 미확보. [Play](https://play.google.com/store/apps/details?id=com.gravitus.app); 상세 미확인 |
| 31 | 筋トレMEMO | 일본 App Store 평가 약 5.2만 건 / 일본어 서비스 | 미확보. [일본 App Store](https://apps.apple.com/jp/app/id1109688815); 공식 설명에 기록 이미지 저장·공유가 있으나 화면 구성 미확인 |
| 32 | Keep 중국판 | [홍콩거래소 공시](https://www.hkexnews.hk/listedco/listconews/sehk/2025/0425/2025042501301.pdf): 2024년 말 누적 등록 4억+, 2024년 연간 활성 1억+ (현재 수치 아님) / 중국 중심 | 미확보. 운동·피트니스 플랫폼 전체 수치이며 근력기록 전용 앱 인기는 아님. 중국판의 이번 결과 화면 확인 불가 |

## 확보 이미지별 관찰

아래는 **이미지에서 보이는 것만** 기술한다. 눈에 안 보이는 수정/확정·공유·세트 세부 기능은 없다고 단정하지 않는다. 스크린샷 일부가 잘렸거나 긴 화면이 축소된 경우 전체 길이를 판단할 수 없다.

| 앱·종류 | 상단 요약 / 운동·세트 / 비교·PR | 수정·확정 / 저장·공유 / 길이·단계 |
|---|---|---|
| Hevy — 저장된 **피드 카드** | 시간·총 볼륨·세트 수와 종목별 세트 수가 카드에 보임. 각 세트 무게·횟수는 이 이미지에 없음. | 공유 아이콘 표시. 실제 완료 직후가 아니라 피드 카드. App Store 홍보 합성, 표본 운동 날짜 2022-08-31, 앱 버전 불명. [원본](https://is1-ssl.mzstatic.com/image/thumb/PurpleSource221/v4/98/0d/b6/980db653-f4a9-613b-826c-5c779efbbac6/46a87f62-fda1-4604-a17a-7bf89cba6be4_screenshot4.png/392x696bb.png) |
| Strong — **운동 축하 요약, 진입 단계 불명** | 완료 축하 문구, 운동 순번·시간·총 중량·PR 수, 종목별 세트 수와 Best Set 한 개. 개별 전체 세트는 안 보임. | 실사용자가 올린 이미지에 효과·워터마크가 붙어 있음. 예시 운동 2024-09-29, 당시 버전 불명. 단독 화면 캡처인지 공유 출력인지 불명. [개인 사용기](https://www.lemon8-app.com/@emfosho/7420191192186864133?region=id), [원본](https://www.lemon8-app.com/seo/image?item_id=7420191192186864133&index=2&sign=223ce7575db83bdb7c1556752d0617b2) |
| Fitbod — **Wear OS 완료 직후** 2장 | 완료 문구, 종목 수, 총 볼륨, 칼로리. 두 장은 같은 화면을 나누어 보여 줌. 종목·세트 상세와 PR은 보이지 않음. | 공식 설명상 종료 → 기록/계속 선택 → 요약 → 다음 운동. 끝부분에 Next workout. 휴대폰 화면이 아님. 캡처 버전·시점 불명. [원본 상단](https://help.fitbod.me/hc/article_attachments/4407117002775), [하단](https://help.fitbod.me/hc/article_attachments/4407117003031), [원문](https://help.fitbod.me/hc/en-us/sections/35305345636375-Integrations) |
| 번핏 — **저장된 기록 상세** | 78분·총 볼륨 등 상단 지표 다음 운동명·종목 볼륨·세트별 kg/회. 세트 하나씩 한 줄로 펼침. | 캘린더에서 지난 기록을 선택한 화면. 아래쪽 전체 길이와 수정 여부는 화면 일부라 불명. 2023년 개인 사용기, 현재 버전 불명. [원문](https://leedebutant.tistory.com/41), [원본](https://blog.kakaocdn.net/dna/b3jHHk/btrVE1Wplvs/AAAAAAAAAAAAAAAAAAAAAAFaf2v1P_hicEXAbe0eKZk0Mup3r2ckNiAgag9gwaBK/img.jpg?credential=yqXZFxpELC7KVnFOS48ylbz2pIh7yKj8&expires=1796050799&allow_ip=&allow_referer=&signature=3H7PGg1eRZpWOsmfvcFjqO3Ze2M%3D) |
| 번핏 — **공유 편집·공유 결과** | 시간·운동 수·총 볼륨, 운동명과 각 종목의 세트 수×횟수. 위 상세의 개별 kg/회 표시와는 다름. | 편집 화면에 다음 버튼과 스타일 선택, 결과 이미지 별도. 2023년 사용기. [편집 원본](https://blog.kakaocdn.net/dna/cWEkto/btrVE1oykp4/AAAAAAAAAAAAAAAAAAAAANuDCzt2n-cErSdmwY9WA_Fg7W3PfiZ6Vo2-la6IjALP/img.png?credential=yqXZFxpELC7KVnFOS48ylbz2pIh7yKj8&expires=1796050799&allow_ip=&allow_referer=&signature=XzrT6krtsnf%2F24EfDs4eZyrAiAY%3D), [완성 원본](https://blog.kakaocdn.net/dna/dlKARs/btrVALUAiyw/AAAAAAAAAAAAAAAAAAAAAOkE-QhP7uLxh5qq-seVovNCHy1WBbC6ZsifTzrmB8vi/img.png?credential=yqXZFxpELC7KVnFOS48ylbz2pIh7yKj8&expires=1796050799&allow_ip=&allow_referer=&signature=8lDrkUbRs4pr1GeXAMxYz2lEGuo%3D). 서명 URL은 만료될 수 있음. |
| 플릭 — **단일 운동 요약, 진입 단계 불명** | 근육 그림, 운동 순번·칼로리·시간·볼륨, 종목·세트·반복 수와 강도. 종목별 무게와 횟수가 원형으로 배열됨. | 뒤로·더보기 아이콘. 상하 일부 잘린 App Store 홍보 합성. 실제 완료 직후인지 저장 상세인지 불명. 예시 날짜 2023-12-25, 버전 불명. [원본](https://is1-ssl.mzstatic.com/image/thumb/PurpleSource126/v4/ac/b2/bc/acb2bc93-a064-ccd0-b4f0-3cca88da0d08/b17cbf3b-7c00-4381-9752-5e0172c4d7ef_1242_2208_6_en.jpg/392x696bb.jpg) |
| 짐워크 — **공유 결과 선택** | 운동 순번·총 볼륨·칼로리, 종목명과 kg·횟수, 추정 1RM·상위 비율 표기. | Instagram·이미지·텍스트 복사·공유 선택지가 함께 보이는 스토어 홍보 합성. 캡처 날짜/버전 불명, 표본 날짜 2025-02-09. 완료 직후인지 지난 기록 진입인지 불명. [원본](https://is1-ssl.mzstatic.com/image/thumb/PurpleSource211/v4/80/6e/28/806e2852-209b-89cd-5ad5-04e155c15952/A_US_07.jpg/320x480bb.jpg) |
| StrengthLog — **완료 후 요약 일부, 2023** | 공식 기사에서 저장 직후 요약이라고 설명. 운동명·시간·칼로리·근육 그림이 보이는 상단 크롭. 세트·PR은 이 이미지에서 미확인. | 2023년 예시이므로 현재 화면으로 취급하지 않음. [공식 기사](https://www.strengthlog.com/new-features-in-the-best-free-workout-tracker-app/), [원본](https://www.strengthlog.com/wp-content/uploads/2023/04/kcal-workout-summary.jpg) |
| StrengthLog — **공유 편집·전체 이미지** | 요약은 통계·배경·형식 선택, 전체 기록 이미지는 길게 이어지는 별도 출력. 축소된 전체 샘플의 개별 글자는 판독 곤란. | 공식 문서 기준 지난 기록 → 더보기 → 이미지 선택 또는 전체 운동 이미지 저장. Share / Save 버튼 표시. 문서 업데이트 2025-07-28, 이미지 경로 2022, 현재 버전 불명. [편집 상단](https://help.strengthlog.com/wp-content/uploads/2022/09/sharing.jpg), [편집 하단](https://help.strengthlog.com/wp-content/uploads/2022/09/sharing2.jpg), [전체 기록](https://help.strengthlog.com/wp-content/uploads/2022/09/sharing3.jpg) |
| Alpha Progression — **단일 운동 요약, 진입 단계 불명** | 시간·스트릭, 5개 운동의 순서와 세트 수·별 표시, 아래 근육별 목록. 어떤 기준의 별인지 이미지만으로 불명. | Close·Share 표시. 한 장에 다 안 들어가는 스토어 홍보 합성. 공식 Play 설명은 매 운동 후 PR·마일스톤 목록을 명시하지만, 이 이미지가 그 완료 단계인지 불명. [원본](https://is1-ssl.mzstatic.com/image/thumb/PurpleSource221/v4/34/92/c0/3492c050-cadc-5a10-aaa4-b5ea9ec39c8b/6.9-en-5.png/320x480bb.jpg) |
| Boostcamp — **완료 후 공유 중심 요약** | ‘You crushed it’, 신규 기록 수, 운동 이름·날짜, 근육 맵·부위별 세트. 각 종목 중량·횟수는 이 화면에 보이지 않음. | Done과 Instagram·Facebook·이미지·텍스트 공유 선택이 한 화면에 보임. 공식 홈페이지의 화면 예시라 촬영 시점·버전 불명, 홍보 맥락. [원문](https://www.boostcamp.app/), [원본](https://www.boostcamp.app/_next/static/media/hiw-step3-track-progress.83c677c6.png) |

## 후속 심화 조사 — 공개 실사용·기록 화면

추가 조사로 9개 앱을 새로 확보했고, 기존에 있던 Hevy·Fitbod의 다른 유형도 추가했다. 다음 12장은 모두 실제 파일을 열어 확인했으며 촬영 버전·현재 UI는 검증하지 않았다. 특히 **FitNotes·RepCount·HeavySet은 세션 전체 요약이 아니라 한 종목의 과거 세트 이력**이다. 18개 앱 집계에 포함하되 15개 앱의 세션 수준 화면과 섞어 해석하면 안 된다.

| 화면 / 파일 | 화면에서 확인한 구성과 제한 | 출처 및 이미지 원본 |
|---|---|---|
| JEFIT **완료 직후 저장 전** `jefit-before-save.webp` | Workout Complete, 시간·볼륨·신기록 수·RPE·근육 그림, 종목 수 및 저장 버튼. 전체 세트는 아래로 내려가야 하는지 미확인. | [공개 쇼케이스](https://screensdesign.com/showcase/jefit-workout-planner-gym-log), [원본](https://media.screensdesign.com/avs-pp-640/2f4c55bcaa314fb09282cdedcec9051e.webp). 실기기 시험 절차를 보여주는 서드파티 캡처, 날짜·버전 불명. |
| JEFIT **저장 후 공유 선택** `jefit-share.webp` | 들었던 총량을 코끼리에 비교하는 카드, 시간·종목 수·기록 수와 Share / Done. 원문의 같은 실행 흐름 화면이며 실제로 스와이프했는지 확인하지 않음. | [원문](https://screensdesign.com/showcase/jefit-workout-planner-gym-log), [원본](https://media.screensdesign.com/avs-pp-640/f7bd2a54a32c4977809167b4fa187445.webp). 날짜·버전 불명. |
| Lyfta **공유 결과물** `lyfta-share-user-2026.jpg` | 총 볼륨·시간, 종목 이름·세트 수와 신체 그림. 개별 세트별 무게·반복은 없음. | [공개 사용자 글](https://www.lemon8-app.com/@thatneurodteacher/7633633824366133773?region=us), [원본 이미지](https://www.lemon8-app.com/seo/image?item_id=7633633824366133773&index=0&sign=1bec397e942a9feb7b052aa5953ea438). 운동 날짜 2026-04-27; 현재 버전 불명. |
| Fitbod **폰 공유 결과물** `fitbod-share-user-2024.jpg` | 운동일·시간·근육, 칼로리·볼륨·기록·거리와 종목 목록. 개별 세트 상세 없음. 앞서 확보한 워치 완료 화면과 다른 유형이다. | [사용자 글](https://www.lemon8-app.com/@hostrike/7383868947214680581?region=us), [원본](https://www.lemon8-app.com/seo/image?item_id=7383868947214680581&index=0&sign=07c8db326baa1306797bca0cd3abd3e3). 2024-06-20 운동, 게시 6월 24일. |
| 플랜핏 **저장 기록 상세** `planfit-history-2023.webp` | 날짜·시간·칼로리, 종목명/세트 수 상단과 아래 종목별 kg×회. 같은 종목의 세트를 가로로 나열. 더보기 표시, 수정 기능은 이미지로 미확인. | [2023 UI 아카이브](https://wwit.design/2023/07/24/planfit/), [원본](https://wwit.design/images/posts/planfit/03_workout/planfit_workout_22.webp). 예시 날짜 2023-06-26, 현행 불명. |
| FitNotes **단일 종목 이력** `fitnotes-exercise-history-2019.png` | 한 운동의 날짜별 세트 kg×회와 특정 날짜 통계(총 세트·반복·볼륨·추정 1RM), View Workout / Edit Sets / Copy Sets. | [공식 1.21 문서](https://www.fitnotesapp.com/release_1_21/), [원본](https://www.fitnotesapp.com/images/change_log/1_21_0/Exercise_History_Workout_Statistics.png). 2019 예시, 전체 운동 결과 아님. |
| GymBook **완료 화면** `gymbook-complete.jpg` | 완료 순번·지난번과 경과일, 이번/직전 소요시간 비교·세트 수, 공유 아이콘. 이미지 아래가 잘려 전체 길이는 불명. | [스토어 스크린샷 재게시](https://mwm.ai/apps/gymbook-strength-training/650113307), [원본 Apple 이미지](https://is1-ssl.mzstatic.com/image/thumb/Purple126/v4/37/05/b0/3705b09f-cdd0-abb6-aa03-e8ffb60af12e/55d3135f-6fcf-465f-a9bc-c828cc10ea2e_en_5.5_7d.png/750x750bb.jpeg). 예시 데이터·버전 불명. |
| Liftin’ **저장 기록 상세** `liftin-history.webp` | 왼쪽 화면: 운동 시간·종목 수·볼륨과 종목별 세트 기록. 오른쪽은 별도 개인기록/달력 화면이며 같은 세션의 결과 전체가 아님. | [공식 사이트](https://liftinapp.co/), [원본](https://images.squarespace-cdn.com/content/v1/6423069b11b9e1546dbfbfef/1c6a85b2-dc1a-4866-b5ff-94cdca4b570e/progrD.png?format=1500w). 2025 예시가 들어간 홍보 합성, 버전 불명. |
| StrongLifts **완료 요약** `stronglifts-complete-2024.png` | 오른쪽: 50회차, 시간·볼륨·신기록 수, 종목별 최고 세트와 각 반복 수, 공유 버튼. 왼쪽은 완료 전 기록 화면이므로 분리. | [공식 2024 문서](https://stronglifts.com/stronglifts-5x5/top-back-off-sets/), [원본](https://stronglifts.com/wp-content/uploads/top-back-off-set-time-saved.png). 현재 버전 불명. |
| RepCount **단일 종목 이력** `repcount-exercise-history-2021.png` | 날짜별 세트 중량×회·1RM·볼륨을 한 줄씩 표시. 종목명은 이미지에 보이지 않으며 세션 전체 요약이 아님. | [공식 도움말](https://support.repcountapp.com/article/50-what-is-included-in-repcount-premium), [원본](https://d33v4339jhl8k0.cloudfront.net/docs/assets/5da389ee04286364bc9055a1/images/60578401207e3b1188e1e5d7/file-aExpl8iaAA.png). 2021 예시·버전 불명. |
| HeavySet **단일 종목 이력** `heavyset-exercise-history-2023.jpg` | 오른쪽에 스쿼트 날짜별 중량×회·메모·기록 별 표시. 가운데는 루틴, 왼쪽은 운동 중 화면이라 결과로 보지 않음. | [스페인어 매체 2023-03-05](https://www.xataka.com/basics/14-apps-para-disenar-tu-rutina-semanal-rastrear-tus-ejercicios-casa-gimnasio), [원본](https://i.blogs.es/791ba5/hset/1366_2000.jpeg). 2018 예시를 포함한 홍보 합성. |
| Hevy **단일 종목 이력** `hevy-exercise-history.png` | 오른쪽에 날짜별 힙스러스트의 준비운동·세트별 무게×회. 왼쪽 그래프는 별도 종목 요약. 전체 세션 화면이 아님. | [공식 도움말](https://help.hevyapp.com/hc/en-us/articles/35382889578135-Exercise-Performance-Tracking-in-Library-Weight-Bodyweight-Cardio-and-Duration-Based-Exercises), [원본](https://help.hevyapp.com/hc/article_attachments/35554887903639). 예시 2025-10-08, 버전 불명. |

### 추가 탐색했으나 세션 전체 결과 이미지가 없는 앱

- **GymRun**: `GymRun workout history sets screenshot`, `GymRun training summary` 등과 [Play 등록](https://play.google.com/store/apps/details?id=com.imperon.android.gymapp)을 확인. 찾은 이미지가 운동 입력·기록 목록·신체 통계라 완료/단일 세션 상세로 확인할 수 없었다.
- **Caliber**: `Caliber workout summary screenshot` 및 [공식 5.12 발표](https://feedback.caliberstrong.com/announcements/caliber-5120-realtime-prs-new-workout-summary-screen-various-bug-fixes)를 확인. 공식 글은 완료 후 결과와 각 PR 공유 카드를 설명하지만 일치하는 이미지 미확보. 검색 이미지 한 건은 다른 앱 Future로 식별되어 제외했다.
- **SmartGym**: `SmartGym workout summary screenshots review` 및 [공식 버전 안내](https://smartgymapp.com/releases/smartgym-8)를 확인. 공개 이미지 중 Workout Summary는 주간·월간 집계라 개별 운동 결과에서 제외; 앱 결과 화면 라이브러리는 잠겨 있었다.
- **TrainHeroic·FITTR·MuscleWiki·Freeletics·Nike Training Club·Gym WP·Fitify·Leap Gym Workout Tracker·Gravitus·筋トレMEMO·Keep 중국판**: 앞 표의 공식 스토어 또는 공시와 각 앱명·workout summary/history 검색에서 식별 가능한 단일 세션 결과 이미지는 아직 확보하지 못했다. 이것은 해당 앱에 기능이 없다는 뜻이 아니다.
- 플랜핏 사용자 게시물의 추가 사진은 접근 제한(403/429)으로 확보하지 않았다. JEFIT의 별도 2023 리뷰는 현재 이미지 서버가 중단됐고, 잠긴 화면은 우회하지 않았다. 대신 공개 쇼케이스와 UI 아카이브 자료를 위에 수록했다.

## 관찰에서 나오는 워치짐 적용 후보 — 결정 아님

1. **짧은 요약과 실제 수행 내역을 함께 검토:** Hevy 피드와 번핏 공유 카드는 요약 위주이고, 번핏 상세는 세트별 kg·횟수를 보여 준다. 결과를 개인이 되돌아볼 때와 공유할 때 필요한 상세 수준은 같다고 가정할 수 없다.
2. **공유의 목적에 따라 요약과 전체 수행을 구분:** StrengthLog는 두 가지 출력을 명시적으로 나눈다. 짐워크와 Boostcamp 사례에서는 이미지와 텍스트 공유 선택지가 보인다. 이 조사가 사용자의 선호 비율을 입증하는 것은 아니다.
3. **성과를 짧게 보여주되 세트 사실과 구분:** Boostcamp는 PR 수, Alpha는 별과 세트 수를 띄운다. PR 계산 방식과 비교 조건은 앱별로 다를 수 있어 같은 의미로 취급하지 않는다.
4. **완료·저장·공유 단계를 따로 판단:** Fitbod 워치의 완료 확인 후 요약과 StrengthLog의 저장된 기록에서 여는 공유 설정은 서로 다른 상황이다. 워치짐의 추정 세트 확인 경로는 이 조사와 별도로 유지해야 한다.
5. **긴 화면인지 탭이 많은지 단정하지 않기:** 현재 이미지 다수는 부분 캡처·홍보 합성이라 전체 스크롤·단계 수, 수정 가능성, 현재 버전을 파악할 수 없다. 특히 Fitbod와 StrengthLog의 옛 워치/요약 예시는 실제 최신 동작 확인이 필요하다.
