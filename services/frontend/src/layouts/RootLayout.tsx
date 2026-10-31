import { Outlet } from "react-router-dom"
import { useAuth } from "../context/AuthContext";
import AppSidebar from "../components/AppSidebar";
import ellipseUrl from "../assets/deco-ellipse.svg";

function RootLayout() {
  const { user } = useAuth();

  return (
    <div className="relative flex min-h-svh flex-col bg-[#f3f5f5] text-[#06234e] md:flex-row">
      <div aria-hidden="true" className="pointer-events-none fixed inset-0 overflow-hidden">
        <img
          className="absolute left-[-25%] top-[-20%] rotate-[330deg] opacity-75 md:left-[-24%] md:top-[-65%]"
          src={ellipseUrl}
          alt=""
        />
        <img
          className="absolute bottom-[-78%] right-[-32%] h-auto w-[min(100vw,1292px)] max-w-none rotate-[135deg] opacity-75 md:bottom-[-80%] md:right-[-30%]"
          src={ellipseUrl}
          alt=""
        />
      </div>
      <AppSidebar role={user?.role ?? null} />
      <main className="relative z-10 min-w-0 flex-1 px-4 pb-8 pt-6 sm:px-6 md:pb-8 md:pl-[6vw] md:pr-[9vw] md:pt-12">
        <Outlet />
      </main>
    </div>
  )
}

export default RootLayout