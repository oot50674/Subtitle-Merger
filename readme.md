# Subtitle Merger

다중 SRT 자막을 손쉽게 병합·정리할 수 있는 Flask 기반 웹 도구입니다. 반복 구간 제거, 시간 조건 필터링, 짧은 자막 제거 등 풍부한 옵션을 UI에서 바로 조정할 수 있으며, 결과는 브라우저에서 바로 복사하거나 ZIP 형태로 내려받을 수 있습니다.

## 목차
- [프로젝트 소개](#프로젝트-소개)
- [주요 기능](#주요-기능)
- [기술 스택](#기술-스택)
- [폴더 구조](#폴더-구조)
- [설치 및 실행](#설치-및-실행)
- [Docker 실행](#docker-실행)
- [웹 UI 사용법](#웹-ui-사용법)
- [API 엔드포인트](#api-엔드포인트)
- [병합 옵션 요약](#병합-옵션-요약)

## 프로젝트 소개
- `/process_subtitles` 엔드포인트가 업로드된 SRT 파일을 병합·정리하고, 브라우저는 결과 파일을 즉시 다운로드 링크와 ZIP 묶음으로 제공합니다.
- `/process_text` 엔드포인트는 텍스트 영역에 붙여넣은 SRT를 동일한 규칙으로 가공해 줍니다.
- 모든 처리가 서버 메모리에서 이루어지므로 별도의 임시 파일 관리가 필요 없습니다.

## 주요 기능
- 멀티 파일 업로드 및 드래그&드롭 지원, 결과 ZIP 일괄 저장(JSZip + FileSaver)
- 동적 옵션(최대 병합 자막 수, 글자 수, 간격, 최소 길이 등) 실시간 제어 및 LocalStorage 복원
- 중복 자막, 이어지는 자막, 짧은 자막, 대괄호 자막 필터링 파이프라인
- 시작/종료 시간 범위 필터링(POST 파라미터로 전달) 및 결과 카운트 표시
- 결과 텍스트 즉시 복사 버튼, 처리 로그(app.log)를 통한 추적

## 기술 스택
- Backend: Python 3.11, Flask, gunicorn(배포용)
- Parsing/로직: srt, numpy, scikit-learn (고급 텍스트 처리를 위한 의존성), utils/common.py
- Frontend: jQuery, JSZip, FileSaver.js, Vanilla JS/CSS
- Tooling: run_app.bat(Windows), Dockerfile, docker-compose.yml

## 폴더 구조
```
Subtitle Merger/
├── app.py                 # Flask 엔트리포인트 및 병합 로직
├── requirements.txt       # Python 의존성
├── run_app.bat            # Windows용 빠른 실행 스크립트
├── templates/
│   └── index.html         # 단일 페이지 UI
├── static/
│   ├── style.css          # UI 스타일
│   └── script.js          # 업로드/옵션/다운로드 로직
├── utils/
│   └── common.py          # 시간 변환 및 단축 자막 판별 유틸
├── docker-compose.yml     # 로컬 컨테이너 실행 설정
├── Dockerfile             # gunicorn 기반 이미지 정의
├── logs/, debug/          # 선택적 디버깅·로그 디렉터리
└── app.log                # Flask 실행 로그(회전 필요 시 직접 관리)
```

## 설치 및 실행
### 1. 필수 요건
- Python 3.10 이상(3.11 권장)
- pip / venv

### 2. 로컬 실행 절차
```bash
git clone <repo-url>
cd Subtitle\ Merger
python -m venv .venv
.venv\Scripts\activate      # macOS/Linux: source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
python app.py               # 또는 flask run --host 0.0.0.0 --port 2121
```
- Windows 환경에서는 `run_app.bat`을 더블클릭하면 동일하게 `python app.py`가 실행됩니다.
- 기본 포트는 `2121`이며, 필요 시 `set PORT=5000` 처럼 환경변수로 재정의할 수 있습니다.

### 3. 개발 팁
- `.env` 파일에 `FLASK_ENV=development` 등을 설정하면 자동 리로드가 활성화됩니다(`python-dotenv` 이용).
- 로그를 파일로 분리하고 싶다면 `logging.basicConfig`를 조정하거나 `app.log`를 logrotate에 등록하세요.

## Docker 실행
### 단일 컨테이너
```bash
docker build -t subtitle-merger .
docker run --rm -p 2121:2121 -e PORT=2121 subtitle-merger
```
- 컨테이너는 기본적으로 `gunicorn --workers 4 --bind 0.0.0.0:${PORT:-2121}`를 실행합니다.

### docker-compose
```bash
docker compose up --build
```

## 웹 UI 사용법
1. 브라우저에서 `http://localhost:2121` 접속
2. `파일 선택` 또는 드래그&드롭으로 하나 이상의 `.srt` 업로드 (또는 상단 텍스트 박스에 붙여넣기)
3. 옵션 섹션에서 병합 조건을 조정
4. `자막 병합` 클릭 → 처리 결과 텍스트/다운로드 링크/카운트 확인
5. `결과 복사` 또는 개별 다운로드, `전체 저장(ZIP)` 버튼으로 일괄 저장

> 옵션과 입력값은 LocalStorage에 보관되어 다음 방문 시 복구됩니다.

## API 엔드포인트
| Method | Path | 설명 | 주요 파라미터 |
| --- | --- | --- | --- |
| GET | `/` | 단일 페이지 UI 렌더링 | - |
| POST | `/process_subtitles` | 멀티파트 업로드된 SRT 목록 병합 | `files[]`(다중 파일), `options`(JSON), `startTime`·`endTime`(선택, `HH:MM:SS,mmm`) |
| POST | `/process_text` | textarea 등에서 전달된 SRT 문자열 병합 | `text`, `options`, `startTime`·`endTime`(선택) |

### 요청 예시
```bash
curl -X POST http://localhost:2121/process_text ^
  -F "text=@sample.srt" ^
  -F "options={\"enableBasicMerge\": true, \"maxMergeCount\": 3}"
```

응답은 `output`(병합된 SRT), `beforeCount`, `afterCount`를 포함하는 JSON입니다.

## 병합 옵션 요약
| 옵션 키 | 설명 |
| --- | --- |
| `enableBasicMerge`, `maxMergeCount`, `maxTextLength`, `maxBasicGap` | 기본 병합 활성화, 최대 병합 개수/글자 수/간격 제한 |
| `candidateChunkSize` | 한 기준 위치에서 비교할 연속 자막 청크 크기(기본 3, 형태소 분석 옵션 그룹에 표시) |
| `enableSpaceMerge` | 문장 사이에 공백을 넣어 자연스러운 연결 |
| `enableMinLengthMerge`, `minTextLength` | 병합 대상 최소 글자 수 조건 |
| `enableDuplicateMerge`, `maxDuplicateGap` | 동일 문구가 짧은 간격으로 반복될 때 병합 |
| `enableEndStartMerge`, `maxEndStartGap` | 이전 자막 끝 단어와 다음 자막 시작 단어가 같을 때 병합 |
| `enableMinDurationRemove`, `minDurationMs` | 표시 시간이 짧은 자막 제거 |
| `enableSegmentAnalyzer`, `segmentAnalyzerLanguage` | 형태소·구문 기반 완전성 점수 계산, 사용 언어(en/ja/ko) |
| `startTime`, `endTime` | 특정 구간만 처리하고 싶을 때 사용(POST 폼 파라미터) |

모든 옵션은 `static/script.js`에서 JSON으로 직렬화되어 서버에 전송되며, 서버 측에서는 `process_srt()` 파이프라인을 통해 순차적으로 적용합니다.

### 병합 파이프라인 상세
- 후보 생성(Candidate Generator): 구간별로 S1, S1+S2, S1+S2+S3 …를 `maxMergeCount`, `candidateChunkSize`, `maxTextLength`, `maxBasicGap`, `minTextLength` 조건을 만족하는 한도에서 모두 생성합니다.
- 스코어링(Scoring Engine): 형태소·구문 분석 점수(문장 완전성 70% + 끊김 자연도 30%)로 후보를 평가합니다. 구두점(., !, ?, …)은 점수에 영향이 없습니다.
- 최적 선택(Best Candidate): 생성된 후보 중 점수가 가장 높은 1개를 선택하고, 포함된 엔트리 개수만큼 인덱스를 건너뜁니다.
