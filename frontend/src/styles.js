// =====================================================================
// styles.js: 여러 화면에서 같이 쓰는 Tailwind 클래스 묶음
// =====================================================================

// 선택 버튼 모양 (장르 칩에서도 같은 모양을 쓰려고 밖으로 꺼내 둠)
// 선택된 버튼이면 진한 메인 색, 아니면 기본 흰 버튼
export function choiceClass(selected) {
  const color = selected
    ? "border-primary-dark bg-primary-dark font-semibold text-card"
    : "border-line bg-card hover:border-primary";
  return `rounded-lg border px-4 py-2 text-sm transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary-dark ${color}`;
}

// 진한 메인 버튼 (추천받기, 시작 화면 버튼 등)
export const primaryButton =
  "inline-flex items-center justify-center gap-2 rounded-lg bg-primary font-semibold text-card transition-colors hover:bg-primary-dark disabled:opacity-60 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary-dark";

// 테두리만 있는 보조 버튼
export const secondaryButton =
  "inline-flex items-center justify-center gap-2 rounded-lg border border-primary bg-card font-semibold text-primary transition-colors hover:bg-line focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary-dark";

// "처음으로" 같은 작은 글자 버튼
export const backButton =
  "mb-6 inline-flex items-center gap-1 text-sm text-ink/60 transition-colors hover:text-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary-dark";
