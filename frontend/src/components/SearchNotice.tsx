// ---------------------------------------------------------------------
// SearchNotice: "By game"과 "By description"이 같이 쓰는 "조건에 맞는 게임 없음" 안내
// afterRefresh: "Refresh"로 보낸 요청이었는지 (그렇다면 남은 게임이 다 떨어진 것)
// ---------------------------------------------------------------------
import clsx from "clsx";
import { SearchX } from "lucide-react";
import { focusRing } from "../styles";

interface NoMatchNoticeProps {
  afterRefresh: boolean;
  onStartOver: () => void;
}

export function NoMatchNotice({ afterRefresh, onStartOver }: NoMatchNoticeProps) {
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
