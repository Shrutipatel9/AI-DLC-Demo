// A simple outline for each face shape (US8.8, AC8.8.2). Decorative: the shape's name and
// description are always shown as text next to it.
const OUTLINES = new Map<string, string>(
  Object.entries({
    oval: "M50 8 C78 8 90 38 90 66 C90 100 70 128 50 128 C30 128 10 100 10 66 C10 38 22 8 50 8 Z",
    round: "M50 14 C80 14 94 40 94 68 C94 98 74 124 50 124 C26 124 6 98 6 68 C6 40 20 14 50 14 Z",
    square: "M18 12 H82 Q92 12 92 24 V96 Q92 126 66 126 H34 Q8 126 8 96 V24 Q8 12 18 12 Z",
    heart: "M10 20 C10 8 90 8 90 20 C90 70 70 126 50 128 C30 126 10 70 10 20 Z",
    diamond: "M50 6 C60 30 92 52 92 68 C92 84 62 112 50 130 C38 112 8 84 8 68 C8 52 40 30 50 6 Z",
    oblong: "M50 4 C80 4 88 36 88 68 C88 108 72 132 50 132 C28 132 12 108 12 68 C12 36 20 4 50 4 Z",
  }),
);

export function FaceShapeWireframe({ name }: { name: string }) {
  const outline = OUTLINES.get(name) ?? OUTLINES.get("oval");
  return (
    <svg
      viewBox="0 0 100 136"
      className="h-36 w-28 text-accent-strong"
      role="img"
      aria-label={`Face shape outline: ${name}`}
      data-testid="face-shape-wireframe"
    >
      <path d={outline} fill="none" stroke="currentColor" strokeWidth="2.5" />
      <line
        x1="50"
        y1="8"
        x2="50"
        y2="128"
        stroke="currentColor"
        strokeWidth="1"
        strokeDasharray="3 4"
      />
    </svg>
  );
}
