// ---------------------------------------------------------------------
// StartScreen: 맨 처음에 보이는 시작 화면
//
// 받는 정보(props)
//   onStart  : "비슷한 게임 추천받기" 버튼을 눌렀을 때 실행할 함수
//   onBrowse : "장르별로 둘러보기" 버튼을 눌렀을 때 실행할 함수
// ---------------------------------------------------------------------
import { ArrowRight, Dices, Heart, LayoutGrid, Search, Users } from "lucide-react";
import { primaryButton, secondaryButton } from "../styles.js";

export default function StartScreen({ onStart, onBrowse }) {
  // min-h-screen: 화면 높이 가득 / items-center, justify-center: 가운데 정렬
  return (
    <div className="flex min-h-screen items-center justify-center px-4 py-12">
      <main className="w-full max-w-xl text-center">

        {/* 대표 아이콘: 네이비 네모 안에 주사위 */}
        {/* strokeWidth: 아이콘 선 두께 (기본 2, 숫자가 작을수록 얇음) */}
        <div className="mx-auto flex h-20 w-20 items-center justify-center rounded-2xl bg-primary text-card">
          <Dices className="h-10 w-10" strokeWidth={1.75} aria-hidden="true" />
        </div>

        {/* 제목과 설명 */}
        <h1 className="mt-6 text-4xl font-bold leading-tight tracking-tight">
          Boardgame Recommender
        </h1>
        <p className="mt-4 text-ink/70">
          좋아하는 게임 하나만 알려 주세요. 비슷한 보드게임을 찾아 드릴게요.
        </p>

        {/* 이용 방법 3단계 */}
        {/* ol: 순서가 있는 목록 / sm:grid-cols-3: 화면이 넓으면 3칸으로 나란히 */}
        <ol className="mt-10 grid gap-3 text-left sm:grid-cols-3">
          <Step icon={Heart} title="좋아하는 게임" text="재밌게 했던 게임 고르기" />
          <Step icon={Users} title="인원과 시간" text="몇 명이서, 얼마나 할지" />
          <Step icon={Search} title="추천 받기" text="비슷한 게임 확인하기" />
        </ol>

        {/* 버튼 두 개: 좁은 화면에서는 세로로, 넓은 화면에서는 가로로 */}
        <div className="mt-10 flex flex-col justify-center gap-3 sm:flex-row">
          <button type="button" onClick={onStart} className={`${primaryButton} px-7 py-3.5 text-lg`}>
            비슷한 게임 추천받기
            <ArrowRight className="h-5 w-5" aria-hidden="true" />
          </button>
          <button type="button" onClick={onBrowse} className={`${secondaryButton} px-7 py-3.5 text-lg`}>
            <LayoutGrid className="h-5 w-5" aria-hidden="true" />
            장르별로 둘러보기
          </button>
        </div>
        <p className="mt-3 text-sm text-ink/60">
          아직 좋아하는 게임이 없다면 장르별 대표 게임부터 둘러보세요.
        </p>
      </main>
    </div>
  );
}


// ---------------------------------------------------------------------
// Step: 시작 화면의 이용 방법 한 칸
//
// 받는 정보(props)
//   icon  : 보여줄 아이콘 (예: Heart)
//   title : 굵은 제목
//   text  : 작은 설명
// ---------------------------------------------------------------------
function Step({ icon: Icon, title, text }) {
  return (
    <li className="rounded-xl border border-line bg-card p-4">
      <Icon className="h-6 w-6 text-primary" strokeWidth={1.75} aria-hidden="true" />
      <p className="mt-3 font-bold">{title}</p>
      <p className="mt-1 text-sm text-ink/60">{text}</p>
    </li>
  );
}
