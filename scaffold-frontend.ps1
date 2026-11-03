
$ErrorActionPreference = "Stop"

# Project and frontend locations
$ProjectRoot = $PSScriptRoot
$FrontendRoot = Join-Path $ProjectRoot "frontend"

# Ensure the Next.js application already exists.
if (-not [System.IO.Directory]::Exists($FrontendRoot)) {
    throw "Frontend directory not found. Create the Next.js application first."
}

Write-Host "`nScaffolding Software Triage Team frontend..." -ForegroundColor Cyan


# --------------------------------------------------
# 1. DIRECTORY STRUCTURE
# --------------------------------------------------

$directories = @(
    "src/app/(staff)/dashboard"
    "src/app/(staff)/tickets/[ticketId]"
    "src/app/(staff)/reviews/[reviewId]"
    "src/app/(staff)/office"
    "src/app/submit-ticket"

    "src/components/layout"
    "src/components/dashboard"
    "src/components/tickets"
    "src/components/reviews"
    "src/components/office"

    "src/lib/api"
    "src/lib/types"
    "src/lib/utils"

    "src/hooks"
)

foreach ($directory in $directories) {
    $path = Join-Path $FrontendRoot $directory

    [System.IO.Directory]::CreateDirectory($path) | Out-Null

    Write-Host "[DIR]  $directory" -ForegroundColor DarkCyan
}


# --------------------------------------------------
# 2. FILE CREATION HELPER
# --------------------------------------------------

function Add-ScaffoldFile {
    param(
        [string]$RelativePath,
        [AllowEmptyString()]
        [string]$Content
    )

    $FullPath = Join-Path $FrontendRoot $RelativePath
    $ParentDirectory = [System.IO.Path]::GetDirectoryName($FullPath)

    [System.IO.Directory]::CreateDirectory(
        $ParentDirectory
    ) | Out-Null

    if ([System.IO.File]::Exists($FullPath)) {
        Write-Host "[SKIP] $RelativePath already exists" -ForegroundColor Yellow
        return
    }

    $Encoding = [System.Text.UTF8Encoding]::new($false)

    [System.IO.File]::WriteAllText(
        $FullPath,
        $Content,
        $Encoding
    )

    Write-Host "[FILE] $RelativePath" -ForegroundColor Green
}


# --------------------------------------------------
# 3. STAFF LAYOUT
# --------------------------------------------------

$staffLayout = @'
import type { ReactNode } from "react";

interface StaffLayoutProps {
  children: ReactNode;
}

export default function StaffLayout({
  children,
}: StaffLayoutProps) {
  return (
    <div className="min-h-screen">
      {children}
    </div>
  );
}
'@

Add-ScaffoldFile `
    -RelativePath "src/app/(staff)/layout.tsx" `
    -Content $staffLayout


# --------------------------------------------------
# 4. ROUTE PAGE GENERATOR
# --------------------------------------------------

function New-PageContent {
    param(
        [string]$ComponentName,
        [string]$Title,
        [string]$Description
    )

    return @"
export default function $ComponentName() {
  return (
    <main className="min-h-screen p-8">
      <div className="mx-auto max-w-7xl">
        <h1 className="text-2xl font-semibold">
          $Title
        </h1>

        <p className="mt-2 text-sm text-gray-500">
          $Description
        </p>
      </div>
    </main>
  );
}
"@
}


# --------------------------------------------------
# 5. ROUTE PAGES
# --------------------------------------------------

$pages = @(
    @{
        Path = "src/app/(staff)/dashboard/page.tsx"
        Component = "DashboardPage"
        Title = "Dashboard"
        Description = "Software Triage Team operational overview."
    },
    @{
        Path = "src/app/(staff)/tickets/page.tsx"
        Component = "TicketsPage"
        Title = "Tickets"
        Description = "View and manage submitted software tickets."
    },
    @{
        Path = "src/app/(staff)/tickets/[ticketId]/page.tsx"
        Component = "TicketDetailsPage"
        Title = "Ticket Details"
        Description = "Inspect ticket information and agent investigation results."
    },
    @{
        Path = "src/app/(staff)/reviews/page.tsx"
        Component = "ReviewsPage"
        Title = "Human Review"
        Description = "Review pending agent proposals and decisions."
    },
    @{
        Path = "src/app/(staff)/reviews/[reviewId]/page.tsx"
        Component = "ReviewDetailsPage"
        Title = "Review Details"
        Description = "Inspect, edit, approve or reject a proposed action."
    },
    @{
        Path = "src/app/(staff)/office/page.tsx"
        Component = "OfficePage"
        Title = "Virtual Office"
        Description = "Observe agent activity across the virtual workspace."
    },
    @{
        Path = "src/app/submit-ticket/page.tsx"
        Component = "SubmitTicketPage"
        Title = "Submit a Ticket"
        Description = "Report a software issue or request a feature."
    }
)

foreach ($page in $pages) {

    $content = New-PageContent `
        -ComponentName $page.Component `
        -Title $page.Title `
        -Description $page.Description

    Add-ScaffoldFile `
        -RelativePath $page.Path `
        -Content $content
}


# --------------------------------------------------
# 6. COMPONENT AND UTILITY PLACEHOLDERS
# --------------------------------------------------

$placeholderDirectories = @(
    "src/components/layout"
    "src/components/dashboard"
    "src/components/tickets"
    "src/components/reviews"
    "src/components/office"
    "src/lib/api"
    "src/lib/types"
    "src/lib/utils"
    "src/hooks"
)

foreach ($directory in $placeholderDirectories) {

    Add-ScaffoldFile `
        -RelativePath "$directory/.gitkeep" `
        -Content ""
}


# --------------------------------------------------
# 7. COMPLETION
# --------------------------------------------------

Write-Host "`n----------------------------------------" -ForegroundColor Cyan
Write-Host "Frontend scaffolding completed!" -ForegroundColor Green
Write-Host "----------------------------------------" -ForegroundColor Cyan

Write-Host "`nExisting files were preserved."
Write-Host "Frontend location: $FrontendRoot"

Write-Host "`nNext step: cd frontend && npm run dev" -ForegroundColor Cyan
