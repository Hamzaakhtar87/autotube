"use client"

import { useState } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { api } from "@/lib/api"
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { useToast } from "@/components/ui/use-toast"
import { Activity, Users, Video, ShieldAlert, CheckCircle, XCircle, Database, Server, Cpu } from "lucide-react"

export default function AdminDashboardPage() {
    const { toast } = useToast()
    const queryClient = useQueryClient()

    // Ensure only admins can load data (backend enforces this anyway)
    const { data: stats, isLoading: statsLoading } = useQuery({
        queryKey: ["admin_stats"],
        queryFn: async () => {
            const res = await api.get("/admin/stats")
            return res.data
        }
    })

    const { data: users, isLoading: usersLoading } = useQuery({
        queryKey: ["admin_users"],
        queryFn: async () => {
            const res = await api.get("/admin/users")
            return res.data
        }
    })

    const { data: health, isLoading: healthLoading } = useQuery({
        queryKey: ["admin_health"],
        queryFn: async () => {
            const res = await api.get("/admin/health")
            return res.data
        },
        refetchInterval: 10000 // refresh every 10s
    })

    const updateUserMutation = useMutation({
        mutationFn: async ({ id, updates }: { id: number, updates: any }) => {
            return api.patch(`/admin/users/${id}`, updates)
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["admin_users"] })
            toast({ title: "User updated" })
        },
        onError: (err: any) => {
            toast({ title: "Action failed", description: err.response?.data?.detail, variant: "destructive" })
        }
    })

    const deleteUserMutation = useMutation({
        mutationFn: async (id: number) => {
            if (confirm("WARNING: This will delete the user and ALL their data permanently!")) {
                return api.delete(`/admin/users/${id}`)
            }
            throw new Error("Cancelled by user")
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["admin_users"] })
            queryClient.invalidateQueries({ queryKey: ["admin_stats"] })
            toast({ title: "User deleted" })
        },
        onError: (err: any) => {
            if (err.message !== "Cancelled by user") {
                toast({ title: "Delete failed", description: err.response?.data?.detail, variant: "destructive" })
            }
        }
    })

    if (statsLoading || usersLoading || healthLoading) {
        return <div className="text-center py-20">Loading administrative systems...</div>
    }

    if (!stats) {
        return <div className="text-center py-20 text-red-500">Access Denied or Server Error.</div>
    }

    return (
        <div className="space-y-6 max-w-7xl mx-auto pb-10">
            <div>
                <h1 className="text-3xl font-bold tracking-tight text-red-600 dark:text-red-500 flex items-center gap-2">
                    <ShieldAlert className="h-8 w-8" /> Control Node [ADMIN]
                </h1>
                <p className="text-muted-foreground mt-1">Platform management and system telemetry.</p>
            </div>

            {/* ═══ SYSTEM TELEMETRY ═══ */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <Card className="bg-slate-900 text-slate-100 border-none shadow-md">
                    <CardHeader className="pb-2">
                        <CardTitle className="text-sm font-medium text-slate-400 flex items-center gap-2">
                            <Server className="h-4 w-4" /> Node Status
                        </CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="text-xl font-bold text-green-400">ONLINE</div>
                    </CardContent>
                </Card>
                <Card className="bg-slate-900 text-slate-100 border-none shadow-md">
                    <CardHeader className="pb-2">
                        <CardTitle className="text-sm font-medium text-slate-400 flex items-center gap-2">
                            <Database className="h-4 w-4" /> PostgreSQL
                        </CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className={`text-xl font-bold ${health?.database === "connected" ? "text-green-400" : "text-red-400"}`}>
                            {health?.database.toUpperCase()}
                        </div>
                    </CardContent>
                </Card>
                <Card className="bg-slate-900 text-slate-100 border-none shadow-md">
                    <CardHeader className="pb-2">
                        <CardTitle className="text-sm font-medium text-slate-400 flex items-center gap-2">
                            <Database className="h-4 w-4 text-red-500" /> Redis (Celery)
                        </CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className={`text-xl font-bold ${health?.redis === "connected" ? "text-green-400" : "text-red-400"}`}>
                            {health?.redis.toUpperCase()}
                        </div>
                    </CardContent>
                </Card>
                <Card className="bg-slate-900 text-slate-100 border-none shadow-md">
                    <CardHeader className="pb-2">
                        <CardTitle className="text-sm font-medium text-slate-400 flex items-center gap-2">
                            <Cpu className="h-4 w-4" /> CPU / RAM
                        </CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="text-lg font-bold text-blue-400">
                            {health?.cpu_percent}% / {health?.memory_used_percent}%
                        </div>
                    </CardContent>
                </Card>
            </div>

            {/* ═══ PLATFORM AGGREGATES ═══ */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                <Card>
                    <CardHeader className="flex flex-row items-center justify-between pb-2">
                        <CardTitle className="text-sm font-medium">Total Users</CardTitle>
                        <Users className="h-4 w-4 text-muted-foreground" />
                    </CardHeader>
                    <CardContent>
                        <div className="text-2xl font-bold">{stats.total_users}</div>
                        <p className="text-xs text-muted-foreground mt-1">
                            {stats.active_users_30d} active this month
                        </p>
                    </CardContent>
                </Card>
                <Card>
                    <CardHeader className="flex flex-row items-center justify-between pb-2">
                        <CardTitle className="text-sm font-medium">Generated Videos</CardTitle>
                        <Video className="h-4 w-4 text-muted-foreground" />
                    </CardHeader>
                    <CardContent>
                        <div className="text-2xl font-bold">{stats.total_videos}</div>
                    </CardContent>
                </Card>
                <Card>
                    <CardHeader className="flex flex-row items-center justify-between pb-2">
                        <CardTitle className="text-sm font-medium">Job Processing</CardTitle>
                        <Activity className="h-4 w-4 text-muted-foreground" />
                    </CardHeader>
                    <CardContent>
                        <div className="text-2xl font-bold">{stats.total_jobs}</div>
                        <p className="text-xs text-muted-foreground mt-1 text-blue-600">
                            {stats.running_jobs} currently running
                        </p>
                    </CardContent>
                </Card>
            </div>

            {/* ═══ USER MANAGEMENT ═══ */}
            <Card>
                <CardHeader>
                    <CardTitle>User Demographics & Management</CardTitle>
                </CardHeader>
                <CardContent>
                    <div className="rounded-md border overflow-x-auto">
                        <Table>
                            <TableHeader>
                                <TableRow>
                                    <TableHead>ID</TableHead>
                                    <TableHead>Email</TableHead>
                                    <TableHead>Tier</TableHead>
                                    <TableHead>Jobs/Vids</TableHead>
                                    <TableHead>Created</TableHead>
                                    <TableHead>Status</TableHead>
                                    <TableHead className="text-right">Actions</TableHead>
                                </TableRow>
                            </TableHeader>
                            <TableBody>
                                {users?.map((user: any) => (
                                    <TableRow key={user.id}>
                                        <TableCell className="font-mono text-xs">{user.id}</TableCell>
                                        <TableCell>
                                            <div className="font-medium">{user.email}</div>
                                            {user.is_admin && <Badge variant="destructive" className="mt-1 text-[10px]">ADMIN</Badge>}
                                        </TableCell>
                                        <TableCell>
                                            <Badge variant={user.subscription_tier === "enterprise" ? "default" : user.subscription_tier === "pro" ? "secondary" : "outline"}>
                                                {user.subscription_tier.toUpperCase()}
                                            </Badge>
                                        </TableCell>
                                        <TableCell>
                                            <span className="text-xs text-muted-foreground">{user.total_jobs} / {user.total_videos}</span>
                                        </TableCell>
                                        <TableCell className="text-xs text-muted-foreground">
                                            {new Date(user.created_at).toLocaleDateString()}
                                        </TableCell>
                                        <TableCell>
                                            {user.is_active ?
                                                <Badge variant="outline" className="text-green-600 border-green-600"><CheckCircle className="w-3 h-3 mr-1" /> Active</Badge> :
                                                <Badge variant="outline" className="text-red-600 border-red-600"><XCircle className="w-3 h-3 mr-1" /> Banned</Badge>
                                            }
                                        </TableCell>
                                        <TableCell className="text-right">
                                            <div className="flex justify-end gap-2">
                                                {!user.is_admin && (
                                                    <>
                                                        <Button
                                                            variant="outline"
                                                            size="sm"
                                                            onClick={() => updateUserMutation.mutate({ id: user.id, updates: { is_active: !user.is_active } })}
                                                        >
                                                            {user.is_active ? "Ban" : "Unban"}
                                                        </Button>
                                                        <Button
                                                            variant="destructive"
                                                            size="sm"
                                                            onClick={() => deleteUserMutation.mutate(user.id)}
                                                        >
                                                            Delete
                                                        </Button>
                                                    </>
                                                )}
                                            </div>
                                        </TableCell>
                                    </TableRow>
                                ))}
                            </TableBody>
                        </Table>
                    </div>
                </CardContent>
            </Card>

        </div>
    )
}
