// ---------------------------------------------------------------------
// GameDetailModal: 게임을 누르면 뜨는 상세 정보 팝업
// 추천 결과 화면과 장르 화면에서 같이 쓴다.
//
// 받는 정보(props)
//   bggId              : 보여줄 게임 ID (null이면 팝업을 그리지 않음)
//   onClose            : 팝업을 닫을 때 실행할 함수
//   onRecommendSimilar : "비슷한 게임 추천받기"를 눌렀을 때 실행할 함수 (게임 이름을 넘겨줌)
//
// <dialog>: 브라우저가 기본으로 제공하는 팝업 태그.
//   showModal()로 열면 뒤 화면을 못 누르게 막고, ESC 키로 닫기(cancel 이벤트)도 지원한다.
// ---------------------------------------------------------------------
import { useEffect, useRef, useState } from "react";
import {
  CircleAlert, Clock, ExternalLink, Gauge, LoaderCircle, Search, Star, Users, X,
} from "lucide-react";
import { getGameDetail } from "../api.js";
import { decodeEntities, formatPlayers, formatPlaytime } from "../format.js";
import { primaryButton } from "../styles.js";
import GameThumb from "./GameThumb.jsx";

export default function GameDetailModal({ bggId, onClose, onRecommendSimilar }) {
  if (bggId == null) return null;
  // key: 게임 ID가 바뀌면 팝업 내용을 처음부터 새로 만든다.
  //      (이전 게임의 정보나 늦게 도착한 응답이 남지 않게 함)
  return (
    <DetailDialog
      key={bggId}
      bggId={bggId}
      onClose={onClose}
      onRecommendSimilar={onRecommendSimilar}
    />
  );
}

function DetailDialog({ bggId, onClose, onRecommendSimilar }) {
  const dialogRef = useRef(null);
  // status: "loading" = 불러오는 중, "ok" = 성공, "notfound" = 없는 게임, "error" = 실패
  const [status, setStatus] = useState("loading");
  const [game, setGame] = useState(null);
  // "다시 시도"를 누를 때마다 숫자를 올려서 다시 불러오게 함
  const [retry, setRetry] = useState(0);

  // 팝업 열기 + 닫힐 때 원래 누른 버튼으로 포커스 돌려주기 + 뒤 화면 스크롤 막기
  useEffect(() => {
    const opener = document.activeElement;
    const dialog = dialogRef.current;
    dialog.showModal();
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      if (dialog.open) dialog.close();
      document.body.style.overflow = prevOverflow;
      opener?.focus?.();
    };
  }, []);

  // 게임 상세 정보 불러오기
  useEffect(() => {
    const controller = new AbortController();
    getGameDetail(bggId, controller.signal)
      .then((data) => {
        setGame(data);
        setStatus("ok");
      })
      .catch((err) => {
        if (controller.signal.aborted) return;
        console.error(err);
        setStatus(err.response?.status === 404 ? "notfound" : "error");
      });
    // 팝업이 닫히면 아직 안 끝난 요청을 취소
    return () => controller.abort();
  }, [bggId, retry]);

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
      className="m-auto max-h-[90vh] w-[min(42rem,calc(100%-2rem))] overflow-hidden rounded-2xl bg-card p-0 text-ink shadow-xl backdrop:bg-ink/50"
    >
      <div className="flex max-h-[90vh] flex-col">
        {/* 위쪽: 닫기 버튼 */}
        <div className="flex justify-end px-3 pt-3">
          <button
            type="button"
            onClick={onClose}
            aria-label="닫기"
            className="rounded-lg p-2 text-ink/60 transition-colors hover:bg-line hover:text-ink focus-visible:outline-2 focus-visible:outline-primary-dark"
          >
            <X className="h-5 w-5" aria-hidden="true" />
          </button>
        </div>

        {/* 가운데: 내용 (길면 이 부분만 스크롤) */}
        <div className="overflow-y-auto px-6 pb-6" aria-live="polite" aria-busy={status === "loading"}>
          {status === "loading" && (
            <p className="flex items-center justify-center gap-2 py-16 text-ink/60">
              <LoaderCircle className="h-5 w-5 motion-safe:animate-spin" aria-hidden="true" />
              게임 정보를 불러오는 중...
            </p>
          )}
          {(status === "error" || status === "notfound") && (
            <div className="py-12 text-center">
              <h2 id="game-detail-title" className="sr-only">게임 정보 오류</h2>
              <p className="inline-flex items-start gap-2 text-danger">
                <CircleAlert className="mt-0.5 h-5 w-5 shrink-0" aria-hidden="true" />
                {status === "notfound" ? "게임을 찾을 수 없습니다." : "게임 정보를 불러오지 못했습니다."}
              </p>
              {status === "error" && (
                <div>
                  <button
                    type="button"
                    onClick={() => {
                      setStatus("loading");
                      setRetry((n) => n + 1);
                    }}
                    className="mt-4 text-sm underline"
                  >
                    다시 시도
                  </button>
                </div>
              )}
            </div>
          )}
          {status === "ok" && <DetailBody game={game} />}
        </div>

        {/* 아래쪽: 비슷한 게임 추천받기 버튼 (불러오기 성공했을 때만) */}
        {status === "ok" && (
          <div className="border-t border-line px-6 py-4">
            <button
              type="button"
              onClick={() => onRecommendSimilar(game.Name)}
              className={`${primaryButton} w-full py-3`}
            >
              <Search className="h-5 w-5" aria-hidden="true" />
              이 게임과 비슷한 게임 추천받기
            </button>
          </div>
        )}
      </div>
    </dialog>
  );
}


