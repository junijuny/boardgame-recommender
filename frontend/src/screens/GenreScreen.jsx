
import { useEffect, useState } from "react";
import {
  ArrowLeft,
  CircleAlert,
  Clock,
  Gauge,
  LoaderCircle,
} from "lucide-react";

import { getGenres, getGenreGames } from "../api.js";
import { formatPlaytime } from "../format.js";
import { backButton, choiceClass } from "../styles.js";
import GameDetailModal from "../components/GameDetailModal.jsx";
import GameThumb from "../components/GameThumb.jsx";

export default function GenreScreen({ onBack, onRecommendSimilar }) {
  const [genres, setGenres] = useState([]);
  const [status, setStatus] = useState("loading");
  const [retry, setRetry] = useState(0);
  const [activeKey, setActiveKey] = useState("");
  const [selectedId, setSelectedId] = useState(null);

  // 사용자가 선택한 플레이 조건
  const [players, setPlayers] = useState(2);
  const [maxTime, setMaxTime] = useState(60);

  // 조건 검색 결과와 상태
  const [results, setResults] = useState(null);
  const [resultStatus, setResultStatus] = useState("idle");
  const [applied, setApplied] = useState(null);
  const [resultRetry, setResultRetry] = useState(0);

  // 최초 장르 목록 로딩
  useEffect(() => {
    let ignore = false;

    getGenres()
      .then((data) => {
        if (ignore) return;
        setGenres(data);
        setStatus("ok");
      })
      .catch((err) => {
        if (ignore) return;
        console.error(err);
        setStatus("error");
      });

    return () => {
      ignore = true;
    };
  }, [retry]);

  const active = genres.find((g) => g.key === activeKey) ?? genres[0];

  // 조건 검색 요청
  useEffect(() => {
    if (!applied) return;

    const controller = new AbortController();

    getGenreGames(
      applied.genreKey,
      applied.players,
      applied.maxTime,
      controller.signal
    )
      .then((data) => {
        if (controller.signal.aborted) return;
        setResults(data);
        setResultStatus("ok");
      })
      .catch((err) => {
        if (controller.signal.aborted) return;
        console.error(err);
        setResultStatus("error");
      });

    return () => controller.abort();
  }, [applied, resultRetry]);

  function handleSearch() {
    if (!active) return;

    setResults(null);
    setResultStatus("loading");
    setApplied({
      genreKey: active.key,
      players,
      maxTime,
    });
    setResultRetry((n) => n + 1);
  }

  function handleGenreChange(key) {
    setActiveKey(key);
    setApplied(null);
    setResults(null);
    setResultStatus("idle");
  }

  function handleReset() {
    setApplied(null);
    setResults(null);
    setResultStatus("idle");
  }

  const showingResults =
    applied !== null &&
    applied.genreKey === active?.key &&
    resultStatus === "ok";

  const games = showingResults ? results ?? [] : active?.games ?? [];

  return (
    <div className="min-h-screen px-4 py-12">
      <main className="mx-auto max-w-3xl">
        <button
          type="button"
          onClick={onBack}
          className={backButton}
        >
          <ArrowLeft className="h-4 w-4" aria-hidden="true" />
          처음으로
        </button>

        <header className="mb-8">
          <h1 className="text-3xl font-bold tracking-tight">
            장르별 맞춤 게임 추천
          </h1>
          <p className="mt-2 text-ink/70">
            원하는 장르와 플레이 인원, 시간을 선택하면
            조건에 맞는 게임을 추천해 드려요.
          </p>
        </header>

        {status === "loading" && (
          <p className="flex items-center justify-center gap-2 py-12 text-ink/60">
            <LoaderCircle
              className="h-5 w-5 motion-safe:animate-spin"
              aria-hidden="true"
            />
            장르 정보를 불러오는 중...
          </p>
        )}

        {status === "error" && (
          <div className="rounded-lg border border-danger/40 bg-danger/10 px-4 py-3 text-danger">
            <p className="flex items-start gap-2">
              <CircleAlert
                className="mt-0.5 h-5 w-5 shrink-0"
                aria-hidden="true"
              />
              장르 정보를 불러오지 못했습니다.
              서버가 켜져 있는지 확인해 주세요.
            </p>
            <button
              type="button"
              onClick={() => {
                setStatus("loading");
                setRetry((n) => n + 1);
              }}
              className="mt-2 text-sm underline"
            >
              다시 시도
            </button>
          </div>
        )}

        {status === "ok" && active && (
          <>
            {/* 장르 선택 */}
            <div
              role="group"
              aria-label="장르 선택"
              className="flex flex-wrap gap-2"
            >
              {genres.map((genre) => {
                const selected = genre.key === active.key;

                return (
                  <button
                    key={genre.key}
                    type="button"
                    aria-pressed={selected}
                    onClick={() => handleGenreChange(genre.key)}
                    className={choiceClass(selected)}
                  >
                    {genre.label}
                  </button>
                );
              })}
            </div>

            {/* 플레이 조건 선택 */}
            <section className="mt-6 rounded-xl border border-line bg-card p-5">
              <h2 className="text-lg font-bold">
                플레이 조건 선택
              </h2>
              <p className="mt-1 text-sm text-ink/60">
                함께 플레이할 인원과 최대 시간을 선택해 주세요.
              </p>

              <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
                <div>
                  <label
                    htmlFor="genre-players"
                    className="mb-2 block text-sm font-semibold"
                  >
                    플레이 인원
                  </label>

                  <select
                    id="genre-players"
                    value={players}
                    onChange={(e) =>
                      setPlayers(Number(e.target.value))
                    }
                    className="w-full rounded-lg border border-line bg-card px-3 py-3 text-ink"
                  >
                    {Array.from(
                      { length: 10 },
                      (_, i) => i + 1
                    ).map((n) => (
                      <option key={n} value={n}>
                        {n}명
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label
                    htmlFor="genre-time"
                    className="mb-2 block text-sm font-semibold"
                  >
                    최대 플레이 시간
                  </label>

                  <select
                    id="genre-time"
                    value={maxTime}
                    onChange={(e) =>
                      setMaxTime(Number(e.target.value))
                    }
                    className="w-full rounded-lg border border-line bg-card px-3 py-3 text-ink"
                  >
                    {[15, 30, 45, 60, 90, 120, 180, 240].map(
                      (minutes) => (
                        <option key={minutes} value={minutes}>
                          {minutes}분
                        </option>
                      )
                    )}
                  </select>
                </div>
              </div>

              <div className="mt-5 flex flex-wrap gap-3">
                <button
                  type="button"
                  onClick={handleSearch}
                  disabled={resultStatus === "loading"}
                  className="rounded-lg bg-primary px-5 py-3 font-semibold text-white transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {resultStatus === "loading"
                    ? "추천 게임 찾는 중..."
                    : "조건에 맞는 게임 추천받기"}
                </button>

                {applied && (
                  <button
                    type="button"
                    onClick={handleReset}
                    className="rounded-lg border border-line px-4 py-3 text-sm font-semibold hover:bg-line/30"
                  >
                    대표 게임 보기
                  </button>
                )}
              </div>
            </section>

            {/* 게임 목록 */}
            <section className="mt-8" aria-live="polite">
              <h2 className="text-lg font-bold">
                {active.label}
                <span className="ml-2 text-sm font-normal text-ink/60">
                  {active.description}
                </span>
              </h2>

              <p className="mt-2 text-sm text-ink/60">
                {showingResults
                  ? `${applied.players}명 · 최대 ${applied.maxTime}분 · 추천 게임 ${games.length}개`
                  : "장르별 평점이 높은 대표 게임 6개"}
              </p>

              {resultStatus === "loading" && (
                <p className="flex items-center gap-2 py-8 text-ink/60">
                  <LoaderCircle
                    className="h-5 w-5 motion-safe:animate-spin"
                    aria-hidden="true"
                  />
                  조건에 맞는 게임을 찾고 있어요...
                </p>
              )}

              {resultStatus === "error" && (
                <div className="mt-4 rounded-lg border border-danger/40 bg-danger/10 p-4 text-danger">
                  <p>게임을 불러오지 못했습니다.</p>
                  <button
                    type="button"
                    onClick={handleSearch}
                    className="mt-2 text-sm underline"
                  >
                    다시 시도
                  </button>
                </div>
              )}

              {showingResults && games.length === 0 && (
                <div className="mt-4 rounded-lg border border-line p-6 text-center">
                  <p className="font-semibold">
                    조건에 맞는 게임이 없어요.
                  </p>
                  <p className="mt-2 text-sm text-ink/60">
                    플레이 인원이나 최대 시간을 변경해 보세요.
                  </p>
                </div>
              )}

              {(resultStatus === "idle" || showingResults) &&
                games.length > 0 && (
                  <ul className="mt-4 grid grid-cols-2 gap-4 sm:grid-cols-3">
                    {games.map((game) => (
                      <li key={game.BGGId}>
                        <GameCard
                          game={game}
                          onSelect={setSelectedId}
                        />
                      </li>
                    ))}
                  </ul>
                )}
            </section>
          </>
        )}
      </main>

      {/* 기존 상세 팝업 유지 */}
      <GameDetailModal
        bggId={selectedId}
        onClose={() => setSelectedId(null)}
        onRecommendSimilar={onRecommendSimilar}
      />
    </div>
  );
}

// 기존 게임 카드 디자인 유지
function GameCard({ game, onSelect }) {
  return (
    <button
      type="button"
      onClick={() => onSelect(game.BGGId)}
      aria-haspopup="dialog"
      className="group flex h-full w-full flex-col overflow-hidden rounded-xl border border-line bg-card text-left transition-colors hover:border-primary focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary-dark"
    >
      <GameThumb
        src={game.ImagePath}
        className="aspect-square w-full"
        iconClassName="h-10 w-10"
      />

      <div className="flex flex-1 flex-col p-3">
        <h3 className="line-clamp-2 font-semibold leading-snug group-hover:underline">
          {game.Name}
        </h3>

        <p className="mt-auto flex flex-wrap gap-x-3 gap-y-1 pt-2 text-xs text-ink/60">
          <span className="inline-flex items-center gap-1">
            <Clock className="h-3.5 w-3.5" aria-hidden="true" />
            {formatPlaytime(game)}
          </span>

          <span className="inline-flex items-center gap-1">
            <Gauge className="h-3.5 w-3.5" aria-hidden="true" />
            {(game.GameWeight ?? 0).toFixed(1)} / 5
          </span>
        </p>
      </div>
    </button>
  );
}
