#!/usr/bin/env python
"""
Multilingual segment analyzer (English / Japanese)

- 텍스트 조각이 완전한 문장인지 평가하고, 끊어 읽었을 때의 자연스러움도 함께 계산합니다.
- 현재는 영어(en)와 일본어(ja)를 지원합니다.

필요:
  pip install spacy
  python -m spacy download en_core_web_sm
  python -m spacy download ja_core_news_sm
"""

from __future__ import annotations

import argparse
import json
import logging
from dataclasses import dataclass, asdict
from functools import lru_cache
from typing import Dict, Iterable, List, Set

import spacy

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LanguageConfig:
    model_name: str
    sent_end_punct: Set[str]
    bad_end_pos: Set[str]
    bad_start_pos: Set[str]
    short_ok_sentences: Set[str]
    bad_end_words: Set[str]
    case_sensitive: bool = False


LANGUAGE_CONFIGS: Dict[str, LanguageConfig] = {
    "en": LanguageConfig(
        model_name="en_core_web_sm",
        sent_end_punct={".", "!", "?"},
        bad_end_pos={"ADP", "DET", "PART", "SCONJ"},
        bad_start_pos={"CCONJ", "SCONJ"},
        short_ok_sentences={
            "yes",
            "no",
            "okay",
            "ok",
            "thanks",
            "thank you",
            "sure",
        },
        bad_end_words={"to", "of", "in", "at", "for", "on", "with"},
    ),
    "ja": LanguageConfig(
        model_name="ja_core_news_sm",
        sent_end_punct={"。", "！", "？", "!", "?"},
        bad_end_pos={"ADP", "SCONJ", "PART"},
        bad_start_pos={"CCONJ", "SCONJ", "ADV"},
        short_ok_sentences={"はい", "いいえ", "了解", "了解です", "ありがとう", "ありがとうございます", "どうも", "うん"},
        bad_end_words={"は", "が", "を", "に", "へ", "で", "と", "から", "まで", "より", "や", "の", "ね", "よ", "か", "も", "って"},
        case_sensitive=True,
    ),
}

DEFAULT_LANGUAGE = "en"


@lru_cache(maxsize=None)
def _load_model(language: str):
    """spaCy 모델을 lazy하게 로드합니다."""
    config = LANGUAGE_CONFIGS[language]
    return spacy.load(config.model_name)


def _get_nlp(language: str):
    return _load_model(language)


def _normalize_language(language: str) -> str:
    if not language:
        return DEFAULT_LANGUAGE
    normalized = language.lower()
    if normalized not in LANGUAGE_CONFIGS:
        logger.warning("지원하지 않는 형태소 분석 언어(%s)가 전달되어 영어로 대체합니다.", language)
        return DEFAULT_LANGUAGE
    return normalized


@dataclass
class SegmentAnalysis:
    text: str
    language: str
    tokens: List[str]
    is_complete_sentence: bool
    completeness_score: float   # 0.0 ~ 1.0
    break_naturalness: float    # 0.0 ~ 1.0 (높을수록 '이대로 끊어도 덜 어색')
    ok_as_segment: bool         # break_naturalness 기준으로 적당한지 여부
    reasons: List[str]          # 점수에 영향을 준 이유들(디버깅용)


def _has_finite_verb(doc: Iterable, language: str) -> bool:
    """시제/인칭이 있는 동사가 있는지 (대충 '문장 같다'의 핵심 조건)."""
    if language == "ja":
        return any(token.pos_ in {"VERB", "AUX"} for token in doc)

    for token in doc:
        if token.pos_ in {"VERB", "AUX"}:
            verb_forms = token.morph.get("VerbForm")
            # VerbForm 정보가 없거나 Fin 포함이면 유한동사로 간주
            if not verb_forms or "Fin" in verb_forms:
                return True
    return False


def _has_subject(doc: Iterable, language: str) -> bool:
    """주어가 있는지 확인."""
    if language == "ja":
        for token in doc:
            if token.dep_ in {"nsubj", "nsubjpass", "csubj"}:
                return True
            if token.pos_ in {"NOUN", "PROPN", "PRON"}:
                for child in token.children:
                    if child.pos_ in {"ADP", "PART"} and child.text in {"は", "が"}:
                        return True
        return False

    for token in doc:
        if token.dep_ in {"nsubj", "nsubjpass", "csubj", "expl"}:
            return True
    return False


def _looks_imperative_en(doc) -> bool:
    """
    명령문 형태인지 대충 체크:
    - 주어(nsubj)가 없고
    - 첫 토큰이 동사(VB)일 때
    """
    if not doc:
        return False

    for token in doc:
        if token.dep_ in {"nsubj", "nsubjpass", "csubj"}:
            return False

    first = doc[0]
    if first.pos_ == "VERB" and first.tag_ == "VB":
        return True

    return False


def _looks_imperative_ja(doc) -> bool:
    if not doc:
        return False

    last = doc[-1]
    if last.pos_ in {"VERB", "AUX"}:
        verb_forms = last.morph.get("VerbForm")
        if verb_forms and "Imp" in verb_forms:
            return True
    last_text = last.lemma_ or last.text
    return last_text.endswith(("て", "で", "なさい", "ください", "ろ", "よ"))


def _looks_imperative(doc, language: str) -> bool:
    if language == "ja":
        return _looks_imperative_ja(doc)
    return _looks_imperative_en(doc)


