import { useState } from "react";
import AdminCreateUserModal, { type ManagedUser } from "../../components/AdminCreateUserModal";
import DataTable from "../../components/DataTable";
import Icon from "../../components/Icon";
import { PageTitle, SmallButton, Surface } from "../../components/PageUI";
import { userRows } from "../mockData";

function AdminUsersPage() {
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [createdUsers, setCreatedUsers] = useState<ManagedUser[]>([]);
  const rows = [
    ...createdUsers.map((user) => [user.name, user.email, user.role, user.lastLogin]),
    ...userRows,
  ];

  return (
    <div className="mx-auto max-w-[1100px]">
      <PageTitle>User Management</PageTitle>
      <Surface className="p-3">
        <DataTable
          columns={["User", "Email", "Role", "Last login"]}
          rows={rows}
          totalCount={112 + createdUsers.length}
          toolbarEnd={
            <SmallButton className="ml-auto" onClick={() => setIsModalOpen(true)} type="button">
              <Icon className="h-4 w-4" name="users" />
              Create an Account
            </SmallButton>
          }
        />
      </Surface>
      {isModalOpen && (
        <AdminCreateUserModal
          onClose={() => setIsModalOpen(false)}
          onCreate={(user) => {
            setCreatedUsers((current) => [user, ...current]);
            setIsModalOpen(false);
          }}
        />
      )}
    </div>
  );
}

export default AdminUsersPage;
