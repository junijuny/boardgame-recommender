// ---------------------------------------------------------------------
// GenreScreen: 장르별 대표 게임 둘러보기 화면
// 장르 버튼을 고르면 그 장르의 대표 게임 카드가 보이고,
// 카드를 누르면 상세 팝업이 열린다.
// 장르 목록은 한 번만 서버에서 받아오고 (TanStack Query가 기억해 둠),
// 장르를 바꿀 때는 이미 받아 둔 목록에서 골라 보여준다.
//
// 로딩 상태
//   처음 불러오는 중   : 장르 버튼과 카드 자리에 로딩 뼈대
//   4초 넘게 걸리면    : 뼈대 위에 "Starting the server" 안내
//   다시 불러오는 중   : 기존 카드는 그대로, 제목 옆에 "Updating…" (헤더에는 진행 막대)
//
// 새로고침(Refresh): 지금 장르에서 이미 본 게임을 빼고 다른 게임 6개를 보여 준다.
//   장르마다 따로 기억하므로 다른 장르에 다녀와도 새로고침한 목록이 그대로 남는다.
//   더 보여 줄 게임이 없으면 안내와 함께 대표 게임 목록으로 돌아갈 수 있다.
//
// 받는 정보(props)
//   onRecommendSimilar : 상세 팝업에서 "Find similar games"를 눌렀을 때 실행할 함수
// ---------------------------------------------------------------------
import clsx from "clsx";
import { useState } from "react";
import { RefreshCw, SearchX } from "lucide-react";
import DifficultyPips from "../components/DifficultyPips";
import GameDetailModal from "../components/GameDetailModal";
import GameThumb from "../components/GameThumb";
import { ErrorNotice, ServerWakeNotice, Skeleton } from "../components/LoadingParts";
import { formatPlaytime, formatScore } from "../format";
import { useGenreRefresh, useGenres, useIsSlow } from "../queries";
import { choiceColor, container, focusRing, pageTitle } from "../styles";
import type { GameDetail, GenreGame } from "../types";

interface GenreScreenProps {
  onRecommendSimilar: (game: GameDetail) => void;
}

// 장르 key → 화면에 보여줄 영어 이름 (백엔드 label은 한국어)
const GENRE_LABELS: Record<string, string> = {
  strategy: "Strategy",
  family: "Family",
  party: "Party",
  thematic: "Thematic",
  war: "Wargames",
  childrens: "Children’s",
  cgs: "Card games",
  deduction: "Deduction",
};

