// ---------------------------------------------------------------------
// RecommendScreen: "Find games" 화면. 제목 + 탭 두 개 + 탭마다 하나씩 있는 패널
//   By game        : 좋아하는 게임과 비슷한 게임 찾기 (SimilarSearch)
//   By description : 원하는 게임을 말로 설명해서 찾기 (DescriptionSearch)
// 서버가 자연어 검색을 꺼 두었으면 탭 없이 "By game"만 보여준다.
// 두 패널은 계속 화면에 올려 두고 안 보이는 쪽만 hidden으로 숨긴다 (탭을 오가도 입력과 결과가 남는다).
// 결과를 누르면 상세 팝업이 열린다. 팝업은 여기서 하나만 관리한다.
//
// 받는 정보(props)
//   initialGame        : "By game"에 처음부터 선택해 둘 게임 { BGGId, Name } (없으면 null)
//   onRecommendSimilar : 상세 팝업에서 "Find similar games"를 눌렀을 때 실행할 함수
// ---------------------------------------------------------------------
import clsx from "clsx";
import { useRef, useState } from "react";
import type { KeyboardEvent } from "react";
import DescriptionSearch from "../components/DescriptionSearch";
import GameDetailModal from "../components/GameDetailModal";
import SimilarSearch from "../components/SimilarSearch";
import { useServerInfo } from "../queries";
import { container, focusRing, pageTitle } from "../styles";
import type { GameDetail, GameSummary } from "../types";

interface RecommendScreenProps {
  initialGame: GameSummary | null;
  onRecommendSimilar: (game: GameDetail) => void;
}

type TabKey = "game" | "description";

const TABS: { key: TabKey; label: string }[] = [
  { key: "game", label: "By game" },
  { key: "description", label: "By description" },
];

export default function RecommendScreen({ initialGame, onRecommendSimilar }: RecommendScreenProps) {
  // 상세 팝업으로 보고 있는 게임 ID (닫혀 있으면 null)
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [tab, setTab] = useState<TabKey>("game");
  const tabRefs = useRef<Record<TabKey, HTMLButtonElement | null>>({ game: null, description: null });
  const naturalOn = useServerInfo().data?.natural_search === true;

  // 화살표·Home·End 키로 탭 옮기기 (옮기면 바로 그 탭이 선택된다)
  function handleTabKeyDown(event: KeyboardEvent<HTMLButtonElement>) {
    const current = TABS.findIndex((t) => t.key === tab);
    let next: number;
    if (event.key === "ArrowRight") next = (current + 1) % TABS.length;
    else if (event.key === "ArrowLeft") next = (current - 1 + TABS.length) % TABS.length;
    else if (event.key === "Home") next = 0;
    else if (event.key === "End") next = TABS.length - 1;
    else return;
    event.preventDefault();
    setTab(TABS[next].key);
    tabRefs.current[TABS[next].key]?.focus();
  }

  return (
    <main className={clsx(container, "flex flex-col gap-7 pt-7 pb-12 sm:pt-10 sm:pb-16")}>
      <h1 className={pageTitle}>Find games</h1>

      {naturalOn && (
        <div role="tablist" aria-label="Search type" className="flex gap-2">
          {TABS.map(({ key, label }) => {
            const selected = tab === key;
            return (
              <button
                key={key}
                ref={(el) => { tabRefs.current[key] = el; }}
                type="button"
                role="tab"
                id={`tab-${key}`}
                aria-selected={selected}
                aria-controls={`panel-${key}`}
                tabIndex={selected ? 0 : -1}
                onClick={() => setTab(key)}
                onKeyDown={handleTabKeyDown}
                className={clsx(
                  "min-h-11 rounded-xl border-[1.5px] px-5 text-[16px] font-bold transition-colors",
                  selected
                    ? "border-primary-dark bg-primary-dark text-card"
                    : "border-line bg-card text-ink hover:border-primary",
                  focusRing,
                )}
              >
                {label}
              </button>
            );
          })}
        </div>
      )}

      {/* 탭이 없을 때는 role도 붙이지 않는다 */}
      <div
        role={naturalOn ? "tabpanel" : undefined}
        id="panel-game"
        aria-labelledby={naturalOn ? "tab-game" : undefined}
        hidden={naturalOn && tab !== "game"}
      >
        <SimilarSearch initialGame={initialGame} onShowDetail={setSelectedId} />
      </div>
      {naturalOn && (
        <div role="tabpanel" id="panel-description" aria-labelledby="tab-description" hidden={tab !== "description"}>
          <DescriptionSearch onShowDetail={setSelectedId} />
        </div>
      )}

      <GameDetailModal
        bggId={selectedId}
        onClose={() => setSelectedId(null)}
        onRecommendSimilar={onRecommendSimilar}
      />
    </main>
  );
}
