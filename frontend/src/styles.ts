// =====================================================================
// styles.ts: 여러 화면에서 같이 쓰는 Tailwind 클래스 묶음
// clsx: 클래스 이름 여러 개를 공백으로 이어 붙이는 도구.
//   조건이 false/undefined인 항목은 빠진다. 예) clsx("a", on && "b") -> on이면 "a b", 아니면 "a"
// =====================================================================

import clsx from "clsx";

// 키보드로 이동했을 때 보이는 테두리 (모든 버튼·링크에 붙인다)
export const focusRing =
  "focus-visible:outline-2 focus-visible:outline-offset-3 focus-visible:outline-primary-dark";

// 진한 메인 버튼 (Find similar games, Get recommendations 등)
export const primaryButton = clsx(
  "inline-flex min-h-14 items-center justify-center gap-2.5 rounded-xl bg-primary px-8 text-[17px] font-bold text-card transition-colors hover:bg-primary-dark disabled:opacity-60",
  focusRing,
);

// 테두리만 있는 보조 버튼 (Browse by genre)
export const secondaryButton = clsx(
  "inline-flex min-h-14 items-center justify-center gap-2.5 rounded-xl border-[1.5px] border-primary bg-card px-7 text-[17px] font-bold text-primary transition-colors hover:bg-line",
  focusRing,
);

// 고를 수 있는 버튼의 색 (인원, 시간, 장르 버튼에서 같이 씀)
// 선택된 버튼이면 진한 네이비 바탕에 밝은 글자
export function choiceColor(selected: boolean): string { 
  return selected
    ? "border-primary-dark bg-primary-dark text-card"
    : "border-line bg-card text-ink hover:border-primary";
}

// 페이지 제목 (Find similar games, Top games by genre)
export const pageTitle =
  "font-display text-[clamp(36px,4.6vw,56px)] font-extrabold leading-[1.05] tracking-[-0.02em]";

// 화면 가운데에 내용을 모으는 폭 (헤더와 본문이 같은 폭을 쓴다)
export const container = "mx-auto w-full max-w-7xl px-4 sm:px-6";
