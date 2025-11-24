from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Tuple, TypedDict

from flask import Flask, jsonify, render_template, request

from utils.common import is_short_subtitle
from utils.segment_analyzer import analyze_segment

app = Flask(__name__, static_folder='static', template_folder='templates')

# 로그 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
)

DEFAULT_ENCODING = 'utf-8'


class SubtitleEntry(TypedDict, total=False):
    """SRT 자막 엔트리 구조."""

    index: int
    start_time: str
    end_time: str
    text: str


def time_to_ms(time_str: str) -> int:
    """시간 문자열(HH:MM:SS,mmm)을 밀리초(int)로 변환."""
    try:
        dt = datetime.strptime(time_str, "%H:%M:%S,%f")
    except Exception as exc:  # pragma: no cover - 방어적 코드
        logging.error("시간 형식 오류: %s - %s", time_str, exc)
        raise ValueError(f"시간 형식 오류: {time_str}") from exc
    return (
        dt.hour * 3_600_000
        + dt.minute * 60_000
        + dt.second * 1_000
        + int(dt.microsecond / 1_000)
    )


def ms_to_time(ms: int) -> str:
    """밀리초(int)를 시간 문자열(HH:MM:SS,mmm)로 변환."""
    try:
        hours, remaining = divmod(ms, 3_600_000)
        minutes, remaining = divmod(remaining, 60_000)
        seconds, milliseconds = divmod(remaining, 1_000)
    except Exception as exc:  # pragma: no cover - 방어적 코드
        logging.error("밀리초 변환 오류: %s - %s", ms, exc)
        raise ValueError(f"밀리초 변환 오류: {ms}") from exc
    return f"{hours:02}:{minutes:02}:{seconds:02},{milliseconds:03}"


def parse_srt(srt_text: str) -> List[SubtitleEntry]:
    """SRT 텍스트를 개별 자막 엔트리 목록으로 변환."""
    entries: List[SubtitleEntry] = []
    entry: SubtitleEntry = {}
    text_lines: List[str] = []

    for raw_line in srt_text.splitlines():
        line = raw_line.strip()
        if not line:
            if entry.get('text', '').strip():
                entry['text'] = '\n'.join(text_lines)
                entries.append(entry)
            entry = {}
            text_lines = []
            continue

        if 'index' not in entry and line.isdigit():
            entry['index'] = int(line)
        elif 'start_time' not in entry and '-->' in line:
            start, end = line.split('-->')
            entry['start_time'] = start.strip()
            entry['end_time'] = end.strip()
        else:
            text_lines.append(line)
            entry['text'] = '\n'.join(text_lines)

    if entry.get('text', '').strip():
        entries.append(entry)

    return entries


def merge_duplicate_entries(entries: List[SubtitleEntry], max_duplicate_gap: int) -> List[SubtitleEntry]:
    """동일 텍스트가 짧은 간격으로 반복되는 자막을 병합."""
    deduplicated_entries: List[SubtitleEntry] = []
    idx = 0

    while idx < len(entries):
        current = entries[idx]
        duplicate_count = 1
        current_end_ms = time_to_ms(current['end_time'])

        while idx + duplicate_count < len(entries):
            next_entry = entries[idx + duplicate_count]
            next_start_ms = time_to_ms(next_entry['start_time'])
            time_gap = next_start_ms - current_end_ms

            if current['text'] == next_entry['text'] and 0 <= time_gap <= max_duplicate_gap:
                current_end_ms = time_to_ms(next_entry['end_time'])
                duplicate_count += 1
            else:
                break

        if duplicate_count > 1:
            deduplicated_entries.append(
                {
                    'start_time': current['start_time'],
                    'end_time': ms_to_time(current_end_ms),
                    'text': current['text'],
                }
            )
            idx += duplicate_count
        else:
            deduplicated_entries.append(current)
            idx += 1

    return deduplicated_entries


