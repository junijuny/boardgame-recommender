// =====================================================================
// 보드게임 추천 화면
// 1) 시작 화면에서 "시작하기"를 누르면
// 2) 추천 화면으로 넘어가서 좋아하는 게임, 인원, 플레이 시간을 고르고
// 3) "추천받기"를 누르면 비슷한 보드게임 목록을 보여준다.
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

// useState: 화면이 "기억"해야 하는 값을 만들 때 쓰는 리액트 기능
import { useEffect, useState } from "react";
// axios: 백엔드 서버에 요청을 보내고 응답을 받아오는 도구
import axios from "axios";
// lucide-react: 아이콘 모음 도구. 쓰고 싶은 아이콘 이름만 골라서 불러온다.
// 아이콘 이름은 lucide.dev 사이트에서 검색해서 찾을 수 있다.
import {
  ArrowLeft,     // 왼쪽 화살표 (처음으로 버튼)
  ArrowRight,    // 오른쪽 화살표 (시작하기 버튼)
  CircleAlert,   // 느낌표 동그라미 (에러)
  Clock,         // 시계 (결과의 플레이 시간)
  Dices,         // 주사위 (대표 아이콘, 이미지 없을 때)
  Gauge,         // 게이지 (결과의 난이도)
  Heart,         // 하트 (좋아하는 게임)
  Hourglass,     // 모래시계 (플레이 시간 고르기)
  LoaderCircle,  // 빙글빙글 도는 원 (로딩)
  Search,        // 돋보기 (추천받기)
  SearchX,       // 엑스 표시 돋보기 (결과 없음)
  Users,         // 사람들 (인원)
} from "lucide-react";


// ---------------------------------------------------------------------
// 설정 값
// ---------------------------------------------------------------------

// 같은 컴퓨터에서 실행 중인 백엔드 서버 주소
const API_URL = "http://localhost:8000";

// 인원 선택 버튼에 들어갈 숫자들 (2명 ~ 6명)
const PLAYER_OPTIONS = [2, 3, 4, 5, 6];

// 플레이 시간 선택 버튼에 들어갈 값들 (단위: 분)
const TIME_OPTIONS = [30, 60, 90, 120];

// ---------------------------------------------------------------------
// 도우미 함수들
// ---------------------------------------------------------------------

// 분 단위 숫자를 읽기 쉬운 글자로 바꿔주는 함수
// 예) 30 -> "30분", 60 -> "1시간", 90 -> "1시간 30분"
function formatMinutes(min) {
  // 60분 미만이면 그냥 "○○분"
  if (min < 60) return `${min}분`;
  // Math.floor: 소수점 버리기. 90 / 60 = 1.5 -> 1
  const h = Math.floor(min / 60);
  // %: 나머지. 90 % 60 = 30
  const m = min % 60;
  // 나머지 분이 0이면 "1시간", 아니면 "1시간 30분"
  return m === 0 ? `${h}시간` : `${h}시간 ${m}분`;
}

// 단어 뒤에 "와" 또는 "과"를 알맞게 붙여주는 함수
// 마지막 글자에 받침이 있으면 "과", 없으면 "와"
// 예) 카탄 -> "카탄과", 스플렌더 -> "스플렌더와"
function withWa(word) {
  // 마지막 글자의 유니코드 번호를 가져옴
  const code = word.charCodeAt(word.length - 1);
  // 한글(가~힣)이 아니면 판단할 수 없으니 "와(과)"로 처리
  if (code < 0xac00 || code > 0xd7a3) return `${word}와(과)`;
  // 한글 번호를 28로 나눈 나머지가 0이면 받침이 없는 글자
  return (code - 0xac00) % 28 === 0 ? `${word}와` : `${word}과`;
}


