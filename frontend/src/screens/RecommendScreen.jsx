// ---------------------------------------------------------------------
// RecommendScreen: 조건을 고르고 추천을 받는 화면
// 좋아하는 게임, 인원, 플레이 시간을 고르고 "추천받기"를 누르면
// 비슷한 보드게임 5개를 보여준다. 결과를 누르면 상세 팝업이 열린다.
//
// 받는 정보(props)
//   initialGame        : 처음부터 선택해 둘 게임 { BGGId, Name } (없으면 null)
//   onBack             : "처음으로" 버튼을 눌렀을 때 실행할 함수
//   onRecommendSimilar : 상세 팝업에서 "비슷한 게임 추천받기"를 눌렀을 때 실행할 함수
// ---------------------------------------------------------------------

// useState: 화면이 "기억"해야 하는 값을 만들 때 쓰는 리액트 기능
import { useState } from "react";
// lucide-react: 아이콘 모음 도구. 쓰고 싶은 아이콘 이름만 골라서 불러온다.
// 아이콘 이름은 lucide.dev 사이트에서 검색해서 찾을 수 있다.
import {
  ArrowLeft,     // 왼쪽 화살표 (처음으로 버튼)
  ChevronRight,  // 오른쪽 꺾쇠 (결과를 누를 수 있다는 표시)
  CircleAlert,   // 느낌표 동그라미 (에러)
  Clock,         // 시계 (결과의 플레이 시간)
  Dices,         // 주사위 (결과 제목)
  Gauge,         // 게이지 (결과의 난이도)
  Hourglass,     // 모래시계 (플레이 시간 고르기)
  LoaderCircle,  // 빙글빙글 도는 원 (로딩)
  Search,        // 돋보기 (추천받기)
  SearchX,       // 엑스 표시 돋보기 (결과 없음)
  Users,         // 사람들 (인원)
} from "lucide-react";
import { recommend } from "../api.js";
import { formatMinutes, formatPlaytime, withWa } from "../format.js";
import { backButton, primaryButton } from "../styles.js";
import GameDetailModal from "../components/GameDetailModal.jsx";
import GameSearch from "../components/GameSearch.jsx";
import GameThumb from "../components/GameThumb.jsx";
import OptionGroup from "../components/OptionGroup.jsx";

// 인원 선택 버튼에 들어갈 숫자들 (2명 ~ 6명)
const PLAYER_OPTIONS = [2, 3, 4, 5, 6];

// 플레이 시간 선택 버튼에 들어갈 값들 (단위: 분)
const TIME_OPTIONS = [30, 60, 90, 120];