// 상세 정보 본문: 이미지, 이름, 주요 정보, 설명
function DetailBody({ game }) {
  const description = decodeEntities(game.Description).trim();

  // 인원 글자. 최적 인원 정보가 있으면 뒤에 붙임. 예) "2~4명 (최적 3명)"
  const players = game.BestPlayers > 0
    ? `${formatPlayers(game)} (최적 ${game.BestPlayers}명)`
    : formatPlayers(game);

  return (
    <article>
      <div className="flex flex-col gap-5 sm:flex-row">
        <GameThumb src={game.ImagePath} className="h-40 w-40 rounded-xl" iconClassName="h-12 w-12" />
        <div className="min-w-0">
          <h2 id="game-detail-title" className="text-2xl font-bold leading-snug tracking-tight">
            {game.Name}
          </h2>
          {game.YearPublished > 0 && <p className="mt-1 text-sm text-ink/60">{game.YearPublished}년 출시</p>}

          {/* dl: 이름-값 쌍 목록 (인원: 2~4명 같은 정보) */}
          <dl className="mt-4 grid grid-cols-2 gap-x-4 gap-y-3 text-sm">
            <InfoItem icon={Users} label="인원" value={players} />
            <InfoItem icon={Clock} label="플레이 시간" value={formatPlaytime(game)} />
            <InfoItem icon={Gauge} label="난이도" value={`${(game.GameWeight ?? 0).toFixed(1)} / 5`} />
            <InfoItem
              icon={Star}
              label="평점"
              value={`${(game.BayesAvgRating ?? 0).toFixed(1)} (리뷰 ${(game.NumUserRatings ?? 0).toLocaleString()}개)`}
            />
          </dl>
        </div>
      </div>

      {/* 데이터셋의 설명은 원문이 아니라 소문자·불용어 제거 등 전처리된 핵심 단어 모음이라서
          그 사실을 알려 주고, 원문은 BoardGameGeek 페이지로 연결한다. */}
      <div className="mt-6 flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="text-sm font-semibold text-ink/60">설명 키워드 (영문)</h3>
        <a
          href={`https://boardgamegeek.com/boardgame/${game.BGGId}`}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1 text-sm font-semibold text-primary underline-offset-2 hover:underline"
        >
          BoardGameGeek에서 원문 보기
          <ExternalLink className="h-3.5 w-3.5" aria-hidden="true" />
          <span className="sr-only">(새 창)</span>
        </a>
      </div>
      <p className="mt-1 text-xs text-ink/50">데이터셋에는 원문 대신 핵심 단어만 정리된 설명이 들어 있어요.</p>
      {/* whitespace-pre-line: 설명 속 줄바꿈을 그대로 보여줌 */}
      <p className="mt-3 whitespace-pre-line leading-relaxed text-ink/80">
        {description || "설명이 없습니다."}
      </p>
    </article>
  );
}


// 상세 정보의 한 칸 (아이콘 + 이름 + 값)
function InfoItem({ icon: Icon, label, value }) {
  return (
    <div>
      <dt className="flex items-center gap-1 text-ink/60">
        <Icon className="h-3.5 w-3.5" aria-hidden="true" />
        {label}
      </dt>
      <dd className="mt-0.5 font-semibold">{value}</dd>
    </div>
  );
}
