"use client"

import * as React from "react"
import { Moon, Sun } from "lucide-react"
import { useTheme } from "next-themes"
import { Switch } from "@/components/ui/switch"

export function ThemeToggle() {
  const { setTheme, resolvedTheme } = useTheme()
  const [mounted, setMounted] = React.useState(false)

  React.useEffect(() => {
    setMounted(true)
  }, [])

  if (!mounted) {
    return (
      <div className="flex items-center gap-2">
        <Sun className="h-5 w-5 text-muted-foreground" />
        <Switch disabled />
        <Moon className="h-5 w-5 text-muted-foreground" />
      </div>
    )
  }

  return (
    <div className="flex items-center gap-2">
      <Sun className="h-5 w-5 text-muted-foreground" />
      <Switch
        checked={resolvedTheme === "dark"}
        onCheckedChange={(checked) => setTheme(checked ? "dark" : "light")}
        aria-label="Toggle theme"
      />
      <Moon className="h-5 w-5 text-muted-foreground" />
    </div>
  )
}
