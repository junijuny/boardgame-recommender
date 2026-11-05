// ---------------------------------------------------------------------
// SelectedGameCard: 검색에서 고른 게임을 보여주는 작은 카드
// 이미지, 이름, 연도와 함께 인원·시간·난이도를 보여주고,
// "자세히 보기"를 누르면 상세 팝업을 연다.
// 인원·시간·난이도는 검색 결과에 없어서 상세 API(GET /games/{id})로 받아온다.
//
// 받는 정보(props)
//   game         : 고른 게임 { BGGId, Name, YearPublished?, ImagePath? }
//   onShowDetail : "자세히 보기"를 눌렀을 때 실행할 함수 (게임 ID를 넘겨줌)
// ---------------------------------------------------------------------
import { useEffect, useState } from "react";
import { ChevronRight, Clock, Gauge, Users } from "lucide-react";
import { getGameDetail } from "../api.js";
import { formatPlayers, formatPlaytime } from "../format.js";
import GameThumb from "./GameThumb.jsx";

export default function SelectedGameCard({ game, onShowDetail }) {
  // 상세 정보 (불러오기 전이나 실패하면 null → 이름만 보여줌)
  const [detail, setDetail] = useState(null);

  useEffect(() => {
    const controller = new AbortController();
    getGameDetail(game.BGGId, controller.signal)
      .then(setDetail)
      .catch((err) => {
        // 정보를 못 받아와도 이름은 이미 있으니 카드는 그대로 보여줌
        if (!controller.signal.aborted) console.error(err);
      });
    // 다른 게임을 고르면 이전 요청을 취소
    return () => controller.abort();
  }, [game.BGGId]);

  // 상세 정보가 오면 그 값을, 아직이면 검색 결과에 있던 값을 사용
  const info = detail ?? game;

  return (
    <div className="flex items-center gap-4 rounded-lg border border-primary/30 bg-page p-3">
      <GameThumb src={info.ImagePath} className="h-20 w-20 rounded-lg" iconClassName="h-8 w-8" />
      <div className="min-w-0 flex-1">
        <p className="text-xs font-semibold text-primary">선택한 게임</p>
        <p className="mt-0.5 truncate font-bold">
          {info.Name}
          {info.YearPublished > 0 && (
            <span className="ml-1.5 text-sm font-normal text-ink/60">({info.YearPublished})</span>
          )}
        </p>
        {detail && (
          <p className="mt-1 flex flex-wrap gap-x-3 gap-y-1 text-sm text-ink/60">
            <span className="inline-flex items-center gap-1">
              <Users className="h-3.5 w-3.5" aria-hidden="true" />
              {formatPlayers(detail)}
            </span>
            <span className="inline-flex items-center gap-1">
              <Clock className="h-3.5 w-3.5" aria-hidden="true" />
              {formatPlaytime(detail)}
            </span>
            <span className="inline-flex items-center gap-1">
              <Gauge className="h-3.5 w-3.5" aria-hidden="true" />
              난이도 {(detail.GameWeight ?? 0).toFixed(1)} / 5
            </span>
          </p>
        )}
      </div>
      <button
        type="button"
        onClick={() => onShowDetail(game.BGGId)}
        aria-haspopup="dialog"
        className="inline-flex shrink-0 items-center gap-0.5 rounded-lg px-2 py-1.5 text-sm font-semibold text-primary transition-colors hover:bg-line focus-visible:outline-2 focus-visible:outline-primary-dark"
      >
        자세히 보기
        <ChevronRight className="h-4 w-4" aria-hidden="true" />
      </button>
    </div>
  );
}
