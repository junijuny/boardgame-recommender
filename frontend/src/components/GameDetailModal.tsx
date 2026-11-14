// ---------------------------------------------------------------------
// GameDetailModal: 게임을 누르면 뜨는 상세 정보 팝업
// 추천 화면과 장르 화면에서 같이 쓴다.
// 휴대폰처럼 좁은 화면에서는 화면 아래에 붙는 시트 모양이 된다.
//
// 받는 정보(props)
//   bggId              : 보여줄 게임 ID (null이면 팝업을 그리지 않음)
//   onClose            : 팝업을 닫을 때 실행할 함수
//   onRecommendSimilar : "Find similar games"를 눌렀을 때 실행할 함수 (게임 정보를 넘겨줌)
//
// <dialog>: 브라우저가 기본으로 제공하는 팝업 태그.
//   showModal()로 열면 뒤 화면을 못 누르게 막고, ESC 키로 닫기(cancel 이벤트)도 지원한다.
// ---------------------------------------------------------------------
import clsx from "clsx";
import { useEffect, useRef } from "react";
import type { ReactNode } from "react";
import { ExternalLink, LoaderCircle, Search, X } from "lucide-react";
import DifficultyPips from "./DifficultyPips";
import GameThumb from "./GameThumb";
import { ErrorNotice, ServerWakeNotice } from "./LoadingParts";
import { errorResponse } from "../api";
import { decodeEntities, formatPlayerRange, formatPlaytime, formatScore } from "../format";
import { useGameDetail, useIsSlow } from "../queries";
import { focusRing, primaryButton } from "../styles";
import type { GameDetail } from "../types";

interface GameDetailModalProps {
  bggId: number | null;
  onClose: () => void;
  onRecommendSimilar: (game: GameDetail) => void;
}

export default function GameDetailModal({ bggId, onClose, onRecommendSimilar }: GameDetailModalProps) {
  if (bggId == null) return null;
  // key: 게임 ID가 바뀌면 팝업을 처음부터 새로 만든다.
  return <DetailDialog key={bggId} bggId={bggId} onClose={onClose} onRecommendSimilar={onRecommendSimilar} />;
}

function DetailDialog({
  bggId, onClose, onRecommendSimilar,
}: GameDetailModalProps & { bggId: number }) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  // 상세 정보 (TanStack Query가 기억해 두므로 같은 게임을 다시 열면 바로 보인다)
  const detail = useGameDetail(bggId);
  // 처음 불러오는 중이거나, 실패한 뒤 "Try again"으로 다시 불러오는 중
  const loading = detail.isPending || (detail.isError && detail.isFetching);
  const slow = useIsSlow(loading);
  const notFound = errorResponse(detail.error)?.status === 404;

  // 팝업 열기 + 닫힐 때 원래 누른 버튼으로 포커스 돌려주기 + 뒤 화면 스크롤 막기
  useEffect(() => {
    const opener = document.activeElement as HTMLElement | null;
    const dialog = dialogRef.current;
    if (!dialog) return;
    dialog.showModal();
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      if (dialog.open) dialog.close();
      document.body.style.overflow = prevOverflow;
      opener?.focus?.();
    };
  }, []);

  return (
    <dialog
      ref={dialogRef}
      aria-labelledby="game-detail-title"
      // ESC 키: 브라우저가 직접 닫지 않게 막고, 부모에게 닫아 달라고 알림
      onCancel={(event) => {
        event.preventDefault();
        onClose();
      }}
      // 팝업 바깥(어두운 배경)을 누르면 닫기
      onClick={(event) => {
        if (event.target === dialogRef.current) onClose();
      }}
      className="m-auto max-h-[90vh] w-[min(680px,calc(100%-24px))] overflow-hidden rounded-3xl bg-card p-0 text-ink backdrop:bg-ink/50 max-sm:mb-3"
    >
      <div className="relative flex max-h-[90vh] flex-col">
        <button
          type="button"
          onClick={onClose}
          aria-label="Close"
          className={clsx("absolute top-3.5 right-3.5 z-10 inline-flex h-11 w-11 items-center justify-center rounded-full bg-card text-ink hover:bg-page", focusRing)}
        >
          <X className="h-5 w-5" aria-hidden="true" />
        </button>

        {detail.data ? (
          <DetailContent game={detail.data} onRecommendSimilar={onRecommendSimilar} />
        ) : (
          <div className="flex flex-col items-center gap-4 px-5 pt-20 pb-14 sm:px-7" aria-live="polite">
            <h2 id="game-detail-title" className="sr-only">Game details</h2>
            {loading && !slow && (
              <p role="status" className="flex items-center gap-2 text-ink/70">
                <LoaderCircle className="h-5 w-5 motion-safe:animate-spin" aria-hidden="true" />
                Loading game…
              </p>
            )}
            {slow && <ServerWakeNotice />}
            {detail.isError && !detail.isFetching && (
              <ErrorNotice
                message={notFound ? "Game not found." : "Couldn't load this game."}
                onRetry={notFound ? undefined : () => detail.refetch()}
              />
            )}
          </div>
        )}
      </div>
    </dialog>
  );
}

