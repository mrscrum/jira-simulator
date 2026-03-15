export const ROLES = ["Dev", "QA", "BA", "SM", "PO"] as const;
export type Role = (typeof ROLES)[number];

export const ROLE_COLORS: Record<string, { bg: string; text: string; border: string }> = {
  Dev: { bg: "bg-blue-100", text: "text-blue-700", border: "border-blue-400" },
  QA: { bg: "bg-teal-100", text: "text-teal-700", border: "border-teal-400" },
  BA: { bg: "bg-orange-100", text: "text-orange-700", border: "border-orange-400" },
  SM: { bg: "bg-amber-100", text: "text-amber-700", border: "border-amber-400" },
  PO: { bg: "bg-purple-100", text: "text-purple-700", border: "border-purple-400" },
};

export function getRoleColor(role: string) {
  return ROLE_COLORS[role] ?? { bg: "bg-gray-100", text: "text-gray-700", border: "border-gray-400" };
}
