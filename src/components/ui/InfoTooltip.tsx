"use client";

import * as Tooltip from "@radix-ui/react-tooltip";

type InfoTooltipProps = {
  content: string;
  children?: React.ReactNode;
};

export function InfoTooltip({ content, children }: InfoTooltipProps) {
  return (
    <Tooltip.Provider delayDuration={300}>
      <Tooltip.Root>
        <Tooltip.Trigger asChild>
          {children ?? (
            <span className="inline-flex items-center justify-center w-3.5 h-3.5 rounded-full bg-zinc-700 text-[9px] font-bold text-zinc-300 cursor-help hover:bg-zinc-600 transition">
              ?
            </span>
          )}
        </Tooltip.Trigger>
        <Tooltip.Portal>
          <Tooltip.Content
            side="top"
            sideOffset={4}
            className="max-w-[180px] rounded-md bg-zinc-800 border border-zinc-700 px-2.5 py-1.5 text-[11px] leading-snug text-zinc-200 shadow-lg animate-in fade-in-0 zoom-in-95 z-50"
          >
            {content}
            <Tooltip.Arrow className="fill-zinc-800" />
          </Tooltip.Content>
        </Tooltip.Portal>
      </Tooltip.Root>
    </Tooltip.Provider>
  );
}