def merge_end_start_entries(
    entries: List[SubtitleEntry],
    max_end_start_gap: int,
    enable_space_merge: bool,
    max_text_length: int,  # pylint: disable=unused-argument
    *_unused_flags: Any,
) -> List[SubtitleEntry]:
    """연속 자막의 앞/뒤 문구가 동일할 때 시간 간격 내에서 병합."""
    merged_entries: List[SubtitleEntry] = []
    idx = 0

    while idx < len(entries):
        merged_entry = entries[idx].copy()

        while idx + 1 < len(entries):
            next_entry = entries[idx + 1]
            current_end_ms = time_to_ms(merged_entry['end_time'])
            next_start_ms = time_to_ms(next_entry['start_time'])
            if next_start_ms - current_end_ms > max_end_start_gap:
                break

            current_words = merged_entry['text'].strip().split()
            next_words = next_entry['text'].strip().split()
            if not current_words or not next_words or current_words[-1] != next_words[0]:
                break

            merged_entry['end_time'] = next_entry['end_time']
            remaining_text = ' '.join(next_words[1:]) if len(next_words) > 1 else ''
            joiner = ' ' if enable_space_merge and remaining_text else ''
            merged_entry['text'] = merged_entry['text'].strip() + joiner + remaining_text
            idx += 1

        merged_entries.append(merged_entry)
        idx += 1

    return merged_entries


def _join_segment_text(current_text: str, next_text: str, enable_space_merge: bool) -> str:
    """개별 자막 텍스트를 병합할 때 사용되는 joiner."""
    left = current_text.strip()
    right = next_text.strip()
    if not left:
        return right
    if not right:
        return left
    separator = ' ' if enable_space_merge else ''
    return left + separator + right


def _safe_analyze_segment(
    text: str,
    language: str,
    enable_analyzer: bool,
):
    """형태소 분석 사용 여부에 따라 안전하게 분석을 수행합니다."""
    if not enable_analyzer:
        return None
    try:
        return analyze_segment(text, language=language)
    except Exception as exc:  # pragma: no cover - 방어적 코드
        logging.error("형태소 분석 중 오류: %s", exc)
        return None


def _compute_candidate_score(analysis) -> float:
    """completeness와 break_naturalness를 가중합으로 계산."""
    if analysis is None:
        return 0.0
    weighted = 0.7 * analysis.completeness_score + 0.3 * analysis.break_naturalness
    return round(weighted, 4)


def _can_extend_merge(
    current_text: str,
    next_entry: SubtitleEntry,
    current_end_time: str,
    options: Dict[str, Any],
) -> bool:
    """시간/길이 옵션을 만족하는지 확인."""
    max_basic_gap = options.get('maxBasicGap', 500)
    enable_min_length_merge = options.get('enableMinLengthMerge', False)
    min_text_length = options.get('minTextLength', 1)

    current_end_ms = time_to_ms(current_end_time)
    next_start_ms = time_to_ms(next_entry['start_time'])
    if next_start_ms - current_end_ms > max_basic_gap:
        return False

    if enable_min_length_merge:
        current_len = len(current_text.replace(' ', ''))
        next_len = len(next_entry['text'].strip().replace(' ', ''))
        if current_len >= min_text_length or next_len >= min_text_length:
            return False

    return True


