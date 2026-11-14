// ---------------------------------------------------------------------
// GameThumb: 게임 표지 이미지 칸
// 이미지 주소가 없거나 불러오기에 실패하면 게임 이름 첫 글자를 대신 보여준다.
//
// 받는 정보(props)
//   src           : 이미지 주소 (빈 글자일 수 있음)
//   name          : 게임 이름 (첫 글자를 대체 표시에 씀)
//   className     : 바깥 칸의 크기·모양 (예: "h-16 w-16 rounded-xl")
//   letterClassName : 대체 글자 크기 (예: "text-[28px]")
// ---------------------------------------------------------------------
import clsx from "clsx";
import { useState } from "react";

interface GameThumbProps {
  src?: string | null;
  name: string;
  className?: string;
  letterClassName?: string;
}

export default function GameThumb({ src, name, className = "", letterClassName = "text-[28px]" }: GameThumbProps) {
  // 이미지 주소가 있는데 불러오기에 실패했는지 기억하는 값
  // (주소가 바뀌면 다시 시도할 수 있도록 실패한 주소를 기억)
  const [failedSrc, setFailedSrc] = useState("");
  const showImage = src && failedSrc !== src;

  return (
    <span className={clsx("flex shrink-0 items-center justify-center overflow-hidden bg-line", className)} aria-hidden="true">
      {showImage ? (
        <img
          src={src}
          alt=""
          loading="lazy"
          onError={() => setFailedSrc(src ?? "")}
          className="h-full w-full object-cover"
        />
      ) : (
        <span className={clsx("font-display font-extrabold text-primary", letterClassName)}>{name.trim().charAt(0)}</span>
      )}
    </span>
  );
}
