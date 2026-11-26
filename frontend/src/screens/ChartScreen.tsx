// ---------------------------------------------------------------------
// ChartScreen: 인기 차트 화면 (주소 /charts)
// 고를 게임도 장르도 없는 사용자에게 "많은 사람이 좋아하는 게임"을 순위로 보여 준다.
// 차트 버튼(Top ranked, Most owned, Most wanted, Recent hits)을 고르면
// 그 차트의 1~10위가 한 줄에 한 게임씩 순위 리스트로 보이고,
// 줄을 누르면 상세 팝업이 열린다.
// 차트 4개는 한 번에 받아 두고 (TanStack Query가 기억), 버튼을 바꿀 때는 받아 둔 목록에서 고른다.
//
// 장르 화면(카드 그리드)과 구분되도록 순위 숫자가 큰 리스트 모양을 쓴다.
// 줄 오른쪽에는 차트마다 그 차트의 기준 숫자를 크게 보여 준다. (예: Most owned -> "166k own it")
//
// 로딩 상태
//   처음 불러오는 중   : 차트 버튼과 리스트 자리에 로딩 뼈대
//   4초 넘게 걸리면    : 뼈대 위에 "Starting the server" 안내
//
// 받는 정보(props)
//   onRecommendSimilar : 상세 팝업에서 "Find similar games"를 눌렀을 때 실행할 함수
// ---------------------------------------------------------------------
import clsx from "clsx";
import { useState } from "react";
import DifficultyPips from "../components/DifficultyPips";
import GameDetailModal from "../components/GameDetailModal";
import GameThumb from "../components/GameThumb";
import { ErrorNotice, ServerWakeNotice, Skeleton } from "../components/LoadingParts";
import { formatCount, formatPlaytime, formatScore } from "../format";
import { useCharts, useIsSlow } from "../queries";
import { choiceColor, container, focusRing, pageTitle } from "../styles";
import type { Chart, ChartGame, GameDetail } from "../types";

interface ChartScreenProps {
  onRecommendSimilar: (game: GameDetail) => void;
}

// 차트 key -> 화면에 보여줄 이름과 설명
// 백엔드 label을 그대로 쓰지 않는 이유: 데이터가 2021년 BGG 스냅샷이라
// "New & Popular"의 2019~2021년 게임은 지금 기준으로 신작이 아니다.
const CHART_TEXT: Record<Chart["key"], { label: string; description: string }> = {
  top: { label: "Top ranked", description: "Highest overall BoardGameGeek rank" },
  most_owned: { label: "Most owned", description: "Games the most people own" },
  most_wanted: { label: "Most wanted", description: "Most added to wishlists" },
  new: { label: "Recent hits", description: "Top rated 2019–2021 releases" },
};

// 차트마다 줄 오른쪽에 크게 보여 줄 숫자와 그 아래 작은 설명
const CHART_STAT: Record<Chart["key"], (game: ChartGame) => { value: string; caption: string }> = {
  top: (game) => ({ value: `#${game.BggRank}`, caption: "on BGG" }),
  most_owned: (game) => ({ value: formatCount(game.NumOwned), caption: "own it" }),
  most_wanted: (game) => ({ value: formatCount(game.NumWish), caption: "want it" }),
  new: (game) => ({ value: formatScore(game.BayesAvgRating), caption: "rating" }),
};

export default function ChartScreen({ onRecommendSimilar }: ChartScreenProps) {
  const charts = useCharts();
  // 처음 불러오는 중이거나, 실패한 뒤 "Try again"으로 다시 불러오는 중
  const loading = charts.isPending || (charts.isError && charts.isFetching);
  const slow = useIsSlow(loading);
  // 지금 고른 차트의 key (처음엔 첫 번째 차트)
  const [activeKey, setActiveKey] = useState("");
  // 상세 팝업으로 보고 있는 게임 ID (닫혀 있으면 null)
  const [selectedId, setSelectedId] = useState<number | null>(null);

  const list = charts.data ?? [];
  const active = list.find((c) => c.key === activeKey) ?? list[0];
  const updating = charts.isFetching && !charts.isPending;

  return (
    <main className={clsx(container, "flex flex-col gap-7 pt-7 pb-12 sm:pt-10 sm:pb-16")}>
      <div className="flex flex-wrap items-baseline gap-x-4 gap-y-2">
        <h1 className={pageTitle}>Popular games</h1>
        {updating && <p role="status" className="text-sm font-medium text-ink/70">Updating…</p>}
      </div>

      {slow && <ServerWakeNotice />}

      {loading && <ChartSkeleton />}

      {charts.isError && !charts.isFetching && !charts.data && (
        <ErrorNotice message="Couldn't load popular games. Check that the server is running." onRetry={() => charts.refetch()} />
      )}

      {active && (
        <>
          <div role="group" aria-label="Chart" className="flex flex-wrap gap-2">
            {list.map((chart) => {
              const selected = chart.key === active.key;
              return (
                <button
                  key={chart.key}
                  type="button"
                  aria-pressed={selected}
                  onClick={() => setActiveKey(chart.key)}
                  className={clsx("min-h-11 rounded-full border-[1.5px] px-[18px] text-[15px] font-bold transition-colors", focusRing, selected ? choiceColor(true) : "border-ink/25 bg-card hover:border-primary")}
                >
                  {CHART_TEXT[chart.key]?.label ?? chart.label}
                </button>
              );
            })}
          </div>

          <section
            aria-labelledby="chart-title"
            className="overflow-hidden rounded-[20px] border border-line bg-card"
          >
            <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 border-b border-line px-5 pt-5 pb-4 sm:px-7">
              <h2 id="chart-title" className="font-display text-2xl font-extrabold">
                {CHART_TEXT[active.key]?.label ?? active.label}
              </h2>
              <p className="text-sm text-ink/70">{CHART_TEXT[active.key]?.description ?? active.description}</p>
            </div>
            <ol>
              {active.games.map((game, i) => (
                <li key={game.BGGId} className="border-b border-line last:border-b-0">
                  <ChartRow game={game} rank={i + 1} chartKey={active.key} onSelect={setSelectedId} />
                </li>
              ))}
            </ol>
          </section>

          <p className="text-sm text-ink/60">Rankings are based on BoardGameGeek data collected in 2021.</p>
        </>
      )}

      <GameDetailModal
        bggId={selectedId}
        onClose={() => setSelectedId(null)}
        onRecommendSimilar={onRecommendSimilar}
      />
    </main>
  );
}

