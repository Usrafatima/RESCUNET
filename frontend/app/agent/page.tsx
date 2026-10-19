"use client";

import {
  Bot,
  Brain,
  Database,
  Search,
  Shield,
  MapPin,
  BarChart3,
  CheckCircle2,
  AlertTriangle,
  ArrowRight,
  Zap,
  Settings,
} from "lucide-react";

const WORKFLOW_STEPS = [
  {
    icon: AlertTriangle,
    label: "INCIDENT",
    description: "Emergency report received",
    color: "text-danger",
    bg: "bg-danger/5",
  },
  {
    icon: Database,
    label: "GET INCIDENT",
    description: "Retrieve verified incident data",
    color: "text-accent",
    bg: "bg-accent/5",
  },
  {
    icon: Brain,
    label: "CLASSIFY",
    description: "Determine type and priority",
    color: "text-info",
    bg: "bg-tangerine/5",
  },
  {
    icon: Search,
    label: "FIND RESOURCES",
    description: "Search available responders",
    color: "text-accent",
    bg: "bg-accent/5",
  },
  {
    icon: Shield,
    label: "CHECK STATUS",
    description: "Verify resource availability",
    color: "text-success",
    bg: "bg-success/5",
  },
  {
    icon: MapPin,
    label: "CALCULATE DISTANCE",
    description: "Haversine geographic distance",
    color: "text-info",
    bg: "bg-tangerine/5",
  },
  {
    icon: BarChart3,
    label: "RECOMMEND",
    description: "Match best resource to incident",
    color: "text-accent",
    bg: "bg-accent/5",
  },
  {
    icon: CheckCircle2,
    label: "HUMAN APPROVAL",
    description: "Human decides before dispatch",
    color: "text-success",
    bg: "bg-success/5",
  },
];

const TOOLS = [
  {
    name: "get_incident",
    description: "Retrieve incident details from the backend database",
    icon: Database,
  },
  {
    name: "list_active_incidents",
    description: "Find all active/unresolved incidents",
    icon: Search,
  },
  {
    name: "find_available_resources",
    description: "Query community responders filtered by type",
    icon: Shield,
  },
  {
    name: "get_resource_status",
    description: "Check if a specific resource is available",
    icon: Settings,
  },
  {
    name: "calculate_distance",
    description: "Haversine distance between two coordinates",
    icon: MapPin,
  },
];

export default function AgentPage() {
  return (
    <div className="flex flex-col h-full overflow-auto">
      {/* Header */}
      <div className="px-4 md:px-6 py-2.5 border-b border-card-border bg-surface">
        <h1 className="text-base font-semibold tracking-wide">AI Agent</h1>
        <p className="text-[11px] text-muted">
          Powered by Strands Agents · Gemini model
        </p>
      </div>

      <div className="p-4 md:p-5 max-w-4xl mx-auto w-full space-y-4">
        {/* Intro */}
        <div className="flex items-start gap-3 py-2">
          <div className="w-9 h-9 rounded-md bg-accent/10 border border-accent/20 flex items-center justify-center shrink-0">
            <Bot className="h-5 w-5 text-accent" />
          </div>
          <div>
            <h2 className="text-sm font-semibold">RescuNet AI</h2>
            <p className="text-xs text-muted max-w-xl mt-0.5">
              An AI-powered emergency coordination agent that uses real tools
              to analyze incidents, find resources, and produce actionable
              response recommendations — always requiring human approval
              before dispatch.
            </p>
          </div>
        </div>

        {/* What the agent does */}
        <section className="bg-card border border-card-border rounded-md p-4">
          <h3 className="text-[11px] font-semibold text-foreground mb-3">
            What the agent does
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
            {[
              "Understands an emergency report",
              "Retrieves verified incident data via tools",
              "Classifies the incident type and priority",
              "Finds relevant community resources",
              "Checks resource availability in real-time",
              "Calculates geographic distance to incident",
              "Produces a response recommendation",
              "Leaves final action to a human decision-maker",
            ].map((item, i) => (
              <div key={i} className="flex items-start gap-2 text-[13px]">
                <CheckCircle2 className="h-3.5 w-3.5 text-success shrink-0 mt-1" />
                <span className="text-muted">{item}</span>
              </div>
            ))}
          </div>
        </section>

        {/* Agent Workflow */}
        <section className="bg-card border border-card-border rounded-md p-4">
          <h3 className="text-[11px] font-semibold text-foreground mb-3">
            Agent workflow
          </h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
            {WORKFLOW_STEPS.map((step, i) => (
              <div key={step.label} className="relative">
                <div
                  className={`${step.bg} border border-card-border rounded-md p-2.5 h-full`}
                >
                  <div className="flex items-center gap-1.5 mb-1.5">
                    <step.icon className={`h-3.5 w-3.5 ${step.color}`} />
                    <span
                      className={`text-[10px] font-semibold ${step.color}`}
                    >
                      {step.label}
                    </span>
                  </div>
                  <p className="text-[11px] text-muted leading-snug">
                    {step.description}
                  </p>
                </div>
                {i < WORKFLOW_STEPS.length - 1 && (
                  <div className="hidden md:flex absolute -right-2 top-1/2 -translate-y-1/2 z-10">
                    <ArrowRight className="h-3 w-3 text-muted/40" />
                  </div>
                )}
              </div>
            ))}
          </div>
        </section>

        {/* Tools */}
        <section className="bg-card border border-card-border rounded-md p-4">
          <h3 className="text-[11px] font-semibold text-foreground mb-3">
            Tools
          </h3>
          <div className="space-y-1.5">
            {TOOLS.map((tool) => (
              <div
                key={tool.name}
                className="flex items-center gap-3 px-3 py-1.5 bg-surface border border-card-border rounded"
              >
                <tool.icon className="h-3.5 w-3.5 text-accent shrink-0" />
                <div className="min-w-0">
                  <span className="text-xs font-mono text-foreground">
                    {tool.name}
                  </span>
                  <span className="text-xs text-muted ml-2">
                    — {tool.description}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* Key principles */}
        <section className="bg-card border border-card-border rounded-md p-4">
          <h3 className="text-[11px] font-semibold text-foreground mb-3">
            Key principles
          </h3>
          <div className="space-y-2.5">
            <Principle
              icon={<Zap className="h-3.5 w-3.5 text-info" />}
              title="Real tools, not fake answers"
              description="The agent uses actual database tools to gather information. It never invents resource IDs or claims resources are available without checking."
            />
            <Principle
              icon={<AlertTriangle className="h-3.5 w-3.5 text-danger" />}
              title="Human approval is mandatory"
              description="The AI recommends, humans decide. No responder is dispatched without explicit human approval."
            />
            <Principle
              icon={<Brain className="h-3.5 w-3.5 text-accent" />}
              title="Agentic reasoning"
              description="The agent reasons through a multi-step workflow: retrieve → classify → search → check → compare → recommend."
            />
          </div>
        </section>
      </div>
    </div>
  );
}

function Principle({
  icon,
  title,
  description,
}: {
  icon: React.ReactNode;
  title: string;
  description: string;
}) {
  return (
    <div className="flex items-start gap-3">
      <div className="w-6 h-6 rounded bg-surface border border-card-border flex items-center justify-center shrink-0">
        {icon}
      </div>
      <div>
        <div className="text-[13px] font-medium">{title}</div>
        <div className="text-xs text-muted mt-0.5">{description}</div>
      </div>
    </div>
  );
}
