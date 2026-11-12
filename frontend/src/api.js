
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

// 6. 영어 자연어 문장으로 보드게임 검색
// 영어 자연어 문장으로 보드게임 추천
export async function semanticSearch(
  query,
  players,
  maxTime,
  excludeIds = [],
  signal,
) {
  const res = await axios.get(
    `${API_URL}/games/semantic-search`,
    {
      params: {
        query,
        players,
        max_time: maxTime,
        exclude_ids: excludeIds,
      },
      paramsSerializer: {
        indexes: null,
      },
      signal,
      timeout: TIMEOUT,
    },
  );

  return res.data;
}

// 입력한 영어 문장에서 기존 보드게임 이름 인식
export async function detectGameName(query) {
  const res = await axios.get(`${API_URL}/games/detect-name`, {
    params: { query },
    timeout: TIMEOUT,
  });

  return res.data.game_name;
}