'use client'

import { useState, useEffect } from 'react'
import { AppShell } from '@/components/layout/AppShell'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { AlertCircle, CheckCircle2, Database, RefreshCw } from 'lucide-react'
import { toast } from 'sonner'
import { apiClient } from '@/lib/api/client'
import { useAuthStore } from '@/lib/stores/auth-store'
import { useRouter } from 'next/navigation'
import { useTranslation } from '@/lib/hooks/use-translation'

interface OracleConfig {
  dsn: string
  username: string
  pool_min: number
  pool_max: number
  enabled: boolean
  user_view: string
}

export default function OracleSettingsPage() {
  const { t } = useTranslation()
  const router = useRouter()
  const { user } = useAuthStore()
  const [config, setConfig] = useState<OracleConfig>({
    dsn: '',
    username: '',
    pool_min: 2,
    pool_max: 10,
    enabled: false,
    user_view: 'INF.VI_INF_USER_INFO',
  })
  const [password, setPassword] = useState('')
  const [isLoading, setIsLoading] = useState(true)
  const [isSaving, setIsSaving] = useState(false)
  const [isTesting, setIsTesting] = useState(false)
  const [testResult, setTestResult] = useState<{ success: boolean; message: string } | null>(null)

  // Admin guard
  useEffect(() => {
    if (user && user.role !== 'admin') {
      router.replace('/notebooks')
    }
  }, [user, router])

  // Load current config
  useEffect(() => {
    const loadConfig = async () => {
      try {
        const response = await apiClient.get<OracleConfig>('/admin/oracle-config')
        setConfig(response.data)
      } catch (err) {
        console.error('Failed to load Oracle config:', err)
        toast.error(t.admin.oracleSettings.loadFailed)
      } finally {
        setIsLoading(false)
      }
    }
    if (user?.role === 'admin') {
      loadConfig()
    }
  }, [user])

  const handleSave = async () => {
    setIsSaving(true)
    setTestResult(null)
    try {
      const payload: Record<string, unknown> = {
        dsn: config.dsn,
        username: config.username,
        pool_min: config.pool_min,
        pool_max: config.pool_max,
        enabled: config.enabled,
        user_view: config.user_view,
      }
      if (password.trim()) {
        payload.password = password
      }
      const response = await apiClient.put<OracleConfig>('/admin/oracle-config', payload)
      setConfig(response.data)
      setPassword('')
      toast.success(t.admin.oracleSettings.saveSuccess)
    } catch (err) {
      console.error('Failed to save Oracle config:', err)
      toast.error(t.admin.oracleSettings.saveFailed)
    } finally {
      setIsSaving(false)
    }
  }

  const handleTest = async () => {
    setIsTesting(true)
    setTestResult(null)
    try {
      const res = await apiClient.post<{ success: boolean; message: string }>(
        '/admin/oracle-config/test',
        {}
      )
      const result = res.data
      setTestResult(result)
      if (result.success) {
        toast.success(result.message)
      } else {
        toast.error(result.message)
      }
    } catch (err) {
      console.error('Connection test failed:', err)
      const msg = t.admin.oracleSettings.testError
      setTestResult({ success: false, message: msg })
      toast.error(msg)
    } finally {
      setIsTesting(false)
    }
  }

  if (!user || user.role !== 'admin') {
    return null
  }

  return (
    <AppShell>
      <div className="flex-1 overflow-y-auto">
        <div className="p-6 max-w-2xl">
          <div className="flex items-center gap-3 mb-6">
            <Database className="h-6 w-6" />
            <h1 className="text-2xl font-bold">{t.admin.oracleSettings.pageTitle}</h1>
          </div>

          {isLoading ? (
            <div className="flex items-center gap-2 text-muted-foreground">
              <RefreshCw className="h-4 w-4 animate-spin" />
              <span>{t.admin.oracleSettings.loading}</span>
            </div>
          ) : (
            <Card>
              <CardHeader>
                <CardTitle>{t.admin.oracleSettings.cardTitle}</CardTitle>
                <CardDescription>
                  {t.admin.oracleSettings.cardDesc}
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-5">

                <div className="flex items-center justify-between">
                  <div>
                    <Label htmlFor="enabled" className="text-sm font-medium">{t.admin.oracleSettings.enabledLabel}</Label>
                    <p className="text-xs text-muted-foreground mt-0.5">
                      {t.admin.oracleSettings.enabledDesc}
                    </p>
                  </div>
                  <Switch
                    id="enabled"
                    checked={config.enabled}
                    onCheckedChange={(val) => setConfig(prev => ({ ...prev, enabled: val }))}
                  />
                </div>

                <div className="space-y-1.5">
                  <Label htmlFor="dsn">{t.admin.oracleSettings.dsnLabel} <span className="text-red-500">*</span></Label>
                  <Input
                    id="dsn"
                    value={config.dsn}
                    onChange={(e) => setConfig(prev => ({ ...prev, dsn: e.target.value }))}
                    placeholder="host:port/service_name (예: 192.168.1.100:1521/HRDB)"
                  />
                </div>

                <div className="space-y-1.5">
                  <Label htmlFor="username">{t.admin.oracleSettings.usernameLabel} <span className="text-red-500">*</span></Label>
                  <Input
                    id="username"
                    value={config.username}
                    onChange={(e) => setConfig(prev => ({ ...prev, username: e.target.value }))}
                    placeholder="Oracle 서비스 계정 ID"
                  />
                </div>

                <div className="space-y-1.5">
                  <Label htmlFor="password">{t.admin.oracleSettings.passwordLabel}</Label>
                  <Input
                    id="password"
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder={t.admin.oracleSettings.passwordPlaceholder}
                  />
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-1.5">
                    <Label htmlFor="pool_min">{t.admin.oracleSettings.poolMinLabel}</Label>
                    <Input
                      id="pool_min"
                      type="number"
                      min={1}
                      max={20}
                      value={config.pool_min}
                      onChange={(e) => setConfig(prev => ({ ...prev, pool_min: Number(e.target.value) }))}
                    />
                  </div>
                  <div className="space-y-1.5">
                    <Label htmlFor="pool_max">{t.admin.oracleSettings.poolMaxLabel}</Label>
                    <Input
                      id="pool_max"
                      type="number"
                      min={1}
                      max={50}
                      value={config.pool_max}
                      onChange={(e) => setConfig(prev => ({ ...prev, pool_max: Number(e.target.value) }))}
                    />
                  </div>
                </div>

                <div className="space-y-1.5">
                  <Label htmlFor="user_view">{t.admin.oracleSettings.userViewLabel} <span className="text-red-500">*</span></Label>
                  <Input
                    id="user_view"
                    value={config.user_view}
                    onChange={(e) => setConfig(prev => ({ ...prev, user_view: e.target.value }))}
                    placeholder="SCHEMA.VIEW_NAME (예: INF.VI_INF_USER_INFO)"
                  />
                  <p className="text-xs text-muted-foreground">{t.admin.oracleSettings.userViewDesc}</p>
                </div>

                {testResult && (
                  <div className={`flex items-start gap-2 text-sm p-3 rounded-md ${
                    testResult.success
                      ? 'bg-green-50 text-green-700 dark:bg-green-950 dark:text-green-300'
                      : 'bg-red-50 text-red-700 dark:bg-red-950 dark:text-red-300'
                  }`}>
                    {testResult.success
                      ? <CheckCircle2 className="h-4 w-4 mt-0.5 flex-shrink-0" />
                      : <AlertCircle className="h-4 w-4 mt-0.5 flex-shrink-0" />
                    }
                    <span>{testResult.message}</span>
                  </div>
                )}

                <div className="flex gap-3 pt-2">
                  <Button
                    onClick={handleSave}
                    disabled={isSaving || !config.dsn || !config.username}
                  >
                    {isSaving ? t.common.saving : t.common.save}
                  </Button>
                  <Button
                    variant="outline"
                    onClick={handleTest}
                    disabled={isTesting || !config.dsn || !config.username}
                  >
                    {isTesting ? t.admin.oracleSettings.testing : t.admin.oracleSettings.testConnection}
                  </Button>
                </div>

              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </AppShell>
  )
}