def _has_unmatched_quotes_or_parens(text: str) -> bool:
    """따옴표/괄호가 짝이 안 맞는지 간단히 체크."""
    # 큰따옴표 짝
    double_quotes = text.count('"')
    if double_quotes % 2 == 1:
        return True

    stack = []
    pairs = {")": "(", "]": "[", "}": "{"}
    for ch in text:
        if ch in "([{":
            stack.append(ch)
        elif ch in ")]}":
            if not stack or stack[-1] != pairs[ch]:
                return True
            stack.pop()

    return bool(stack)


def _normalize_text(text: str, config: LanguageConfig) -> str:
    return text if config.case_sensitive else text.lower()


def analyze_segment(text: str, language: str = DEFAULT_LANGUAGE) -> SegmentAnalysis:
    """주어진 텍스트 조각에 대해 분석을 수행합니다."""
    stripped = text.strip()
    normalized_language = _normalize_language(language)
    config = LANGUAGE_CONFIGS[normalized_language]
    doc = _get_nlp(normalized_language)(stripped)
    tokens = [t.text for t in doc if not t.is_space]
    normalized_text = _normalize_text(stripped, config)

    reasons: List[str] = []

    if not tokens:
        return SegmentAnalysis(
            text=text,
            language=normalized_language,
            tokens=[],
            is_complete_sentence=False,
            completeness_score=0.0,
            break_naturalness=0.0,
            ok_as_segment=False,
            reasons=["empty"],
        )

    length = len(tokens)
    last_token = doc[-1]
    first_token = doc[0]

    has_finite_verb = _has_finite_verb(doc, normalized_language)
    has_subject = _has_subject(doc, normalized_language)
    looks_imperative = _looks_imperative(doc, normalized_language)

    # ---------- 1) 문장 완전성 점수 ----------
    score = 0.0

    if has_finite_verb:
        score += 0.4
        reasons.append("finite_verb")

    if has_subject or looks_imperative:
        score += 0.3
        reasons.append("subject_or_imperative")

    normalized_last = _normalize_text(last_token.text, config)
    if last_token.text in config.sent_end_punct:
        score += 0.1
        reasons.append("sentence_punctuation")

    if length >= 4:
        score += 0.1

    if any(t.dep_ == "ROOT" and t.pos_ in {"VERB", "AUX"} for t in doc):
        score += 0.1
        reasons.append("verbal_root")

    # 아주 짧아도 자연스러운 상용 표현
    if length <= 3 and normalized_text in config.short_ok_sentences:
        score = max(score, 0.8)
        reasons.append("short_but_common")

    completeness_score = max(0.0, min(1.0, score))
    is_complete = completeness_score >= 0.7

    # ---------- 2) 조각으로 끊을 때 자연스러운지 ----------
    awkward = 0.4  # 기본은 '그럭저럭'

    if not is_complete:
        awkward += 0.1  # 완전한 문장이 아니면 조금 감점

    # 끝이 전치사/관사/접속사 등이면 어색
    if last_token.pos_ in config.bad_end_pos:
        awkward += 0.3
        reasons.append(f"bad_end_pos:{last_token.pos_}")

    if normalized_last in config.bad_end_words:
        awkward += 0.2
        reasons.append(f"bad_end_word:{normalized_last}")

    # 시작이 접속사(And, But, Because...)이면 어색한 조각일 가능성
    if first_token.pos_ in config.bad_start_pos:
        awkward += 0.2
        reasons.append(f"bad_start_pos:{first_token.pos_}")

    # 너무 짧은 조각은 (예외 리스트 외에는) 어색하다고 봄
    if length <= 2 and normalized_text not in config.short_ok_sentences:
        awkward += 0.2
        reasons.append("too_short")

    # 따옴표/괄호 짝이 안 맞으면 어색
    if _has_unmatched_quotes_or_parens(stripped):
        awkward += 0.2
        reasons.append("unmatched_quotes_or_parens")

    awkward = max(0.0, min(1.0, awkward))
    break_naturalness = 1.0 - awkward  # 높을수록 자연스러운 끊김

    # 임계값은 필요에 따라 조정 가능
    ok_as_segment = break_naturalness >= 0.5

    return SegmentAnalysis(
        text=text,
        language=normalized_language,
        tokens=tokens,
        is_complete_sentence=is_complete,
        completeness_score=round(completeness_score, 3),
        break_naturalness=round(break_naturalness, 3),
        ok_as_segment=ok_as_segment,
        reasons=reasons,
    )


def main():
    parser = argparse.ArgumentParser(
        description="Analyze segments for sentence completeness and break naturalness."
    )
    parser.add_argument(
        "text",
        nargs="+",
        help="분석할 텍스트 (여러 단어를 그대로 붙여서 하나의 세그먼트로 취급합니다).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="사람이 읽기 좋은 텍스트 대신 JSON으로 출력합니다.",
    )
    parser.add_argument(
        "--language",
        choices=sorted(LANGUAGE_CONFIGS.keys()),
        default=DEFAULT_LANGUAGE,
        help="분석에 사용할 언어 코드 (기본값: en).",
    )
    args = parser.parse_args()

    # 공백으로 join 해서 하나의 세그먼트로 처리
    joined_text = " ".join(args.text)

    analysis = analyze_segment(joined_text, language=args.language)

    if args.json:
        print(json.dumps(asdict(analysis), ensure_ascii=False, indent=2))
    else:
        print(f"TEXT: {analysis.text}")
        print(f"Language: {analysis.language}")
        print(f"Tokens: {analysis.tokens}")
        print(
            f"Complete sentence: {analysis.is_complete_sentence} "
            f"(score={analysis.completeness_score})"
        )
        print(
            f"Break naturalness: {analysis.break_naturalness} "
            f"(ok_as_segment={analysis.ok_as_segment})"
        )
        print(f"Reasons: {', '.join(analysis.reasons)}")


if __name__ == "__main__":
    main()
