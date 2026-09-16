"use client"

import { useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { api } from "@/lib/api"
import { Card, CardHeader, CardTitle, CardContent, CardDescription } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { useToast } from "@/components/ui/use-toast"
import { KeyRound, CheckCircle2, XCircle, AlertTriangle, Loader2, Trash2 } from "lucide-react"

type ProviderId = "anthropic" | "openai" | "groq" | "gemini" | "kling" | "veo" | "seedance"

type ProviderStatus = {
    provider: ProviderId
    label: string
    fields: string[]
    configured: boolean
    last_tested_at: string | null
    last_test_status: string | null
}

type TestOutcome = { status: string; ok: boolean; message: string; saved?: boolean; warning?: boolean }

const HINTS: Record<ProviderId, string> = {
    anthropic: "Used for script writing. console.anthropic.com → API Keys.",
    openai: "Used for script writing. platform.openai.com → API keys.",
    groq: "Used for script writing and caption timestamps. console.groq.com.",
    gemini: "Used for script writing. aistudio.google.com → Get API key.",
    kling: "Used for video generation. Access key + secret key from the Kling developer console.",
    veo: "Used for video generation. A Gemini API key from AI Studio with Veo enabled.",
    seedance: "Used for video generation. BytePlus ModelArk API key (international endpoint).",
}

const FIELD_LABELS: Record<string, string> = {
    api_key: "API key",
    access_key: "Access key",
    secret_key: "Secret key",
}

const STATUS_LABELS: Record<string, string> = {
    ok: "verified",
    rate_limited: "saved, rate limited at test time",
}

function errorOutcome(err: any): TestOutcome {
    const detail = err?.response?.data?.detail
    if (detail && typeof detail === "object" && "message" in detail) return { status: detail.status, ok: false, message: detail.message, saved: false }
    if (typeof detail === "string") return { status: "error", ok: false, message: detail }
    return { status: "error", ok: false, message: "Could not reach the server." }
}

function OutcomeLine({ outcome }: { outcome: TestOutcome | null }) {
    if (!outcome) return null
    // Saved-but-not-ok (e.g. rate limited at test time) reads as a warning, not a failure.
    let tone = "text-red-600 dark:text-red-400"
    let Icon = XCircle
    if (outcome.ok) {
        tone = "text-green-600 dark:text-green-400"
        Icon = CheckCircle2
    } else if (outcome.saved) {
        tone = "text-amber-600 dark:text-amber-400"
        Icon = AlertTriangle
    }
    return (
        <p className={`text-sm flex items-start gap-2 ${tone}`} role="status">
            <Icon className="h-4 w-4 mt-0.5 shrink-0" />
            <span>{outcome.message}</span>
        </p>
    )
}

function ProviderRow({ row, onChanged }: { row: ProviderStatus; onChanged: () => void }) {
    const { toast } = useToast()
    const empty = Object.fromEntries(row.fields.map((f) => [f, ""])) as Record<string, string>
    const [values, setValues] = useState<Record<string, string>>(empty)
    const [outcome, setOutcome] = useState<TestOutcome | null>(null)
    const filled = row.fields.every((f) => values[f]?.trim())

    const test = useMutation({
        mutationFn: async () => (await api.post<TestOutcome>(`/keys/${row.provider}/test`, values)).data,
        onSuccess: (data) => setOutcome(data),
        onError: (err) => setOutcome(errorOutcome(err)),
    })

    const save = useMutation({
        mutationFn: async () => (await api.put<TestOutcome>(`/keys/${row.provider}`, values)).data,
        onSuccess: (data) => {
            setOutcome(data)
            setValues(empty)
            toast({ title: `${row.label} key saved`, description: data.warning ? data.message : undefined })
            onChanged()
        },
        onError: (err) => setOutcome(errorOutcome(err)),
    })

    const remove = useMutation({
        mutationFn: async () => (await api.delete(`/keys/${row.provider}`)).data,
        onSuccess: () => {
            setOutcome(null)
            toast({ title: `${row.label} key removed` })
            onChanged()
        },
        onError: () => toast({ title: "Could not remove key", variant: "destructive" }),
    })

    const busy = test.isPending || save.isPending || remove.isPending
    const saveLabel = row.configured ? "Test & replace" : "Test & save"

    return (
        <div className="rounded-lg border p-4 space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                    <h3 className="font-semibold">{row.label}</h3>
                    <p className="text-xs text-muted-foreground">{HINTS[row.provider]}</p>
                </div>
                {row.configured ? (
                    <Badge className="bg-green-500/15 text-green-700 dark:text-green-300 hover:bg-green-500/15 border-transparent">
                        Configured
                        {row.last_test_status && ` · ${STATUS_LABELS[row.last_test_status] ?? row.last_test_status}`}
                        {row.last_tested_at && ` ${new Date(row.last_tested_at).toLocaleDateString()}`}
                    </Badge>
                ) : (
                    <Badge variant="outline">Not set</Badge>
                )}
            </div>

            <div className={`grid gap-2 ${row.fields.length > 1 ? "sm:grid-cols-2" : ""}`}>
                {row.fields.map((f) => {
                    const fieldLabel = FIELD_LABELS[f] ?? f
                    return (
                        <Input
                            key={f}
                            type="password"
                            autoComplete="off"
                            spellCheck={false}
                            placeholder={row.configured ? `New ${fieldLabel} (replaces the saved one)` : fieldLabel}
                            value={values[f]}
                            onChange={(e) => { setValues({ ...values, [f]: e.target.value }); setOutcome(null) }}
                            aria-label={`${row.label} ${fieldLabel}`}
                        />
                    )
                })}
            </div>

            <div className="flex flex-wrap items-center gap-2">
                <Button variant="outline" size="sm" disabled={!filled || busy} onClick={() => test.mutate()}>
                    {test.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : "Test key"}
                </Button>
                <Button size="sm" disabled={!filled || busy} onClick={() => save.mutate()}>
                    {save.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : saveLabel}
                </Button>
                {row.configured && (
                    <Button
                        variant="ghost"
                        size="sm"
                        className="text-red-600 hover:text-red-700 ml-auto"
                        disabled={busy}
                        onClick={() => {
                            if (window.confirm(`Remove your ${row.label} key? Jobs that need it will fail until you add a new one.`)) remove.mutate()
                        }}
                    >
                        <Trash2 className="h-4 w-4 mr-1" /> Delete
                    </Button>
                )}
            </div>

            <OutcomeLine outcome={outcome} />
        </div>
    )
}

export function ApiKeysCard() {
    const queryClient = useQueryClient()
    const { data, isLoading, isError } = useQuery({
        queryKey: ["provider_keys"],
        queryFn: async () => (await api.get<{ providers: ProviderStatus[] }>("/keys")).data.providers,
    })

    return (
        <Card>
            <CardHeader>
                <CardTitle className="flex items-center gap-2 font-semibold">
                    <KeyRound className="h-5 w-5 text-indigo-500" /> API Keys (bring your own)
                </CardTitle>
                <CardDescription>
                    One key per provider. Each key is checked against the provider before it is saved, then encrypted so that only
                    the job runner can read it — it is never shown again here.
                </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
                {isLoading && <p className="text-sm text-muted-foreground">Loading…</p>}
                {isError && <p className="text-sm text-red-500">Could not load key status.</p>}
                {data?.map((row) => (
                    <ProviderRow key={row.provider} row={row} onChanged={() => queryClient.invalidateQueries({ queryKey: ["provider_keys"] })} />
                ))}
            </CardContent>
        </Card>
    )
}
