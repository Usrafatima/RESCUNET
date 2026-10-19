import type { Metadata } from "next";
import { CitizenDashboard } from "@/components/citizen/CitizenDashboard";

export const metadata: Metadata = {
  title: "Emergency Assistance (SOS) — RescuNet Citizen Portal",
  description:
    "Report an emergency, share your location, and safely track response coordination without administrative access.",
};

export default function CitizenHelpPage() {
  return <CitizenDashboard />;
}