export default function RecommendScreen({ initialGame, onBack, onRecommendSimilar }) {
  // useState 사용법: const [현재값, 값을바꾸는함수] = useState(처음값);
  // 값을 바꾸는 함수를 부르면 리액트가 화면을 자동으로 다시 그려준다.

  // 검색 결과에서 선택한 게임 { BGGId, Name, ... } (선택 안 했으면 null)
  const [game, setGame] = useState(initialGame);
  // 사용자가 고른 인원 (처음엔 4명)
  const [players, setPlayers] = useState(4);
  // 사용자가 고른 최대 플레이 시간 (처음엔 60분)
  const [maxTime, setMaxTime] = useState(60);
  // 추천 결과 목록 (처음엔 빈 목록)
  const [results, setResults] = useState([]);
  // 지금 추천을 받아오는 중인지 여부
  const [loading, setLoading] = useState(false);
  // 에러 메시지 (문제없으면 빈 글자)
  const [error, setError] = useState("");
  // "추천받기"를 한 번이라도 눌렀는지 여부
  // (안 누른 상태와, 눌렀는데 결과가 0개인 상태를 구분하려고 씀)
  const [searched, setSearched] = useState(false);
  // 상세 팝업으로 보고 있는 게임 ID (닫혀 있으면 null)
  const [selectedId, setSelectedId] = useState(null);

  function clearRecommendation() {
    setResults([]);
    setError("");
    setSearched(false);
  }

  // "추천받기" 버튼을 누르면 실행되는 함수
  // async: 서버 응답처럼 시간이 걸리는 일을 기다릴 수 있게 해주는 표시
  async function handleRecommend() {
    if (!game || loading) return;
    // 1. 로딩 시작, 이전 에러 메시지 지우기
    setLoading(true);
    setError("");

    // try: 일단 시도해보고, 중간에 문제가 생기면 catch로 넘어감
    try {
      // 검색 결과의 Name을 백엔드 요청의 game_name으로 전달
      setResults(await recommend({ game_name: game.Name, players, max_time: maxTime }));
    } catch (err) {
      // 연결 실패와 백엔드가 반환한 오류를 구분
      console.error(err); // 개발자 도구(F12) Console 탭에 자세한 에러 출력
      setResults([]);
      const status = err.response?.status;
      const detail = err.response?.data?.detail;
      if (status === 404 && detail === "No games match the selected conditions") {
        // Results의 기존 '조건에 맞는 게임이 없어요' 안내를 표시
        setError("");
      } else if (status === 404 && detail === "Game not found") {
        setError("선택한 게임을 찾을 수 없습니다. 다른 게임을 선택해 주세요.");
      } else if (status === 400 || status === 422) {
        setError("게임, 인원, 플레이 시간을 확인해 주세요.");
      } else if (!err.response) {
        setError("서버에 연결할 수 없습니다. 잠시 후 다시 시도해 주세요.");
      } else {
        setError("추천을 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.");
      }
    } finally {
      // finally: 성공하든 실패하든 마지막에 무조건 실행
      setLoading(false);
      setSearched(true);
    }
  }

  // return 안에 있는 것이 실제로 화면에 그려지는 부분 (JSX)
  // className에 있는 글자들은 Tailwind 디자인 설정
  // (예: px-4 = 좌우 여백, text-3xl = 큰 글씨, bg-card = 카드 배경색)
  return (
    <div className="min-h-screen px-4 py-12">
      {/* 화면 가운데에 최대 너비를 정해서 내용을 모아둠 */}
      <main className="mx-auto max-w-3xl">

        {/* 처음으로 돌아가기 버튼 */}
        <button type="button" onClick={onBack} disabled={loading} className={backButton}>
          <ArrowLeft className="h-4 w-4" aria-hidden="true" />
          처음으로
        </button>

        {/* 1. 제목과 설명 (질문하는 말투) */}
        <header className="mb-8">
          <h1 className="text-3xl font-bold tracking-tight">오늘은 어떤 보드게임 해볼까요?</h1>
          <p className="mt-2 text-ink/70">
            좋아하는 게임과 인원, 플레이 시간을 알려 주세요. 비슷한 게임을 찾아 드릴게요.
          </p>
        </header>

        {/* 2. 조건 입력 영역 (흰 박스) */}
        <section className="space-y-6 rounded-xl border border-line bg-card p-6">

          {/* 실제 데이터셋에서 게임을 검색하고 하나를 선택 */}
          <GameSearch
            value={game}
            disabled={loading}
            onChange={(picked) => {
              setGame(picked);
              clearRecommendation();
            }}
            onShowDetail={setSelectedId}
          />

          {/* 2-2. 인원 고르기 (버튼 묶음) */}
          {/* options: [2,3,4,5,6]을 [{value: 2, label: "2명"}, ...] 모양으로 바꿔서 넘김 */}
          <OptionGroup
            icon={Users}
            label="인원"
            options={PLAYER_OPTIONS.map((n) => ({ value: n, label: `${n}명` }))}
            value={players}
            disabled={loading}
            onChange={(value) => { setPlayers(value); clearRecommendation(); }}
          />

          {/* 2-3. 플레이 시간 고르기 (버튼 묶음) */}
          {/* 예) 90 -> { value: 90, label: "1시간 30분 이하" } */}
          <OptionGroup
            icon={Hourglass}
            label="플레이 시간"
            options={TIME_OPTIONS.map((m) => ({ value: m, label: `${formatMinutes(m)} 이하` }))}
            value={maxTime}
            disabled={loading}
            onChange={(value) => { setMaxTime(value); clearRecommendation(); }}
          />

          {/* 2-4. 추천받기 버튼 */}
          {/* disabled: 로딩 중이거나 게임을 안 골랐으면 못 누르게 막음 (중복 요청 방지) */}
          <button
            type="button"
            onClick={handleRecommend}
            disabled={loading || !game}
            className={`${primaryButton} w-full py-3 text-lg`}
          >
            {loading ? (
              <>
                <LoaderCircle className="h-5 w-5 motion-safe:animate-spin" aria-hidden="true" />
                찾는 중...
              </>
            ) : (
              <>
                <Search className="h-5 w-5" aria-hidden="true" />
                추천받기
              </>
            )}
          </button>
        </section>

        {/* 3. 결과 영역 */}
        {/* aria-live: 결과가 바뀌면 화면 읽기 프로그램이 알려주도록 하는 설정 (접근성) */}
        <div className="mt-10" aria-live="polite">
          <Results
            gameLabel={game?.Name ?? ""}
            results={results}
            loading={loading}
            error={error}
            searched={searched}
            onSelect={setSelectedId}
          />
        </div>
      </main>

      {/* 결과를 눌렀을 때 뜨는 상세 팝업 */}
      <GameDetailModal
        bggId={selectedId}
        onClose={() => setSelectedId(null)}
        onRecommendSimilar={onRecommendSimilar}
      />
    </div>
  );
}


