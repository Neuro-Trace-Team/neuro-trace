import { Outlet } from "react-router-dom"
import AuthBackgroundDecoration from "../components/AuthBackgroundDecoration"

function AuthLayout() {
  return (
    <main className="relative isolate flex min-h-svh w-full items-center justify-center overflow-hidden px-4 py-8 text-[#06234e] antialiased">
      <AuthBackgroundDecoration />

      <div className="relative z-10 flex w-full items-center justify-center">
        <Outlet />
      </div>
    </main>
  )
}

export default AuthLayout