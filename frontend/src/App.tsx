import { Route, Routes } from "react-router-dom"

import { RoleProvider } from "@/context/RoleContext"
import { DashboardLayout } from "@/layouts/DashboardLayout"
import { MainLayout } from "@/layouts/MainLayout"
import { AnalysisDetailPage } from "@/pages/AnalysisDetailPage"
import { AnalysisReportsPage } from "@/pages/AnalysisReportsPage"
import { DashboardPage } from "@/pages/DashboardPage"
import { DocumentsPage } from "@/pages/DocumentsPage"
import { HomePage } from "@/pages/HomePage"
import { LegalHelpPage } from "@/pages/LegalHelpPage"
import { MessagesPage } from "@/pages/MessagesPage"
import { NotFoundPage } from "@/pages/NotFoundPage"
import { SettingsPage } from "@/pages/SettingsPage"
import { UploadPage } from "@/pages/UploadPage"

function App() {
  return (
    <RoleProvider>
      <Routes>
        <Route element={<MainLayout />}>
          <Route index element={<HomePage />} />
          <Route path="*" element={<NotFoundPage />} />
        </Route>
        <Route path="/dashboard" element={<DashboardLayout />}>
          <Route index element={<DashboardPage />} />
          <Route path="upload" element={<UploadPage />} />
          <Route path="documents" element={<DocumentsPage />} />
          <Route path="reports" element={<AnalysisReportsPage />} />
          <Route path="legal-help" element={<LegalHelpPage />} />
          <Route path="messages" element={<MessagesPage />} />
          <Route path="analyses/:id" element={<AnalysisDetailPage />} />
          <Route path="settings" element={<SettingsPage />} />
        </Route>
      </Routes>
    </RoleProvider>
  )
}

export default App
