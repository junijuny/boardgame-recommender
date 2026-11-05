// ---------------------------------------------------------------------
// GameThumb: 게임 표지 이미지 칸
// 이미지 주소가 없거나 불러오기에 실패하면 주사위 아이콘을 대신 보여준다.
//
// 받는 정보(props)
//   src           : 이미지 주소 (빈 글자일 수 있음)
//   className     : 바깥 칸의 크기·모양 (예: "h-16 w-16 rounded-lg")
//   iconClassName : 주사위 아이콘 크기 (예: "h-7 w-7")
// ---------------------------------------------------------------------
import { useState } from "react";
import { Dices } from "lucide-react";

export default function GameThumb({ src, className = "", iconClassName = "h-7 w-7" }) {
  // 이미지 주소가 있는데 불러오기에 실패했는지 기억하는 값
  // (주소가 바뀌면 다시 시도할 수 있도록 실패한 주소를 기억)
  const [failedSrc, setFailedSrc] = useState("");
  const showImage = src && failedSrc !== src;

  return (
    <div className={`flex shrink-0 items-center justify-center overflow-hidden bg-line ${className}`}>
      {showImage ? (
        <img
          src={src}
          alt=""
          loading="lazy"
          onError={() => setFailedSrc(src)}
          className="h-full w-full object-cover"
        />
      ) : (
        <Dices className={`text-primary ${iconClassName}`} strokeWidth={1.75} aria-hidden="true" />
      )}
    </div>
  );
}
