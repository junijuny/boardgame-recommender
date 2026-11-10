// =====================================================================
// api.js: 백엔드 서버에 요청을 보내는 함수 모음
// 화면 코드에서는 axios를 직접 쓰지 않고 여기 있는 함수만 부른다.
// 모든 함수는 서버가 돌려준 데이터(response.data)를 돌려주고,
// 실패하면 axios 에러를 그대로 던진다. (상태 코드는 err.response?.status)
// =====================================================================

// axios: 백엔드 서버에 요청을 보내고 응답을 받아오는 도구
import axios from "axios";

// 백엔드 서버 주소
// 배포 시에는 빌드 환경변수 VITE_API_URL 로 지정 (예: https://xxx.onrender.com)
// 지정하지 않으면 같은 컴퓨터에서 실행 중인 개발 서버를 사용
const API_URL = (import.meta.env.VITE_API_URL || "http://localhost:8000").replace(/\/+$/, "");

// 응답을 기다리는 최대 시간 (60초)
// 배포 서버는 15분간 요청이 없으면 잠들고 깨어나는 데 15초 이상 걸릴 수 있음
const TIMEOUT = 60000;

// 게임 이름 검색 (최대 10개)
// signal: 검색어가 바뀌면 이전 요청을 취소할 때 쓰는 값 (AbortController)
export async function searchGames(query, signal) {
  const res = await axios.get(`${API_URL}/games/search`, {
    params: { query },
    signal,
    timeout: TIMEOUT,
  });
  return res.data;
}

// 비슷한 게임 추천 (최대 5개)
export async function recommend({ game_name, players, max_time }) {
  const res = await axios.post(
    `${API_URL}/recommend`,
    { game_name, players, max_time },
    { timeout: TIMEOUT },
  );
  return res.data;
}

// 게임 한 개의 상세 정보 (설명, 인원, 평점 등)
export async function getGameDetail(bggId, signal) {
  const res = await axios.get(`${API_URL}/games/${bggId}`, { signal, timeout: TIMEOUT });
  return res.data;
}

// 장르 8개와 장르별 대표 게임
export async function getGenres() {
  const res = await axios.get(`${API_URL}/genres`, { timeout: TIMEOUT });
  return res.data;
}

// 장르별 플레이 인원·시간 조건에 맞는 게임 조회
export async function getGenreGames(genreKey, players, maxTime, signal) {
  const res = await axios.get(`${API_URL}/genres/${genreKey}/games`, {
    params: {
      players,
      max_time: maxTime,
    },
    signal,
    timeout: TIMEOUT,
  });

  return res.data;
}