def merge_basic_entries(entries: List[SubtitleEntry], options: Dict[str, Any]) -> List[SubtitleEntry]:
    """새 파이프라인 기반 기본 병합: 슬라이딩 창 후보 생성 → 점수 계산 → 최적 선택."""
    processed_entries: List[SubtitleEntry] = []
    idx = 0

    raw_candidate_chunk = options.get('candidateChunkSize', 3)
    try:
        candidate_chunk_size = int(raw_candidate_chunk)
    except (TypeError, ValueError):
        candidate_chunk_size = 3
    candidate_chunk_size = max(1, candidate_chunk_size)

    max_merge_count = options.get('maxMergeCount', 2)
    max_text_length = options.get('maxTextLength', 50)
    enable_space_merge = options.get('enableSpaceMerge', False)
    enable_segment_analyzer = options.get('enableSegmentAnalyzer', False)
    analyzer_language = str(options.get('segmentAnalyzerLanguage', 'en') or 'en').lower()

    logging.info(
        "병합 옵션: max_merge_count=%s, candidate_chunk_size=%s, max_text_length=%s, max_basic_gap=%s, min_text_length=%s",
        max_merge_count,
        candidate_chunk_size,
        max_text_length,
        options.get('maxBasicGap', 500),
        options.get('minTextLength', 1),
    )
    logging.info(
        "옵션 활성화 상태: basic_merge=%s, space_merge=%s, min_length_merge=%s, segment_analyzer=%s",
        options.get('enableBasicMerge', False),
        enable_space_merge,
        options.get('enableMinLengthMerge', False),
        enable_segment_analyzer,
    )

    while idx < len(entries):
        window_end = min(len(entries), idx + candidate_chunk_size)
        window_candidates: List[Dict[str, Any]] = []

        for start_idx in range(idx, window_end):
            start_entry = entries[start_idx]
            current_text = start_entry['text'].strip()
            current_end_time = start_entry['end_time']
            merge_count = 1
            current_analysis = _safe_analyze_segment(current_text, analyzer_language, enable_segment_analyzer)

            while True:
                score = _compute_candidate_score(current_analysis)
                is_complete = bool(current_analysis.is_complete_sentence) if current_analysis else False

                candidate_entry = {
                    'start_time': start_entry['start_time'],
                    'end_time': current_end_time,
                    'text': current_text,
                }
                window_candidates.append(
                    {
                        'entry': candidate_entry,
                        'merge_count': merge_count,
                        'analysis': current_analysis,
                        'score': score,
                        'is_complete': is_complete,
                        'start_idx': start_idx,
                    }
                )

                if (
                    merge_count >= max_merge_count
                    or merge_count >= candidate_chunk_size
                    or start_idx + merge_count >= window_end
                ):
                    break

                next_entry = entries[start_idx + merge_count]
                if not _can_extend_merge(current_text, next_entry, current_end_time, options):
                    break

                combined_text = _join_segment_text(current_text, next_entry['text'], enable_space_merge)
                if len(combined_text) > max_text_length:
                    break

                current_text = combined_text
                current_end_time = next_entry['end_time']
                merge_count += 1
                current_analysis = _safe_analyze_segment(current_text, analyzer_language, enable_segment_analyzer)

        if not window_candidates:
            processed_entries.append(entries[idx].copy())
            idx += 1
            continue

        formatted_candidates: List[str] = []
        for cand in window_candidates:
            cand_text = cand['entry']['text'].strip()
            if len(cand_text) > 40:
                cand_text = cand_text[:37] + "..."
            formatted_candidates.append(
                "start=%s|merge=%s|score=%.3f|complete=%s|text=%s"
                % (
                    cand['start_idx'] + 1,
                    cand['merge_count'],
                    cand['score'],
                    "Y" if cand['is_complete'] else "N",
                    cand_text,
                )
            )
        logging.info(
            "후보군 생성: window=%s-%s count=%s [%s]",
            idx + 1,
            window_end,
            len(window_candidates),
            "; ".join(formatted_candidates),
        )

        best_candidate = max(
            window_candidates,
            key=lambda cand: (
                cand['score'],
                cand['analysis'].break_naturalness if cand['analysis'] else 0.0,
                cand['merge_count'],
            ),
        )

        # 창 내에서 최고 후보보다 앞에 있는 엔트리는 단독으로 먼저 확정
        if best_candidate['start_idx'] > idx:
            for fill_idx in range(idx, best_candidate['start_idx']):
                processed_entries.append(entries[fill_idx].copy())

        processed_entries.append(best_candidate['entry'])
        idx = best_candidate['start_idx'] + best_candidate['merge_count']

    return processed_entries


