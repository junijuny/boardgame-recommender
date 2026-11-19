// ---------------------------------------------------------------------
// ChoicePickers: 추천 조건을 고르는 입력 묶음
//   PlayerPicker   : 인원 (큰 숫자 + "players" 버튼)
//   TimeSlotPicker : 플레이 시간 구간 (4칸으로 나뉜 슬라이더, 모래시계 손잡이)
//
// fieldset, legend: 관련된 입력들을 하나로 묶고 제목을 붙이는 HTML 태그
// ---------------------------------------------------------------------
import clsx from "clsx";
import { useRef } from "react";
import type { PointerEvent } from "react";
import { Hourglass } from "lucide-react";
import { TIME_SLOTS } from "../filters";
import { formatHourRange, formatHours } from "../format";
import { choiceColor, focusRing } from "../styles";
import type { TimeRange } from "../types";

// 받는 정보(props)
//   options  : 고를 수 있는 숫자 목록
//   value    : 지금 선택된 숫자
//   onChange : 버튼을 눌렀을 때 실행할 함수 (고른 숫자를 넘겨줌)
//   disabled : true면 모든 버튼을 못 누르게 함
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

// 받는 정보(props)
//   value    : 지금 선택된 구간 { min, max } (TIME_SLOTS 중 하나)
//   onChange : 다른 칸을 골랐을 때 실행할 함수 (새 구간을 넘겨줌)
//   disabled : true면 슬라이더를 못 움직이게 함
interface TimeSlotPickerProps {
  value: TimeRange;
  onChange: (value: TimeRange) => void;
  disabled?: boolean;
}

// 칸 경계의 눈금 (0, 0.5, 1, 1.5, 2)
const BOUNDARIES = [TIME_SLOTS[0].min, ...TIME_SLOTS.map((slot) => slot.max)];

export function TimeSlotPicker({ value, onChange, disabled }: TimeSlotPickerProps) {
  const count = TIME_SLOTS.length;
  const found = TIME_SLOTS.findIndex((slot) => slot.min === value.min && slot.max === value.max);
  const index = found === -1 ? 0 : found;
  const label = formatHourRange(value.min, value.max);
  const inputRef = useRef<HTMLInputElement>(null);

  function select(next: number) {
    if (next !== index) onChange(TIME_SLOTS[next]);
  }

  // 막대 위 손가락·마우스 위치가 몇 번째 칸인지
  function slotAt(event: PointerEvent<HTMLDivElement>) {
    const rect = event.currentTarget.getBoundingClientRect();
    const ratio = (event.clientX - rect.left) / rect.width;
    return Math.min(count - 1, Math.max(0, Math.floor(ratio * count)));
  }

  // 막대를 누르거나 끌면 그 칸으로 옮긴다. 누른 뒤에는 화살표 키로도 옮길 수 있게 입력에 포커스를 준다
  function handlePointerDown(event: PointerEvent<HTMLDivElement>) {
    if (disabled) return;
    // 기본 동작(마우스 누름의 포커스 이동, 글자 선택)을 막아야 아래에서 준 포커스가 남는다
    event.preventDefault();
    event.currentTarget.setPointerCapture(event.pointerId);
    inputRef.current?.focus({ preventScroll: true });
    select(slotAt(event));
  }
  function handlePointerMove(event: PointerEvent<HTMLDivElement>) {
    if (!event.currentTarget.hasPointerCapture(event.pointerId)) return;
    select(slotAt(event));
  }

  return (
    <fieldset disabled={disabled} className="disabled:opacity-60">
      <legend className="mb-3 font-bold">Play time</legend>
      <div className="flex flex-col gap-3 rounded-xl border-[1.5px] border-line bg-page px-4 pt-3.5 pb-3">
        <p className="font-display text-[22px] leading-none font-extrabold" aria-hidden="true">{label}</p>

        {/* 키보드·스크린리더용 range 입력은 눈에 안 보이게 두고, 마우스·터치는 막대가 직접 받는다
            touch-pan-y: 막대 위에서도 위아래 스크롤은 되고, 옆으로 끄는 건 슬라이더가 받는다 */}
        <div
          className={clsx("relative h-9 touch-pan-y", disabled ? "cursor-default" : "cursor-pointer")}
          onPointerDown={handlePointerDown}
          onPointerMove={handlePointerMove}
        >
          <input
            ref={inputRef}
            type="range"
            min={0}
            max={count - 1}
            step={1}
            value={index}
            onChange={(event) => select(Number(event.target.value))}
            aria-label="Play time"
            aria-valuetext={label}
            className="peer sr-only"
          />
          <div className="absolute inset-x-0 top-1/2 grid -translate-y-1/2 gap-1" style={{ gridTemplateColumns: `repeat(${count}, minmax(0, 1fr))` }} aria-hidden="true">
            {TIME_SLOTS.map((slot, i) => (
              <span
                key={slot.max}
                className={clsx("h-2.5 rounded-md transition-colors", i === index ? "bg-primary-dark" : "bg-line")}
              />
            ))}
          </div>
          {/* 손잡이: 고른 칸의 가운데로 미끄러지고, 칸을 바꿀 때마다 모래시계가 뒤집힌다 */}
          <span
            className="pointer-events-none absolute top-1/2 flex h-9 w-9 -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full border-2 border-primary-dark bg-card text-primary-dark shadow-[0_1px_3px_rgb(15_26_51/0.25)] transition-[left] duration-200 ease-out peer-focus-visible:outline-2 peer-focus-visible:outline-offset-3 peer-focus-visible:outline-primary-dark motion-reduce:transition-none"
            style={{ left: `${((index + 0.5) / count) * 100}%` }}
            aria-hidden="true"
          >
            <Hourglass key={index} className="h-[18px] w-[18px] motion-safe:animate-hourglass-flip" />
          </span>
        </div>

        <div className="relative h-4 text-[13px] text-ink/70" aria-hidden="true">
          {BOUNDARIES.map((m, i) => (
            <span
              key={m}
              className={clsx(
                "absolute whitespace-nowrap",
                i === 0 ? "" : i === BOUNDARIES.length - 1 ? "-translate-x-full" : "-translate-x-1/2",
              )}
              style={{ left: `${(i / count) * 100}%` }}
            >
              {i === BOUNDARIES.length - 1 ? `${formatHours(m)} hr` : formatHours(m)}
            </span>
          ))}
        </div>
      </div>
    </fieldset>
  );
}
