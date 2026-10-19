"use client";

import {
  CheckCircle2,
  AlertTriangle,
  Circle,
  Clock,
} from "lucide-react";
import type { AgentActivityStep } from "@/lib/types";

interface AgentActivityProps {
  activity: AgentActivityStep[];
}

export function AgentActivity({ activity }: AgentActivityProps) {
  return (
    <div className="bg-card border border-card-border rounded-lg overflow-hidden mb-4">
      <div className="px-4 py-3 bg-accent-dim/10 border-b border-card-border">
        <div className="flex items-center gap-2">
          <Clock className="h-3.5 w-3.5 text-accent" />
          <span className="text-[10px] font-bold tracking-wider text-accent">
            AI ACTIVITY
          </span>
        </div>
      </div>
      <div className="p-3">
        <div className="space-y-1.5">
          {activity.map((item, i) => (
            <div key={i} className="flex items-start gap-2.5 text-[11px]">
              <div className="mt-0.5 shrink-0">
                {item.status === "completed" ? (
                  <CheckCircle2 className="h-3 w-3 text-success" />
                ) : item.status === "pending" ? (
                  <AlertTriangle className="h-3 w-3 text-accent" />
                ) : item.status === "warning" ? (
                  <AlertTriangle className="h-3 w-3 text-danger" />
                ) : item.status === "failed" ? (
                  <AlertTriangle className="h-3 w-3 text-danger" />
                ) : (
                  <Circle className="h-3 w-3 text-muted/30" />
                )}
              </div>
              <span
                className={`leading-tight ${
                  item.status === "completed"
                    ? "text-foreground/80"
                    : item.status === "pending"
                      ? "text-accent"
                      : item.status === "warning"
                        ? "text-danger"
                        : "text-muted/50"
                }`}
              >
                {item.step}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