def reindex_entries(entries: Iterable[SubtitleEntry]) -> None:
    """엔트리에 1부터 시작하는 index 부여."""
    for idx, entry in enumerate(entries, start=1):
        entry['index'] = idx


def generate_srt(entries: Iterable[SubtitleEntry]) -> str:
    """엔트리 목록을 SRT 문자열로 변환."""
    lines: List[str] = []
    for entry in entries:
        lines.append(str(entry['index']))
        lines.append(f"{entry['start_time']} --> {entry['end_time']}")
        lines.append(entry['text'])
        lines.append("")
    return '\n'.join(lines)


def filter_bracket_entries(entries: List[SubtitleEntry]) -> List[SubtitleEntry]:
    """대괄호로 전체가 감싸진 자막 엔트리를 제거."""
    filtered_entries: List[SubtitleEntry] = []
    removed_count = 0

    for entry in entries:
        text = entry['text'].strip()
        if text.startswith('[') and text.endswith(']'):
            removed_count += 1
            continue
        filtered_entries.append(entry)

    logging.info("대괄호 자막 필터링: %s개 제거됨", removed_count)
    return filtered_entries


def filter_by_time_range(
    entries: List[SubtitleEntry],
    start_time: Optional[str],
    end_time: Optional[str],
) -> List[SubtitleEntry]:
    """시작/종료 시간 범위에 포함되는 자막만 반환."""
    if not start_time or not end_time:
        return entries

    start_ms = time_to_ms(start_time)
    end_ms = time_to_ms(end_time)
    filtered = [
        entry
        for entry in entries
        if start_ms <= time_to_ms(entry['start_time']) <= end_ms
    ]
    return filtered


def remove_short_entries(entries: List[SubtitleEntry], options: Dict[str, Any]) -> List[SubtitleEntry]:
    """최소 지속 시간 옵션이 있는 경우, 기준 미만 자막 제거."""
    if not options.get('enableMinDurationRemove'):
        return entries

    min_duration_ms = options.get('minDurationMs', 300)
    initial_count = len(entries)
    filtered_entries = [
        entry
        for entry in entries
        if not is_short_subtitle(entry['start_time'], entry['end_time'], min_duration_ms)
    ]
    removed = initial_count - len(filtered_entries)
    logging.info("최소 자막 길이 제거: %s개 제거됨 (기준: %sms)", removed, min_duration_ms)
    return filtered_entries


def apply_merge_pipeline(entries: List[SubtitleEntry], options: Dict[str, Any]) -> List[SubtitleEntry]:
    """옵션에 따라 순차적으로 병합 단계를 수행."""
    if options.get('enableDuplicateMerge'):
        entries = merge_duplicate_entries(entries, options.get('maxDuplicateGap', 300))
        logging.info("중복 병합 후 자막 수: %s", len(entries))

    if options.get('enableEndStartMerge'):
        entries = merge_end_start_entries(
            entries,
            options.get('maxEndStartGap', 300),
            options.get('enableSpaceMerge', False),
            options.get('maxTextLength', 50),
            options.get('enableJapaneseEndingDetection', False),
        )
        logging.info("앞뒤 병합 후 자막 수: %s", len(entries))

    if options.get('enableBasicMerge'):
        entries = merge_basic_entries(entries, options)
        logging.info("기본 병합 후 자막 수: %s", len(entries))

    return entries


