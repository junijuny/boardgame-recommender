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

// Find games의 결과 카드 ("By game", "By description" 공통)
//   resultCard    : 카드 전체. 입력 카드(rounded-[20px] border bg-card)와 같은 모양
//   resultHeader  : 제목·조건 요약·Refresh 줄. 아래 구분선으로 목록과 나눈다. 여백은 입력 카드(p-5 sm:p-7)와 맞춤
//   resultNotices : 서버 깨우는 중·오류·검색 안내를 모아 두는 줄. 안내가 없으면 숨는다 (empty:hidden)
//   resultEmpty   : 아직 검색 전일 때 카드 가운데에 보이는 안내 문장
export const resultCard = "flex min-w-0 flex-[999_1_540px] flex-col overflow-hidden rounded-[20px] border border-line bg-card";
export const resultHeader = "flex flex-wrap items-end justify-between gap-x-4 gap-y-2 border-b border-line px-5 pt-5 pb-4 sm:px-7 sm:pt-7 sm:pb-5";
export const resultNotices = "flex flex-col gap-3 border-b border-line px-5 py-4 empty:hidden sm:px-7";
export const resultEmpty = "flex flex-1 items-center justify-center px-5 py-10 text-center text-ink/70";

// 결과 위에 띄우는 안내 상자와 웹 검색 상자가 같이 쓰는 카드 모양
export const noticeBox = "rounded-xl border border-line bg-card px-4 py-3 text-[15px] text-ink/80";
