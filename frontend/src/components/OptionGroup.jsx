// ---------------------------------------------------------------------
// OptionGroup: 버튼 여러 개 중에 하나를 고르는 묶음
// 인원 고르기, 시간 고르기에서 같이 재사용한다.
//
// 받는 정보(props)
//   icon     : 묶음 제목 옆에 보여줄 아이콘
//   label    : 묶음 제목 (예: "인원")
//   options  : 버튼 목록 [{ value, label }, ...]
//   value    : 지금 선택된 값
//   onChange : 버튼을 눌렀을 때 값을 바꿀 함수
//   disabled : true면 모든 버튼을 못 누르게 함
//
// fieldset, legend: 관련된 입력들을 하나로 묶고 제목을 붙이는 HTML 태그
// icon: Icon 이라고 쓴 이유:
//   리액트는 대문자로 시작하는 이름만 컴포넌트로 알아봐서,
//   받은 icon을 Icon(대문자)이라는 이름으로 바꿔서 <Icon /> 으로 쓰는 것
// ---------------------------------------------------------------------

import { choiceClass } from "../styles.js";

export default function OptionGroup({ icon: Icon, label, options, value, onChange, disabled }) {
  return (
    <fieldset disabled={disabled}>
      <legend className="mb-2 flex items-center gap-1.5 text-sm font-semibold">
        <Icon className="h-4 w-4 text-primary" aria-hidden="true" />
        {label}
      </legend>
      <div className="flex flex-wrap gap-2">
        {options.map((opt) => {
          // 이 버튼이 지금 선택된 버튼인지 확인
          const selected = value === opt.value;
          return (
            <button
              key={opt.value}
              type="button"
              onClick={() => onChange(opt.value)}
              aria-pressed={selected}
              className={choiceClass(selected)}
            >
              {opt.label}
            </button>
          );
        })}
      </div>
    </fieldset>
  );
}
