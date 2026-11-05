// =====================================================================
// 보드게임 추천 화면 (Boardgame Recommender)
// 1) 시작 화면에서 "비슷한 게임 추천받기" 또는 "장르별로 둘러보기"를 고른다.
// 2) 추천 화면: 좋아하는 게임, 인원, 플레이 시간을 고르고 "추천받기"를 누르면
//    비슷한 보드게임 목록을 보여준다.
// 3) 장르 화면: 장르별 대표 게임을 둘러본다.
// 어느 화면이든 게임을 누르면 상세 팝업이 열리고,
// 팝업의 "비슷한 게임 추천받기"를 누르면 그 게임이 선택된 추천 화면으로 이동한다.
//
// 파일 구성
//   screens/    : 화면 하나씩 (StartScreen, RecommendScreen, GenreScreen)
//   components/ : 여러 화면에서 같이 쓰는 조각 (검색창, 상세 팝업 등)
//   api.js      : 백엔드 요청 함수 / format.js : 글자 변환 / styles.js : 공통 버튼 모양
//
// 색 이름 (index.css의 @theme에서 정함)
//   page         : 전체 배경
//   card         : 박스 배경
//   line         : 테두리, 구분선
//   primary      : 메인 색 (버튼, 아이콘)
//   primary-dark : 진한 메인 색 (선택됨, 마우스 올림)
//   ink          : 글자색
//   danger       : 에러
// =====================================================================

import { useState } from "react";
import GenreScreen from "./screens/GenreScreen.jsx";
import RecommendScreen from "./screens/RecommendScreen.jsx";
import StartScreen from "./screens/StartScreen.jsx";

// ---------------------------------------------------------------------
// App: 어떤 화면을 보여줄지 정하는 맨 바깥 컴포넌트
// (컴포넌트 = 화면 조각을 만드는 함수. 이름은 대문자로 시작해야 함)
// ---------------------------------------------------------------------
export default function App() {
  // 지금 보여줄 화면: "start" = 시작, "recommend" = 추천, "genres" = 장르
  const [screen, setScreen] = useState("start");
  // 추천 화면에 처음부터 선택해 둘 게임 { BGGId, Name, ... } (없으면 null)
  const [initialGame, setInitialGame] = useState(null);
  // 추천 화면을 새로 열 때마다 올리는 번호
  // (key가 바뀌면 리액트가 추천 화면을 처음 상태로 새로 만든다)
  const [recommendKey, setRecommendKey] = useState(0);

  // 추천 화면 열기. game이 있으면 그 게임이 선택된 상태로 시작
  function openRecommend(game = null) {
    setInitialGame(game);
    setRecommendKey((n) => n + 1);
    setScreen("recommend");
    window.scrollTo(0, 0);
  }

  function goStart() {
    setScreen("start");
  }

  if (screen === "recommend") {
    return (
      <RecommendScreen
        key={recommendKey}
        initialGame={initialGame}
        onBack={goStart}
        onRecommendSimilar={openRecommend}
      />
    );
  }

  if (screen === "genres") {
    return <GenreScreen onBack={goStart} onRecommendSimilar={openRecommend} />;
  }

  return (
    <StartScreen
      onStart={() => openRecommend()}
      onBrowse={() => {
        setScreen("genres");
        window.scrollTo(0, 0);
      }}
    />
  );
}