// 차트의 한 줄: 순위 숫자 + 표지 + 이름·연도·시간 (+ 넓은 화면에서 난이도·평점) + 차트 숫자
// 휴대폰에서는 이름이 너무 잘리지 않도록 난이도와 평점을 숨긴다
function ChartRow({ game, rank, chartKey, onSelect }: { game: ChartGame; rank: number; chartKey: Chart["key"]; onSelect: (bggId: number) => void }) {
  const stat = (CHART_STAT[chartKey] ?? CHART_STAT.top)(game);
  return (
    <button
      type="button"
      onClick={() => onSelect(game.BGGId)}
      aria-haspopup="dialog"
      // 리스트 상자가 overflow-hidden이라 포커스 테두리를 바깥(focusRing)이 아니라 안쪽에 그린다
      className="group flex w-full items-center gap-3 px-4 py-3 text-left transition-colors hover:bg-page focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-primary-dark sm:gap-5 sm:px-7 sm:py-3.5"
    >
      {/* 1~3위는 크고 진하게 */}
      <span
        className={clsx(
          "w-7 shrink-0 text-center font-display font-extrabold sm:w-10",
          rank <= 3 ? "text-[28px] text-primary" : "text-xl text-ink/50",
        )}
      >
        <span className="sr-only">Rank </span>
        {rank}
      </span>
      <GameThumb src={game.ImagePath} name={game.Name} className="h-14 w-14 rounded-xl sm:h-16 sm:w-16" letterClassName="text-[26px]" />
      <span className="flex min-w-0 flex-1 flex-col gap-1">
        {/* 긴 이름(예: Pandemic Legacy: Season 1)도 휴대폰에서 알아볼 수 있게 두 줄까지 보여 준다 */}
        <span className="line-clamp-2 text-[17px] leading-snug font-bold group-hover:underline">
          {game.Name}
          {game.YearPublished > 0 && <span className="ml-1.5 text-sm font-normal text-ink/70">{game.YearPublished}</span>}
        </span>
        <span className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-ink/70">
          <span>{formatPlaytime(game)}</span>
          <span className="hidden items-center gap-1.5 sm:inline-flex">
            Difficulty
            <DifficultyPips weight={game.GameWeight} />
            {formatScore(game.GameWeight)}
          </span>
          {/* Recent hits는 오른쪽 숫자가 평점이라 여기서는 빼도 된다 */}
          {chartKey !== "new" && <span className="hidden sm:inline">Rating {formatScore(game.BayesAvgRating)}</span>}
        </span>
      </span>
      <span className="flex shrink-0 flex-col items-end leading-tight">
        <span className="font-display text-lg font-extrabold sm:text-[22px]">{stat.value}</span>
        <span className="text-xs text-ink/70">{stat.caption}</span>
      </span>
    </button>
  );
}

// 처음 불러오는 동안 차트 버튼 4개와 리스트 줄 자리를 미리 보여 준다
function ChartSkeleton() {
  return (
    <div className="flex flex-col gap-7">
      <p role="status" className="sr-only">Loading popular games</p>
      <div className="flex flex-wrap gap-2" aria-hidden="true">
        {[118, 116, 122, 108].map((width, i) => (
          <Skeleton key={i} className="h-11 rounded-full" style={{ width }} />
        ))}
      </div>
      <ul className="overflow-hidden rounded-[20px] border border-line bg-card" aria-hidden="true">
        {[58, 44, 66, 50, 62].map((width, i) => (
          <li key={i} className="flex items-center gap-3 border-b border-line px-4 py-3 last:border-b-0 sm:gap-5 sm:px-7">
            <Skeleton className="h-7 w-7 rounded-md sm:w-10" />
            <Skeleton className="h-14 w-14 rounded-xl sm:h-16 sm:w-16" />
            <span className="flex flex-1 flex-col gap-2">
              <Skeleton className="h-[18px] rounded-md" style={{ width: `${width}%` }} />
              <Skeleton className="h-3.5 w-1/3 rounded-md" />
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
