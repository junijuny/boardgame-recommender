// ---------------------------------------------------------------------
// ResultList: 추천 결과 목록과 로딩 뼈대 ("By game"과 "By description" 화면이 함께 쓴다)
//   ResultItem     : 한 줄에 보여 줄 게임과, 이유가 없을 때 대신 보여 줄 칩(메커니즘 이름)
//   ResultList     : 결과 목록. 한 줄을 누르면 onSelect에 게임 ID를 넘겨준다.
//   ResultSkeleton : 결과를 기다리는 동안 5줄 자리를 미리 보여 준다.
// 이유 문장 표시 순서: 이유 -> (이유를 불러오는 중이면) 뼈대 두 줄 -> 칩
//
// 높이가 덜 흔들리게 하는 규칙
//   - 이유 자리는 처음부터 두 줄 높이로 잡아 두고, 문장이 길면 두 줄에서 자른다.
//     (이유가 늦게 도착해도, 뼈대 -> 문장으로 바뀌어도 줄 높이가 그대로)
//   - 로딩 뼈대는 실제 결과 한 줄과 같은 모양·높이로 그린다. (ROW, THUMB, REASON_SLOT 공유)
// ---------------------------------------------------------------------
import clsx from "clsx";
import { ChevronRight } from "lucide-react";
import DifficultyPips from "./DifficultyPips";
import GameThumb from "./GameThumb";
import { Skeleton } from "./LoadingParts";
import { formatPlayers, formatPlaytime, formatScore } from "../format";
import { focusRing } from "../styles";
import type { FilteredGame } from "../types";

// 결과 한 줄과 로딩 뼈대 한 줄이 같이 쓰는 모양
// 목록은 결과 카드(styles.ts의 resultCard) 안에 들어가므로 따로 테두리를 두지 않고 줄 사이 구분선만 둔다.
// 좌우 여백은 카드 제목 줄(resultHeader)과 같아서 순위 숫자가 "Results" 제목과 같은 선에 선다.
const LIST = "flex flex-col";
const ROW = "flex w-full items-center gap-3 px-5 py-3.5 sm:gap-[18px] sm:px-7 sm:py-[18px]";
const RANK = "w-[18px] flex-none text-center sm:w-7";
const THUMB = "h-12 w-12 shrink-0 rounded-xl sm:h-16 sm:w-16";
// 이유 문장 자리: 15px 글자 두 줄 높이 (leading-snug = 1.375 -> 2.75em)
const REASON_SLOT = "min-h-[2.75em] text-[15px] leading-snug";

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
  // 목록 상자에 더 붙일 클래스 (예: 옆 입력 상자와 높이를 맞추는 flex-1)
  className?: string;
}

export function ResultList({ items, reasons, reasonsLoading, onSelect, className }: ResultListProps) {
  return (
    <ol className={clsx(LIST, className)}>
      {items.map(({ game, chips }, i) => {
        const reason = reasons?.[String(game.BGGId)];
        return (
          <li key={game.BGGId ?? game.Name} className="border-t border-line first:border-t-0">
            <button
              type="button"
              onClick={() => onSelect(game.BGGId)}
              aria-haspopup="dialog"
              className={clsx("group text-left transition-colors hover:bg-page", ROW, focusRing, "focus-visible:-outline-offset-2")}
            >
              <span className={clsx(RANK, "font-display text-lg font-extrabold text-ink/50 sm:text-[26px]")}>
                {i + 1}
              </span>
              <GameThumb src={game.ImagePath} name={game.Name} className={THUMB} letterClassName="text-[22px] sm:text-[28px]" />
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
                <span className={clsx(REASON_SLOT, "block")}>
                  {reason ? (
                    <span className="line-clamp-2 text-ink/85" title={reason}>{reason}</span>
                  ) : reasonsLoading ? (
                    <ReasonSkeleton />
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
              </span>
              <ChevronRight className="h-5 w-5 shrink-0 text-ink/45 group-hover:text-primary" aria-hidden="true" />
            </button>
          </li>
        );
      })}
    </ol>
  );
}

// 이유 문장을 기다리는 동안 두 줄 자리 (REASON_SLOT 안에 그린다)
function ReasonSkeleton() {
  return (
    <span className="flex flex-col gap-[0.55em] pt-[0.3em]">
      <Skeleton className="h-3.5 w-11/12 rounded-md" />
      <Skeleton className="h-3.5 w-3/5 rounded-md" />
    </span>
  );
}

// 결과를 기다리는 동안 5줄 자리를 미리 보여 준다. label은 스크린 리더용 안내 문구
// 실제 결과 한 줄과 같은 칸(순위, 사진, 이름, 정보, 이유 두 줄, 화살표)을 같은 높이로 둔다.
export function ResultSkeleton({ label, className }: { label: string; className?: string }) {
  return (
    <>
      <p role="status" className="sr-only">{label}</p>
      <ol className={clsx(LIST, className)} aria-hidden="true">
        {[62, 48, 70, 54, 66].map((width, i) => (
          <li key={i} className={clsx(ROW, "border-t border-line first:border-t-0")}>
            <span className={RANK} />
            <Skeleton className={THUMB} />
            <span className="flex min-w-0 flex-1 flex-col gap-1.5">
              {/* 이름 줄 (text-lg 한 줄 높이) */}
              <span className="flex h-7 items-center">
                <Skeleton className="h-[18px] rounded-md" style={{ width: `${width}%` }} />
              </span>
              {/* 인원·시간·난이도 줄. 휴대폰 폭에서는 실제 결과가 두 줄로 넘어가므로 뼈대도 두 줄
                  (20px + 간격 6px + 20px = 46px), 넓은 화면(sm 이상)에서는 한 줄 (20px) */}
              <span className="flex h-[46px] flex-col justify-around sm:h-5 sm:justify-center">
                <Skeleton className="h-3 w-4/5 rounded-md sm:w-1/2" />
                <Skeleton className="h-3 w-2/5 rounded-md sm:hidden" />
              </span>
              <span className={clsx(REASON_SLOT, "block")}>
                <ReasonSkeleton />
              </span>
            </span>
            <span className="h-5 w-5 shrink-0" />
          </li>
        ))}
      </ol>
    </>
  );
}