// ---------------------------------------------------------------------
// App: 어떤 화면을 보여줄지 정하는 맨 바깥 컴포넌트
// (컴포넌트 = 화면 조각을 만드는 함수. 이름은 대문자로 시작해야 함)
// ---------------------------------------------------------------------
export default function App() {
  // 지금 보여줄 화면을 기억하는 값
  // "start" = 시작 화면, "recommend" = 추천 화면
  const [screen, setScreen] = useState("start");

  // 시작 화면이면 StartScreen을 보여줌
  // onStart: "시작하기"를 누르면 화면을 "recommend"로 바꾸라고 함수를 넘겨줌
  if (screen === "start") {
    return <StartScreen onStart={() => setScreen("recommend")} />;
  }

  // 그 외에는 추천 화면을 보여줌
  // onBack: "처음으로"를 누르면 다시 시작 화면으로 돌아가게 함
  return <RecommendScreen onBack={() => setScreen("start")} />;
}


// ---------------------------------------------------------------------
// StartScreen: 맨 처음에 보이는 시작 화면
//
// 받는 정보(props)
//   onStart : "시작하기" 버튼을 눌렀을 때 실행할 함수
// ---------------------------------------------------------------------
function StartScreen({ onStart }) {
  // min-h-screen: 화면 높이 가득 / items-center, justify-center: 가운데 정렬
  return (
    <div className="flex min-h-screen items-center justify-center px-4 py-12">
      <main className="w-full max-w-xl text-center">

        {/* 대표 아이콘: 네이비 네모 안에 주사위 */}
        {/* strokeWidth: 아이콘 선 두께 (기본 2, 숫자가 작을수록 얇음) */}
        <div className="mx-auto flex h-20 w-20 items-center justify-center rounded-2xl bg-primary text-card">
          <Dices className="h-10 w-10" strokeWidth={1.75} aria-hidden="true" />
        </div>

        {/* 제목과 설명 / <br />: 줄바꿈 */}
        <h1 className="mt-6 text-4xl font-bold leading-tight tracking-tight">
          뭐 하고 놀지<br />고민될 때
        </h1>
        <p className="mt-4 text-ink/70">
          좋아하는 게임 하나만 알려 주세요. 비슷한 보드게임을 찾아 드릴게요.
        </p>

        {/* 이용 방법 3단계 */}
        {/* ol: 순서가 있는 목록 / sm:grid-cols-3: 화면이 넓으면 3칸으로 나란히 */}
        <ol className="mt-10 grid gap-3 text-left sm:grid-cols-3">
          <Step icon={Heart} title="좋아하는 게임" text="재밌게 했던 게임 고르기" />
          <Step icon={Users} title="인원과 시간" text="몇 명이서, 얼마나 할지" />
          <Step icon={Search} title="추천 받기" text="비슷한 게임 확인하기" />
        </ol>

        {/* 시작하기 버튼: 누르면 onStart 실행 -> 추천 화면으로 이동 */}
        <button
          type="button"
          onClick={onStart}
          className="mt-10 inline-flex items-center gap-2 rounded-lg bg-primary px-8 py-3.5 text-lg font-bold text-card transition-colors hover:bg-primary-dark focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary-dark"
        >
          시작하기
          <ArrowRight className="h-5 w-5" aria-hidden="true" />
        </button>
      </main>
    </div>
  );
}


// ---------------------------------------------------------------------
// Step: 시작 화면의 이용 방법 한 칸
//
// 받는 정보(props)
//   icon  : 보여줄 아이콘 (예: Heart)
//   title : 굵은 제목
//   text  : 작은 설명
//
// icon: Icon 이라고 쓴 이유:
//   리액트는 대문자로 시작하는 이름만 컴포넌트로 알아봐서,
//   받은 icon을 Icon(대문자)이라는 이름으로 바꿔서 <Icon /> 으로 쓰는 것
// ---------------------------------------------------------------------
function Step({ icon: Icon, title, text }) {
  return (
    <li className="rounded-xl border border-line bg-card p-4">
      <Icon className="h-6 w-6 text-primary" strokeWidth={1.75} aria-hidden="true" />
      <p className="mt-3 font-bold">{title}</p>
      <p className="mt-1 text-sm text-ink/60">{text}</p>
    </li>
  );
}


