import DataTable from "../../components/DataTable";
import { PageTitle, Surface } from "../../components/PageUI";
import { activityRows } from "../mockData";

function AdminActivityLogPage() {
  return (
    <div className="mx-auto max-w-[1100px]">
      <PageTitle>App Activity Log</PageTitle>
      <Surface className="p-3">
        <DataTable columns={["Date", "Category", "Description"]} rows={activityRows} totalCount={112} searchPlaceholder="Search activity" />
      </Surface>
    </div>
  );
}

export default AdminActivityLogPage;
