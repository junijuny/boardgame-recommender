// ---------------------------------------------------------------------
// SelectedGameCard: 검색에서 고른 게임을 보여주는 작은 카드
// 표지, 이름, 연도와 함께 인원·시간을 보여주고,
// "Details"를 누르면 상세 팝업을 연다.
// 인원·시간은 검색 결과에 없어서 상세 API(GET /games/{id})로 받아온다.
// (상세 팝업도 같은 데이터를 쓰므로 TanStack Query가 한 번만 요청한다)
//
// 받는 정보(props)
//   game         : 고른 게임 { BGGId, Name, YearPublished?, ImagePath? }
//   onShowDetail : "Details"를 눌렀을 때 실행할 함수 (게임 ID를 넘겨줌)
// ---------------------------------------------------------------------
import clsx from "clsx";
import GameThumb from "./GameThumb";
import { formatPlayers, formatPlaytime } from "../format";
import { useGameDetail } from "../queries";
import { focusRing } from "../styles";
import type { GameSummary } from "../types";

interface SelectedGameCardProps {
  game: GameSummary;
  onShowDetail: (bggId: number) => void;
}

export default function SelectedGameCard({ game, onShowDetail }: SelectedGameCardProps) {
  // 상세 정보 (불러오기 전이나 실패하면 undefined → 이름만 보여줌)
  const { data: detail } = useGameDetail(game.BGGId);
  // 상세 정보가 오면 그 값을, 아직이면 검색 결과에 있던 값을 사용
  const info = detail ?? game;

  return (
    <div className="flex items-center gap-3.5 rounded-[14px] border border-line bg-page p-3">
      <GameThumb src={info.ImagePath} name={info.Name} className="h-14 w-14 rounded-[10px]" letterClassName="text-[26px]" />
      <div className="min-w-0 flex-1">
        <p className="text-[17px] leading-snug font-bold">
          {info.Name}
          {info.YearPublished > 0 && <span className="ml-1.5 text-sm font-normal text-ink/70">{info.YearPublished}</span>}
        </p>
        {detail && (
          <p className="mt-0.5 text-sm text-ink/70">
            {formatPlayers(detail)}, {formatPlaytime(detail)}
          </p>
        )}
      </div>
      <button
        type="button"
        onClick={() => onShowDetail(game.BGGId)}
        aria-haspopup="dialog"
        className={clsx("inline-flex min-h-11 shrink-0 items-center rounded-lg px-2 text-sm font-bold text-primary hover:underline", focusRing)}
      >
        Details
      </button>
    </div>
  );
}
