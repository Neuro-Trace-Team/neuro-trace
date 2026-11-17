import { Outlet } from "react-router-dom"
import { useAuth } from "../context/useAuth";
import AppSidebar from "../components/AppSidebar";
import ellipseUrl from "../assets/deco-ellipse.svg";

function RootLayout() {
  const { user } = useAuth();

  return (
    <div className="app-background relative flex min-h-svh flex-col text-[#06234e] md:flex-row">
      <div className="app-background-shapes" aria-hidden="true">
        <img className="app-background-ellipse app-background-ellipse--top" src={ellipseUrl} alt="" />
        <img className="app-background-ellipse app-background-ellipse--bottom" src={ellipseUrl} alt="" />
      </div>
      <AppSidebar role={user?.role ?? "doctor"} />
      <main className="relative z-10 min-w-0 flex-1 px-4 pb-8 pt-6 sm:px-6 md:pb-8 md:pl-[6vw] md:pr-[9vw] md:pt-12">
        <Outlet />
      </main>
    </div>
  )
}

export default RootLayout