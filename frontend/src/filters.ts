// =====================================================================
// filters.ts: 추천 조건으로 고를 수 있는 값
// 추천 화면의 버튼과 시작 화면의 무작위 사진에서 같이 쓴다.
// =====================================================================

// 인원 (2명 ~ 6명)
export const PLAYER_OPTIONS = [2, 3, 4, 5, 6];

// 최대 플레이 시간 (단위: 분). 시작 화면의 무작위 사진 조합에서 쓴다
export const TIME_OPTIONS = [30, 60, 90, 120];

import type { TimeRange } from "./types";

// 추천 화면의 플레이 시간 구간 (단위: 분). 슬라이더의 칸 하나 = 구간 하나
// 요청에는 고른 구간의 min, max를 min_time, max_time으로 보낸다
// 마지막 칸은 상한이 없다 (max: null = 2시간 이상 전체)
export const TIME_SLOTS: TimeRange[] = [
  { min: 0, max: 30 },
  { min: 30, max: 60 },
  { min: 60, max: 90 },
  { min: 90, max: 120 },
  { min: 120, max: null },
];

// 처음 선택된 구간 (0.5 ~ 1 hr)
export const DEFAULT_TIME_SLOT = TIME_SLOTS[1];
