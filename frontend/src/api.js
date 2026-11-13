
// =====================================================================
// api.js: 백엔드 서버에 요청을 보내는 함수 모음
// =====================================================================

import axios from "axios";

// 백엔드 서버 주소
const API_URL = (
  import.meta.env.VITE_API_URL || "http://localhost:8000"
).replace(/\/+$/, "");

// 응답 대기 시간 (60초)
const TIMEOUT = 60000;


// 0. 백엔드 서버 미리 깨우기 (콜드 스타트 체감 지연 완화, 실패해도 무시)
export function warmupServer() {
  axios.get(`${API_URL}/`, { timeout: TIMEOUT }).catch(() => {});
}


// 1. 게임 이름 검색 (최대 10개)
export async function searchGames(query, signal) {
  const res = await axios.get(`${API_URL}/games/search`, {
    params: { query },
    signal,
    timeout: TIMEOUT,
  });

  return res.data;
}


// 2. 비슷한 게임 추천 (이미 본 게임 제외 가능)
export async function recommend({
  game_name,
  players,
  max_time,
  exclude_ids = [],
}) {
  const res = await axios.post(
    `${API_URL}/recommend`,
    {
      game_name,
      players,
      max_time,
      exclude_ids,
    },
    { timeout: TIMEOUT },
  );

  return res.data;
}


// 3. 게임 상세 정보 조회
export async function getGameDetail(bggId, signal) {
  const res = await axios.get(`${API_URL}/games/${bggId}`, {
    signal,
    timeout: TIMEOUT,
  });

  return res.data;
}


// 4. 장르 목록 및 대표 게임 조회
export async function getGenres() {
  const res = await axios.get(`${API_URL}/genres`, {
    timeout: TIMEOUT,
  });

  return res.data;
}


// 5. 장르별 인원/시간 조건 추천
export async function getGenreGames(
  genreKey,
  players,
  maxTime,
  signal,
) {
  const res = await axios.get(
    `${API_URL}/genres/${genreKey}/games`,
    {
      params: {
        players,
        max_time: maxTime,
      },
      signal,
      timeout: TIMEOUT,
    },
  );

  return res.data;
}

// 장르별 플레이 인원·시간 조건에 맞는 게임 조회

