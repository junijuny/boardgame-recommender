// ---------------------------------------------------------------------
// DiceBadge: 네이비 네모 안에 주사위 아이콘 (서비스 로고)
// 헤더 로고와 "서버 깨우는 중" 안내에서 같이 쓴다.
//
// 받는 정보(props)
//   size   : "sm" = 헤더용 36px, "md" = 안내용 44px
//   wobble : true면 주사위가 좌우로 흔들림 (로딩 중 표시)
// ---------------------------------------------------------------------
import clsx from "clsx";
import { Dices } from "lucide-react";

interface DiceBadgeProps {
  size?: "sm" | "md";
  wobble?: boolean;
}

export default function DiceBadge({ size = "md", wobble = false }: DiceBadgeProps) {
  const box = size === "sm" ? "h-9 w-9 rounded-[10px]" : "h-11 w-11 rounded-xl";
  const icon = size === "sm" ? "h-[22px] w-[22px]" : "h-[26px] w-[26px]";
  return (
    <span
      className={clsx("inline-flex flex-none items-center justify-center bg-primary text-card", box, wobble && "motion-safe:animate-dice-wobble")}
      aria-hidden="true"
    >
      <Dices className={icon} strokeWidth={1.75} />
    </span>
  );
}
