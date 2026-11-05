// ---------------------------------------------------------------------
// GameSearch: 데이터셋에서 게임을 검색하고 하나를 선택하는 입력창
// 검색 결과의 게임을 선택해야 추천 요청을 보낼 수 있음.
// 입력을 바꾸면 이전 요청을 취소해 늦은 응답이 새 검색 결과를 덮지 않게 함.
//
// 받는 정보(props)
//   value    : 지금 선택된 게임 이름 (선택 안 했으면 빈 글자)
//              처음부터 값이 있으면(상세 화면에서 넘어온 경우) 입력창에 그 이름을 채워 둔다.
//   onChange : 게임을 선택하거나 입력을 바꿨을 때 실행할 함수 (선택 해제면 "")
//   disabled : true면 입력과 선택을 막음
// ---------------------------------------------------------------------
import { useEffect, useState } from "react";
import { Heart } from "lucide-react";
import { searchGames } from "../api.js";

export default function GameSearch({ value, onChange, disabled }) {
  const [query, setQuery] = useState(value);
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
        const games = await searchGames(term, controller.signal);
        if (!controller.signal.aborted) {
          setMatches(games);
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