// ---------------------------------------------------------------------
// Results: 상황에 따라 다른 내용을 보여주는 결과 영역
// 위에서부터 순서대로 확인해서, 해당하는 것 하나만 보여준다.
// onSelect: 결과 한 줄을 눌렀을 때 그 게임 ID를 넘겨받는 함수
// ---------------------------------------------------------------------
function Results({ gameLabel, results, loading, error, searched, onSelect }) {
  // 1) 불러오는 중일 때
  if (loading) {
    return (
      <p className="flex items-center justify-center gap-2 text-ink/60">
        <LoaderCircle className="h-5 w-5 motion-safe:animate-spin" aria-hidden="true" />
        추천 게임을 찾고 있어요...
      </p>
    );
  }
  // 2) 에러가 났을 때 (빨간 박스 + 느낌표 아이콘)
  if (error) {
    return (
      <p className="flex items-start gap-2 rounded-lg border border-danger/40 bg-danger/10 px-4 py-3 text-danger">
        <CircleAlert className="mt-0.5 h-5 w-5 shrink-0" aria-hidden="true" />
        {error}
      </p>
    );
  }
  // 3) 추천받기를 눌렀는데 결과가 0개일 때 (돋보기X 아이콘)
  if (searched && results.length === 0) {
    return (
      <div className="flex flex-col items-center gap-2 rounded-lg border border-line bg-card px-4 py-8 text-center text-ink/70">
        <SearchX className="h-8 w-8 text-primary" aria-hidden="true" />
        <p>조건에 맞는 게임이 없어요. 인원이나 플레이 시간을 바꿔 보세요.</p>
      </div>
    );
  }
  // 4) 아직 아무것도 안 눌렀을 때: 아무것도 안 보여줌
  if (results.length === 0) return null;

  // 5) 결과가 있을 때: 목록 보여주기
  return (
    <section>
      {/* 예) "카탄과 비슷한 게임" + 주사위 아이콘 */}
      <h2 className="flex items-center gap-2 text-lg font-bold">
        <Dices className="h-5 w-5 text-primary" aria-hidden="true" />
        {withWa(gameLabel)} 비슷한 게임
      </h2>
      <p className="mb-3 mt-1 text-sm text-ink/60">게임을 누르면 자세한 설명을 볼 수 있어요.</p>
      {/* divide-y: 목록 줄 사이에 구분선 넣기 */}
      {/* i는 0부터 시작하는 순서라서 rank는 i + 1 (1위, 2위...) */}
      <ul className="divide-y divide-line overflow-hidden rounded-xl border border-line bg-card">
        {results.map((g, i) => (
          <GameRow key={g.BGGId ?? g.Name} game={g} rank={i + 1} onSelect={onSelect} />
        ))}
      </ul>
    </section>
  );
}


// ---------------------------------------------------------------------
// GameRow: 추천 결과 목록의 한 줄 (누르면 상세 팝업)
//
// 받는 정보(props)
//   game     : 게임 정보 하나 (이름, 이미지, 난이도, 시간 등)
//   rank     : 순위 (1, 2, 3...)
//   onSelect : 눌렀을 때 실행할 함수 (게임 ID를 넘겨줌)
// ---------------------------------------------------------------------
function GameRow({ game, rank, onSelect }) {
  // 난이도를 소수점 한 자리로 표시 (예: 1.79 -> "1.8"), 값이 없으면 0
  const weight = (game.GameWeight ?? 0).toFixed(1);

  return (
    <li>
      {/* aria-haspopup: 누르면 팝업이 열린다는 것을 화면 읽기 프로그램에 알려줌 */}
      <button
        type="button"
        onClick={() => onSelect(game.BGGId)}
        aria-haspopup="dialog"
        className="group flex w-full items-center gap-4 px-5 py-4 text-left transition-colors hover:bg-page focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-primary-dark"
      >
        {/* 왼쪽: 순위 숫자 */}
        <span className="w-5 text-center text-sm font-semibold text-ink/50">{rank}</span>

        {/* 가운데: 게임 표지 이미지 (정사각형) */}
        <GameThumb src={game.ImagePath} className="h-16 w-16 rounded-lg" />

        {/* 오른쪽: 게임 이름과 정보 */}
        {/* min-w-0, truncate: 이름이 너무 길면 "..."으로 자르기 */}
        <div className="min-w-0 flex-1">
          <h3 className="truncate font-semibold group-hover:underline">{game.Name}</h3>
          <p className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-ink/60">
            <span className="inline-flex items-center gap-1">
              <Clock className="h-3.5 w-3.5" aria-hidden="true" />
              {formatPlaytime(game)}
            </span>
            <span className="inline-flex items-center gap-1">
              <Gauge className="h-3.5 w-3.5" aria-hidden="true" />
              난이도 {weight} / 5
            </span>
          </p>
          {/* 추천 이유: 기준 게임과 공통으로 가진 메커니즘 (드문 것부터 최대 3개) */}
          {game.SharedMechanics?.length > 0 && (
            <p className="mt-1 truncate text-xs text-ink/50">
              공통 메커니즘: {game.SharedMechanics.join(" · ")}
            </p>
          )}
        </div>

        <ChevronRight className="h-5 w-5 shrink-0 text-ink/30 transition-colors group-hover:text-primary" aria-hidden="true" />
      </button>
    </li>
  );
}
