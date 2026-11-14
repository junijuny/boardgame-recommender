// ---------------------------------------------------------------------
// GameSearch: 데이터셋에서 게임을 검색하고 하나를 선택하는 입력창
// 검색 결과의 게임을 선택해야 추천 요청을 보낼 수 있음.
// 입력이 300ms 동안 멈추면 검색하고, 검색어가 바뀌면 이전 요청은 취소된다.
//
// 받는 정보(props)
//   value        : 지금 선택된 게임 { BGGId, Name, ... } (선택 안 했으면 null)
//                  처음부터 값이 있으면(상세 팝업에서 넘어온 경우) 입력창에 그 이름을 채워 둔다.
//   onChange     : 게임을 선택하거나 입력을 바꿨을 때 실행할 함수 (선택 해제면 null)
//   onShowDetail : 선택한 게임 카드의 "Details"를 눌렀을 때 실행할 함수 (게임 ID)
//   disabled     : true면 입력과 선택을 막음
// ---------------------------------------------------------------------
import clsx from "clsx";
import { useState } from "react";
import GameThumb from "./GameThumb";
import SelectedGameCard from "./SelectedGameCard";
import { errorResponse } from "../api";
import { useDebouncedValue, useGameSearch } from "../queries";
import { focusRing } from "../styles";
import type { GameSummary } from "../types";

interface GameSearchProps {
  value: GameSummary | null;
  onChange: (game: GameSummary | null) => void;
  onShowDetail: (bggId: number) => void;
  disabled?: boolean;
}

export default function GameSearch({ value, onChange, onShowDetail, disabled }: GameSearchProps) {
  const [query, setQuery] = useState(value?.Name ?? "");
  const term = useDebouncedValue(query.trim(), 300);
  // 게임을 이미 골랐으면 검색하지 않는다
  const search = useGameSearch(term, !value);

  const typing = query.trim() !== term;          // 입력이 아직 멈추지 않음
  const active = !value && query.trim().length >= 2;
  const searching = active && (typing || search.isFetching);
  const matches = active && !typing ? search.data ?? [] : [];
  const noResults = active && !typing && search.isSuccess && matches.length === 0;
  const failed = active && !typing && search.isError;

  return (
    <div className="flex flex-col gap-2.5">
      <label htmlFor="game-search" className="font-bold">Favorite game</label>
      <input
        id="game-search"
        type="search"
        value={query}
        disabled={disabled}
        autoComplete="off"
        placeholder="Game name"
        onChange={(event) => {
          setQuery(event.target.value);
          onChange(null);
        }}
        className="min-h-12 w-full rounded-xl border-[1.5px] border-ink/35 bg-page px-3.5 text-base focus:border-primary-dark focus:outline-none disabled:opacity-60"
      />

      <div aria-live="polite" aria-busy={searching}>
        {value && <SelectedGameCard game={value} onShowDetail={onShowDetail} />}
        {searching && <p className="text-sm text-ink/70">Searching…</p>}
        {failed && (
          <div className="flex flex-wrap items-center gap-x-3 text-sm text-danger">
            <p>{errorResponse(search.error) ? "Search failed." : "Can't reach the server."}</p>
            <button
              type="button"
              disabled={disabled}
              onClick={() => search.refetch()}
              className={clsx("min-h-11 rounded-lg font-bold underline", focusRing)}
            >
              Search again
            </button>
          </div>
        )}
        {noResults && <p className="text-sm text-ink/70">No games found. Try another English name.</p>}
        {matches.length > 0 && (
          <ul aria-label="Search results" className="max-h-80 divide-y divide-line overflow-y-auto rounded-xl border border-line bg-card">
            {matches.map((item) => (
              <li key={item.BGGId}>
                <button
                  type="button"
                  disabled={disabled}
                  onClick={() => {
                    setQuery(item.Name);
                    onChange(item);
                  }}
                  className={clsx("flex w-full items-center gap-3 px-3 py-2 text-left hover:bg-page", focusRing, "focus-visible:-outline-offset-2")}
                >
                  <GameThumb src={item.ImagePath} name={item.Name} className="h-10 w-10 rounded-md" letterClassName="text-lg" />
                  <span className="min-w-0">
                    <span className="font-bold">{item.Name}</span>
                    {item.YearPublished > 0 && <span className="ml-2 text-sm text-ink/70">{item.YearPublished}</span>}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
