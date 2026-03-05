"use client"

import Link from "next/link"
import { usePathname, useRouter } from "next/navigation"
import Cookies from "js-cookie"
import { useQuery } from "@tanstack/react-query"
import { api } from "@/lib/api"
import { Button } from "@/components/ui/button"
import { LayoutDashboard, PlusCircle, Settings, LogOut, Youtube, LineChart, CreditCard, ShieldAlert } from "lucide-react"

export default function DashboardLayout({
    children,
}: {
    children: React.ReactNode
}) {
    const pathname = usePathname()
    const router = useRouter()

    const { data: status } = useQuery({
        queryKey: ["config_status"],
        queryFn: async () => {
            const res = await api.get("/config/status")
            return res.data
        },
        retry: 0
    })

    const logout = () => {
        Cookies.remove("access_token")
        router.push("/login")
    }

    const NavLink = ({ href, icon: Icon, children }: any) => {
        const isActive = pathname === href
        return (
            <Link href={href}>
                <Button
                    variant={isActive ? "secondary" : "ghost"}
                    className="w-full justify-start gap-2"
                >
                    <Icon className="h-4 w-4" />
                    {children}
                </Button>
            </Link>
        )
    }

    return (
        <div className="flex h-screen overflow-hidden">
            <div className="hidden w-[280px] shrink-0 border-r bg-gray-100/40 lg:flex dark:bg-gray-800/40">
                <div className="flex h-full w-full flex-col gap-2">
                    <div className="flex h-[60px] items-center border-b px-6">
                        <Link className="flex items-center gap-2 font-semibold" href="/dashboard">
                            <Youtube className="h-6 w-6 text-red-600" />
                            <span>Autotube</span>
                        </Link>
                    </div>
                    <div className="flex-1 overflow-auto py-2">
                        <nav className="grid items-start px-4 text-sm font-medium">
                            <NavLink href="/dashboard" icon={LayoutDashboard}>
                                Overview
                            </NavLink>
                            <NavLink href="/analytics" icon={LineChart}>
                                Analytics
                            </NavLink>
                            <NavLink href="/jobs/create" icon={PlusCircle}>
                                New Automation
                            </NavLink>
                            <NavLink href="/billing" icon={CreditCard}>
                                Billing
                            </NavLink>
                            <NavLink href="/settings" icon={Settings}>
                                Settings
                            </NavLink>
                            {status?.is_admin && (
                                <NavLink href="/admin" icon={ShieldAlert}>
                                    Admin Panel
                                </NavLink>
                            )}
                        </nav>
                    </div>
                    <div className="mt-auto p-4 border-t">
                        <Button onClick={logout} variant="outline" className="w-full justify-start gap-2">
                            <LogOut className="h-4 w-4" />
                            Logout
                        </Button>
                    </div>
                </div>
            </div>
            <div className="flex flex-1 flex-col overflow-hidden">
                <main className="flex-1 overflow-y-auto p-4 md:p-6 bg-background text-foreground">
                    {children}
                </main>
            </div>
        </div>
    )
}
