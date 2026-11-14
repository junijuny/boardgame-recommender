// ---------------------------------------------------------------------
// ChoicePickers: 추천 조건을 고르는 버튼 묶음
//   PlayerPicker : 인원 (큰 숫자 + "players")
//   TimePicker   : 최대 플레이 시간 (글자 + 시간 길이만큼 차는 막대)
//
// 받는 정보(props) — 두 묶음 모두 같음
//   options  : 고를 수 있는 숫자 목록
//   value    : 지금 선택된 숫자
//   onChange : 버튼을 눌렀을 때 실행할 함수 (고른 숫자를 넘겨줌)
//   disabled : true면 모든 버튼을 못 누르게 함
//
// fieldset, legend: 관련된 입력들을 하나로 묶고 제목을 붙이는 HTML 태그
// ---------------------------------------------------------------------
import clsx from "clsx";
import { formatMinutes } from "../format";
import { choiceColor, focusRing } from "../styles";

interface PickerProps {
  options: number[];
  value: number;
  onChange: (value: number) => void;
  disabled?: boolean;
}

export function PlayerPicker({ options, value, onChange, disabled }: PickerProps) {
  return (
    <fieldset disabled={disabled}>
      <legend className="mb-3 font-bold">Players</legend>
      <div className="grid grid-cols-5 gap-2">
        {options.map((n) => {
          const selected = n === value;
          return (
            <button
              key={n}
              type="button"
              onClick={() => onChange(n)}
              aria-pressed={selected}
              className={clsx("flex min-h-[72px] flex-col items-center justify-center gap-0.5 rounded-[14px] border-[1.5px] px-1 transition-colors disabled:opacity-60", focusRing, choiceColor(selected))}
            >
              <span className="font-display text-[26px] leading-none font-extrabold">{n}</span>
              <span className="text-[13px] font-medium">players</span>
            </button>
          );
        })}
      </div>
    </fieldset>
  );
}

export function TimePicker({ options, value, onChange, disabled }: PickerProps) {
  const longest = Math.max(...options);
  return (
    <fieldset disabled={disabled}>
      <legend className="mb-3 font-bold">Play time</legend>
      <div className="flex flex-col gap-1.5">
        {options.map((m) => {
          const selected = m === value;
          return (
            <button
              key={m}
              type="button"
              onClick={() => onChange(m)}
              aria-pressed={selected}
              className={clsx("grid min-h-12 grid-cols-[112px_minmax(0,1fr)] items-center gap-3 rounded-xl border-[1.5px] px-3.5 text-left transition-colors disabled:opacity-60", focusRing, selected ? "border-primary-dark bg-primary-dark text-card" : "border-line bg-page text-ink hover:border-primary")}
            >
              <span className="text-[15px] font-bold">Up to {formatMinutes(m)}</span>
              {/* 막대 길이 = 가장 긴 시간 대비 비율 */}
              <span className={clsx("h-2 overflow-hidden rounded-full", selected ? "bg-card/25" : "bg-line")} aria-hidden="true">
                <span
                  className={clsx("block h-full rounded-full", selected ? "bg-card" : "bg-ink/40")}
                  style={{ width: `${(m / longest) * 100}%` }}
                />
              </span>
            </button>
          );
        })}
      </div>
    </fieldset>
  );
}
