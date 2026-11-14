// ---------------------------------------------------------------------
// RecommendScreen: 조건을 고르고 추천을 받는 화면
// 왼쪽(휴대폰에서는 위)은 조건 입력, 오른쪽(아래)은 추천 결과.
// 좋아하는 게임, 인원, 플레이 시간을 고르고 "Get recommendations"를 누르면
// 비슷한 보드게임 5개를 보여준다. 결과를 누르면 상세 팝업이 열린다.
//
// 받는 정보(props)
//   initialGame        : 처음부터 선택해 둘 게임 { BGGId, Name } (없으면 null)
//   onRecommendSimilar : 상세 팝업에서 "Find similar games"를 눌렀을 때 실행할 함수
// ---------------------------------------------------------------------
import clsx from "clsx";
import { useState } from "react";
import { RefreshCw, Search, SearchX } from "lucide-react";
import GameDetailModal from "../components/GameDetailModal";
import GameSearch from "../components/GameSearch";
import { ResultList, ResultSkeleton } from "../components/ResultList";
import { PlayerPicker, TimePicker } from "../components/ChoicePickers";
import { ErrorNotice, ServerWakeNotice } from "../components/LoadingParts";
import { errorResponse } from "../api";
import { PLAYER_OPTIONS, TIME_OPTIONS } from "../filters";
import { formatMinutes } from "../format";
import { useExplanations, useIsSlow, useRecommend, useServerInfo } from "../queries";
import { container, focusRing, pageTitle, primaryButton } from "../styles";
import type { GameDetail, GameSummary, RecommendRequest } from "../types";

interface RecommendScreenProps {
  initialGame: GameSummary | null;
  onRecommendSimilar: (game: GameDetail) => void;
}

export default function RecommendScreen({ initialGame, onRecommendSimilar }: RecommendScreenProps) {
  // 검색 결과에서 선택한 게임 (선택 안 했으면 null)
  const [game, setGame] = useState<GameSummary | null>(initialGame);
  const [players, setPlayers] = useState(4);
  const [maxTime, setMaxTime] = useState(60);
  // 상세 팝업으로 보고 있는 게임 ID (닫혀 있으면 null)
  const [selectedId, setSelectedId] = useState<number | null>(null);

  // 추천 요청 (isPending: 요청 중, data: 결과, error: 실패, variables: 보낸 조건)
  const recommendation = useRecommend();
  const loading = recommendation.isPending;
  const slow = useIsSlow(loading);
  // 한 문장 추천 이유: 서버가 켜 둔 경우에만, 추천이 성공한 뒤에 요청한다.
  // 실패하거나 꺼져 있으면 reasons가 비어 카드는 기존처럼 공통 메커니즘 칩을 보여 준다.
  const explanationsOn = useServerInfo().data?.explanations === true;
  const results = recommendation.data;
  const explanations = useExplanations(
    explanationsOn && results && recommendation.variables
      ? { mode: "similar", basis: recommendation.variables.game_name, game_ids: results.map((g) => g.BGGId) }
      : null,
  );
  // 지금 조건으로 지금까지 보여 준 게임 ID ("Refresh"를 누를 때 이 게임들은 빼고 받는다)
  const [shownIds, setShownIds] = useState<number[]>([]);

  // 조건을 바꾸면 이전 결과는 지운다 (지금 조건과 안 맞으므로)
  function clearRecommendation() {
    recommendation.reset();
    setShownIds([]);
  }

  // 추천 요청 보내기. exclude: 결과에서 뺄 게임 ID
  function requestRecommendations(exclude: number[]) {
    if (!game || loading) return;
    recommendation.mutate(
      { game_name: game.Name, players, max_time: maxTime, exclude_ids: exclude },
      { onSuccess: (games) => setShownIds([...exclude, ...games.map((g) => g.BGGId)]) },
    );
  }

  // "Get recommendations": 처음부터 다시
  function handleRecommend() {
    requestRecommendations([]);
  }

  // "Refresh": 지금까지 본 게임을 빼고 다음 5개
  function handleRefresh() {
    requestRecommendations(shownIds);
  }

  // 실패한 요청을 같은 조건으로 다시 보내기
  function handleRetry() {
    requestRecommendations(recommendation.variables?.exclude_ids ?? []);
  }

  return (
    <main className={clsx(container, "flex flex-col gap-7 pt-7 pb-12 sm:pt-10 sm:pb-16")}>
      <h1 className={pageTitle}>Find similar games</h1>

      <div className="flex flex-wrap items-start gap-6">
        <form
          aria-label="Recommendation filters"
          onSubmit={(event) => {
            event.preventDefault();
            handleRecommend();
          }}
          className="flex min-w-0 flex-[1_1_340px] flex-col gap-7 rounded-[20px] border border-line bg-card p-5 sm:p-7"
        >
          <GameSearch
            value={game}
            disabled={loading}
            onChange={(picked) => {
              setGame(picked);
              clearRecommendation();
            }}
            onShowDetail={setSelectedId}
          />
          <PlayerPicker
            options={PLAYER_OPTIONS}
            value={players}
            disabled={loading}
            onChange={(value) => { setPlayers(value); clearRecommendation(); }}
          />
          <TimePicker
            options={TIME_OPTIONS}
            value={maxTime}
            disabled={loading}
            onChange={(value) => { setMaxTime(value); clearRecommendation(); }}
          />
          <button type="submit" disabled={loading || !game} className={clsx(primaryButton, "w-full text-lg")}>
            <Search className="h-5 w-5" aria-hidden="true" />
            Get recommendations
          </button>
        </form>

        <section
          aria-labelledby="result-title"
          aria-live="polite"
          aria-busy={loading}
          className="flex min-w-0 flex-[999_1_540px] flex-col gap-4"
        >
          <div className="flex flex-wrap items-end justify-between gap-x-4 gap-y-2 px-1 pt-1">
            <div className="flex min-w-0 flex-col gap-1.5">
              <h2 id="result-title" className="font-display text-[26px] font-extrabold tracking-[-0.01em]">Results</h2>
              {recommendation.variables && <p className="text-[15px] text-ink/70">{summarize(recommendation.variables)}</p>}
            </div>
            {/* 새로고침: 지금까지 본 게임은 빼고 다른 게임 5개를 받는다 */}
            {recommendation.isSuccess && (
              <button
                type="button"
                onClick={handleRefresh}
                className={clsx(
                  "inline-flex min-h-11 items-center gap-2 rounded-xl border-[1.5px] border-primary bg-card px-4 text-[15px] font-bold text-primary transition-colors hover:bg-line",
                  focusRing,
                )}
              >
                <RefreshCw className="h-[18px] w-[18px]" aria-hidden="true" />
                Refresh
              </button>
            )}
          </div>

          {slow && <ServerWakeNotice />}
          {loading && <ResultSkeleton label="Finding similar games" />}
          {recommendation.isError && (
            <RecommendError
              error={recommendation.error}
              afterRefresh={(recommendation.variables?.exclude_ids?.length ?? 0) > 0}
              onRetry={handleRetry}
              onStartOver={handleRecommend}
            />
          )}
          {recommendation.isSuccess && (
            <ResultList
              items={recommendation.data.map((g) => ({ game: g, chips: g.SharedMechanics }))}
              reasons={explanations.data?.reasons}
              reasonsLoading={explanations.isFetching}
              onSelect={setSelectedId}
            />
          )}
          {recommendation.isIdle && (
            <p className="rounded-[20px] border border-dashed border-ink/25 px-5 py-8 text-center text-ink/70">
              Pick a game to get recommendations.
            </p>
          )}
        </section>
      </div>

      <GameDetailModal
        bggId={selectedId}
        onClose={() => setSelectedId(null)}
        onRecommendSimilar={onRecommendSimilar}
      />
    </main>
  );
}

