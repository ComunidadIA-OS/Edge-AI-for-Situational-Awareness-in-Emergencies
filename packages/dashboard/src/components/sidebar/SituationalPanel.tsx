"use client";

import { useState } from "react";
import {
  AlertTriangle,
  TrendingUp,
  Activity,
  Flame,
  Zap,
  CheckSquare,
  ChevronDown,
  Gauge,
  Building2,
} from "lucide-react";
import { useMeteoReport } from "@/src/api/meteo-report";
import { SchemaValidationError } from "@/src/api/SchemaValidationError";
import { InfoTooltip } from "@/src/components/ui/InfoTooltip";
import { cn } from "@/src/lib/utils";
import type { FireTrend, RiskLevel } from "@/src/types/meteo-report";

function kpi(label: string, value: string | number | null, unit: string, highlight = false, tooltip?: string) {
  return (
    <div className={cn("rounded-lg p-2.5", highlight ? "bg-red-950/60 border border-red-700/50" : "bg-zinc-800/60")}>
      <p className="text-[10px] font-medium text-zinc-400 uppercase tracking-wide flex items-center gap-1">
        {label}
        {tooltip && <InfoTooltip content={tooltip} />}
      </p>
      <p className={cn("text-lg font-bold leading-tight", highlight ? "text-red-300" : "text-white")}>
        {value === null || value === undefined ? <span className="text-zinc-500 text-sm italic">computing…</span> : value}
        {value !== null && value !== undefined && <span className="text-xs font-normal text-zinc-400 ml-1">{unit}</span>}
      </p>
    </div>
  );
}

/** Collapsible disclosure block — keeps technical depth available without
 *  overwhelming a first-time reader. Closed by default unless told otherwise. */
function Section({
  title,
  icon,
  defaultOpen = false,
  children,
}: {
  title: string;
  icon: React.ReactNode;
  defaultOpen?: boolean;
  children: React.ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="rounded-lg border border-zinc-800 overflow-hidden">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        className="w-full flex items-center gap-1.5 px-3 py-2 text-xs font-semibold text-zinc-400 uppercase tracking-wider hover:bg-zinc-800/40 transition"
      >
        {icon}
        <span className="flex-1 text-left">{title}</span>
        <ChevronDown className={cn("w-3.5 h-3.5 transition-transform flex-shrink-0", open && "rotate-180")} />
      </button>
      {open && <div className="px-3 pb-3 pt-0.5">{children}</div>}
    </div>
  );
}

const TREND_LABEL: Record<FireTrend, string> = {
  growing: "Growing",
  stable: "Stable",
  shrinking: "Shrinking",
  extinguishing: "Extinguishing",
};

/** Human phrasing for the at-a-glance sentence. */
const TREND_PHRASE: Record<FireTrend, string> = {
  growing: "growing",
  stable: "holding steady",
  shrinking: "receding",
  extinguishing: "dying down",
};

function dangerWord(fwi: number): string {
  if (fwi >= 70) return "critical";
  if (fwi >= 50) return "high";
  if (fwi >= 30) return "moderate";
  return "low";
}

const RISK_COLOR: Record<RiskLevel, string> = {
  low: "bg-green-500/20 text-green-300 border-green-600/40",
  moderate: "bg-yellow-500/20 text-yellow-300 border-yellow-600/40",
  high: "bg-orange-500/20 text-orange-300 border-orange-600/40",
  extreme: "bg-red-500/20 text-red-300 border-red-600/40",
};