// ---------------------------------------------------------------------
// RecommendScreen: 조건을 고르고 추천을 받는 화면
//
// 받는 정보(props)
//   onBack : "처음으로" 버튼을 눌렀을 때 실행할 함수
// ---------------------------------------------------------------------
function RecommendScreen({ onBack }) {
  // useState 사용법: const [현재값, 값을바꾸는함수] = useState(처음값);
  // 값을 바꾸는 함수를 부르면 리액트가 화면을 자동으로 다시 그려준다.

  // 검색 결과에서 선택한 실제 게임 이름
  const [game, setGame] = useState("");
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
      const res = await axios.post(`${API_URL}/recommend`, {
        game_name: game,
        players: players,
        max_time: maxTime,
      }, { timeout: 15000 });
      setResults(res.data);
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
        <button
          type="button"
          onClick={onBack}
          disabled={loading}
          className="mb-6 inline-flex items-center gap-1 text-sm text-ink/60 transition-colors hover:text-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary-dark"
        >
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
            onChange={(name) => {
              setGame(name);
              clearRecommendation();
            }}
          />

          {/* 2-2. 인원 고르기 (버튼 묶음) */}
          {/* OptionGroup 컴포넌트에 필요한 정보(props)를 넘겨줌 */}
          {/* icon: 칸 이름 옆에 보여줄 아이콘 */}
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
          {/* onClick: 누르면 handleRecommend 실행 */}
          {/* disabled: 로딩 중에는 버튼을 못 누르게 막음 (중복 요청 방지) */}
          {/* 로딩 중이면 도는 아이콘 + "찾는 중...", 아니면 돋보기 + "추천받기" */}
          <button
            type="button"
            onClick={handleRecommend}
            disabled={loading || !game}
            className="flex w-full items-center justify-center gap-2 rounded-lg bg-primary py-3 text-lg font-semibold text-card transition-colors hover:bg-primary-dark disabled:opacity-60 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary-dark"
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
            gameLabel={game}
            results={results}
            loading={loading}
            error={error}
            searched={searched}
          />
        </div>
      </main>
    </div>
  );
}


