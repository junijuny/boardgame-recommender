// ---------------------------------------------------------------------
// DescriptionSearch: "By description" 탭. 원하는 게임을 말로 설명하고, 인원과 플레이 시간을
// 고르면 설명에 맞는 보드게임 5개를 보여준다. (한국어로 써도 된다)
// 왼쪽(휴대폰에서는 위)은 조건 입력, 오른쪽(아래)은 결과. "Refresh"는 본 게임을 빼고 다음 5개.
//
// 받는 정보(props)
//   onShowDetail : 결과를 눌렀을 때 상세 팝업을 열어 달라고 부탁하는 함수 (팝업은 화면이 하나만 둔다)
// ---------------------------------------------------------------------
import clsx from "clsx";
import { useState } from "react";
import { RefreshCw, Search } from "lucide-react";
import { ResultList, ResultSkeleton } from "./ResultList";
import { PlayerPicker, TimePicker } from "./ChoicePickers";
import { ErrorNotice, ServerWakeNotice } from "./LoadingParts";
import { NoMatchNotice } from "./SearchNotice";
import { errorResponse } from "../api";
import { PLAYER_OPTIONS, TIME_OPTIONS } from "../filters";
import { formatMinutes } from "../format";
import { useExplanations, useIsSlow, useNaturalSearch, useServerInfo } from "../queries";
import { focusRing, primaryButton } from "../styles";
import type { NaturalSearchRequest } from "../types";

interface DescriptionSearchProps {
  onShowDetail: (bggId: number) => void;
}

