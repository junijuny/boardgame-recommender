// ---------------------------------------------------------------------
// Header: 모든 화면 맨 위에 붙는 헤더
// 왼쪽은 로고(누르면 시작 화면), 오른쪽은 화면 이동 메뉴.
// 데이터가 이미 있는 상태에서 서버에 다시 요청하는 동안에는
// 헤더 아래 테두리 위로 얇은 막대가 지나간다.
//
// 받는 정보(props)
//   current    : 지금 보고 있는 화면 (메뉴에 굵게 표시)
//   onNavigate : 로고나 메뉴를 눌렀을 때 실행할 함수 (화면 이름을 넘겨줌)
// ---------------------------------------------------------------------
import clsx from "clsx";
import { useIsFetching } from "@tanstack/react-query";
import DiceBadge from "./DiceBadge";
import { container, focusRing } from "../styles";
import type { Screen } from "../types";

interface HeaderProps {
  current: Screen;
  onNavigate: (screen: Screen) => void;
}

const MENU: { screen: Screen; label: string }[] = [
  { screen: "recommend", label: "Find similar games" },
  { screen: "genres", label: "Browse by genre" },
];

export default function Header({ current, onNavigate }: HeaderProps) {
  // 이미 데이터가 있는 요청 중에서 지금 다시 불러오는 것의 개수
  // (처음 불러오는 중이면 화면에 로딩 뼈대가 따로 보이므로 막대는 띄우지 않음)
  const refetching = useIsFetching({ predicate: (query) => query.state.data !== undefined }) > 0;

  return (
    <header className="relative border-b border-line bg-card">
      <div className={clsx(container, "flex min-h-[68px] flex-wrap items-center justify-between gap-x-6 gap-y-2 py-2.5")}>
        <button
          type="button"
          onClick={() => onNavigate("start")}
          className={clsx("inline-flex min-h-11 items-center gap-2.5 rounded-lg", focusRing)}
        >
          <DiceBadge size="sm" />
          <span className="font-display text-xl font-extrabold tracking-[-0.01em]">Boardgame Recommender</span>
        </button>

        <nav aria-label="Main">
          <ul className="flex flex-wrap gap-1">
            {MENU.map(({ screen, label }) => {
              const active = screen === current;
              return (
                <li key={screen}>
                  <button
                    type="button"
                    onClick={() => onNavigate(screen)}
                    aria-current={active ? "page" : undefined}
                    className={clsx("inline-flex min-h-11 items-center rounded-[10px] px-3.5 text-[15px] transition-colors", focusRing, active ? "bg-line font-bold" : "font-medium hover:bg-page")}
                  >
                    {label}
                  </button>
                </li>
              );
            })}
          </ul>
        </nav>
      </div>

      {refetching && (
        <div className="absolute inset-x-0 -bottom-px h-[3px] overflow-hidden bg-line" aria-hidden="true">
          <div className="h-full w-[30%] bg-primary motion-safe:animate-bar-run" />
        </div>
      )}
    </header>
  );
}