// 결과 위의 조건 요약. 예) "Based on Catan, 4 players, up to 1 hr"
function summarize({ game_name, players, max_time }: RecommendRequest) {
  return `Based on ${game_name}, ${players} players, up to ${formatMinutes(max_time)}`;
}

// 추천 실패: 조건에 맞는 게임이 없으면 안내, 그 밖에는 오류 메시지
// afterRefresh: "Refresh"로 보낸 요청이었는지 (그렇다면 남은 게임이 다 떨어진 것)
interface RecommendErrorProps {
  error: unknown;
  afterRefresh: boolean;
  onRetry: () => void;
  onStartOver: () => void;
}

function RecommendError({ error, afterRefresh, onRetry, onStartOver }: RecommendErrorProps) {
  const response = errorResponse(error);
  const status = response?.status;
  const detail = response?.data?.detail;

  if (status === 404 && detail === "No games match the selected conditions") {
    return (
      <div className="flex flex-col items-center gap-2 rounded-[20px] border border-line bg-card px-5 py-8 text-center text-ink/70">
        <SearchX className="h-8 w-8 text-primary" aria-hidden="true" />
        {afterRefresh ? (
          <>
            <p>You've seen every match for these filters.</p>
            <button type="button" onClick={onStartOver} className={clsx("min-h-11 rounded-lg px-2 font-bold text-primary underline", focusRing)}>
              Start over
            </button>
          </>
        ) : (
          <p>No games match these filters. Try more players or more time.</p>
        )}
      </div>
    );
  }
  if (status === 404 && detail === "Game not found") {
    return <ErrorNotice message="This game isn't in the dataset anymore. Pick another one." />;
  }
  if (status === 400 || status === 422) {
    return <ErrorNotice message="Check the game, player count and play time." />;
  }
  if (!response) {
    return <ErrorNotice message="Can't reach the server." onRetry={onRetry} />;
  }
  return <ErrorNotice message="Couldn't load recommendations." onRetry={onRetry} />;
}
