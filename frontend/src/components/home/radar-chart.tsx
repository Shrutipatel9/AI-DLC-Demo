// The six-axis Harmony Profile radar chart (US11.1, [RD] 12.1). It only draws values it is given:
// an axis with no value is labelled "Not measured" and is never plotted as 0 ([RD] 12.3). The
// same values are always listed as text under the chart (AC11.1.4).
import type { RadarAxis } from "@/lib/report";

const CENTER = 150;
const RADIUS = 100;
const LABEL_RADIUS = 124;
const RINGS = [25, 50, 75, 100] as const;

function point(index: number, count: number, radius: number): [number, number] {
  const angle = -Math.PI / 2 + (index * 2 * Math.PI) / count;
  return [CENTER + radius * Math.cos(angle), CENTER + radius * Math.sin(angle)];
}

function polygon(points: [number, number][]): string {
  return points.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(" ");
}

export function valueText(axis: RadarAxis): string {
  return axis.value === null ? "Not measured" : `${axis.value} out of 100`;
}

export function RadarChart({ axes }: { axes: RadarAxis[] }) {
  const count = axes.length;
  const plotted: [number, number][] = [];
  axes.forEach((axis, index) => {
    if (axis.value !== null) plotted.push(point(index, count, (RADIUS * axis.value) / 100));
  });
  return (
    <figure data-testid="radar-chart">
      <svg
        viewBox="0 0 300 300"
        className="mx-auto h-auto w-full max-w-[320px]"
        role="img"
        aria-label="Harmony Profile radar chart. The values are listed below the chart."
      >
        {RINGS.map((ring) => (
          <polygon
            key={ring}
            points={polygon(axes.map((_, index) => point(index, count, (RADIUS * ring) / 100)))}
            fill="none"
            stroke="#c9d3da"
            strokeWidth="1"
          />
        ))}
        {axes.map((axis, index) => {
          const [x, y] = point(index, count, RADIUS);
          return (
            <line
              key={axis.axis}
              x1={CENTER}
              y1={CENTER}
              x2={x}
              y2={y}
              stroke="#c9d3da"
              strokeWidth="1"
            />
          );
        })}
        {plotted.length >= 3 ? (
          <polygon
            points={polygon(plotted)}
            fill="rgba(42, 127, 115, 0.25)"
            stroke="#1f6159"
            strokeWidth="2"
          />
        ) : null}
        {plotted.map(([x, y]) => (
          <circle key={`${x}-${y}`} cx={x} cy={y} r="3.5" fill="#1f6159" />
        ))}
        {axes.map((axis, index) => {
          const [x, y] = point(index, count, LABEL_RADIUS);
          return (
            <text
              key={axis.axis}
              x={x}
              y={y}
              textAnchor="middle"
              dominantBaseline="middle"
              fontSize="12"
              fill="#1b2a35"
            >
              {axis.axis}
            </text>
          );
        })}
      </svg>
      <figcaption className="sr-only">Harmony Profile</figcaption>
      <dl className="mt-3 grid grid-cols-2 gap-x-4 gap-y-1 text-base" data-testid="radar-values">
        {axes.map((axis) => (
          <div
            key={axis.axis}
            className="flex justify-between gap-2 border-t border-card-border py-1"
          >
            <dt className="font-medium text-heading">{axis.axis}</dt>
            <dd>{valueText(axis)}</dd>
          </div>
        ))}
      </dl>
    </figure>
  );
}
