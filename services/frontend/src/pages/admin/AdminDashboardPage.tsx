import DataTable from "../../components/DataTable";
import { PageTitle, SectionTitle, Surface } from "../../components/PageUI";
import { useAuth } from "../../context/AuthContext";
import { activityRows } from "../mockData";

const stats = [
  { label: "Active users in the last 24h", value: "875" },
  { label: "Failed log-in attempts in last 24h", value: "209" },
  { label: "Database usage", value: "56%" },
  { label: "Last backup", value: "3 days ago" },
];

function AdminDashboardPage() {
  const { user } = useAuth();
  return (
    <div className="mx-auto max-w-[1100px]">
      <PageTitle>Welcome back, {user?.firstName || "Alice"}</PageTitle>
      <Surface className="mb-3 px-5 py-3">
        <SectionTitle>System Status</SectionTitle>
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          {stats.map((stat) => (
            <div className="flex min-h-[145px] flex-col justify-between rounded-md border border-white/90 bg-white/60 p-3 shadow-[0_2px_3px_rgba(0,0,0,0.2)]" key={stat.label}>
              <span className="max-w-[135px] text-[12px] leading-[15px]">{stat.label}</span>
              <strong className="text-center font-heading text-[32px] font-extrabold leading-none sm:text-[36px]">{stat.value}</strong>
            </div>
          ))}
        </div>
      </Surface>
      <Surface className="px-4 py-3">
        <SectionTitle>Recent App Activity</SectionTitle>
        <DataTable columns={["Date", "Category", "Description"]} rows={activityRows.slice(0, 9)} selectable={false} showPagination={false} showToolbar={false} />
      </Surface>
    </div>
  );
}

export default AdminDashboardPage;
