// ---------------------------------------------------------------------
// DifficultyPips: 난이도(1~5)를 작은 네모 5칸으로 보여 준다
// 반올림한 숫자만큼 칸이 채워진다. 숫자는 옆에 글자로 따로 보여 주므로
// 화면 읽기 프로그램에는 숨긴다.
// ---------------------------------------------------------------------
import clsx from "clsx";

interface DifficultyPipsProps {
  weight: number | null;
  size?: "sm" | "md";
}

export default function DifficultyPips({ weight, size = "sm" }: DifficultyPipsProps) {
  const filled = Math.round(weight ?? 0);
  const box = size === "sm" ? "h-[9px] w-[9px]" : "h-2.5 w-2.5";
  return (
    <span className="inline-flex gap-[3px]" aria-hidden="true">
      {[1, 2, 3, 4, 5].map((i) => (
        <span key={i} className={clsx("rounded-[2px]", box, i <= filled ? "bg-primary" : "bg-line")} />
      ))}
    </span>
  );
}
