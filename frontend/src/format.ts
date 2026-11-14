// =====================================================================
// format.ts: 숫자나 글자를 화면에 보여주기 좋게 바꾸는 도우미 함수 모음
// =====================================================================

import type { GameDetail } from "./types";

// 분 단위 숫자를 읽기 쉬운 글자로 바꿔주는 함수
// 예) 30 -> "30 min", 60 -> "1 hr", 90 -> "1.5 hr"
export function formatMinutes(min: number): string {
  if (min < 60) return `${min} min`;
  const hours = min / 60;
  return `${Number.isInteger(hours) ? hours : hours.toFixed(1)} hr`;
}

// 게임의 플레이 시간 글자 만들기
// 실제 데이터의 누락·잘못된 시간 범위는 숫자 대신 안내
// 최소·최대가 같으면 "30 min", 다르면 "30–45 min"
export function formatPlaytime(game: Pick<GameDetail, "ComMinPlaytime" | "ComMaxPlaytime">): string {
  const min = game.ComMinPlaytime;
  const max = game.ComMaxPlaytime;
  if (!(min > 0 && max >= min)) return "Time unknown";
  return min === max ? `${max} min` : `${min}–${max} min`;
}

// 인원 범위 글자 만들기. 예) "2–4", 같으면 "2" (정보가 없으면 null)
export function formatPlayerRange(game: Pick<GameDetail, "MinPlayers" | "MaxPlayers">): string | null {
  const { MinPlayers: min, MaxPlayers: max } = game;
  if (!(min > 0 && max >= min)) return null;
  return min === max ? `${min}` : `${min}–${max}`;
}

// 인원 글자 만들기. 예) "2–4 players", "1 player"
export function formatPlayers(game: Pick<GameDetail, "MinPlayers" | "MaxPlayers">): string {
  const range = formatPlayerRange(game);
  if (range == null) return "Players unknown";
  return range === "1" ? "1 player" : `${range} players`;
}

// 난이도·평점 숫자를 소수점 한 자리로. 예) 1.79 -> "1.8", 값이 없으면 "0.0"
export function formatScore(value: number | null | undefined): string {
  return (value ?? 0).toFixed(1);
}

// 게임 설명에 들어 있는 &quot; &#10; 같은 HTML 엔티티를 원래 글자로 바꾸는 함수
// DOMParser는 글자를 해석만 하고 화면에 넣지 않으므로, 설명 속 태그나 스크립트가 실행되지 않는다.
// 결과는 textContent(순수 글자)만 꺼내서 쓴다.
export function decodeEntities(text: string | null | undefined): string {
  if (!text) return "";
  const doc = new DOMParser().parseFromString(text.replace(/</g, "&lt;"), "text/html");
  return doc.documentElement.textContent ?? "";
}