export default function DescriptionSearch({ onShowDetail }: DescriptionSearchProps) {
  const [query, setQuery] = useState("");
  const [players, setPlayers] = useState(4);
  const [maxTime, setMaxTime] = useState(60);
  // 지금 조건으로 지금까지 보여 준 게임 ID ("Refresh"를 누를 때 이 게임들은 빼고 받는다)
  const [shownIds, setShownIds] = useState<number[]>([]);

  const search = useNaturalSearch();
  const loading = search.isPending;
  const slow = useIsSlow(loading);
  // 한 문장 추천 이유: 서버가 켜 둔 경우에만, 검색이 성공한 뒤에 요청한다.
  const explanationsOn = useServerInfo().data?.explanations === true;
  const results = search.data;
  const explanations = useExplanations(
    explanationsOn && results && search.variables
      ? { mode: "query", basis: search.variables.query, game_ids: results.map((g) => g.BGGId) }
      : null,
  );

  // 조건을 바꾸면 이전 결과는 지운다 (지금 조건과 안 맞으므로)
  function clearResults() {
    search.reset();
    setShownIds([]);
  }

  // 검색 요청 보내기. exclude: 결과에서 뺄 게임 ID
  function requestSearch(exclude: number[], request?: NaturalSearchRequest) {
    const body = request ?? { query: query.trim(), players, max_time: maxTime, exclude_ids: exclude };
    if (!body.query || loading) return;
    search.mutate(body, {
      onSuccess: (games) => setShownIds([...exclude, ...games.map((g) => g.BGGId)]),
    });
  }

  // "Get recommendations": 처음부터 다시
  function handleSearch() {
    requestSearch([]);
  }

  // "Refresh": 지금까지 본 게임을 빼고 다음 5개
  function handleRefresh() {
    requestSearch(shownIds);
  }

  // 실패한 요청을 보냈던 조건 그대로 다시 보내기
  function handleRetry() {
    const last = search.variables;
    if (last) requestSearch(last.exclude_ids ?? [], last);
  }

  return (
    <div className="flex flex-wrap items-start gap-6">
      <form
        aria-label="Description search filters"
        onSubmit={(event) => {
          event.preventDefault();
          handleSearch();
        }}
        className="flex min-w-0 flex-[1_1_340px] flex-col gap-7 rounded-[20px] border border-line bg-card p-5 sm:p-7"
      >
        <div className="flex flex-col gap-2.5">
          <label htmlFor="description-query" className="font-bold">Describe the game you want</label>
          <input
            id="description-query"
            type="text"
            value={query}
            maxLength={300}
            disabled={loading}
            autoComplete="off"
            placeholder="e.g. a cooperative game with no dice, under an hour"
            onChange={(event) => {
              setQuery(event.target.value);
              clearResults();
            }}
            className="min-h-12 w-full rounded-xl border-[1.5px] border-ink/35 bg-page px-3.5 text-base focus:border-primary-dark focus:outline-none disabled:opacity-60"
          />
        </div>
        <PlayerPicker
          options={PLAYER_OPTIONS}
          value={players}
          disabled={loading}
          onChange={(value) => { setPlayers(value); clearResults(); }}
        />
        <TimePicker
          options={TIME_OPTIONS}
          value={maxTime}
          disabled={loading}
          onChange={(value) => { setMaxTime(value); clearResults(); }}
        />
        <button type="submit" disabled={loading || !query.trim()} className={clsx(primaryButton, "w-full text-lg")}>
          <Search className="h-5 w-5" aria-hidden="true" />
          Get recommendations
        </button>
      </form>

      <section
        aria-labelledby="description-result-title"
        aria-live="polite"
        aria-busy={loading}
        className="flex min-w-0 flex-[999_1_540px] flex-col gap-4"
      >
        <div className="flex flex-wrap items-end justify-between gap-x-4 gap-y-2 px-1 pt-1">
          <div className="flex min-w-0 flex-col gap-1.5">
            <h2 id="description-result-title" className="font-display text-[26px] font-extrabold tracking-[-0.01em]">Results</h2>
            {search.variables && <p className="break-words text-[15px] text-ink/70">{summarize(search.variables)}</p>}
          </div>
          {search.isSuccess && (
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
        {loading && <ResultSkeleton label="Finding games" />}
        {search.isError && (
          <DescriptionError
            error={search.error}
            afterRefresh={(search.variables?.exclude_ids?.length ?? 0) > 0}
            onRetry={handleRetry}
            onStartOver={handleSearch}
          />
        )}
        {search.isSuccess && (
          <ResultList
            items={search.data.map((g) => ({ game: g, chips: [...g.MatchedMechanics, ...g.MatchedThemes].slice(0, 3) }))}
            reasons={explanations.data?.reasons}
            reasonsLoading={explanations.isFetching}
            onSelect={onShowDetail}
          />
        )}
        {search.isIdle && (
          <p className="rounded-[20px] border border-dashed border-ink/25 px-5 py-8 text-center text-ink/70">
            Describe the kind of game you want to play.
          </p>
        )}
      </section>
    </div>
  );
}

// 결과 위의 조건 요약. 예) 'Matching "co-op, no dice", 4 players, up to 1 hr'
function summarize({ query, players, max_time }: NaturalSearchRequest) {
  return `Matching "${query}", ${players} players, up to ${formatMinutes(max_time)}`;
}

// 검색 실패: 조건에 맞는 게임이 없으면 안내, 그 밖에는 오류 메시지
interface DescriptionErrorProps {
  error: unknown;
  afterRefresh: boolean;
  onRetry: () => void;
  onStartOver: () => void;
}

function DescriptionError({ error, afterRefresh, onRetry, onStartOver }: DescriptionErrorProps) {
  const response = errorResponse(error);
  const status = response?.status;
  const detail = response?.data?.detail;

  if (status === 404 && detail === "No games match the selected conditions") {
    return <NoMatchNotice afterRefresh={afterRefresh} onStartOver={onStartOver} />;
  }
  if (status === 429) {
    return <ErrorNotice message="Too many searches. Wait a minute and try again." />;
  }
  if (status === 503) {
    return <ErrorNotice message='Description search is unavailable right now. Try "By game" instead.' />;
  }
  if (status === 400 || status === 422) {
    return <ErrorNotice message="Check the description, player count and play time." />;
  }
  if (!response) {
    return <ErrorNotice message="Can't reach the server." onRetry={onRetry} />;
  }
  return <ErrorNotice message="Couldn't load recommendations." onRetry={onRetry} />;
}