export function SituationalPanel() {
  const { data: report, isPending, isError, error } = useMeteoReport();

  if (isPending) {
    return (
      <div className="flex flex-col items-center justify-center h-40 gap-2 text-zinc-500">
        <Activity className="w-5 h-5 animate-pulse" />
        <p className="text-sm">Waiting for Jetson data…</p>
      </div>
    );
  }

  if (isError || !report) {
    const isSchemaError = error instanceof SchemaValidationError;
    return (
      <div className="flex flex-col items-center justify-center h-40 gap-2 text-red-400">
        <AlertTriangle className="w-5 h-5" />
        <p className="text-sm font-medium">
          {isSchemaError ? "Jetson reachable but payload invalid" : "No Jetson data"}
        </p>
        {isSchemaError && (
          <p className="text-xs text-zinc-500 text-center max-w-[200px]">
            Check device firmware version — schema mismatch detected.
          </p>
        )}
      </div>
    );
  }

  const { prediction, situational_awareness: sa, fire_perimeter: fp } = report;
  const fwi = prediction.fire_weather_index;
  const isCritical = fwi >= 70 || sa.warnings.some((w) => w.startsWith("CRITICAL"));

  // Nearest asset, for the plain-language headline.
  const assets = sa.infrastructure_at_risk;
  const nearest =
    assets.length > 0
      ? assets.reduce((a, b) => (b.distance_km < a.distance_km ? b : a))
      : null;

  return (
    <div className="space-y-4 pb-2">
      {/* Critical header */}
      {isCritical && (
        <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-red-900/60 border border-red-600/60 animate-pulse">
          <AlertTriangle className="w-4 h-4 text-red-400 flex-shrink-0" />
          <span className="text-xs font-semibold text-red-300">CRITICAL SITUATION — FWI {Math.round(fwi)}</span>
        </div>
      )}

      {/* At a glance — plain-language summary for first-time readers */}
      <div className="rounded-lg bg-zinc-800/40 border border-zinc-700/60 px-3 py-2.5">
        <p className="text-[10px] font-semibold text-zinc-500 uppercase tracking-wider mb-1 flex items-center gap-1">
          <Flame className="w-3 h-3 text-orange-400" /> At a glance
        </p>
        <p className="text-xs text-zinc-200 leading-relaxed">
          The fire now covers <strong className="text-white">{Math.round(fp.area_ha)} ha</strong>{" "}
          and is <strong className="text-white">{TREND_PHRASE[prediction.trend]}</strong>. Fire-weather
          danger is{" "}
          <strong className={cn(fwi >= 70 ? "text-red-300" : fwi >= 50 ? "text-amber-300" : "text-zinc-200")}>
            {dangerWord(fwi)}
          </strong>{" "}
          (FWI {Math.round(fwi)}).
          {nearest && (
            <>
              {" "}
              <strong className="text-white">{assets.length}</strong>{" "}
              {assets.length === 1 ? "asset is" : "assets are"} in the risk zone — nearest is{" "}
              <strong className="text-white">{nearest.name}</strong>, {nearest.distance_km.toFixed(1)} km
              away (~{nearest.eta_hours.toFixed(0)}h).
            </>
          )}
        </p>
      </div>

      {/* Primary KPIs — the four headline numbers */}
      <div>
        <p className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-2 flex items-center gap-1.5">
          <TrendingUp className="w-3 h-3" /> Key metrics
        </p>
        <div className="grid grid-cols-2 gap-2">
          {kpi("Current area", Math.round(fp.area_ha), "ha", false, "Hectares currently inside the detected fire perimeter.")}
          {kpi("24h forecast", Math.round(prediction.predicted_area_24h_ha), "ha", isCritical, "Predicted burned area 24 hours from now if conditions hold.")}
          {kpi(
            "Spread",
            Math.round(prediction.spread_rate_mh),
            "m/h",
            false,
            "Estimated head-fire spread in metres per hour."
          )}
          {kpi(
            "FWI",
            Math.round(fwi),
            "",
            fwi >= 50,
            "Fire Weather Index — Canadian standard scale 0–100. ≥ 70 means critical fire weather."
          )}
        </div>
      </div>

      {/* Trend badge */}
      <div className="flex items-center gap-2">
        <Flame className="w-3.5 h-3.5 text-orange-400 flex-shrink-0" />
        <span className="text-xs text-zinc-400">Trend:</span>
        <span className={cn("text-xs px-2 py-0.5 rounded-full border font-medium", RISK_COLOR[prediction.trend === "growing" ? "high" : prediction.trend === "stable" ? "moderate" : "low"])}>
          {TREND_LABEL[prediction.trend]}
        </span>
        <span className="text-xs text-zinc-500 ml-auto">{Math.round(prediction.confidence * 100)}% confidence</span>
      </div>

      {/* Summary narrative — model's own short readout */}
      <p className="text-xs text-zinc-300 leading-relaxed">{sa.summary}</p>

      {/* Warnings — kept up-front, they're actionable */}
      {sa.warnings.length > 0 && (
        <div>
          <p className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-2 flex items-center gap-1.5">
            <AlertTriangle className="w-3 h-3 text-amber-400" /> Warnings
          </p>
          <div className="space-y-1.5">
            {sa.warnings.map((w, i) => (
              <div
                key={i}
                className={cn(
                  "text-xs px-2.5 py-1.5 rounded-lg border",
                  w.startsWith("CRITICAL")
                    ? "bg-red-950/50 border-red-700/50 text-red-300"
                    : "bg-amber-950/40 border-amber-700/40 text-amber-300"
                )}
              >
                {w}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Recommended actions — kept up-front */}
      {sa.recommended_actions.length > 0 && (
        <div>
          <p className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-2 flex items-center gap-1.5">
            <CheckSquare className="w-3 h-3 text-emerald-400" /> Recommended actions
          </p>
          <ul className="space-y-1.5">
            {sa.recommended_actions.map((action, i) => (
              <li key={i} className="flex items-start gap-2 text-xs text-zinc-300">
                <Zap className="w-3 h-3 text-emerald-400 flex-shrink-0 mt-0.5" />
                {action}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* ── Progressive disclosure: detail tucked into collapsibles ───────── */}

      {/* Infrastructure at risk */}
      {assets.length > 0 && (
        <Section
          title={`Infrastructure at risk (${assets.length})`}
          icon={<Building2 className="w-3 h-3 text-zinc-400 flex-shrink-0" />}
          defaultOpen={isCritical}
        >
          <div className="space-y-1.5">
            {assets.map((item, i) => (
              <div key={i} className="flex items-center gap-2 text-xs">
                <span className={cn("px-1.5 py-0.5 rounded text-[10px] font-medium border", RISK_COLOR[item.risk_level])}>
                  {item.risk_level.toUpperCase()}
                </span>
                <span className="text-zinc-300 truncate flex-1">{item.name}</span>
                <span className="text-zinc-500 whitespace-nowrap">
                  {item.distance_km.toFixed(1)} km · {item.eta_hours.toFixed(0)}h
                </span>
              </div>
            ))}
          </div>
        </Section>
      )}

      {/* Full fire & weather analysis */}
      <Section
        title="Detailed analysis"
        icon={<Activity className="w-3 h-3 text-zinc-400 flex-shrink-0" />}
      >
        <div className="space-y-2 text-xs leading-relaxed">
          <p className="text-zinc-400">{sa.fire_behavior}</p>
          <p className="text-zinc-500">{sa.weather_summary}</p>
        </div>
      </Section>

      {/* Advanced growth metrics — the derivatives newcomers find cryptic */}
      <Section
        title="Advanced metrics"
        icon={<Gauge className="w-3 h-3 text-zinc-400 flex-shrink-0" />}
      >
        <div className="grid grid-cols-2 gap-2">
          {kpi(
            "dA/dt",
            prediction.growth_rate_m2_s !== null ? prediction.growth_rate_m2_s.toFixed(1) : null,
            "m²/s",
            false,
            "Rate of area growth in m²/s. How fast the fire is currently expanding."
          )}
          {kpi(
            "d²A/dt²",
            prediction.acceleration_m2_s2 !== null ? prediction.acceleration_m2_s2.toFixed(2) : null,
            "m²/s²",
            false,
            "Acceleration of area growth in m²/s². Positive = the fire is speeding up."
          )}
        </div>
      </Section>

      {/* Footer: model info */}
      <div className="pt-1 border-t border-zinc-800 text-[10px] text-zinc-600 space-y-0.5">
        <p>Model: {report.metadata.model_version} · {" "}
          <span className="inline-flex items-center gap-0.5">
            {report.prediction.fuel_model_name}
            <InfoTooltip content="Vegetation type used by the spread model (e.g. grass, shrub, timber-litter)." />
          </span>
        </p>
        <p>Sources: {report.metadata.data_sources.join(", ")}</p>
      </div>
    </div>
  );
}
