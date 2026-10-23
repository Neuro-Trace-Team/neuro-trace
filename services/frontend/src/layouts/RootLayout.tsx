import { Outlet } from "react-router-dom"

function RootLayout() {
//   const { user, isLoading } = useAuth();

//   if (isLoading) return <div>Ładowanie aplikacji...</div>;

  return (
    <div>
      {/* <Sidebar role={user?.role || null} /> */}
      <main>
        <Outlet />
      </main>
    </div>
  )
}

export default RootLayout