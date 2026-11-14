// =====================================================================
// types.ts: 백엔드가 돌려주는 데이터의 모양 (TypeScript 타입)
// 필드 이름은 백엔드(BGG 데이터셋 컬럼)와 똑같이 맞춘다.
// =====================================================================

// 게임 이름 검색 결과 한 개 (GET /games/search)
// 다른 응답들도 모두 이 항목은 갖고 있어서 "게임 하나"를 나타내는 기본 모양으로 쓴다.
export interface GameSummary {
  BGGId: number;
  Name: string;
  YearPublished: number;
  ImagePath: string | null;
}

// 장르 화면의 게임 카드 한 장 (GET /genres 안의 games)
export interface GenreGame extends GameSummary {
  GameWeight: number | null;
  ComMinPlaytime: number;
  ComMaxPlaytime: number;
  BayesAvgRating: number | null;
}

// 장르 하나와 그 장르의 대표 게임 (GET /genres)
export interface Genre {
  key: string;
  label: string;
  description: string;
  games: GenreGame[];
}

// 조건 필터 결과 한 개 (GET /games/filter)
export interface FilteredGame extends GameSummary {
  GameWeight: number | null;
  MinPlayers: number;
  MaxPlayers: number;
  ComMinPlaytime: number;
  ComMaxPlaytime: number;
  BayesAvgRating: number | null;
  NumUserRatings: number | null;
}

// 추천 결과 한 개 (POST /recommend): 필터 결과 + 유사도와 추천 이유
export interface RecommendedGame extends FilteredGame {
  Similarity: number;
  Score: number;
  // 기준 게임과 공통으로 가진 메커니즘·테마 (추천 이유)
  SharedMechanics: string[];
  SharedThemes: string[];
}

// 게임 상세 정보 (GET /games/{id})
export interface GameDetail extends GameSummary {
  Description: string | null;
  GameWeight: number | null;
  MinPlayers: number;
  MaxPlayers: number;
  BestPlayers: number;
  ComMinPlaytime: number;
  ComMaxPlaytime: number;
  BayesAvgRating: number | null;
  NumUserRatings: number | null;
}

// 추천 요청 바디 (POST /recommend)
export interface RecommendRequest {
  game_name: string;
  players: number;
  max_time: number;
  // 결과에서 뺄 게임 ID (이미 보여 준 게임). 추천 결과의 "Refresh"에서 사용
  exclude_ids?: number[];
}

// 백엔드가 오류일 때 돌려주는 바디 (FastAPI의 HTTPException)
export interface ApiErrorBody {
  detail?: string;
}

// 앱 안의 화면 이름: "start" = 시작, "recommend" = 비슷한 게임 찾기, "genres" = 장르
export type Screen = "start" | "recommend" | "genres";
