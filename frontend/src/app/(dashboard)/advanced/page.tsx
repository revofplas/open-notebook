'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { AppShell } from '@/components/layout/AppShell'
import { RebuildEmbeddings } from './components/RebuildEmbeddings'
import { SystemInfo } from './components/SystemInfo'
import { useTranslation } from '@/lib/hooks/use-translation'
import { useAuthStore } from '@/lib/stores/auth-store'

export default function AdvancedPage() {
  const { t } = useTranslation()
  const router = useRouter()
  const { user } = useAuthStore()

  useEffect(() => {
    if (user && user.role !== 'admin') {
      router.replace('/notebooks')
    }
  }, [user, router])

  if (!user || user.role !== 'admin') return null
  return (
    <AppShell>
      <div className="flex-1 overflow-y-auto">
        <div className="p-6">
          <div className="max-w-4xl mx-auto space-y-6">
            <div>
              <h1 className="text-3xl font-bold">{t.advanced.title}</h1>
              <p className="text-muted-foreground mt-2">
                {t.advanced.desc}
              </p>
            </div>

            <SystemInfo />
            <RebuildEmbeddings />
          </div>
        </div>
      </div>
    </AppShell>
  )
}