export default function GenreScreen({ onRecommendSimilar }: GenreScreenProps) {
  const genres = useGenres();
  // 처음 불러오는 중이거나, 실패한 뒤 "Try again"으로 다시 불러오는 중
  const loading = genres.isPending || (genres.isError && genres.isFetching);
  // 지금 고른 장르의 key (처음엔 첫 번째 장르)
  const [activeKey, setActiveKey] = useState("");
  // 상세 팝업으로 보고 있는 게임 ID (닫혀 있으면 null)
  const [selectedId, setSelectedId] = useState<number | null>(null);

  // 새로고침: 장르 key → 새로고침해서 받은 게임 목록 / 지금까지 본 게임 ID
  const [refreshed, setRefreshed] = useState<Record<string, GenreGame[]>>({});
  const [seen, setSeen] = useState<Record<string, number[]>>({});
  // 더 보여 줄 게임이 없었던 장르 key
  const [exhaustedKey, setExhaustedKey] = useState<string | null>(null);
  const refresh = useGenreRefresh();

  const list = genres.data ?? [];
  // 고른 장르가 없거나 목록에 없으면 첫 번째 장르를 보여줌
  const active = list.find((g) => g.key === activeKey) ?? list[0];
  const updating = genres.isFetching && !genres.isPending;

  // 지금 보이는 장르의 새로고침 상태
  const refreshing = refresh.isPending && refresh.variables?.key === active?.key;
  const refreshFailed = refresh.isError && refresh.variables?.key === active?.key;
  const games = (active && refreshed[active.key]) ?? active?.games ?? [];
  const slow = useIsSlow(loading || refreshing);

  function handleRefresh() {
    if (!active || refresh.isPending) return;
    const key = active.key;
    // 처음 새로고침이면 대표 게임 6개를, 그 뒤로는 지금까지 본 게임을 모두 뺀다
    const exclude = seen[key] ?? active.games.map((g) => g.BGGId);
    setExhaustedKey(null);
    refresh.mutate(
      { key, exclude },
      {
        onSuccess: (next) => {
          if (next.length === 0) {
            setExhaustedKey(key);
            return;
          }
          setRefreshed((prev) => ({ ...prev, [key]: next }));
          setSeen((prev) => ({ ...prev, [key]: [...exclude, ...next.map((g) => g.BGGId)] }));
        },
      },
    );
  }

  // 새로고침한 목록을 지우고 대표 게임으로 돌아가기
  function handleShowTop() {
    if (!active) return;
    const key = active.key;
    setRefreshed((prev) => withoutKey(prev, key));
    setSeen((prev) => withoutKey(prev, key));
    setExhaustedKey(null);
    refresh.reset();
  }

  return (
    <main className={clsx(container, "flex flex-col gap-7 pt-7 pb-12 sm:pt-10 sm:pb-16")}>
      <div className="flex flex-wrap items-end justify-between gap-x-4 gap-y-3">
        <div className="flex flex-wrap items-baseline gap-x-4 gap-y-2">
          <h1 className={pageTitle}>Top games by genre</h1>
          {updating && <p role="status" className="text-sm font-medium text-ink/70">Updating…</p>}
        </div>
        {/* 새로고침: 지금 장르에서 본 게임을 빼고 다른 게임 6개 */}
        {active && (
          <button
            type="button"
            onClick={handleRefresh}
            disabled={refreshing}
            className={clsx(
              "inline-flex min-h-11 items-center gap-2 rounded-xl border-[1.5px] border-primary bg-card px-4 text-[15px] font-bold text-primary transition-colors hover:bg-line disabled:opacity-60",
              focusRing,
            )}
          >
            <RefreshCw className={clsx("h-[18px] w-[18px]", refreshing && "motion-safe:animate-spin")} aria-hidden="true" />
            Refresh
          </button>
        )}
      </div>

      {slow && <ServerWakeNotice />}

      {loading && <GenreSkeleton />}

      {genres.isError && !genres.isFetching && !genres.data && (
        <ErrorNotice message="Couldn't load genres. Check that the server is running." onRetry={() => genres.refetch()} />
      )}

      {active && (
        <>
          <div role="group" aria-label="Genre" className="flex flex-wrap gap-2">
            {list.map((genre) => {
              const selected = genre.key === active.key;
              return (
                <button
                  key={genre.key}
                  type="button"
                  aria-pressed={selected}
                  onClick={() => setActiveKey(genre.key)}
                  className={clsx("min-h-11 rounded-full border-[1.5px] px-[18px] text-[15px] font-bold transition-colors", focusRing, selected ? choiceColor(true) : "border-ink/25 bg-card hover:border-primary")}
                >
                  {GENRE_LABELS[genre.key] ?? genre.label}
                </button>
              );
            })}
          </div>

          <section
            aria-label={`${GENRE_LABELS[active.key] ?? active.label} games`}
            aria-live="polite"
            aria-busy={refreshing}
            className="flex flex-col gap-4"
          >
            {refreshFailed && (
              <ErrorNotice message="Couldn't load other games." onRetry={handleRefresh} />
            )}
            {exhaustedKey === active.key && (
              <div className="flex flex-col items-center gap-2 rounded-[20px] border border-line bg-card px-5 py-8 text-center text-ink/70">
                <SearchX className="h-8 w-8 text-primary" aria-hidden="true" />
                <p>You've seen every game we can find in this genre.</p>
                <button type="button" onClick={handleShowTop} className={clsx("min-h-11 rounded-lg px-2 font-bold text-primary underline", focusRing)}>
                  Back to top games
                </button>
              </div>
            )}
            {refreshing ? (
              <>
                <p role="status" className="sr-only">Loading other games</p>
                <CardSkeletons />
              </>
            ) : (
              <ul className="grid grid-cols-[repeat(auto-fill,minmax(min(100%,300px),1fr))] gap-4">
                {games.map((game, i) => (
                  <li key={game.BGGId}>
                    {/* 순위 번호는 대표 게임 목록에서만 (새로고침한 목록은 순위가 아님) */}
                    <GameCard game={game} rank={refreshed[active.key] ? undefined : i + 1} onSelect={setSelectedId} />
                  </li>
                ))}
              </ul>
            )}
          </section>
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

// 객체에서 key 하나만 뺀 새 객체
function withoutKey<T>(record: Record<string, T>, key: string): Record<string, T> {
  const next = { ...record };
  delete next[key];
  return next;
}

// 처음 불러오는 동안 장르 버튼 8개와 카드 6장 자리를 미리 보여 준다
function GenreSkeleton() {
  return (
    <div className="flex flex-col gap-7">
      <p role="status" className="sr-only">Loading genres</p>
      <div className="flex flex-wrap gap-2" aria-hidden="true">
        {[92, 84, 78, 104, 112, 108, 118, 110].map((width, i) => (
          <Skeleton key={i} className="h-11 rounded-full" style={{ width }} />
        ))}
      </div>
      <CardSkeletons />
    </div>
  );
}

// 게임 카드 6장 자리 (처음 불러올 때와 새로고침할 때 같이 씀)
function CardSkeletons() {
  return (
    <ul className="grid grid-cols-[repeat(auto-fill,minmax(min(100%,300px),1fr))] gap-4" aria-hidden="true">
      {[62, 48, 70, 54, 66, 44].map((width, i) => (
        <li key={i} className="flex flex-col overflow-hidden rounded-2xl border border-line bg-card">
          <Skeleton className="aspect-[16/10]" />
          <span className="flex flex-col gap-2.5 p-[18px]">
            <Skeleton className="h-[18px] rounded-md" style={{ width: `${width}%` }} />
            <Skeleton className="h-3.5 w-4/5 rounded-md" />
          </span>
        </li>
      ))}
    </ul>
  );
}

// 장르 화면의 게임 카드 한 장 (누르면 상세 팝업)
function GameCard({ game, rank, onSelect }: { game: GenreGame; rank?: number; onSelect: (bggId: number) => void }) {
  return (
    <button
      type="button"
      onClick={() => onSelect(game.BGGId)}
      aria-haspopup="dialog"
      className={clsx("group flex h-full w-full flex-col overflow-hidden rounded-2xl border border-line bg-card text-left transition-colors hover:border-primary", focusRing)}
    >
      <span className="relative block w-full">
        <GameThumb src={game.ImagePath} name={game.Name} className="aspect-[16/10] w-full" letterClassName="text-[64px]" />
        {rank != null && (
          <span className="absolute top-3 left-3 inline-flex h-8 min-w-8 items-center justify-center rounded-full bg-primary px-2 font-display text-[15px] font-extrabold text-card">
            {rank}
          </span>
        )}
      </span>
      <span className="flex flex-1 flex-col gap-2 px-[18px] pt-4 pb-[18px]">
        <span className="text-lg leading-snug font-bold group-hover:underline">
          {game.Name}
          {game.YearPublished > 0 && <span className="ml-1.5 text-sm font-normal text-ink/70">{game.YearPublished}</span>}
        </span>
        <span className="mt-auto flex flex-wrap items-center gap-x-4 gap-y-1.5 text-sm text-ink/70">
          <span>{formatPlaytime(game)}</span>
          <span className="inline-flex items-center gap-1.5">
            Difficulty
            <DifficultyPips weight={game.GameWeight} />
            {formatScore(game.GameWeight)}
          </span>
          <span>Rating {formatScore(game.BayesAvgRating)}</span>
        </span>
      </span>
    </button>
  );
}
