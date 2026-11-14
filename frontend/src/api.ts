// =====================================================================
// api.ts: 백엔드 서버에 요청을 보내는 함수 모음
// 화면 코드에서는 axios를 직접 쓰지 않고, queries.ts의 훅이 여기 있는 함수를 부른다.
// 모든 함수는 서버가 돌려준 데이터(response.data)를 돌려주고,
// 실패하면 axios 에러를 그대로 던진다. (상태 코드는 err.response?.status)
// =====================================================================

// axios: 백엔드 서버에 요청을 보내고 응답을 받아오는 도구
import axios from "axios";
import { PLAYER_OPTIONS, TIME_OPTIONS } from "./filters";
import type {
  ApiErrorBody, ExplainRequest, ExplainResponse, FilteredGame, GameDetail, GameSummary, Genre, GenreGame,
  NaturalGame, NaturalSearchRequest, RecommendRequest, RecommendedGame, ServerInfo,
} from "./types";

// 백엔드 서버 주소
// .env 파일의 VITE_BASE_URL (배포된 백엔드 주소)을 쓴다. 예전 이름 VITE_API_URL도 인식한다.
// 둘 다 없으면 같은 컴퓨터에서 실행 중인 개발 서버를 사용
const DEPLOYED_URL = (import.meta.env.VITE_BASE_URL || import.meta.env.VITE_API_URL || "").replace(/\/+$/, "");
// 개발 중(npm run dev)에는 /api 로 보내면 Vite 개발 서버가 배포된 백엔드로 전달한다 (vite.config.js의 proxy)
// 브라우저가 다른 주소로 직접 요청하지 않으니 CORS에 막히지 않는다.
const BASE_URL = DEPLOYED_URL ? (import.meta.env.DEV ? "/api" : DEPLOYED_URL) : "http://localhost:8000";

// 모든 요청이 같이 쓰는 axios 설정
// timeout: 응답을 기다리는 최대 시간 (60초)
// 배포 서버는 한동안 요청이 없으면 잠들고, 깨어나는 데 시간이 걸릴 수 있음
const api = axios.create({ baseURL: BASE_URL, timeout: 60000 });

// 게임 이름 검색 (최대 10개)
// signal: 검색어가 바뀌면 이전 요청을 취소할 때 쓰는 값 (TanStack Query가 넘겨줌)
export async function searchGames(query: string, signal?: AbortSignal) {
  const res = await api.get<GameSummary[]>("/games/search", { params: { query }, signal });
  return res.data;
}

// 인원·최대 시간 조건에 맞는 게임 (평점 높은 순 최대 10개)
export async function filterGames(players: number, maxTime: number, signal?: AbortSignal) {
  const res = await api.get<FilteredGame[]>("/games/filter", { params: { players, max_time: maxTime }, signal });
  return res.data;
}

// 비슷한 게임 추천 (최대 5개)
// exclude_ids: 이미 보여 준 게임 ID. 넣으면 그 게임들을 빼고 다음으로 비슷한 게임을 돌려준다.
export async function recommend({ game_name, players, max_time, exclude_ids }: RecommendRequest) {
  const res = await api.post<RecommendedGame[]>("/recommend", {
    game_name,
    players,
    max_time,
    ...(exclude_ids && exclude_ids.length > 0 ? { exclude_ids } : {}),
  });
  return res.data;
}

// 서버 정보: 자연어 검색·추천 이유 기능이 켜져 있는지 (GET /)
export async function getServerInfo() {
  const res = await api.get<ServerInfo>("/");
  return res.data;
}

// 자연어 검색 (최대 5개). exclude_ids는 recommend와 같이 비어 있으면 보내지 않는다.
export async function naturalSearch({ query, players, max_time, exclude_ids }: NaturalSearchRequest) {
  const res = await api.post<NaturalGame[]>("/search/natural", {
    query,
    players,
    max_time,
    ...(exclude_ids && exclude_ids.length > 0 ? { exclude_ids } : {}),
  });
  return res.data;
}

// 결과 게임마다 한 문장짜리 추천 이유 받기 (게임 1~10개)
export async function explain(req: ExplainRequest) {
  const res = await api.post<ExplainResponse>("/explain", req);
  return res.data;
}

// 게임 한 개의 상세 정보 (설명, 인원, 평점 등)
export async function getGameDetail(bggId: number, signal?: AbortSignal) {
  const res = await api.get<GameDetail>(`/games/${bggId}`, { signal });
  return res.data;
}

// 장르 8개와 장르별 대표 게임
export async function getGenres() {
  const res = await api.get<Genre[]>("/genres");
  return res.data;
}

// 장르 새로고침: 이미 본 게임(exclude)을 뺀 같은 장르의 다른 게임 (인기·평점 순 최대 6개)
// 백엔드가 exclude_ids에 든 게임을 빼고 다음 순위 게임을 돌려준다. 남은 게임이 없으면 빈 배열.
// FastAPI는 목록을 ?exclude_ids=13&exclude_ids=822처럼 받으므로,
// axios 기본값(exclude_ids[]=13)이 아니라 [] 없이 같은 이름을 반복해서 보낸다 (indexes: null).
export async function getOtherGenreGames(key: string, exclude: number[]) {
  const res = await api.get<GenreGame[]>(`/genres/${key}/games`, {
    params: { exclude_ids: exclude },
    paramsSerializer: { indexes: null },
  });
  return res.data;
}

// 시작 화면용 무작위 사진
// 인원·시간 필터를 무작위로 골라 /games/filter를 부르고, 받은 게임 정보 중 표지 사진 주소만 남긴다.
// 사진이 count장보다 적으면 다른 조합으로 최대 3번까지 더 불러온 뒤, 순서를 섞어서 돌려준다.
export async function getRandomPhotos(count: number, signal?: AbortSignal) {
  const photos = new Set<string>();
  for (const { players, maxTime } of randomCombos().slice(0, 3)) {
    const games = await filterGames(players, maxTime, signal);
    for (const game of games) {
      if (game.ImagePath) photos.add(game.ImagePath);  // 사진 주소만 쓰고 나머지 정보는 버림
    }
    if (photos.size >= count) break;
  }
  return shuffle([...photos]).slice(0, count);
}

// 인원 × 최대 시간 조합 전체를 무작위 순서로 (예: [{players: 4, maxTime: 60}, ...])
function randomCombos() {
  return shuffle(PLAYER_OPTIONS.flatMap((players) => TIME_OPTIONS.map((maxTime) => ({ players, maxTime }))));
}

// 배열 순서를 무작위로 섞은 새 배열 (Fisher–Yates)
function shuffle<T>(items: T[]): T[] {
  const result = [...items];
  for (let i = result.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [result[i], result[j]] = [result[j], result[i]];
  }
  return result;
}

// 요청이 실패했을 때 서버가 돌려준 응답 (상태 코드, 오류 바디)
// 서버에 연결조차 못 했거나 axios 오류가 아니면 undefined
export function errorResponse(err: unknown) {
  return axios.isAxiosError<ApiErrorBody>(err) ? err.response : undefined;
}
