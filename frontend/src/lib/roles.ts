export const ROLES = [
  "DEV", "QA", "BA", "SM", "PO",
  "DevOps", "Frontend", "Backend",
  "iOS", "Android",
  "Data Eng", "ML Eng", "Analyst",
] as const;
export type Role = (typeof ROLES)[number];

export const ROLE_COLORS: Record<string, { bg: string; text: string; border: string }> = {
  DEV: { bg: "bg-blue-100", text: "text-blue-700", border: "border-blue-400" },
  Dev: { bg: "bg-blue-100", text: "text-blue-700", border: "border-blue-400" },
  QA: { bg: "bg-teal-100", text: "text-teal-700", border: "border-teal-400" },
  BA: { bg: "bg-orange-100", text: "text-orange-700", border: "border-orange-400" },
  SM: { bg: "bg-amber-100", text: "text-amber-700", border: "border-amber-400" },
  PO: { bg: "bg-purple-100", text: "text-purple-700", border: "border-purple-400" },
  DevOps: { bg: "bg-slate-100", text: "text-slate-700", border: "border-slate-400" },
  Frontend: { bg: "bg-indigo-100", text: "text-indigo-700", border: "border-indigo-400" },
  Backend: { bg: "bg-sky-100", text: "text-sky-700", border: "border-sky-400" },
  iOS: { bg: "bg-pink-100", text: "text-pink-700", border: "border-pink-400" },
  Android: { bg: "bg-green-100", text: "text-green-700", border: "border-green-400" },
  "Data Eng": { bg: "bg-cyan-100", text: "text-cyan-700", border: "border-cyan-400" },
  "ML Eng": { bg: "bg-violet-100", text: "text-violet-700", border: "border-violet-400" },
  Analyst: { bg: "bg-rose-100", text: "text-rose-700", border: "border-rose-400" },
};

export function getRoleColor(role: string) {
  return ROLE_COLORS[role] ?? { bg: "bg-gray-100", text: "text-gray-700", border: "border-gray-400" };
}
