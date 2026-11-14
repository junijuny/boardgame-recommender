// =====================================================================
// 보드게임 추천 화면 (Boardgame Recommender)
// 1) 시작 화면에서 "Find similar games" 또는 "Browse by genre"를 고른다.
// 2) 추천 화면: 좋아하는 게임, 인원, 플레이 시간을 고르고 "Get recommendations"를 누르면
//    비슷한 보드게임 목록을 보여준다.
// 3) 장르 화면: 장르별 대표 게임을 둘러본다.
// 어느 화면이든 게임을 누르면 상세 팝업이 열리고,
// 팝업의 "Find similar games"를 누르면 그 게임이 선택된 추천 화면으로 이동한다.
// 헤더는 모든 화면에 같이 붙는다.
//
// 파일 구성
//   screens/    : 화면 하나씩 (StartScreen, RecommendScreen, GenreScreen)
//   components/ : 여러 화면에서 같이 쓰는 조각 (헤더, 검색창, 상세 팝업, 로딩 표시 등)
//   api.ts      : 백엔드 요청 함수 / queries.ts : 서버 데이터 훅 (TanStack Query)
//   format.ts   : 글자 변환 / styles.ts : 공통 버튼 모양 / types.ts : 데이터 모양 (타입)
//
// 색 이름 (index.css의 @theme에서 정함)
//   page         : 전체 배경
//   card         : 헤더, 박스 배경
//   line         : 테두리, 구분선
//   primary      : 메인 색 (버튼, 로고)
//   primary-dark : 진한 메인 색 (선택됨, 마우스 올림)
//   ink          : 글자색
//   danger       : 에러
// =====================================================================

import { useState } from "react";
import Header from "./components/Header";
import GenreScreen from "./screens/GenreScreen";
import RecommendScreen from "./screens/RecommendScreen";
import StartScreen from "./screens/StartScreen";
import type { GameSummary, Screen } from "./types";

// ---------------------------------------------------------------------
// App: 어떤 화면을 보여줄지 정하는 맨 바깥 컴포넌트
// (컴포넌트 = 화면 조각을 만드는 함수. 이름은 대문자로 시작해야 함)
// ---------------------------------------------------------------------
export default function App() {
  // 지금 보여줄 화면
  const [screen, setScreen] = useState<Screen>("start");
  // 추천 화면에 처음부터 선택해 둘 게임 { BGGId, Name, ... } (없으면 null)
  const [initialGame, setInitialGame] = useState<GameSummary | null>(null);
  // 추천 화면을 새로 열 때마다 올리는 번호
  // (key가 바뀌면 리액트가 추천 화면을 처음 상태로 새로 만든다)
  const [recommendKey, setRecommendKey] = useState(0);

  // 추천 화면 열기. game이 있으면 그 게임이 선택된 상태로 시작
  function openRecommend(game: GameSummary | null = null) {
    setInitialGame(game);
    setRecommendKey((n) => n + 1);
    setScreen("recommend");
    window.scrollTo(0, 0);
  }

  // 헤더 로고·메뉴, 시작 화면 버튼에서 화면 이동
  function navigate(next: Screen) {
    if (next === "recommend") {
      // 이미 추천 화면이면 입력해 둔 조건을 그대로 둔다
      if (screen !== "recommend") openRecommend();
      return;
    }
    setScreen(next);
    window.scrollTo(0, 0);
  }

  return (
    <div className="flex min-h-screen flex-col">
      <Header current={screen} onNavigate={navigate} />
      {screen === "recommend" && (
        <RecommendScreen key={recommendKey} initialGame={initialGame} onRecommendSimilar={openRecommend} />
      )}
      {screen === "genres" && <GenreScreen onRecommendSimilar={openRecommend} />}
      {screen === "start" && <StartScreen onNavigate={navigate} />}
    </div>
  );
}
