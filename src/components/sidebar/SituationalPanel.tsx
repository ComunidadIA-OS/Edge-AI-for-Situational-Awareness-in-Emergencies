"use client";

import { AlertTriangle, TrendingUp, Activity, Flame, Zap, CheckSquare } from "lucide-react";
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

const TREND_LABEL: Record<FireTrend, string> = {
  growing: "Growing",
  stable: "Stable",
  shrinking: "Shrinking",
  extinguishing: "Extinguishing",
};

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
  const isCritical =
    prediction.fire_weather_index >= 70 ||
    sa.warnings.some((w) => w.startsWith("CRITICAL"));

  return (
    <div className="space-y-4 pb-2">
      {/* Critical header */}
      {isCritical && (
        <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-red-900/60 border border-red-600/60 animate-pulse">
          <AlertTriangle className="w-4 h-4 text-red-400 flex-shrink-0" />
          <span className="text-xs font-semibold text-red-300">CRITICAL SITUATION — FWI {Math.round(prediction.fire_weather_index)}</span>
        </div>
      )}

      {/* KPIs */}
      <div>
        <p className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-2 flex items-center gap-1.5">
          <TrendingUp className="w-3 h-3" /> Key metrics
        </p>
        <div className="grid grid-cols-2 gap-2">
          {kpi("Current area", Math.round(fp.area_ha), "ha")}
          {kpi("24h forecast", Math.round(prediction.predicted_area_24h_ha), "ha", isCritical)}
          {kpi(
            "Spread",
            Math.round(prediction.spread_rate_mh),
            "m/h",
            false,
            "Estimated head-fire spread in metres per hour."
          )}
          {kpi(
            "FWI",
            Math.round(prediction.fire_weather_index),
            "",
            prediction.fire_weather_index >= 50,
            "Fire Weather Index — Canadian standard scale 0–100. ≥ 70 means critical fire weather."
          )}
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

      {/* Narrative text */}
      <div className="space-y-2 text-xs text-zinc-300 leading-relaxed">
        <p>{sa.summary}</p>
        <p className="text-zinc-400">{sa.fire_behavior}</p>
        <p className="text-zinc-500">{sa.weather_summary}</p>
      </div>

      {/* Warnings */}
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

      {/* Recommended actions */}
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

      {/* Infrastructure at risk */}
      {sa.infrastructure_at_risk.length > 0 && (
        <div>
          <p className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-2">Infrastructure at risk</p>
          <div className="space-y-1.5">
            {sa.infrastructure_at_risk.map((item, i) => (
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
        </div>
      )}

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
