import AppShell from "@/components/layout/AppShell";
import AdminRedirect from "./AdminRedirect";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <>
      <AdminRedirect />
      <AppShell>{children}</AppShell>
    </>
  );
}