def process_srt(
    srt_text: str,
    options: Dict[str, Any],
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
) -> Dict[str, Any]:
    """SRT 문자열을 옵션에 맞게 병합/필터링한 결과 반환."""
    try:
        entries = parse_srt(srt_text)
        entries = filter_by_time_range(entries, start_time, end_time)
        before_count = len(entries)
        logging.info("병합 전 자막 수: %s", before_count)

        entries = filter_bracket_entries(entries)
        logging.info("대괄호 자막 필터링 후 자막 수: %s", len(entries))

        entries = remove_short_entries(entries, options)
        entries = apply_merge_pipeline(entries, options)

        after_count = len(entries)
        logging.info("병합 후 자막 수: %s", after_count)

        reindex_entries(entries)
        output = generate_srt(entries)

        return {
            'output': output,
            'beforeCount': before_count,
            'afterCount': after_count,
        }
    except Exception as exc:  # pragma: no cover - 방어적 코드
        logging.error("자막 처리 중 오류: %s", exc)
        raise ValueError(f"자막 처리 중 오류가 발생했습니다: {exc}") from exc


def _extract_options_from_form(form) -> Tuple[Dict[str, Any], Optional[str], Optional[str]]:
    """공통 옵션/시간 파라미터 파싱 helper."""
    options_json = form.get('options')
    if not options_json:
        logging.warning("옵션 데이터가 제공되지 않았습니다.")
        raise ValueError('옵션 데이터가 제공되지 않았습니다.')

    options = json.loads(options_json)
    logging.info("자막 병합 옵션: %s", options)
    return options, form.get('startTime'), form.get('endTime')


@app.route('/')
def index():
    """기본 페이지."""
    return render_template('index.html')


@app.route('/process_subtitles', methods=['POST'])
def process_subtitles():
    """업로드된 SRT 파일들을 병합 처리."""
    try:
        files = request.files.getlist('files[]')
        if not files:
            logging.warning("업로드된 파일이 없습니다.")
            return jsonify({'error': '업로드된 파일이 없습니다.'}), 400

        try:
            options, start_time, end_time = _extract_options_from_form(request.form)
        except ValueError as exc:
            return jsonify({'error': str(exc)}), 400

        processed_files = []
        for file in files:
            filename = file.filename
            if not filename:
                logging.warning("파일명이 비어있는 파일이 있습니다. 건너뜁니다.")
                continue

            srt_content = file.read().decode(DEFAULT_ENCODING, errors='ignore')
            logging.info("파일 처리 시작: %s", filename)
            result = process_srt(srt_content, options, start_time, end_time)
            logging.info("파일 처리 완료: %s", filename)

            processed_files.append(
                {
                    'content': result['output'],
                    'name': filename,
                    'beforeCount': result['beforeCount'],
                    'afterCount': result['afterCount'],
                }
            )

        return jsonify({'files': processed_files}), 200
    except Exception as exc:  # pragma: no cover - 방어적 코드
        logging.error("파일 처리 중 오류: %s", exc)
        return jsonify({'error': f"파일 처리 중 오류가 발생했습니다: {exc}"}), 500


@app.route('/process_text', methods=['POST'])
def process_text():
    """텍스트로 입력된 SRT를 병합 처리."""
    try:
        text = request.form.get('text', '')
        if not text.strip():
            logging.warning("입력된 자막 내용이 없습니다.")
            return jsonify({'error': '입력된 자막 내용이 없습니다.'}), 400

        try:
            options, start_time, end_time = _extract_options_from_form(request.form)
        except ValueError as exc:
            return jsonify({'error': str(exc)}), 400

        result = process_srt(text, options, start_time, end_time)
        logging.info("텍스트 자막 처리 완료")

        return jsonify(
            {
                'output': result['output'],
                'beforeCount': result['beforeCount'],
                'afterCount': result['afterCount'],
            }
        ), 200

    except Exception as exc:  # pragma: no cover - 방어적 코드
        logging.error("텍스트 처리 중 오류: %s", exc)
        return jsonify({'error': f"텍스트 처리 중 오류가 발생했습니다: {exc}"}), 500


if __name__ == '__main__':  # pragma: no cover - 개발 환경 실행
    app.run(debug=True, host='0.0.0.0', port=2121)
