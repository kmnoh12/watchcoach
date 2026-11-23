# V6 이동 모션

걷기, 조깅, 대기 동작은 [Quaternius Universal Animation Library Standard](https://quaternius.com/packs/universalanimationlibrary.html)의 CC0 애니메이션을 V6 관절에 맞춰 변환했다. 각각 Walk_Loop, Jog_Fwd_Loop, Idle_Loop를 사용했다. [사용한 Standard 파일](https://github.com/J-Ponzo/gltf-universal-animation-library/tree/e24c23cf2a1323488a3faa226ea7ea21f644b73e).

계단은 [Carnegie Mellon Graphics Lab Motion Capture Database](https://mocap.cs.cmu.edu/)의 83_27 (walk forward stepping up stairs) 기록에서 4.42–6.27초를 사용했다. CMU 데이터베이스는 NSF EIA-0196217의 지원을 받았다. [사용한 BVH 변환본](https://github.com/una-dinosauria/cmu-mocap/blob/master/data/083/83_27.bvh).

v6_locomotion.json에는 V6의 관절 이름으로 변환한 로컬 회전과 골반 이동이 초 단위로 저장돼 있다. 장면 이동은 제거했고, 계단에서 발을 딛는 구간은 깊이 27.5cm, 높이 19.6cm의 발판에 맞췄다. Three.js에서는 AnimationClip.parse로 읽는다. 폰 뷰어에서 사용하려면 V6 몸에 적용해 뷰어용 프레임으로 변환해야 한다.
