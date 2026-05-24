import { line, curveLinear } from "d3-shape";
import {
  useCallback,
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
  type PointerEvent as ReactPointerEvent,
} from "react";
import {
  buildTicks,
  findBreakevens,
  formatPnlTick,
  formatPriceTick,
  pnlAtPrice,
} from "../lib/payoffExpiry";
import type { PayoffPoint } from "../types";
import { MetricCell } from "./MetricCell";

type PayoffChartProps = {
  data: PayoffPoint[];
  currentPrice: number;
  accentColor?: string;
  compact?: boolean;
};

const MARGIN = { top: 20, right: 16, bottom: 36, left: 52 };

function useChartSize(ref: React.RefObject<HTMLDivElement | null>) {
  const [size, setSize] = useState({ width: 320, height: 200 });

  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    const update = () => {
      const w = el.clientWidth || 320;
      const h = Math.max(200, Math.min(w * 0.48, 380));
      setSize({ width: w, height: h });
    };

    update();
    const ro = new ResizeObserver(update);
    ro.observe(el);
    return () => ro.disconnect();
  }, [ref]);

  return size;
}

export function PayoffChart({
  data,
  currentPrice,
  accentColor = "#c9a655",
  compact = false,
}: PayoffChartProps) {
  const uid = useId().replace(/:/g, "");
  const wrapRef = useRef<HTMLDivElement>(null);
  const { width, height } = useChartSize(wrapRef);
  const [spotPrice, setSpotPrice] = useState(currentPrice);
  const [dragging, setDragging] = useState(false);

  useEffect(() => {
    setSpotPrice(currentPrice);
  }, [currentPrice]);

  const plotW = width - MARGIN.left - MARGIN.right;
  const plotH = height - MARGIN.top - MARGIN.bottom;

  const geom = useMemo(() => {
    if (!data.length || plotW <= 0 || plotH <= 0) return null;

    const prices = data.map((d) => d.price);
    const pnls = data.map((d) => d.pnl);
    const pMin = Math.min(...prices);
    const pMax = Math.max(...prices);
    const pSpan = pMax - pMin || 1;
    let yMin = Math.min(...pnls, 0);
    let yMax = Math.max(...pnls, 0);
    const ySpan = yMax - yMin || 1;
    const yPad = Math.max(ySpan * 0.08, 50);
    yMin -= yPad;
    yMax += yPad;
    const ySpanPlot = yMax - yMin || 1;

    const xScale = (p: number) => MARGIN.left + ((p - pMin) / pSpan) * plotW;
    const yScale = (pnl: number) =>
      MARGIN.top + (1 - (pnl - yMin) / ySpanPlot) * plotH;
    const zeroY = yScale(0);

    const linePath =
      line<PayoffPoint>()
        .x((d) => xScale(d.price))
        .y((d) => yScale(d.pnl))
        .curve(curveLinear)(data) ?? "";

    const areaPath = `${linePath} L${xScale(data[data.length - 1].price).toFixed(2)},${zeroY.toFixed(2)} L${xScale(data[0].price).toFixed(2)},${zeroY.toFixed(2)} Z`;

    const priceTicks = buildTicks(pMin, pMax, Math.max(4, Math.floor(plotW / 72)));
    const pnlTicks = buildTicks(yMin, yMax, Math.max(4, Math.floor(plotH / 36)));
    const breakevens = findBreakevens(data);

    return {
      pMin,
      pMax,
      yMin,
      yMax,
      xScale,
      yScale,
      zeroY,
      linePath,
      areaPath,
      priceTicks,
      pnlTicks,
      breakevens,
    };
  }, [data, plotW, plotH]);

  const priceFromClientX = useCallback(
    (clientX: number) => {
      if (!geom || !wrapRef.current) return currentPrice;
      const rect = wrapRef.current.getBoundingClientRect();
      const x = clientX - rect.left;
      const ratio = Math.min(
        1,
        Math.max(0, (x - MARGIN.left) / (rect.width - MARGIN.left - MARGIN.right)),
      );
      return geom.pMin + ratio * (geom.pMax - geom.pMin);
    },
    [geom, currentPrice],
  );

  const onPointerDown = (e: ReactPointerEvent) => {
    e.stopPropagation();
    e.currentTarget.setPointerCapture(e.pointerId);
    setDragging(true);
    setSpotPrice(priceFromClientX(e.clientX));
  };

  const onPointerMove = (e: ReactPointerEvent) => {
    if (!dragging) return;
    setSpotPrice(priceFromClientX(e.clientX));
  };

  const onPointerUp = (e: ReactPointerEvent) => {
    setDragging(false);
    e.currentTarget.releasePointerCapture(e.pointerId);
  };

  if (!geom) return null;

  const {
    xScale,
    yScale,
    zeroY,
    linePath,
    areaPath,
    priceTicks,
    pnlTicks,
    breakevens,
  } = geom;

  const clampedSpot = Math.max(geom.pMin, Math.min(geom.pMax, spotPrice));
  const spotX = xScale(clampedSpot);
  const spotPnl = pnlAtPrice(data, clampedSpot);
  const isProfit = spotPnl >= 0;
  const pnlColor = isProfit ? "var(--positive)" : "var(--negative)";

  const fillMaskId = `payoff-fill-mask-${uid}`;
  const strokeGradId = `payoff-stroke-${uid}`;

  return (
    <div
      ref={wrapRef}
      className="payoff-chart-wrap payoff-chart-expiry"
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={onPointerUp}
      onPointerCancel={onPointerUp}
      style={{
        touchAction: "none",
        cursor: dragging ? "grabbing" : "crosshair",
        minHeight: height,
      }}
    >
      <svg
        width={width}
        height={height}
        viewBox={`0 0 ${width} ${height}`}
        role="application"
        aria-label="Profit and loss at expiration by stock price"
        style={{ display: "block", width: "100%", height }}
      >
        <defs>
          <linearGradient id={strokeGradId} x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%" stopColor="#3dd68c" />
            <stop offset="45%" stopColor="#c9a655" />
            <stop offset="100%" stopColor="#ff6b6b" />
          </linearGradient>
          <linearGradient id={`payoff-fill-up-${uid}`} x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%" stopColor="#3dd68c" stopOpacity="0.35" />
            <stop offset="100%" stopColor="#3dd68c" stopOpacity="0.02" />
          </linearGradient>
          <linearGradient id={`payoff-fill-down-${uid}`} x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%" stopColor="#ff6b6b" stopOpacity="0.02" />
            <stop offset="100%" stopColor="#ff6b6b" stopOpacity="0.35" />
          </linearGradient>
          <mask id={fillMaskId}>
            <rect x={0} y={0} width={width} height={zeroY} fill="#fff" />
          </mask>
          <mask id={`${fillMaskId}-rev`}>
            <rect x={0} y={zeroY} width={width} height={height - zeroY} fill="#fff" />
          </mask>
        </defs>

        {/* Grid + Y ticks */}
        {pnlTicks.map((v) => (
          <g key={`y-${v}`}>
            <line
              x1={MARGIN.left}
              y1={yScale(v)}
              x2={width - MARGIN.right}
              y2={yScale(v)}
              stroke="rgba(255,255,255,0.06)"
              strokeWidth={v === 0 ? 0 : 0.5}
            />
            <text
              x={MARGIN.left - 8}
              y={yScale(v)}
              textAnchor="end"
              dominantBaseline="middle"
              fill={v === 0 ? "rgba(255,255,255,0.55)" : "rgba(255,255,255,0.28)"}
              fontSize={10}
              fontFamily="var(--mono)"
              fontWeight={v === 0 ? 600 : 400}
            >
              {formatPnlTick(v)}
            </text>
          </g>
        ))}

        {/* Grid + X ticks */}
        {priceTicks.map((v) => (
          <g key={`x-${v}`}>
            <line
              x1={xScale(v)}
              y1={MARGIN.top}
              x2={xScale(v)}
              y2={height - MARGIN.bottom}
              stroke="rgba(255,255,255,0.05)"
              strokeWidth={0.5}
            />
            <text
              x={xScale(v)}
              y={height - MARGIN.bottom + 18}
              textAnchor="middle"
              fill="rgba(255,255,255,0.28)"
              fontSize={10}
              fontFamily="var(--mono)"
            >
              {formatPriceTick(v)}
            </text>
          </g>
        ))}

        {/* Zero line */}
        <line
          x1={MARGIN.left}
          y1={zeroY}
          x2={width - MARGIN.right}
          y2={zeroY}
          stroke="rgba(255,255,255,0.35)"
          strokeWidth={1}
        />

        {/* Fill profit / loss */}
        <path
          d={areaPath}
          fill={`url(#payoff-fill-up-${uid})`}
          mask={`url(#${fillMaskId})`}
        />
        <path
          d={areaPath}
          fill={`url(#payoff-fill-down-${uid})`}
          mask={`url(#${fillMaskId}-rev)`}
        />

        {/* Payoff line */}
        <path
          d={linePath}
          fill="none"
          stroke={`url(#${strokeGradId})`}
          strokeWidth={2.5}
          strokeLinejoin="round"
          strokeLinecap="round"
        />

        {/* Breakeven lines */}
        {breakevens.map((bp) => (
          <g key={bp}>
            <line
              x1={xScale(bp)}
              y1={MARGIN.top}
              x2={xScale(bp)}
              y2={height - MARGIN.bottom}
              stroke={accentColor}
              strokeWidth={1}
              strokeOpacity={0.35}
            />
            <text
              x={xScale(bp)}
              y={MARGIN.top - 6}
              textAnchor="middle"
              fill={accentColor}
              fontSize={9}
              fontFamily="var(--mono)"
              fontWeight={500}
            >
              {formatPriceTick(bp)}
            </text>
          </g>
        ))}

        {/* Spot price marker */}
        <line
          x1={spotX}
          y1={MARGIN.top}
          x2={spotX}
          y2={height - MARGIN.bottom}
          stroke="rgba(255,255,255,0.9)"
          strokeWidth={2}
          strokeDasharray="6,4"
        />

        <circle
          cx={spotX}
          cy={yScale(spotPnl)}
          r={5}
          fill={pnlColor}
          stroke="var(--bg-surface)"
          strokeWidth={2}
        />

        {/* Axis captions */}
        <text
          x={width / 2}
          y={height - 4}
          textAnchor="middle"
          fill="rgba(255,255,255,0.2)"
          fontSize={9}
          fontFamily="var(--mono)"
          letterSpacing="0.06em"
        >
          STOCK PRICE AT EXPIRATION
        </text>
        <text
          x={12}
          y={MARGIN.top + plotH / 2}
          textAnchor="middle"
          fill="rgba(255,255,255,0.2)"
          fontSize={9}
          fontFamily="var(--mono)"
          letterSpacing="0.06em"
          transform={`rotate(-90, 12, ${MARGIN.top + plotH / 2})`}
        >
          P&amp;L
        </text>
      </svg>

      <div className="payoff-chart-footer">
        <div
          className={`strategy-card-metrics${compact ? " strategy-card-metrics--compact" : ""}`}
        >
          <MetricCell label="Spot" value={formatPriceTick(clampedSpot)} />
          <MetricCell
            label="P&amp;L at spot"
            value={`${isProfit ? "+" : ""}${formatPnlTick(spotPnl)}`}
            color={pnlColor}
          />
        </div>
      </div>
    </div>
  );
}