// 검색 결과의 게임을 선택해야 추천 요청을 보낼 수 있음.
// 입력을 바꾸면 이전 요청을 취소해 늦은 응답이 새 검색 결과를 덮지 않게 함.
function GameSearch({ value, onChange, disabled }) {
  const [query, setQuery] = useState("");
  const [matches, setMatches] = useState([]);
  const [searching, setSearching] = useState(false);
  const [searchError, setSearchError] = useState("");
  const [finished, setFinished] = useState(false);
  const [retry, setRetry] = useState(0);

  useEffect(() => {
    const term = query.trim();
    if (term.length < 2 || value) return;

    const controller = new AbortController();
    const timer = setTimeout(async () => {
      try {
        const response = await axios.get(`${API_URL}/games/search`, {
          params: { query: term },
          signal: controller.signal,
          timeout: 15000,
        });
        if (!controller.signal.aborted) {
          setMatches(response.data);
          setFinished(true);
        }
      } catch (err) {
        if (!controller.signal.aborted) {
          setSearchError(err.response
            ? "게임 검색에 실패했습니다. 다시 시도해 주세요."
            : "게임 목록을 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.");
        }
      } finally {
        if (!controller.signal.aborted) setSearching(false);
      }
    }, 300);

    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [query, value, retry]);

  return (
    <div>
      <label htmlFor="game-search" className="mb-2 flex items-center gap-1.5 text-sm font-semibold">
        <Heart className="h-4 w-4 text-primary" aria-hidden="true" />
        좋아하는 게임 검색
      </label>
      <input
        id="game-search"
        type="search"
        value={query}
        disabled={disabled}
        autoComplete="off"
        placeholder="영문 게임 이름 입력 (예: Catan, Wingspan)"
        aria-describedby="game-search-help"
        onChange={(event) => {
          setQuery(event.target.value);
          setMatches([]);
          setFinished(false);
          setSearchError("");
          setSearching(event.target.value.trim().length >= 2);
          onChange("");
        }}
        className="w-full rounded-lg border border-line bg-page px-3 py-2.5 focus:border-primary-dark focus:outline-none"
      />
      <p id="game-search-help" className="mt-2 text-sm text-ink/60">
        영문 이름을 2글자 이상 입력한 뒤 검색 결과에서 게임을 선택해 주세요.
      </p>
      <div className="mt-3" aria-live="polite" aria-busy={searching}>
        {value && <p className="text-sm font-semibold text-primary">선택한 게임: {value}</p>}
        {searching && <p className="text-sm text-ink/60">게임 검색 중...</p>}
        {searchError && (
          <div className="text-sm text-danger">
            <p>{searchError}</p>
            <button type="button" disabled={disabled} onClick={() => {
              setSearchError("");
              setSearching(true);
              setRetry((count) => count + 1);
            }} className="mt-2 underline">
              다시 검색
            </button>
          </div>
        )}
        {finished && matches.length === 0 && <p className="text-sm text-ink/60">검색 결과가 없어요. 다른 영문 이름을 입력해 주세요.</p>}
        {matches.length > 0 && (
          <>
            <p className="mb-2 text-sm text-ink/60">최대 10개 표시 · 찾는 게임이 없으면 이름을 더 입력해 주세요.</p>
            <ul aria-label="게임 검색 결과" className="max-h-64 overflow-y-auto divide-y divide-line rounded-lg border border-line">
              {matches.map((item) => (
                <li key={item.BGGId}>
                  <button
                    type="button"
                    disabled={disabled}
                    onClick={() => {
                      setQuery(item.Name);
                      setMatches([]);
                      setFinished(false);
                      setSearching(false);
                      onChange(item.Name);
                    }}
                    className="w-full px-3 py-3 text-left hover:bg-line focus-visible:outline-2 focus-visible:outline-primary"
                  >
                    <span className="font-semibold">{item.Name}</span>
                    {item.YearPublished > 0 && <span className="ml-2 text-sm text-ink/60">({item.YearPublished})</span>}
                  </button>
                </li>
              ))}
            </ul>
          </>
        )}
      </div>
    </div>
  );
}


// ---------------------------------------------------------------------
// OptionGroup: 버튼 여러 개 중에 하나를 고르는 묶음
// 인원 고르기, 시간 고르기에서 같이 재사용한다.
//
// 받는 정보(props)
//   icon     : 묶음 제목 옆에 보여줄 아이콘
//   label    : 묶음 제목 (예: "인원")
//   options  : 버튼 목록 [{ value, label }, ...]
//   value    : 지금 선택된 값
//   onChange : 버튼을 눌렀을 때 값을 바꿀 함수
//
// fieldset, legend: 관련된 입력들을 하나로 묶고 제목을 붙이는 HTML 태그
// ---------------------------------------------------------------------
function OptionGroup({ icon: Icon, label, options, value, onChange, disabled }) {
  return (
    <fieldset disabled={disabled}>
      <legend className="mb-2 flex items-center gap-1.5 text-sm font-semibold">
        <Icon className="h-4 w-4 text-primary" aria-hidden="true" />
        {label}
      </legend>
      <div className="flex flex-wrap gap-2">
        {options.map((opt) => {
          // 이 버튼이 지금 선택된 버튼인지 확인
          const selected = value === opt.value;
          // 선택된 버튼이면 진한 메인 색, 아니면 기본 흰 버튼
          // ? : 는 "조건 ? 맞을 때 : 아닐 때" 라는 뜻
          const colorClass = selected
            ? "border-primary-dark bg-primary-dark font-semibold text-card"
            : "border-line bg-card hover:border-primary";
          return (
            <button
              key={opt.value}
              type="button"
              onClick={() => onChange(opt.value)}
              aria-pressed={selected}
              className={`rounded-lg border px-4 py-2 text-sm transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary-dark ${colorClass}`}
            >
              {opt.label}
            </button>
          );
        })}
      </div>
    </fieldset>
  );
}


// ---------------------------------------------------------------------
// Results: 상황에 따라 다른 내용을 보여주는 결과 영역
// 위에서부터 순서대로 확인해서, 해당하는 것 하나만 보여준다.
// ---------------------------------------------------------------------
function Results({ gameLabel, results, loading, error, searched }) {
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
      <h2 className="mb-3 flex items-center gap-2 text-lg font-bold">
        <Dices className="h-5 w-5 text-primary" aria-hidden="true" />
        {withWa(gameLabel)} 비슷한 게임
      </h2>
      {/* divide-y: 목록 줄 사이에 구분선 넣기 */}
      {/* i는 0부터 시작하는 순서라서 rank는 i + 1 (1위, 2위...) */}
      <ul className="divide-y divide-line rounded-xl border border-line bg-card px-5">
        {results.map((g, i) => (
          <GameRow key={g.BGGId ?? g.Name} game={g} rank={i + 1} />
        ))}
      </ul>
    </section>
  );
}