// 상세 정보 본문: 표지와 이름, 주요 정보 4칸, 설명, 비슷한 게임 찾기 버튼
function DetailContent({ game, onRecommendSimilar }: { game: GameDetail; onRecommendSimilar: (game: GameDetail) => void }) {
  const description = decodeEntities(game.Description).trim();
  // 원문이 없는 일부 게임은 소문자·불용어 제거된 키워드만 들어 있으므로 구분해서 안내
  const isKeywordOnly = Boolean(description) && !/[A-Z.!?,]/.test(description);

  return (
    <>
      <div className="flex flex-wrap items-end gap-4 bg-line p-5 sm:flex-nowrap sm:gap-[22px] sm:px-7 sm:pt-7 sm:pb-6">
        <GameThumb
          src={game.ImagePath}
          name={game.Name}
          className="h-[88px] w-[88px] rounded-2xl bg-card! sm:h-[140px] sm:w-[140px]"
          letterClassName="text-[44px] sm:text-[72px]"
        />
        <div className="flex min-w-0 flex-col gap-1.5 pb-1">
          <h2 id="game-detail-title" className="pr-12 font-display text-[32px] leading-none font-extrabold tracking-[-0.02em] sm:text-[44px]">
            {game.Name}
          </h2>
          {game.YearPublished > 0 && <p className="text-[15px] text-ink/70">{game.YearPublished}</p>}
        </div>
      </div>

      <div className="flex min-h-0 flex-1 flex-col gap-6 overflow-y-auto p-5 sm:px-7 sm:py-6">
        {/* dl: 이름-값 쌍 목록. gap-px + 선 색 바탕으로 칸 사이에 1px 선을 만든다 */}
        <dl className="grid grid-cols-2 gap-px overflow-hidden rounded-2xl border border-line bg-line sm:grid-cols-4">
          <Fact label="Players" value={formatPlayerRange(game) ?? "—"} note={game.BestPlayers > 0 ? `Best with ${game.BestPlayers}` : undefined} />
          <Fact label="Play time" value={formatPlaytime(game)} />
          <Fact label="Difficulty" value={formatScore(game.GameWeight)}>
            <dd className="mt-1.5">
              <DifficultyPips weight={game.GameWeight} size="md" />
            </dd>
          </Fact>
          <Fact label="Rating" value={formatScore(game.BayesAvgRating)} />
        </dl>

        <section aria-labelledby="desc-title" className="flex flex-col gap-2.5">
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <h3 id="desc-title" className="font-bold">{isKeywordOnly ? "Keywords" : "Description"}</h3>
            <a
              href={`https://boardgamegeek.com/boardgame/${game.BGGId}`}
              target="_blank"
              rel="noopener noreferrer"
              className={clsx("inline-flex min-h-11 items-center gap-1.5 rounded-lg text-sm font-bold text-primary hover:underline", focusRing)}
            >
              BoardGameGeek
              <ExternalLink className="h-3.5 w-3.5" aria-hidden="true" />
              <span className="sr-only">(opens in a new tab)</span>
            </a>
          </div>
          {/* whitespace-pre-line: 설명 속 줄바꿈을 그대로 보여줌 */}
          <p className="max-w-[62ch] leading-relaxed whitespace-pre-line">{description || "No description."}</p>
        </section>
      </div>

      <div className="border-t border-line px-5 pt-3.5 pb-5 sm:px-7 sm:pt-[18px] sm:pb-6">
        <button type="button" onClick={() => onRecommendSimilar(game)} className={clsx(primaryButton, "w-full")}>
          <Search className="h-5 w-5" aria-hidden="true" />
          Find similar games
        </button>
      </div>
    </>
  );
}

// 주요 정보 한 칸 (이름 + 값, 필요하면 작은 설명이나 추가 내용)
function Fact({ label, value, note, children }: { label: string; value: string; note?: string; children?: ReactNode }) {
  return (
    <div className="bg-card px-4 py-3.5">
      <dt className="text-[13px] text-ink/70">{label}</dt>
      <dd className="mt-1 text-[17px] font-bold">{value}</dd>
      {note && <dd className="mt-0.5 text-[13px] text-ink/70">{note}</dd>}
      {children}
    </div>
  );
}
