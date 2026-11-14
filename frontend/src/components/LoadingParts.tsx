// ---------------------------------------------------------------------
// LoadingParts: 로딩·오류 상태에서 여러 화면이 같이 쓰는 조각
//   ServerWakeNotice : 로딩이 오래 걸릴 때 "서버 깨우는 중" 안내
//   ErrorNotice      : 불러오기 실패 안내 + 다시 시도 버튼
//   Skeleton         : 내용이 들어올 자리를 미리 보여 주는 회색 뼈대
// ---------------------------------------------------------------------
import clsx from "clsx";
import type { CSSProperties } from "react";
import { CircleAlert } from "lucide-react";
import DiceBadge from "./DiceBadge";
import { focusRing } from "../styles";

// 배포 서버는 15분간 요청이 없으면 잠들고, 첫 요청에 깨어나는 데 최대 1분쯤 걸린다.
export function ServerWakeNotice() {
  return (
    <div role="status" className="flex max-w-160 items-center gap-4 rounded-2xl border border-line bg-card px-5 py-[18px]">
      <DiceBadge wobble />
      <div className="min-w-0">
        <p className="font-bold">Starting the server</p>
        <p className="mt-1 text-[15px] leading-normal text-ink/70">
          The first request after a quiet period can take up to a minute.
        </p>
      </div>
    </div>
  );
}

interface ErrorNoticeProps {
  message: string;
  onRetry?: () => void;
}

export function ErrorNotice({ message, onRetry }: ErrorNoticeProps) {
  return (
    <div role="alert" className="flex max-w-160 flex-wrap items-center gap-x-4 gap-y-2 rounded-2xl border border-danger/40 bg-danger/10 px-5 py-4 text-danger">
      <p className="flex flex-1 items-start gap-2">
        <CircleAlert className="mt-0.5 h-5 w-5 shrink-0" aria-hidden="true" />
        {message}
      </p>
      {onRetry && (
        <button type="button" onClick={onRetry} className={clsx("min-h-11 rounded-lg px-2 font-bold underline", focusRing)}>
          Try again
        </button>
      )}
    </div>
  );
}

// className으로 크기와 모양을 정한다. 예) "h-11 w-24 rounded-full"
// 칸마다 폭을 다르게 하고 싶으면 style로 넘긴다. 예) style={{ width: "60%" }}
export function Skeleton({ className = "", style }: { className?: string; style?: CSSProperties }) {
  return <span className={clsx("skeleton block motion-safe:animate-skeleton", className)} style={style} aria-hidden="true" />;
}
