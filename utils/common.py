#!/usr/bin/env python
# -*- coding: utf-8 -*-
import re
from datetime import datetime
import logging

# 로그 설정 (app.py와 동일한 설정 사용)
logging.basicConfig(
    level=logging.INFO,  # 로그 레벨 설정 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    format='%(asctime)s [%(levelname)s] %(message)s',  # 로그 메시지 포맷
    datefmt='%Y-%m-%d %H:%M:%S'  # 날짜 형식
)

# 시간 문자열을 밀리초로 변환하는 함수
def time_to_ms(time_str):
    try:
        # 시간 문자열을 datetime 객체로 파싱
        dt = datetime.strptime(time_str, "%H:%M:%S,%f")
        # 밀리초로 변환
        total_ms = dt.hour * 3600000 + dt.minute * 60000 + dt.second * 1000 + int(dt.microsecond / 1000)
        return total_ms
    except Exception as e:
        logging.error(f"시간 형식 오류: {time_str} - {e}")
        raise ValueError(f"시간 형식 오류: {time_str}") from e

def is_short_subtitle(start_time_str, end_time_str, threshold_ms):
    """
    자막의 길이가 특정 ms 이하인지 확인합니다.

    매개변수:
      start_time_str (str): 자막 시작 시간 (HH:MM:SS,fff 형식).
      end_time_str (str): 자막 종료 시간 (HH:MM:SS,fff 형식).
      threshold_ms (int): 기준 길이 (밀리초).

    반환:
      bool: 자막 길이가 기준 길이 이하이면 True, 아니면 False.
    """
    try:
        start_ms = time_to_ms(start_time_str)
        end_ms = time_to_ms(end_time_str)
        duration_ms = end_ms - start_ms
        return duration_ms <= threshold_ms
    except ValueError as e:
        logging.error(f"시간 처리 오류: {e}")
        return False # 시간 형식 오류 발생 시 False 반환

