// ---------------------------------------------------------------------
// ResultList: 추천 결과 목록과 로딩 뼈대 ("By game"과 "By description" 화면이 함께 쓴다)
//   ResultItem     : 한 줄에 보여 줄 게임과, 이유가 없을 때 대신 보여 줄 칩(메커니즘 이름)
//   ResultList     : 결과 목록. 한 줄을 누르면 onSelect에 게임 ID를 넘겨준다.
//   ResultSkeleton : 결과를 기다리는 동안 5줄 자리를 미리 보여 준다.
// 이유 문장 표시 순서: 이유 -> (이유를 불러오는 중이면) 뼈대 한 줄 -> 칩
// ---------------------------------------------------------------------
import clsx from "clsx";
import { ChevronRight } from "lucide-react";
import DifficultyPips from "./DifficultyPips";
import GameThumb from "./GameThumb";
import { Skeleton } from "./LoadingParts";
import { formatPlayers, formatPlaytime, formatScore } from "../format";
import { focusRing } from "../styles";
import type { FilteredGame } from "../types";

export interface ResultItem {
  game: FilteredGame;
  chips: string[];
}

interface ResultListProps {
  items: ResultItem[];
  // BGGId(문자열) -> 한 문장 이유. 아직 없거나 실패했으면 undefined
  reasons?: Record<string, string>;
  // 이유를 지금 불러오는 중인지 (요청이 꺼져 있으면 false)
  reasonsLoading: boolean;
  onSelect: (bggId: number) => void;
}

export function ResultList({ items, reasons, reasonsLoading, onSelect }: ResultListProps) {
  return (
    <ol className="overflow-hidden rounded-[20px] border border-line bg-card">
      {items.map(({ game, chips }, i) => {
        const reason = reasons?.[String(game.BGGId)];
        return (
          <li key={game.BGGId ?? game.Name} className="border-t border-line first:border-t-0">
            <button
              type="button"
              onClick={() => onSelect(game.BGGId)}
              aria-haspopup="dialog"
              className={clsx("group flex w-full items-center gap-3 px-4 py-3.5 text-left transition-colors hover:bg-page sm:gap-[18px] sm:px-[22px] sm:py-[18px]", focusRing, "focus-visible:-outline-offset-2")}
            >
              <span className="w-[18px] flex-none text-center font-display text-lg font-extrabold text-ink/50 sm:w-7 sm:text-[26px]">
                {i + 1}
              </span>
              <GameThumb
                src={game.ImagePath}
                name={game.Name}
                className="h-12 w-12 rounded-xl sm:h-16 sm:w-16"
                letterClassName="text-[22px] sm:text-[28px]"
              />
              <span className="flex min-w-0 flex-1 flex-col gap-1.5">
                <span className="text-lg font-bold group-hover:underline">
                  {game.Name}
                  {game.YearPublished > 0 && <span className="ml-1.5 text-sm font-normal text-ink/70">{game.YearPublished}</span>}
                </span>
                <span className="flex flex-wrap items-center gap-x-4 gap-y-1.5 text-sm text-ink/70">
                  <span>{formatPlayers(game)}</span>
                  <span>{formatPlaytime(game)}</span>
                  <span className="inline-flex items-center gap-1.5">
                    Difficulty
                    <DifficultyPips weight={game.GameWeight} />
                    {formatScore(game.GameWeight)}
                  </span>
                </span>
                {reason ? (
                  <span className="block text-[15px] leading-snug text-ink/85">{reason}</span>
                ) : reasonsLoading ? (
                  <Skeleton className="h-3.5 w-4/5 rounded-md" />
                ) : (
                  chips.length > 0 && (
                    <span className="flex flex-wrap gap-1.5">
                      {chips.map((name) => (
                        <span key={name} className="inline-flex min-h-[26px] items-center rounded-full border border-line bg-page px-2.5 text-[13px] font-medium">
                          {name}
                        </span>
                      ))}
                    </span>
                  )
                )}
              </span>
              <ChevronRight className="h-5 w-5 shrink-0 text-ink/45 group-hover:text-primary" aria-hidden="true" />
            </button>
          </li>
        );
      })}
    </ol>
  );
}

// 결과를 기다리는 동안 5줄 자리를 미리 보여 준다. label은 스크린 리더용 안내 문구
export function ResultSkeleton({ label }: { label: string }) {
  return (
    <>
      <p role="status" className="sr-only">{label}</p>
      <ol className="overflow-hidden rounded-[20px] border border-line bg-card" aria-hidden="true">
        {[62, 48, 70, 54, 66].map((width, i) => (
          <li key={i} className="flex items-center gap-3 border-t border-line px-4 py-3.5 first:border-t-0 sm:gap-[18px] sm:px-[22px] sm:py-[18px]">
            <Skeleton className="h-12 w-12 shrink-0 rounded-xl sm:h-16 sm:w-16" />
            <span className="flex flex-1 flex-col gap-2.5">
              <Skeleton className="h-[18px] rounded-md" style={{ width: `${width}%` }} />
              <Skeleton className="h-3.5 w-4/5 rounded-md" />
            </span>
          </li>
        ))}
      </ol>
    </>
  );
}
