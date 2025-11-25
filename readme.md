# 🎬 Subtitle Merger

<img width="1652" height="1112" alt="image" src="https://github.com/user-attachments/assets/a20d0c9e-e2e0-481d-9c17-d411228ffaa9" />


**Subtitle Merger**는 단순히 두 개의 자막 파일을 합치는 것을 넘어, **NLP(자연어 처리) 기반의 문장 분석**을 통해 파편화된 자막 라인을 읽기 편한 문장 단위로 재구성해주는 웹 기반 도구입니다.

영화나 드라마 자막이 지나치게 짧은 단위로 끊어져 있어 가독성이 떨어지거나, OCR 과정에서 발생한 중복 라인을 정리하고 싶을 때 최적의 솔루션을 제공합니다.

---

## 🛠 Key Features (주요 기능 및 로직)

이 프로젝트는 Python(Flask) 백엔드 위에서 동작하며, 다음과 같은 알고리즘을 통해 자막 품질을 개선합니다.

### 1. NLP 기반 지능형 병합 (Smart Segment Analysis)
단순히 시간 간격만으로 병합하는 기존 방식과 달리, **`spaCy` 및 `Stanza` 라이브러리**를 활용하여 문장의 문법적 완성도를 평가합니다.
* **지원 언어:** 한국어(Ko), 영어(En), 일본어(Ja)
* **작동 원리:**
    * **Completeness Score:** 현재 라인이 문장 종결 어미(다/요, Period 등)나 유한 동사로 끝나는지 분석합니다.
    * **Naturalness Check:** 문장을 합쳤을 때 주어-동사 호응이나 문법적 연결이 자연스러운지 평가하여, 무리한 병합으로 인한 가독성 저하를 방지합니다.

### 2. 슬라이딩 윈도우(Sliding Window) 병합 최적화
* `merge_basic_entries` 파이프라인은 슬라이딩 윈도우 알고리즘을 사용하여 인접한 자막 후보군(Chunk)을 탐색합니다.
* 각 병합 후보(Candidate)에 대해 점수(Score)를 매기고, 가장 높은 점수를 가진 조합을 최적의 자막 라인으로 선택합니다.

### 3. 중복 및 노이즈 제거 (Deduplication & Filtering)
* **Duplicate Merge:** 짧은 시간 차이로 동일한 텍스트가 반복되는 경우(예: 깜빡임 오류) 이를 하나로 병합합니다.
* **End-Start Merge:** 앞 자막의 끝부분과 뒤 자막의 시작 부분이 겹치는 OCR 오류 패턴을 감지하여 이어 붙입니다.
* **Glitches Removal:** 지정된 시간(예: 300ms) 미만의 의미 없는 짧은 자막을 필터링합니다.

---

## 🚀 Installation & Usage

이 프로젝트는 **Docker** 환경을 권장하지만, 로컬 Python 환경에서도 구동 가능합니다.

### Option 1: Docker (Recommended)
환경 설정 번거로움 없이 컨테이너 기반으로 즉시 실행합니다.

```bash
# Repository Clone
git clone [https://github.com/oot50674/subtitle-merger.git](https://github.com/oot50674/subtitle-merger.git)
cd subtitle-merger

# Build & Run
docker-compose up -d --build