// ---------------------------------------------------------------------
// GameRow: 추천 결과 목록의 한 줄
//
// 받는 정보(props)
//   game : 게임 정보 하나 (이름, 이미지, 난이도, 시간 등)
//   rank : 순위 (1, 2, 3...)
// ---------------------------------------------------------------------
function GameRow({ game, rank }) {
  // 이미지 주소가 있는데 불러오기에 실패했는지 기억하는 값
  const [imgFailed, setImgFailed] = useState(false);

  // 난이도를 소수점 한 자리로 표시 (예: 1.79 -> "1.8")
  // 값이 없으면 0으로 처리
  const weight = (game.GameWeight ?? 0).toFixed(1);

  // 플레이 시간 글자 만들기
  // 실제 데이터의 누락·잘못된 시간 범위는 숫자 대신 안내
  // 최소·최대가 같으면 "30분", 다르면 "30~45분"
  const time =
    !(game.ComMinPlaytime > 0 && game.ComMaxPlaytime >= game.ComMinPlaytime)
      ? "시간 정보 없음"
      : game.ComMinPlaytime === game.ComMaxPlaytime
        ? `${game.ComMaxPlaytime}분`
        : `${game.ComMinPlaytime}~${game.ComMaxPlaytime}분`;

  return (
    <li className="flex items-center gap-4 py-4">
      {/* 왼쪽: 순위 숫자 */}
      <span className="w-5 text-center text-sm font-semibold text-ink/50">{rank}</span>

      {/* 가운데: 게임 표지 이미지 (정사각형) */}
      {/* 이미지 주소가 있고 실패하지 않았으면 이미지, 없거나 실패했으면 주사위 아이콘 */}
      <div className="flex h-16 w-16 shrink-0 items-center justify-center overflow-hidden rounded-lg bg-line">
        {game.ImagePath && !imgFailed ? (
          <img
            src={game.ImagePath}
            alt=""
            onError={() => setImgFailed(true)}
            className="h-full w-full object-cover"
          />
        ) : (
          <Dices className="h-7 w-7 text-primary" strokeWidth={1.75} aria-hidden="true" />
        )}
      </div>

      {/* 오른쪽: 게임 이름과 정보 */}
      {/* min-w-0, truncate: 이름이 너무 길면 "..."으로 자르기 */}
      <div className="min-w-0">
        <h3 className="truncate font-semibold">{game.Name}</h3>
        <p className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-ink/60">
          <span className="inline-flex items-center gap-1">
            <Clock className="h-3.5 w-3.5" aria-hidden="true" />
            {time}
          </span>
          <span className="inline-flex items-center gap-1">
            <Gauge className="h-3.5 w-3.5" aria-hidden="true" />
            난이도 {weight} / 5
          </span>
        </p>
      </div>
    </li>
  );
}
